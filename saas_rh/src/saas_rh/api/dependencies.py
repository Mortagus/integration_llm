from fastapi import HTTPException, Request, status

from saas_rh.candidates.pdf import CandidatePdfTextExtractor
from saas_rh.candidates.service import CandidateParserService
from saas_rh.rag.service import RAGService


def get_candidate_parser_service(request: Request) -> CandidateParserService:
    """Return the shared candidate parser configured during app startup."""
    service: CandidateParserService | None = getattr(
        request.app.state, "candidate_parser_service", None
    )
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de parsing des CV n'est pas configuré.",
        )
    return service


def get_candidate_pdf_text_extractor() -> CandidatePdfTextExtractor:
    """Return the candidate PDF text extractor."""
    return CandidatePdfTextExtractor()


def get_rag_service(request: Request) -> RAGService:
    """Return the shared RAG service configured during application startup."""
    service: RAGService | None = getattr(request.app.state, "rag_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service RAG n'est pas configuré.",
        )
    return service
