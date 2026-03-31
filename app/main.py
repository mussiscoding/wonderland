import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings

logging.basicConfig(level=logging.INFO)

from app.database import init_db
from app.migration import run_migration
from app.routes import auth, artists, events, genres


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    run_migration()
    yield


app = FastAPI(title="wonderland", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    max_age=14 * 24 * 60 * 60,  # 14 days
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(artists.router)
app.include_router(events.router)
app.include_router(genres.router)


@app.get("/")
def home():
    return RedirectResponse("/artists")
