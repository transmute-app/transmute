from fastapi import APIRouter, Request
from core import get_settings
from fastapi.openapi.docs import get_redoc_html

router = APIRouter(prefix="/docs", tags=["docs"], redirect_slashes=True)
settings = get_settings()

@router.get("", include_in_schema=False)
def overridden_redoc(request: Request):
    """
    Overrides the default /redoc endpoint to use a custom favicon.
    """
    # Prefix absolute URLs with the sub-path the docs page is served from.
    root_path = request.scope.get("root_path", "")
    return get_redoc_html(
        openapi_url=f"{root_path}/openapi.json",
        title=f"{settings.app_name} API - ReDoc",
        redoc_favicon_url=f"{root_path}/icons/beaker-red-bg.png"
    )
