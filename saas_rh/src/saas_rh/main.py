import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI
from openai import OpenAI

from saas_rh.api.routers import agent, candidates, interviews, rag, system
from saas_rh.candidates.service import CandidateParserService


def _configured_fallback_models(environment_variable: str) -> tuple[str, ...]:
    configured_models = os.getenv(environment_variable, "")
    return tuple(
        model.strip() for model in configured_models.split(",") if model.strip()
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create and close the configured shared LLM client."""
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    client: OpenAI | Anthropic | None = None

    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = OpenAI(
                base_url=os.getenv("GEMINI_BASE_URL", ""),
                api_key=api_key,
                max_retries=0,
            )
            model_name = os.getenv("GEMINI_MODEL", "")
            fallback_models = _configured_fallback_models("GEMINI_FALLBACK_MODELS")
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
            client = Anthropic(
                base_url=os.getenv("ANTHROPIC_BASE_URL", ""),
                api_key=api_key,
                max_retries=0,
                default_headers=(
                    {"anthropic-workspace-id": workspace_id} if workspace_id else {}
                ),
            )
            model_name = os.getenv("ANTHROPIC_MODEL", "")
            fallback_models = _configured_fallback_models("ANTHROPIC_FALLBACK_MODELS")
    else:
        raise ValueError("LLM_PROVIDER doit valoir 'gemini' ou 'anthropic'.")

    if client is not None:
        app.state.candidate_parser_service = CandidateParserService(
            client=client,
            model_name=model_name,
            fallback_model_names=fallback_models,
        )
    else:
        app.state.candidate_parser_service = None

    try:
        yield
    finally:
        if client is not None:
            client.close()


app = FastAPI(
    title="SaaS RH",
    version="0.1.0",
    description="API d'assistant de recrutement enrichi par LLM.",
    lifespan=lifespan,
)

app.include_router(system.router)

app.include_router(candidates.router)
app.include_router(rag.router)
app.include_router(agent.router)
app.include_router(interviews.router)
