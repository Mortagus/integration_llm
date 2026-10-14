from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["interface web"])

_CHAT_PAGE = Path(__file__).parents[2] / "web" / "static" / "index.html"


@router.get("/", include_in_schema=False)
async def chat_page() -> FileResponse:
    """Serve the small browser interface for the recruitment agent."""
    return FileResponse(_CHAT_PAGE)
