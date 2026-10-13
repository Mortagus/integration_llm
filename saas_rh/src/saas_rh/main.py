from fastapi import FastAPI

from saas_rh.api.routers import agent, candidates, interviews, rag, system

app = FastAPI(
    title="SaaS RH",
    version="0.1.0",
    description="API d'assistant de recrutement enrichi par LLM.",
)

app.include_router(system.router)

app.include_router(candidates.router)
app.include_router(rag.router)
app.include_router(agent.router)
app.include_router(interviews.router)
