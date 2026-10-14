import re

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+|00)?(?:\d[\s()./-]*){9,15}(?!\w)")
_LABELED_PERSONAL_DATA_PATTERN = re.compile(
    r"(?im)^\s*(?:"
    r"nom(?:\s+complet)?|prénom|name|full\s+name|candidate|candidat|"
    r"adresse|address|domicile|date\s+de\s+naissance|né[e]?\s+le|"
    r"birth(?:\s+date)?|date\s+of\s+birth|dob|âge|age|nationalité|"
    r"nationality|sexe|gender|état\s+civil|marital\s+status|"
    r"situation\s+familiale|santé|health|handicap|disability|"
    r"(?:numéro|no\.?|n°)\s*(?:de\s+)?sécurité\s+sociale|nir|"
    r"(?:numéro|no\.?|n°)\s+(?:de\s+)?(?:passeport|carte\s+d'identité)|"
    r"passport(?:\s+number)?|national\s+id"
    r")\s*[:：].*$"
)
_LABELED_PROFILE_URL_PATTERN = re.compile(
    r"(?im)^\s*(?:linkedin|github|portfolio|site\s+web|website)\s*[:：]?\s*.*$"
)
_NAME_HEADER_PATTERN = re.compile(
    r"^\s*[A-ZÀ-ÖØ-Þ][\w'’.-]*(?:\s+[A-ZÀ-ÖØ-Þ][\w'’.-]*){1,3}\s*$"
)
_NAME_PREFIX_PATTERN = re.compile(
    r"^\s*[A-ZÀ-ÖØ-Þ][\w'’.-]*(?:\s+[A-ZÀ-ÖØ-Þ][\w'’.-]*){1,3}"
    r"(?=\s+[-–—|,])"
)


def redact_candidate_pii(cv_text: str) -> str:
    """Remove direct identifiers and clearly labeled personal details from a CV."""
    redacted_lines = cv_text.splitlines()
    first_content_line = next(
        (index for index, line in enumerate(redacted_lines) if line.strip()), None
    )

    if first_content_line is not None:
        header = redacted_lines[first_content_line]
        if _NAME_HEADER_PATTERN.fullmatch(header):
            redacted_lines[first_content_line] = "[NOM SUPPRIMÉ]"
        else:
            redacted_lines[first_content_line] = _NAME_PREFIX_PATTERN.sub(
                "[NOM SUPPRIMÉ]", header, count=1
            )

    redacted_text = "\n".join(redacted_lines)
    redacted_text = _LABELED_PERSONAL_DATA_PATTERN.sub(
        "[DONNÉES PERSONNELLES SUPPRIMÉES]", redacted_text
    )
    redacted_text = _LABELED_PROFILE_URL_PATTERN.sub(
        "[LIEN DE PROFIL SUPPRIMÉ]", redacted_text
    )
    redacted_text = _EMAIL_PATTERN.sub("[EMAIL SUPPRIMÉ]", redacted_text)

    def replace_phone(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group())
        return "[TÉLÉPHONE SUPPRIMÉ]" if 9 <= len(digits) <= 15 else match.group()

    return _PHONE_PATTERN.sub(replace_phone, redacted_text)
