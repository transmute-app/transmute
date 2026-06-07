from contextlib import asynccontextmanager
import logging
import re
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.openapi.utils import get_openapi
from textwrap import dedent
from api import router
from api.routes.oidc import attach_session_middleware
from core import build_logging_config, configure_logging, get_settings
from background import (
    get_conversion_worker_manager_thread,
    get_upload_cleanup_thread,
    recover_running_jobs,
)
import uvicorn

logger = logging.getLogger(__name__)


def render_index_html(raw_html: str, root_path: str) -> str:
    """Inject the runtime sub-path into the SPA shell's <base> tag and
    window.__BASE_PATH__ placeholder (both no-ops when root_path is empty)."""
    base_href = f"{root_path}/" if root_path else "/"
    html = re.sub(
        r'<base\s+href="[^"]*"\s*/?>',
        f'<base href="{base_href}" />',
        raw_html,
        count=1,
    )
    html = re.sub(
        r'window\.__BASE_PATH__\s*=\s*"[^"]*"',
        f'window.__BASE_PATH__ = "{root_path}"',
        html,
        count=1,
    )
    return html


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

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Mark any jobs that were `running` when the previous process died
        # as stale so they can be retried from scratch.
        recover_running_jobs()
        # Start the conversion queue manager (daemon thread). It lazily starts
        # worker threads only when queued jobs exist, up to the configured
        # concurrency limit.
        worker_manager = get_conversion_worker_manager_thread()
        worker_manager.start()
        yield
        # Daemon threads exit with the process; nothing to clean up here.

    app = FastAPI(
        title=f"{settings.app_name} API",
        description=build_api_description(settings.app_name),
        version=f"{settings.app_version}",
        servers=[{"url": settings.api_server_url, "description": f"{settings.app_name} API server"}],
        docs_url=None,
        redoc_url=None,
        redirect_slashes=True,
        # Fixes OpenAPI/docs/url_for URLs under a reverse-proxy sub-path ("" = root).
        root_path=settings.root_path,
        # We already advertise the full URL via `servers`, so skip the
        # auto-added relative root_path entry to avoid a duplicate.
        root_path_in_servers=False,
        lifespan=lifespan,
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

        # Template the SPA shell once with the runtime sub-path.
        index_file = web_dir / "index.html"
        index_html = (
            render_index_html(index_file.read_text(encoding="utf-8"), settings.root_path)
            if index_file.exists()
            else None
        )

        # Catch-all route for SPA - serves index.html for non-API routes
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(request: Request, path: str):
            requested_file = (web_dir / path).resolve()
            if requested_file.is_file() and requested_file.is_relative_to(web_dir.resolve()):
                return FileResponse(requested_file)

            if index_html is not None:
                return HTMLResponse(index_html)
            raise HTTPException(status_code=404, detail="SPA index not found")

    return app


def run_api_server(app: FastAPI, settings) -> None:
    if settings.has_host_override_conflict():
        logger.warning("Both host and hosts are configured. Using hosts and ignoring host.")

    uvicorn.run(
        app,
        host=settings.resolved_bind_host(),
        port=settings.port,
        log_config=build_logging_config(),
    )


if __name__ == "__main__":
    settings = get_settings()
    app = create_app()
    cleanup_thread = get_upload_cleanup_thread()
    cleanup_thread.start()
    run_api_server(app, settings)
