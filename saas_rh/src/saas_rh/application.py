import os
from dataclasses import dataclass, field
from pathlib import Path

import chromadb
from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

from saas_rh.agent.service import AgentService
from saas_rh.candidates.service import CandidateParserService
from saas_rh.interviews.repository import InterviewScheduleRepository
from saas_rh.interviews.service import InterviewService
from saas_rh.llm.gateway import AnthropicGateway, LLMGateway, OpenAICompatibleGateway
from saas_rh.rag.service import RAGService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LLM_REQUEST_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class ApplicationSettings:
    provider: str
    api_key: str | None = field(repr=False)
    base_url: str | None = None
    model_name: str | None = None
    fallback_model_names: tuple[str, ...] = ()
    chroma_db_path: str = str(PROJECT_ROOT / ".chroma")
    anthropic_workspace_id: str = field(default="", repr=False)


@dataclass
class ApplicationServices:
    interview_service: InterviewService
    agent_service: AgentService | None
    candidate_parser_service: CandidateParserService | None
    rag_service: RAGService | None
    client: OpenAI | Anthropic | None = field(repr=False)

    def close(self) -> None:
        if self.client is not None:
            self.client.close()


def _required_setting(environment_variable: str) -> str:
    value = os.getenv(environment_variable, "").strip()
    if not value:
        raise ValueError(f"La variable {environment_variable} doit être renseignée.")
    return value


def _configured_fallback_models(environment_variable: str) -> tuple[str, ...]:
    configured_models = os.getenv(environment_variable, "")
    return tuple(
        model.strip() for model in configured_models.split(",") if model.strip()
    )


def _chroma_db_path() -> str:
    configured_path = os.getenv("CHROMA_DB_PATH", ".chroma").strip() or ".chroma"
    path = Path(configured_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return str(path.resolve())


def load_application_settings() -> ApplicationSettings:
    """Load and validate the selected provider configuration."""
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        base_url = None
        model_name = None
        fallback_model_names: tuple[str, ...] = ()
        if api_key:
            base_url = _required_setting("GEMINI_BASE_URL")
            model_name = _required_setting("GEMINI_MODEL")
            fallback_model_names = _configured_fallback_models("GEMINI_FALLBACK_MODELS")
        workspace_id = ""
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None
        model_name = _required_setting("ANTHROPIC_MODEL") if api_key else None
        fallback_model_names = (
            _configured_fallback_models("ANTHROPIC_FALLBACK_MODELS") if api_key else ()
        )
        workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
    else:
        raise ValueError("LLM_PROVIDER doit valoir 'gemini' ou 'anthropic'.")

    return ApplicationSettings(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        fallback_model_names=fallback_model_names,
        chroma_db_path=_chroma_db_path(),
        anthropic_workspace_id=workspace_id,
    )


def _build_llm_client_and_gateway(
    settings: ApplicationSettings,
) -> tuple[OpenAI | Anthropic | None, LLMGateway | None]:
    if not settings.api_key:
        return None, None
    if settings.provider == "gemini":
        openai_client = OpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            max_retries=0,
            timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        )
        return openai_client, OpenAICompatibleGateway(openai_client)

    anthropic_client = Anthropic(
        api_key=settings.api_key,
        base_url=settings.base_url,
        max_retries=0,
        timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        default_headers=(
            {"anthropic-workspace-id": settings.anthropic_workspace_id}
            if settings.anthropic_workspace_id
            else None
        ),
    )
    return anthropic_client, AnthropicGateway(anthropic_client)


def build_application_services(
    settings: ApplicationSettings,
) -> ApplicationServices:
    """Construct shared clients and domain services for one application lifespan."""
    interview_service = InterviewService(InterviewScheduleRepository())
    client, gateway = _build_llm_client_and_gateway(settings)
    if gateway is None or settings.model_name is None:
        return ApplicationServices(interview_service, None, None, None, client)
    try:
        agent_service = AgentService(gateway, settings.model_name, interview_service)
        candidate_parser_service = CandidateParserService(
            gateway,
            settings.model_name,
            fallback_model_names=settings.fallback_model_names,
        )
        chroma_client = chromadb.PersistentClient(path=settings.chroma_db_path)
        collection = chroma_client.get_or_create_collection(name="politiques_rh")
        rag_service = RAGService(collection, gateway, settings.model_name)
        rag_service.index_policies()
        return ApplicationServices(
            interview_service,
            agent_service,
            candidate_parser_service,
            rag_service,
            client,
        )
    except Exception:
        if client is not None:
            client.close()
        raise
