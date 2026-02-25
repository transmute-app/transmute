from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.openapi.docs import get_redoc_html
from api import router
from core import get_settings
import uvicorn

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{settings.app_name} API",
        description=f"API to interact with {settings.app_name} without the need for a frontend",
        version=f"{settings.app_version}",
        docs_url=None,
        redoc_url=None,
        redirect_slashes=True
    )
    app.include_router(router, prefix="/api")
    web_dir = settings.web_dir
    if web_dir.exists():
        app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")
        app.mount("/icons", StaticFiles(directory=web_dir / "icons"), name="icons")
        
        # Catch-all route for SPA - serves index.html for non-API routes
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(request: Request, path: str):
            # For API routes, redirect if missing trailing slash
            # Required to do this here instead of using redirect_slashes=True on 
            # the router because the SPA catch-all would intercept and return 
            # index.html instead of redirecting
            if path.startswith("api/"):
                # Remove any non alpha or slash characters for security
                safe_path = "".join(c for c in path if c.isalnum() or c in "/")
                if not request.url.path.endswith("/"):
                    return RedirectResponse(url=f"/{safe_path}/", status_code=307)
            
            index_file = web_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            raise HTTPException(status_code=404, detail="SPA index not found")
    
    return app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=3313)
