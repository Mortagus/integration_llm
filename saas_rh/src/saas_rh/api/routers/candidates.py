from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from saas_rh.candidates.schemas import CandidateParseResponse

router = APIRouter(
    prefix="/api/candidates",
    tags=["candidats"],
)


@router.post(
    "/parse",
    response_model=CandidateParseResponse,
    responses={501: {"description": "Parsing LLM non implémenté"}},
)
async def parse_candidate(
    cv_text: Annotated[str | None, Form()] = None,
    cv_file: Annotated[UploadFile | None, File()] = None,
) -> CandidateParseResponse:
    has_text = cv_text is not None and bool(cv_text.strip())
    has_file = cv_file is not None

    if has_text == has_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fournissez exactement un CV texte ou un fichier CV.",
        )

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Le parsing de CV n'est pas encore implémenté.",
    )
