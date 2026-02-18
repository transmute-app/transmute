from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from api import router
from core import get_settings
import uvicorn

def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    web_dir = get_settings().web_dir
    if web_dir.exists():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=3313)
