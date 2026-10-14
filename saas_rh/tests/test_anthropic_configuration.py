import asyncio
from unittest.mock import Mock

from fastapi import FastAPI

from saas_rh.main import lifespan


def test_anthropic_client_receives_workspace_header(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "test-workspace-id")
    client = Mock()
    anthropic_factory = Mock(return_value=client)
    monkeypatch.setattr("saas_rh.main.Anthropic", anthropic_factory)

    async def run_lifespan() -> None:
        async with lifespan(FastAPI()):
            pass

    asyncio.run(run_lifespan())

    assert anthropic_factory.call_args.kwargs["default_headers"] == {
        "anthropic-workspace-id": "test-workspace-id"
    }
