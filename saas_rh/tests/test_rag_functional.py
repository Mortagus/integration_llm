import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import pytest
from dotenv import load_dotenv

BASE_URL = os.getenv("SAAS_RH_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
STARTUP_TIMEOUT_SECONDS = 30
RTT_AND_CET_QUESTION = "Combien de jours de RTT ai-je droit et puis-je les placer sur un CET ?"
BIRTH_BONUS_QUESTION = "Quelle est la prime de naissance accordée par l'entreprise ?"
EXPECTED_ABSTENTION = "Je ne trouve pas cette information dans les politiques RH fournies."


def _check_health() -> bool:
    try:
        with urlopen(f"{BASE_URL}/health", timeout=1) as response:
            return response.status == 200
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def _start_local_server() -> subprocess.Popen[bytes]:
    parsed_url = urlparse(BASE_URL)
    host = parsed_url.hostname or "127.0.0.1"
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "saas_rh.main:app", "--host", host, "--port", str(port)],
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )


@pytest.fixture(scope="module")
def local_api() -> Iterator[str]:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    api_key_name = {
        "gemini": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }.get(provider)
    if api_key_name is None:
        pytest.fail("LLM_PROVIDER doit valoir 'gemini' ou 'anthropic'.")
    if not os.getenv(api_key_name):
        pytest.skip(f"{api_key_name} est nécessaire pour appeler le service LLM réel.")

    server_process = None if _check_health() else _start_local_server()
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while not _check_health():
            if server_process is not None and server_process.poll() is not None:
                pytest.fail(
                    "Uvicorn s'est arrêté avant que /health réponde. "
                    "Vérifiez la configuration locale de l'application."
                )
            if time.monotonic() >= deadline:
                pytest.fail("Le serveur local n'a pas démarré dans le délai imparti.")
            time.sleep(0.25)
        yield BASE_URL
    finally:
        if server_process is not None:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=5)


def _ask_rag(base_url: str, question: str) -> dict[str, object]:
    request = Request(
        f"{base_url}/api/rag/ask",
        data=urlencode({"question": question}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            assert response.status == 200
            return json.loads(response.read())
    except HTTPError as error:
        body = error.read().decode(errors="replace")
        pytest.fail(f"Le RAG a répondu avec le statut {error.code} : {body}")


@pytest.mark.skipif(
    os.getenv("SAAS_RH_RUN_FUNCTIONAL_TESTS") != "1",
    reason="Test RAG avec serveur local et appel LLM réel : exécution opt-in.",
)
def test_rag_answers_rtt_and_cet_question_with_policy_source(
    local_api: str,
) -> None:
    response = _ask_rag(local_api, RTT_AND_CET_QUESTION)

    assert set(response) == {"content", "sources"}
    content = str(response["content"]).casefold()
    assert "10" in content
    assert "5" in content
    assert "cet" in content
    assert any(source["id"] == "rh_doc_02" for source in response["sources"])


@pytest.mark.skipif(
    os.getenv("SAAS_RH_RUN_FUNCTIONAL_TESTS") != "1",
    reason="Test RAG avec serveur local et appel LLM réel : exécution opt-in.",
)
def test_rag_refuses_undocumented_birth_bonus_question(local_api: str) -> None:
    response = _ask_rag(local_api, BIRTH_BONUS_QUESTION)

    assert response["content"] == EXPECTED_ABSTENTION
