from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_CV_TEXT_LENGTH = 20_000
MAX_PDF_PAGES = 20


class CandidatePdfExtractionError(ValueError):
    """Raised when a candidate PDF cannot provide extractable text."""


class CandidatePdfLimitError(CandidatePdfExtractionError):
    """Raised when a candidate PDF exceeds a processing limit."""


class CandidatePdfTextExtractor:
    """Extract selectable text from a candidate PDF."""

    def extract_text(self, pdf_content: bytes) -> str:
        """Return text from every page, or raise when the PDF has no readable text."""
        if not pdf_content.startswith(b"%PDF-"):
            raise CandidatePdfExtractionError(
                "Le fichier fourni n'est pas un PDF lisible."
            )

        try:
            reader = PdfReader(BytesIO(pdf_content))
            if len(reader.pages) > MAX_PDF_PAGES:
                raise CandidatePdfLimitError(
                    f"Le PDF dépasse la limite de {MAX_PDF_PAGES} pages."
                )
            extracted_pages: list[str] = []
            extracted_length = 0
            for page in reader.pages:
                page_text = page.extract_text() or ""
                extracted_length += len(page_text)
                if extracted_length > MAX_CV_TEXT_LENGTH:
                    raise CandidatePdfLimitError(
                        "Le texte extrait du PDF dépasse la limite autorisée."
                    )
                extracted_pages.append(page_text)
            text = "\n".join(extracted_pages).strip()
        except CandidatePdfLimitError:
            raise
        except (PdfReadError, OSError) as error:
            raise CandidatePdfExtractionError(
                "Le fichier fourni n'est pas un PDF lisible."
            ) from error

        if not text:
            raise CandidatePdfExtractionError(
                "Aucun texte extractible n'a été trouvé dans le PDF."
            )
        return text
