from fastapi import APIRouter

from prefix_api import __version__
from prefix_api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> HealthResponse:
    """Liveness probe. Does not touch the database or Redis."""
    return HealthResponse(status="ok", service="prefix-api", version=__version__)
