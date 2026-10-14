import pytest

from saas_rh.candidates.privacy import redact_candidate_pii


@pytest.mark.parametrize(
    "phone",
    [
        "06 12 34 56 78",
        "06.12.34.56.78",
        "0612345678",
        "(06) 12 34 56 78",
        "+33 6 12 34 56 78",
        "0033612345678",
    ],
)
def test_redact_removes_phone_numbers(phone: str) -> None:
    redacted = redact_candidate_pii(f"Développeur\nContact : {phone} merci")

    assert "[TÉLÉPHONE SUPPRIMÉ]" in redacted
    assert phone not in redacted


@pytest.mark.parametrize(
    "dated_line",
    [
        "Dev chez X 03/2019 - 11/2021",
        "Dev chez Y 01/2015 - 02/2019",
        "2018 - 2021 : Développeur Backend",
        "Expérience 2018 2019 2020 2021 2022 2023",
    ],
)
def test_redact_keeps_experience_dates(dated_line: str) -> None:
    redacted = redact_candidate_pii(f"Développeur Python\n{dated_line}")

    assert dated_line in redacted


def test_redact_removes_email_and_profile_links() -> None:
    redacted = redact_candidate_pii(
        "Développeur\njean@exemple.fr\nhttps://www.linkedin.com/in/jean-dupont-123"
    )

    assert "jean@exemple.fr" not in redacted
    assert "linkedin.com" not in redacted


def test_redact_removes_name_header_and_labeled_details() -> None:
    redacted = redact_candidate_pii(
        "Jean Dupont - Développeur Fullstack\nDate de naissance : 01/01/1990\nPython"
    )

    assert "Jean Dupont" not in redacted
    assert "1990" not in redacted
    assert "Python" in redacted
