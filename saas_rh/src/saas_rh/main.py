from fastapi import FastAPI

app = FastAPI(
    title="SaaS RH",
    version="0.1.0",
    description="API d'assistant de recrutement enrichi par LLM.",
)


@app.get("/health", tags=["système"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
