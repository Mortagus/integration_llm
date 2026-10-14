import logging
from collections.abc import Sequence

from anthropic import Anthropic
from anthropic import APIStatusError as AnthropicAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from saas_rh.candidates.schemas import CandidateParseResponse
from saas_rh.data.candidates.mock_data import OFFRE_POSTE_DEV_PYTHON

logger = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {404, 408, 429, 500, 502, 503, 504}


class CandidateModelsUnavailableError(RuntimeError):
    """Raised when all configured models are temporarily unavailable."""

    def __init__(
        self,
        model_name: str,
        status_code: int,
        provider_message: str,
    ) -> None:
        self.model_name = model_name
        self.status_code = status_code
        self.provider_message = provider_message
        super().__init__(
            f"Le modèle {model_name} a répondu HTTP {status_code} : {provider_message}"
        )


class CandidateParserService:
    """Extrait un profil candidat structuré à partir du texte de son CV."""

    def __init__(
        self,
        client: OpenAI | Anthropic,
        model_name: str,
        fallback_model_names: Sequence[str] = (),
    ) -> None:
        self.client = client
        self.model_names = tuple(dict.fromkeys((model_name, *fallback_model_names)))

    def parse_candidate(self, cv_text: str) -> CandidateParseResponse:
        """Analyse un CV selon l'offre Python/IA et valide la sortie avec Pydantic."""
        system_prompt = (
            "Tu es un assistant de recrutement. Analyse le CV fourni et "
            "évalue son adéquation avec l'offre. N'invente aucune "
            "information absente du CV. Retourne les années totales "
            "d'expérience professionnelle pertinentes et justifie "
            "les points de vigilance."
        )
        user_prompt = f"Offre de poste :\n{OFFRE_POSTE_DEV_PYTHON}\n\nCV :\n{cv_text}"
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        retryable_errors = (OpenAIAPIStatusError, AnthropicAPIStatusError)
        last_retryable_error: OpenAIAPIStatusError | AnthropicAPIStatusError | None = (
            None
        )
        last_retryable_model: str | None = None
        for model_name in self.model_names:
            try:
                if isinstance(self.client, Anthropic):
                    response = self.client.messages.parse(
                        model=model_name,
                        max_tokens=4096,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                        output_format=CandidateParseResponse,
                    )
                    candidate = response.parsed_output
                else:
                    response = self.client.chat.completions.parse(
                        model=model_name,
                        response_format=CandidateParseResponse,
                        messages=messages,
                        temperature=0.0,
                    )
                    candidate = response.choices[0].message.parsed
            except retryable_errors as error:
                if error.status_code not in RETRYABLE_STATUS_CODES:
                    raise
                last_retryable_error = error
                last_retryable_model = model_name
                logger.warning(
                    "LLM model %s returned HTTP %s; trying the next configured model.",
                    model_name,
                    error.status_code,
                )
                continue

            if candidate is None:
                raise ValueError("Le LLM n'a pas retourné de profil candidat valide.")
            logger.info("Le parsing candidat a réussi avec le modèle %s.", model_name)
            return candidate

        if last_retryable_error is not None:
            raise CandidateModelsUnavailableError(
                model_name=last_retryable_model or self.model_names[-1],
                status_code=last_retryable_error.status_code,
                provider_message=str(last_retryable_error),
            ) from last_retryable_error

        raise RuntimeError("Aucun modèle n'est configuré pour le parsing.")
