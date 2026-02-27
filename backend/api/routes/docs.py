from fastapi import APIRouter
from core import get_settings
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

router = APIRouter(prefix="/docs", tags=["docs"], redirect_slashes=True)
settings = get_settings()

@router.get("", include_in_schema=False)
def overridden_redoc():
    """
    Overrides the default /redoc endpoint to use a custom favicon.
    """
    return get_redoc_html(
        openapi_url="/openapi.json",
        title=f"{settings.app_name} API - ReDoc",
        redoc_favicon_url="/icons/beaker-red-bg.png" # Replace with your custom favicon URL
    )

#@router.get("/swagger/", include_in_schema=False)
#def overridden_swagger():
#    """
#    Overrides the default /swagger endpoint to use a custom favicon.
#    """
#    return get_swagger_ui_html(
#        openapi_url="/openapi.json",
#        title=f"{settings.app_name} API - Swagger",
#        swagger_favicon_url="/icons/beaker-red-bg.png" # Replace with your custom favicon URL
#    )