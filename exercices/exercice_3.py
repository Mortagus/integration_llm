# # Exercice 3 : Agent Assistant Météo & Calendrier Multi-Outils
#
# ## Objectif
# Implémenter un agent capable d'utiliser **deux fonctions locales distinctes** pour répondre à une requête complexe de l'utilisateur.
#
# ## Consignes
# 1. Créez un fichier `exercice_3.py`.
# 2. Écrivez deux fonctions Python locales mockées :
#    - `get_meteo(ville: str)` -> retourne un dictionnaire `{"ville": ville, "temperature": "22°C", "condition": "Ensoleillé"}`.
#    - `get_agenda(date: str)` -> retourne un dictionnaire `{"date": date, "evenements": ["10h: Réunion d'équipe", "14h: Démo client IA"]}`.
# 3. Définissez la liste `tools` contenant la description JSON Schema de ces deux fonctions.
# 4. Écrivez la boucle d'agent pour traiter le message utilisateur suivant :
#    > *"Quel temps fait-il à Bruxelles et quel est mon programme pour aujourd'hui (2026-10-12) ?"*
# 5. **Gestion du multi-tools** : Attention ! L'IA peut renvoyer plusieurs appels de fonctions dans la liste `message.tool_calls`. Parcourez cette liste avec une boucle `for` pour exécuter chaque fonction demandée et ajouter chaque réponse à l'historique de conversation avant de faire l'appel final !

import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class BetterAssistant:
    system_prompt: str
    base_url: str
    api_key: str
    model_name: str
    final_response: str

    def __init__(self, base_url, api_key, model_name, system_prompt):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.final_response = ""

        self._tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_meteo",
                    "description": "Obtenir la météo à partir du nom d'une ville",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ville": {"type": "string", "description": "Le nom de la ville pour laquelle on désire la météo du jour."},
                        },
                        "required": ["ville"],
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_agenda",
                    "description": "Obtenir la liste des choses à faire durant la journée pour une date donnée",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "La date de la journée pour laquelle on désire l'emploie du temps."},
                        },
                        "required": ["date"],
                    }
                }
            }
        ]

    def _get_meteo(self, ville: str) -> dict:
        return {"ville": ville, "temperature": "22°C", "condition": "Ensoleillé"}

    def _get_agenda(self, date: str) -> dict:
        return {"date": date, "evenements": ["10h: Réunion d'équipe", "14h: Démo client IA"]}

    def handle_user_request(self, user_request: str) -> str:
        # tool detection
        messages = [
            {"role": "system", "content": self.system_prompt},
            {'role': 'user', 'content': user_request}
        ]
        tool_detection_chat_response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=self._tools,
            tool_choice="auto"
        )
        message_assistant = tool_detection_chat_response.choices[0].message
        if message_assistant.content:
            self.final_response += message_assistant.content
        messages.append(message_assistant)

        for tool_call in message_assistant.tool_calls:
            current_tool_name = tool_call.function.name
            current_tool_args = json.loads(tool_call.function.arguments)

            data = {}
            if current_tool_name == "get_meteo":
                data = self._get_meteo(current_tool_args.get("ville"))

            if current_tool_name == "get_agenda":
                data = self._get_agenda(current_tool_args.get("date"))

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(data)
            })
            second_response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            if second_response.choices[0].message.content:
                self.final_response += second_response.choices[0].message.content

        return self.final_response


def main():
    assistant = BetterAssistant(
        system_prompt="Tu est un assistant support client utile et poli",
        # base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        # api_key=os.getenv("GEMINI_API_KEY"),
        # model_name="gemini-3.6-flash",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model_name="openrouter/free",
    )
    user_request = "Quel temps fait-il à Bruxelles et quel est mon programme pour aujourd'hui (2026-10-12) ?"
    response_finale = assistant.handle_user_request(user_request)
    print(f"Réponse de l'assistant :{response_finale}")


if __name__ == "__main__":
    main()
