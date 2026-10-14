from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from saas_rh.api.dependencies import (
    get_candidate_parser_service,
    get_candidate_pdf_text_extractor,
)
from saas_rh.candidates.pdf import (
    CandidatePdfExtractionError,
    CandidatePdfTextExtractor,
)
from saas_rh.candidates.schemas import CandidateParseResponse
from saas_rh.candidates.service import (
    CandidateModelsUnavailableError,
    CandidateParserService,
)

router = APIRouter(
    prefix="/api/candidates",
    tags=["candidats"],
)


@router.post("/parse", response_model=CandidateParseResponse)
def parse_candidate(
    parser: Annotated[CandidateParserService, Depends(get_candidate_parser_service)],
    pdf_text_extractor: Annotated[
        CandidatePdfTextExtractor, Depends(get_candidate_pdf_text_extractor)
    ],
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

    if has_file:
        assert cv_file is not None
        try:
            cv_text = pdf_text_extractor.extract_text(cv_file.file.read())
        except CandidatePdfExtractionError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error

    assert cv_text is not None
    try:
        return parser.parse_candidate(cv_text.strip())
    except CandidateModelsUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le modèle n'a pas retourné de profil candidat valide.",
        ) from error
