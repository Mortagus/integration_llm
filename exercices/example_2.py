import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()

@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int

class StatutLivraison(BaseModel):
    commande_id: str = Field(description="Identifiant unique de la commande")
    statut: Literal['Expédier', 'En préparation', 'Livré', 'Inconnu'] = Field(description="Le statut actuel")
    jours_estimes: int = Field(description ="Le nombres de jours de livraison estimé")
    est_urgent: bool =Field(description="Vrai si le client exprime une urgence ou un mécontentement")

class LLMService:
    def __init__(self):
        gemini_key = os.getenv("GEMINI_API_KEY")
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key,
        )
    def interroger_llm(self, question:str) -> LLMResponse:
        response = self.client.chat.completions.create(
            model="gemini-3.5-flash",
            messages=[
                {"role":"system", "content":"Tu es un expert en logistique E-commerce très précis"},
                {"role":"user", "content":question},
            ],
            temperature=0.2,
        )
        return LLMResponse(
            content = response.choices[0].message.content,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens
        )
    def analyser_demande_json(self, texte_client:str) -> StatutLivraison:
        response = self.client.beta.chat.completions.parse(
            model="gemini-3.5-flash",
            response_format=StatutLivraison,
            messages=[
                {
                    "role": "system",
                    "content":"Tu es un système d'extraction de données logistique. Extrais les informations du message client."
                },
                {
                    "role": "user",
                    "content":texte_client
                }
            ],
            temperature=0.0
        )
        return response.choices[0].message.parsed

if __name__ == "__main__":
    service = LLMService()
    message = "Bonjour, ma commande #cmd-42 devait arriver hier, c'est honteux c'est super urgent"
    donnees_parsed = service.analyser_demande_json(message)

    print(donnees_parsed.commande_id)
    print(donnees_parsed.statut)
    print(donnees_parsed.jours_estimes)
    print(donnees_parsed.est_urgent)
    print(type(donnees_parsed))