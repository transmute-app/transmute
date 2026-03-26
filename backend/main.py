from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.openapi.utils import get_openapi
from textwrap import dedent
from api import router
from api.routes.oidc import attach_session_middleware
from core import build_logging_config, configure_logging, get_settings
from background import get_upload_cleanup_thread
import uvicorn


def build_api_description(app_name: str) -> str:
    return dedent(f"""
    API to interact with {app_name} without the need for a frontend.

    ## Authentication

    ### Getting an API key

    Authenticate with your user account first, then create a key under 'My Account' -> 'API Keys'.
    The generated key is shown exactly once, so store it safely after creation.

    ### Using an API key

    For any endpoint that expects bearer authentication, send your API key in the `Authorization` header:

    ```http
    Authorization: Bearer <your-api-key>
    ```

    The API accepts either a JWT bearer token for authenticated users through the web interface,
    or an API key for programmatic access anywhere bearer auth is required.
    """).strip()

def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        description=build_api_description(settings.app_name),
        version=f"{settings.app_version}",
        servers=[{"url": settings.api_server_url, "description": f"{settings.app_name} API server"}],
        docs_url=None,
        redoc_url=None,
        redirect_slashes=True
    )

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
            servers=app.servers,
        )
        schema["components"] = schema.get("components", {})
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "Send either a JWT or an API key as `Authorization: Bearer <token>`. "
                    "Authenticate with your user account first, then create a key under 'My Account' -> 'API Keys'. "
                    "The generated key is shown exactly once, so store it safely after creation."
                ),
            }
        }
        schema["security"] = [{"BearerAuth": []}]
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # Session middleware is needed for the OIDC authorization round-trip
    attach_session_middleware(app)

    app.include_router(router, prefix="/api")
    web_dir = settings.web_dir
    if web_dir.exists():
        app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")
        app.mount("/icons", StaticFiles(directory=web_dir / "icons"), name="icons")
        
        # Catch-all route for SPA - serves index.html for non-API routes
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(request: Request, path: str):
            index_file = web_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            raise HTTPException(status_code=404, detail="SPA index not found")
    
    return app

if __name__ == "__main__":
    settings = get_settings()
    app = create_app()
    cleanup_thread = get_upload_cleanup_thread()
    cleanup_thread.start()
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=build_logging_config())
