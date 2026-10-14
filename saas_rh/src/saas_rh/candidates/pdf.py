from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class CandidatePdfExtractionError(ValueError):
    """Raised when a candidate PDF cannot provide extractable text."""


class CandidatePdfTextExtractor:
    """Extract selectable text from a candidate PDF."""

    def extract_text(self, pdf_content: bytes) -> str:
        """Return text from every page, or raise when the PDF has no readable text."""
        try:
            reader = PdfReader(BytesIO(pdf_content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except (PdfReadError, OSError) as error:
            raise CandidatePdfExtractionError(
                "Le fichier fourni n'est pas un PDF lisible."
            ) from error

        if not text:
            raise CandidatePdfExtractionError(
                "Aucun texte extractible n'a été trouvé dans le PDF."
            )
        return text
