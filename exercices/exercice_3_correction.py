import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def get_meteo(ville:str)->dict:
    return{"ville":ville, "temperature":"22°C", "condition":"Ensoleillé"}

def get_agenda(date:str)->dict:
    return{
        "date":date,
        "evenements":["10h: Réunion d'équipe", "14h Démo client"]
    }

FONCTIONS_DISPONIBLES = {
    "get_meteo":get_meteo,
    "get_agenda":get_agenda
}

tools=[
    {
        "type": "function",
        "function":{
            "name": "get_meteo",
            "description":"Obtenir la météo d'une ville",
            "parameters": {
                "type" : "object",
                "properties": {
                    "ville":{
                        "type": "string",
                        "description": "Le nom de la ville"
                    }
                },
                "required": ["ville"]
            },
        },
    },
    {
        "type": "function",
        "function":{
            "name": "get_agenda",
            "description":"Obtenir la liste des évènements enregistrer dans l'agenda",
            "parameters": {
                "type" : "object",
                "properties": {
                   "date":{
                       "type": "string",
                       "description": "Date de l'évènement au format DD-MM-YYYY",
                   }
                },
                "required": ["date"]
            },
        },
    },
]

def agent_assistant(question_utilisateur:str)->str:
    gemini_key = os.getenv("GEMINI_API_KEY")
    client = OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=gemini_key
    )

    messages=[
        {
            "role":"system",
            "content":"Tu es un assistant personnel intelligent. Utilise les outils à ta disposition pour récupérer les informations requises"
        },
        {
            "role":"user",
            "content":question_utilisateur
        }
    ]
    response= client.chat.completions.create(
        model="gemini-3.5-flash",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )

    message_assistant = response.choices[0].message

    if message_assistant.tool_calls:
        print(f"Le llm a effectuer  {len(message_assistant.tool_calls)} appel d'outil")
        messages.append(message_assistant)
        for tool_call in message_assistant.tool_calls:
            nom_fonction = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Outil appelé : {nom_fonction}")
            print(f"Arguments donné : {arguments}")

            if nom_fonction in FONCTIONS_DISPONIBLES:
                resultat = FONCTIONS_DISPONIBLES[nom_fonction](**arguments)
            else:
                resultat = {"Erreur": f"Fonction {nom_fonction} inconnue"}
            print(f"Resultat : {resultat}")

            messages.append({
                "role":"tool",
                "tool_call_id":tool_call.id,
                "content": json.dumps(resultat)
            })
        second_response = client.chat.completions.create(
            model="gemini-3.5-flash",
            messages=messages,
        )
        return second_response.choices[0].message.content
    return message_assistant.content

if __name__ == "__main__":
    question = "Quel temps fait-il à Namur et quel est mon programme pour aujourd'hui (12-10-2026)"
    response_finale = agent_assistant(question)
    print(response_finale)