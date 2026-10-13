import json
import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import Field, BaseModel

load_dotenv()


@dataclass
class LLMResponse:
    content: str
    prompt_token: int
    completion_token: int


class StatutLivraison(BaseModel):
    commande_id: str = Field(description="L'identifiant unique de la commande")
    statut: Literal['Expédié', 'En préparation', 'Livré', 'Inconnu'] = Field(description="Le statut actuel")
    jours_estimes: int = Field(description="Le nombre de jours de livraison estimé")
    est_urgent: bool = Field(description="Vrai si le client exprime une urgence")


class LLMService:
    def __init__(self):
        gemini_key = os.getenv("GEMINI_API_KEY")
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key,
        )

        self._mock_db = {
            "CMD-101": {"statut": "Expédié", "transporteur": "DHL", "eta": "2 jours"},
            "CMD-202": {"statut": "En préparation", "transporteur": "UPS", "eta": "5 jours"}
        }
        self._tools = [{
            "type": "function",
            "function": {
                "name": "rechercher_commande_db",
                "description": "Obtenir le statut et les détails d'une commande",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commande_id": {"type": "string", "description": "L'identifiant de ma commande"},
                    },
                    "required": ["commande_id"],
                }
            }
        }]

    def _rechercher_commande_db(self, commande_id: str) -> dict:
        return self._mock_db.get(commande_id, {"erreur": "Commande introuvable"})

    def interroger_llm(self, question: str) -> LLMResponse:
        response = self.client.chat.completions.create(
            model="gemini-3.5-flash",
            messages=[
                {"role": "system", "content": "Tu est un expert en logistique E-commerce très précis"},
                {"role": 'user', "content": question}
            ],
            temperature=0.2
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_token=response.usage.prompt_tokens,
            completion_token=response.usage.completion_tokens
        )

    def analyser_demande_json(self, texte_client: str) -> StatutLivraison:
        response = self.client.chat.completions.parse(
            model="gemini-3.5-flash",
            messages=[
                {"role": "system", "content": "Tu est un systeme d'extraction de donnée"},
                {"role": 'user', "content": texte_client}
            ],
            temperature=0.0
        )
        return response.choices[0].message.parsed

    def agent_support(self, question_client: str) -> str:
        messages = [
            {"role": "system", "content": "Tu est un assistant support client utile et poli"},
            {"role": 'user', "content": question_client}
        ]
        response = self.client.chat.completions.create(
            model="gemini-3.5-flash",
            messages=messages,
            tools=self._tools,
            tool_choice="auto"
        )
        message_assistant = response.choices[0].message

        if message_assistant.tool_calls:
            tool_call = message_assistant.tool_calls[0]
            nom_fonction = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"L'agent à décider d'appeler la fonction {nom_fonction}")
            print(f"Arguments extrait : {arguments}")

            if nom_fonction == "rechercher_commande_db":
                resultat_bdd = self._rechercher_commande_db(arguments.get("commande_id"))
                print(f"Données brut → {resultat_bdd}")
                messages.append(message_assistant)
                messages.append({"role": "tool",
                                 "tool_call_id": tool_call.id,
                                 "content": json.dumps(resultat_bdd)
                                 })
                second_response = self.client.chat.completions.create(
                    model="gemini-3.5-flash",
                    messages=messages
                )
                return second_response.choices[0].message.content
        return message_assistant.content


if __name__ == "__main__":
    service = LLMService()
    print("Test function calling")
    response_finale = service.agent_support("Bonjour, où en est ma commande CMD-101 ?")
    print(f"Réponse de l'assistant :{response_finale}")
