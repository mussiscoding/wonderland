import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(level=logging.INFO)

from app.database import init_db
from app.routes import auth, artists, events, genres

app = FastAPI(title="wonderland")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(auth.router)
app.include_router(artists.router)
app.include_router(events.router)
app.include_router(genres.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def home():
    return RedirectResponse("/artists")
