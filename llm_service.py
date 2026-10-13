import os
from dataclasses import dataclass
from dotenv import load_dotenv
from openai import OpenAI

@dataclass
class LLMResponse:
	content: str
	prompt_tokens: int
	completion_tokens: int

class LLMService:
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

	def interroger_llm(self, temperature:float, question:str) -> LLMResponse:
		response = self.client.chat.completions.create(
			model=self.model_name,
			messages=[
				{"role": "system", "content": self.system_prompt},
				{"role": "user", "content": question},
			],
			temperature=temperature
		)
		return LLMResponse(
			content=response.choices[0].message.content,
			prompt_tokens=response.usage.prompt_tokens,
			completion_tokens=response.usage.completion_tokens,
		)

	def json_llm_request(self, temperature:float, request_message:str, response_format:dataclass):
		response = self.client.beta.chat.completions.parse(
			model=self.model_name,
			response_format=StatutLivraison,
			messages=[
				{
					"role": "system",
					"content": "Tu es un système d'extraction de données logistique. Extrais les informations du message client."
				},
				{
					"role": "user",
					"content": texte_client
				}
			],
			temperature=0.0
		)
		return response.choices[0].message.parsed