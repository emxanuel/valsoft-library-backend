from contextlib import asynccontextmanager
import logging

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from core.config import get_settings
from core.logging import AccessLogMiddleware, setup_logging
from database.metrics import register_db_pool_metrics
from features.admin.routes import admin_router
from features.auth.routes import auth_router
from features.books.routes import books_router
from features.clients.routes import clients_router
from features.health.routes import health_router
from features.loans.routes import loans_router
from middlewares.exception_handler import exception_handler_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging()
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT.value,
            traces_sample_rate=0.1,
        )
    if settings.METRICS_ENABLED:
        register_db_pool_metrics()
    yield
    logging.getLogger(__name__).info("Shutting down...")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
    )
    app.middleware("http")(exception_handler_middleware)
    if settings.METRICS_ENABLED:
        Instrumentator(
            excluded_handlers=[r"/health/.*", r"/metrics"],
        ).instrument(app).expose(app, include_in_schema=False)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/auth")
    app.include_router(admin_router, prefix="/admin")
    app.include_router(books_router, prefix="/library")
    app.include_router(loans_router, prefix="/library")
    app.include_router(clients_router, prefix="/library")
    return app
