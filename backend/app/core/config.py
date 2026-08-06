"""Configuración del servicio: todo secreto entra por acá y por ningún otro lado.

El servicio no arranca en modo degradado. Si falta una variable obligatoria, el proceso
muere nombrándola: un backend a medio configurar que igual responde 200 es peor que uno
que no levanta.
"""

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# El .env vive en la raíz del repo, no en backend/. Se resuelve desde la ubicación de este
# archivo y no desde el working directory, que cambia según se arranque con uvicorn, pytest
# o Docker. En el contenedor el archivo no existe y las variables llegan por environment.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Obligatorias. min_length=1 porque el .env.example las trae declaradas y vacías, y una
    # variable presente pero vacía tiene que fallar igual que una ausente.
    supabase_url: str = Field(min_length=1)
    supabase_anon_key: str = Field(min_length=1)
    supabase_service_role_key: str = Field(min_length=1)
    database_url: str = Field(min_length=1)

    # Docta: nombres canónicos desde ya, obligatorias recién en F-006, que es la feature que
    # las consume. Exigir una credencial que el servicio no usa acopla el deploy a config muerta.
    docta_api_token: str | None = None
    docta_cashflow_url: str | None = None
    docta_yield_bonds_url: str | None = None
    docta_serie_precios_url: str | None = None

    # BYMA: la API abierta no lleva token. La base se declara igual para poder apuntar a otro
    # host sin tocar código, y la demora es un dato de la fuente que el snapshot informa.
    byma_base_url: str = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free"
    byma_demora_minutos: int = 20

    # IAMC: el informe diario llega por subida manual, no por descarga. Esta ruta es dónde se
    # guardan los que se van subiendo.
    iamc_directorio: str = "fuentes"

    log_level: str = "INFO"
    environment: str = "development"


def _missing_variable_names(exc: ValidationError) -> list[str]:
    """Nombres de las variables de entorno que provocaron el fallo, como se escriben en .env."""
    return sorted({str(error["loc"][0]).upper() for error in exc.errors() if error["loc"]})


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        nombres = ", ".join(_missing_variable_names(exc))
        # En el contenedor no hay .env —los secretos llegan por environment— y mandar a
        # completar un archivo inexistente es la peor pista posible para un deploy que falla.
        donde = (
            f"Completalas en {ENV_FILE} (ver .env.example)"
            if ENV_FILE.exists()
            else "Definilas como variables de entorno del servicio "
            "(fly secrets set / variables de Railway)"
        )
        print(
            f"FATAL: faltan variables de entorno obligatorias o están vacías: {nombres}. "
            f"{donde} y volvé a arrancar.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
