import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from saas_rh.data.candidates.mock_data import CANDIDAT_EXEMPLE_1, CANDIDAT_EXEMPLE_2

BASE_URL = os.getenv("SAAS_RH_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
STARTUP_TIMEOUT_SECONDS = 30


def _check_health() -> bool:
    try:
        with urlopen(f"{BASE_URL}/health", timeout=1) as response:
            if response.status != 200:
                raise AssertionError(
                    "Le serveur local répond avec le statut "
                    f"{response.status} sur /health."
                )
            return True
    except HTTPError as error:
        raise AssertionError(
            f"Le serveur local répond avec le statut {error.code} sur /health."
        ) from error
    except (URLError, TimeoutError, OSError):
        return False


def _start_local_server() -> subprocess.Popen[bytes]:
    parsed_url = urlparse(BASE_URL)
    host = parsed_url.hostname or "127.0.0.1"
    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "saas_rh.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )


@pytest.mark.skipif(
    os.getenv("SAAS_RH_RUN_FUNCTIONAL_TESTS") != "1",
    reason="Test avec serveur local et appel LLM réel : exécution opt-in.",
)
def test_parse_candidate_through_local_server() -> None:
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

    server_process = None
    if not _check_health():
        server_process = _start_local_server()

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

        for candidate_name, cv_text in (
            ("Jean Dupont", CANDIDAT_EXEMPLE_1),
            ("Sophie Martin", CANDIDAT_EXEMPLE_2),
        ):
            request = Request(
                f"{BASE_URL}/api/candidates/parse",
                data=urlencode({"cv_text": cv_text}).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=120) as response:
                    assert response.status == 200
                    parsed_candidate = json.loads(response.read())
            except HTTPError as error:
                response_body = error.read().decode(errors="replace")
                pytest.fail(
                    f"Le parsing de {candidate_name} a répondu avec le statut "
                    f"{error.code} : {response_body}\n"
                    "Consultez les logs Uvicorn pour la traceback côté serveur."
                )

            print(
                f"Réponse de l'API pour {candidate_name} :\n"
                + json.dumps(parsed_candidate, indent=2, ensure_ascii=False)
            )
            assert set(parsed_candidate) == {
                "skills",
                "years_of_experience",
                "education_level",
                "match_score",
                "warning_points",
            }

            if candidate_name == "Jean Dupont":
                assert parsed_candidate["match_score"] > 80
                assert any(
                    "fastapi" in skill.casefold()
                    for skill in parsed_candidate["skills"]
                )
            else:
                assert parsed_candidate["match_score"] < 40

        pdf_path = (
            Path(__file__).parents[1]
            / "src"
            / "saas_rh"
            / "data"
            / "candidates"
            / "20261014_test_cv.pdf"
        )
        if pdf_path.exists():
            boundary = uuid4().hex
            pdf_content = pdf_path.read_bytes()
            multipart_body = b"".join(
                [
                    f"--{boundary}\r\n".encode(),
                    (
                        'Content-Disposition: form-data; name="cv_file"; '
                        f'filename="{pdf_path.name}"\r\n'
                    ).encode(),
                    b"Content-Type: application/pdf\r\n\r\n",
                    pdf_content,
                    f"\r\n--{boundary}--\r\n".encode(),
                ]
            )
            pdf_request = Request(
                f"{BASE_URL}/api/candidates/parse",
                data=multipart_body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            )
            try:
                with urlopen(pdf_request, timeout=120) as response:
                    assert response.status == 200
                    parsed_pdf_candidate = json.loads(response.read())
            except HTTPError as error:
                response_body = error.read().decode(errors="replace")
                pytest.fail(
                    f"Le parsing du CV PDF a répondu avec le statut {error.code} : "
                    f"{response_body}\nConsultez les logs Uvicorn."
                )

            print(
                "Réponse de l'API pour le CV PDF :\n"
                + json.dumps(parsed_pdf_candidate, indent=2, ensure_ascii=False)
            )
            assert set(parsed_pdf_candidate) == {
                "skills",
                "years_of_experience",
                "education_level",
                "match_score",
                "warning_points",
            }
    finally:
        if server_process is not None:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=5)
