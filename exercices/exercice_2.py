# # Exercice 2 : Extracteur de Formulaires de Contact avec Pydantic
#
# ## Objectif
# Utiliser Pydantic et le mode Structured Output d'OpenAI pour transformer un e-mail ou message non structuré en objet Python fortement typé.
#
# ## Consignes
# 1. Créez un fichier `exercice_2.py`.
# 2. Définissez un modèle Pydantic `DemandeContact` avec les champs suivants :
#    - `nom_client`: `str`
#    - `email`: `str` (astuce : vous pouvez utiliser `EmailStr` de Pydantic)
#    - `quantite_souhaitee`: `int`
#    - `categorie`: `Literal['Réservation', 'Réclamation', 'Demande d'information']`
#    - `resume_court`: `str` (un résumé en une phrase de la demande)
# 3. Écrivez une fonction `traiter_message_contact(message: str) -> DemandeContact`.
# 4. Testez votre fonction avec ce texte brut :
#    > *"Bonjour, je suis Marc Dupont (adresse email: marc.dupont@corp.com). Je souhaiterais commander 15 licences de votre logiciel pour mon équipe, mais j'aurais besoin d'un devis au préalable. Merci !"*
# 5. Affichez l'objet Pydantic obtenu sous forme de dictionnaire grâce à la méthode `.model_dump()`.

import os
from typing import Literal
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, EmailStr, Field


class DemandeContact(BaseModel):
    nom_client: str = Field(description="Nom d'utilisateur")
    email: EmailStr = Field(description="Email d'utilisateur")
    quantite_souhaitee: int = Field(description="Quantitée demandée par l'utilisateur")
    categorie: Literal['Réservation', 'Réclamation', 'Demande d\'information'] = Field(description="Catégorie de la demande")
    resume_court: str = Field(description="Résumé court de la demande")


class PydanticRequestConverter:
    system_prompt: str
    base_url: str
    api_key: str
    model_name: str

    def __init__(self, base_url, api_key, model_name, system_prompt):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        self.model_name = model_name
        self.system_prompt = system_prompt

    def traiter_message_contact(self, request_message: str) -> DemandeContact:
        response = self.client.beta.chat.completions.parse(
            model=self.model_name,
            response_format=DemandeContact,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt,
                },
                {
                    "role": "user",
                    "content": request_message
                }
            ],
            temperature=0.0
        )
        result = response.choices[0].message.parsed

        if result is None:
            raise ValueError("Le LLM n'a pas retourné de demande valide.")

        return result


if __name__ == '__main__':
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    service = PydanticRequestConverter(
        base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
        api_key=api_key,
        model_name='gemini-3.5-flash',
        system_prompt="Tu es un convertisseur de demande : l'utilisateur envoie une demande au format textuel et tu dois convertire le texte en entrée en sortie fortement structurée."
    )
    demande_textuelle = "Bonjour, je suis Marc Dupont (adresse email: marc.dupont@corp.com). Je souhaiterais commander 15 licences de votre logiciel pour mon équipe, mais j'aurais besoin d'un devis au préalable. Merci !"
    response = service.traiter_message_contact(demande_textuelle)
    print(response.model_dump())