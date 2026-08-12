"""Punto de entrada del servicio.

Acá sólo se cablea: configuración, logging, ciclo de vida del pool, middleware, handlers de
error y el router de la v1. Toda decisión de comportamiento vive en el módulo que le corresponde.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.db.pool import close_pool, create_pool
from app.jobs.scheduler import Scheduler

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool(app.state.settings)
    # F-008: el scheduler no aborta el arranque si falta pool o si `ingesta_habilitada` es False
    # (el default) — el mismo criterio que el pool mismo, que tampoco tumba el arranque sin base.
    scheduler = Scheduler(app.state.pool, app.state.settings)
    scheduler.iniciar()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        await scheduler.detener()
        await close_pool(app.state.pool)
        app.state.pool = None


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="10-Swaper API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{API_V1_PREFIX}/docs",
        openapi_url=f"{API_V1_PREFIX}/openapi.json",
    )
    app.state.settings = settings
    app.state.pool = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    register_exception_handlers(app)
    app.include_router(v1_router, prefix=API_V1_PREFIX)
    return app


# Si falta configuración obligatoria, get_settings() corta acá: uvicorn muere antes de bindear
# el puerto, en vez de levantar un servicio que responde pero no sirve.
app = create_app()
