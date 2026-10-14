import logging
from typing import Annotated

from anthropic import APIError as AnthropicAPIError
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from openai import APIError as OpenAIAPIError

from saas_rh.api.dependencies import (
    get_candidate_parser_service,
    get_candidate_pdf_text_extractor,
)
from saas_rh.candidates.pdf import (
    CandidatePdfExtractionError,
    CandidatePdfLimitError,
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
MAX_PDF_BYTES = 5 * 1024 * 1024
logger = logging.getLogger(__name__)


@router.post("/parse", response_model=CandidateParseResponse)
def parse_candidate(
    parser: Annotated[CandidateParserService, Depends(get_candidate_parser_service)],
    pdf_text_extractor: Annotated[
        CandidatePdfTextExtractor, Depends(get_candidate_pdf_text_extractor)
    ],
    cv_text: Annotated[str | None, Form(max_length=20_000)] = None,
    cv_file: Annotated[UploadFile | None, File()] = None,
) -> CandidateParseResponse:
    has_text = cv_text is not None and bool(cv_text.strip())
    has_file = cv_file is not None

    if has_text == has_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fournissez exactement un CV texte ou un fichier CV.",
        )

    if cv_file is not None:
        try:
            pdf_content = cv_file.file.read(MAX_PDF_BYTES + 1)
            if len(pdf_content) > MAX_PDF_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Le fichier PDF dépasse la limite de 5 Mo.",
                )
            cv_text = pdf_text_extractor.extract_text(pdf_content)
        except CandidatePdfLimitError as error:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(error),
            ) from error
        except CandidatePdfExtractionError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error

    if cv_text is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fournissez exactement un CV texte ou un fichier CV.",
        )
    try:
        return parser.parse_candidate(cv_text.strip())
    except CandidateModelsUnavailableError as error:
        logger.error(
            "Parsing candidat indisponible : modèle=%s statut_fournisseur=%s",
            error.model_name,
            error.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service d'analyse est momentanément indisponible.",
        ) from error
    except (OpenAIAPIError, AnthropicAPIError) as error:
        logger.error(
            "Échec du fournisseur LLM pendant le parsing : type=%s",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service d'analyse est momentanément indisponible.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le modèle n'a pas retourné de profil candidat valide.",
        ) from error
