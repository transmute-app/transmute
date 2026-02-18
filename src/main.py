from fastapi import FastAPI
from api import router
import uvicorn

if __name__ == "__main__":
    app = FastAPI()
    app.include_router(router)
    uvicorn.run(app, host="0.0.0.0", port=3313)
