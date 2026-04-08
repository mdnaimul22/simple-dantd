import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.config import settings
from src.api import router

app = FastAPI(title="Dante Management API")

# Add session middleware for simple authentication state and flash messages
app.add_middleware(SessionMiddleware, secret_key=settings.dante_ui_secret)

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Mount static files safely with absolute path
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")

# Include all the web UI and API routing endpoints
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.app_host, port=settings.app_port, reload=True)
