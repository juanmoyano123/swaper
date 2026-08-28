"""Pool de conexiones a PostgreSQL, creado una vez al arrancar y compartido por todo el servicio.

Que la base esté caída no impide arrancar: es una condición operativa, no de configuración. El
servicio levanta, `/health` responde 503 y la plataforma reintenta. El arranque sólo falla
ruidosamente cuando falta configuración (ver `app.core.config`).
"""

import asyncpg
import structlog

from app.core.config import Settings

logger = structlog.get_logger()

# DATABASE_URL apunta al Session pooler de Supabase (puerto 5432), que es compatible con IPv4 y
# soporta sentencias preparadas. Si alguna vez se pasa al Transaction pooler (6543, pgbouncer en
# modo transacción), asyncpg necesita statement_cache_size=0 o falla con sentencias ya preparadas.
CONNECT_TIMEOUT_S = 10.0
COMMAND_TIMEOUT_S = 30.0


async def create_pool(settings: Settings) -> asyncpg.Pool | None:
    """Crea el pool. Devuelve None si la base no responde, sin tumbar el arranque."""
    try:
        pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            # El Session pooler admite 15 clientes en total y cada instancia del backend arma su
            # propio pool: con max_size=10, dos instancias (un deploy de Vercel escalado, o uno
            # local de prueba) alcanzan para agotar el cupo y el resto de los pedidos muere con
            # 503 — pasó el 28/08/2026 (EMAXCONNSESSION). Con 5, tres instancias conviven y el uso
            # real (un puñado de asesores) no nota la diferencia.
            max_size=5,
            timeout=CONNECT_TIMEOUT_S,
            command_timeout=COMMAND_TIMEOUT_S,
        )
    except Exception as exc:
        logger.error("db_pool_no_disponible", error=str(exc), error_type=type(exc).__name__)
        return None
    logger.info("db_pool_creado")
    return pool


async def close_pool(pool: asyncpg.Pool | None) -> None:
    if pool is not None:
        await pool.close()
        logger.info("db_pool_cerrado")
