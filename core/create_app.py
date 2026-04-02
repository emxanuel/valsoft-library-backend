from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logging import setup_logging
from core.config import settings
from features.auth.routes import auth_router
from features.books.routes import books_router
from features.clients.routes import clients_router
from features.loans.routes import loans_router
from middlewares.exception_handler import exception_handler_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield
    logging.info("Shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
    )
    app.middleware("http")(exception_handler_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router, prefix="/auth")
    app.include_router(books_router, prefix="/library")
    app.include_router(loans_router, prefix="/library")
    app.include_router(clients_router, prefix="/library")
    return app