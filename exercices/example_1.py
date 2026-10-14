import os
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int


class LLMService:

    def __init__(self):
        gemini_key = os.getenv("GEMINI_API_KEY")
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key,
        )

    def interroger_llm(self, question: str) -> LLMResponse:
        response = self.client.chat.completions.create(
            model="gemini-3.8-flash",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Tu es un expert en logistique e-commerce très précis."
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0.2,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )


if __name__ == "__main__":
    service = LLMService()
    res = service.interroger_llm(
        "Quels sont les délais de livraison pour Bierwart"
    )

    print(f"Reponse llm = \n{res.content}\n")
    print(
        f"Token consommés  : Entrée → {res.prompt_tokens} Sortie →"
        f" {res.completion_tokens}"
    )
