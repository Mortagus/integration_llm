import os
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field,EmailStr


load_dotenv()

class DemandeContact(BaseModel):
    nom_client: str = Field(description="Nom et prenom du client ou expéditeur")
    email: EmailStr  = Field(description="Email")
    quantite_souhaitee: int = Field(description="Quantite souhaitee")
    categorie: Literal["Reservation","Réclamation","Demande d'information"] = Field(description="Categorie")
    resume_court: str = Field(description="Resume de la demander en une seule phrase concise")

def traiter_message_contact(msg:str)->DemandeContact:
    gemini_key= os.getenv("GEMINI_API_KEY")
    client= OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=gemini_key,
    )

    system_prompt = (
        "Tu est un assistant de gestion de relation client.\n"
        "Ton rôle est d'analyser le message d'un client et d'en extraire toutes les informations clés selon le schéma Pydantic fournis"
    )

    response = client.chat.completions.parse(
        model="gemini-3.5-flash",
        messages=[
            {"role": "system", "content":system_prompt},
            {"role":"user", "content":msg},
        ],
        response_format=DemandeContact,
        temperature=0.2
    )

    return response.choices[0].message.parsed

if __name__ == "__main__":
    message_test=("Bonjour, je suis Marc Dupont (adresse email: marc.dupont@corp.com). "
        "Je souhaiterais commander 15 licences de votre logiciel pour mon équipe, "
        "mais j'aurais besoin d'un devis au préalable. Merci !")
    print(f"Message à analyser : {message_test}")
    print("Extraction en cours...")

    demande_extraite: DemandeContact = traiter_message_contact(message_test)
    donnees_dict = demande_extraite.model_dump()

    print("Donnée extraite avec succès")
    for cle, value in donnees_dict.items():
        print(f"Clé: {cle} | Value : {value}")
    print(donnees_dict)