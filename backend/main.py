from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.openapi.docs import get_redoc_html
from fastapi.openapi.utils import get_openapi
from api import router
from core import get_settings
import uvicorn

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        description=f"API to interact with {settings.app_name} without the need for a frontend",
        version=f"{settings.app_version}",
        servers=[{"url": settings.server_url, "description": f"{settings.app_name} API server"}],
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
        # Explicitly declare no authentication is required.
        # This satisfies OpenAPI linters that require security to be defined
        # at the root level or per-operation.
        schema.setdefault("security", [])
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi

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
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=3313)
