"""Endpoint de salud: lo sondean la plataforma de hosting y el HEALTHCHECK del contenedor."""

from datetime import datetime
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import get_db_optional
from app.db.health import check_database, get_last_snapshot

logger = structlog.get_logger()

router = APIRouter(tags=["salud"])

AVISO_BASE_CAIDA = "No hay conexión con PostgreSQL: el servicio no puede leer ni escribir datos."


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "error"]
    last_market_snapshot_at: datetime | None = None
    warnings: list[str] = []


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Estado del servicio y del dato de mercado",
    responses={503: {"model": HealthResponse, "description": "La base de datos no responde"}},
)
async def health(conn: Annotated[Any | None, Depends(get_db_optional)]) -> Any:
    if conn is None:
        return _base_caida()

    try:
        await check_database(conn)
        ultimo_snapshot, avisos = await get_last_snapshot(conn)
    except Exception as exc:
        logger.warning("health_db_error", error=str(exc), error_type=type(exc).__name__)
        return _base_caida()

    return HealthResponse(
        status="ok",
        database="ok",
        last_market_snapshot_at=ultimo_snapshot,
        warnings=avisos,
    )


def _base_caida() -> JSONResponse:
    # 503 y no 200: es la señal que mira la plataforma para no rutear tráfico a esta instancia.
    return JSONResponse(
        status_code=503,
        content=HealthResponse(
            status="error",
            database="error",
            last_market_snapshot_at=None,
            warnings=[AVISO_BASE_CAIDA],
        ).model_dump(mode="json"),
    )
