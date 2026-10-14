from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from saas_rh.api.routers import agent, candidates, interviews, pages, rag, system
from saas_rh.application import build_application_services, load_application_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create shared application services and close external clients."""
    settings = load_application_settings()
    services = build_application_services(settings)
    app.state.interview_service = services.interview_service
    app.state.agent_service = services.agent_service
    app.state.candidate_parser_service = services.candidate_parser_service
    app.state.rag_service = services.rag_service
    try:
        yield
    finally:
        services.close()


# TODO: Avant une mise en production, évaluer le masquage de /docs et l'ajout
# d'en-têtes de sécurité adaptés, notamment une Content Security Policy (CSP).
app = FastAPI(
    title="SaaS RH",
    version="0.1.0",
    description="API d'assistant de recrutement enrichi par LLM.",
    lifespan=lifespan,
)

_STATIC_DIR = Path(__file__).parent / "web" / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

app.include_router(pages.router)
app.include_router(system.router)

app.include_router(candidates.router)
app.include_router(rag.router)
app.include_router(agent.router)
app.include_router(interviews.router)
