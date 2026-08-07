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

    # F-008 — job programado. Los horarios son configurables para poder ejercitar el job en un
    # entorno de prueba sin esperar a la hora real, y para que un cambio de horario de la rueda
    # no sea un cambio de código. `ingesta_habilitada` en False deja el servicio sin scheduler:
    # los tests y el desarrollo local no necesitan que corra solo.
    ingesta_habilitada: bool = False
    ingesta_zona_horaria: str = "America/Argentina/Buenos_Aires"
    # 11:30 y no las 09:00 que traía F-008: **antes de que abra la rueda BYMA no publica precios**.
    # Medido el 07/08/2026 a las 08:00 y 08:15, la fuente devuelve HTTP 200 con `empty: true`, 826
    # acciones sin una sola con precio, y cero bonos y cero CEDEARs. Como la fila de `precios` se
    # inserta igual y la vista `resumen` toma la más reciente, una corrida a esa hora le pisaba el
    # precio de ayer a todo el universo con un vacío.
    #
    # El número sale de dos datos y no de una intuición: la rueda abre 11:00 y la API abierta
    # declara 20 minutos de demora, así que a las 11:30 se ve el mercado de las 11:10, ya operando.
    # A las 11:15 se vería el de las 10:55, que sigue siendo mercado cerrado.
    #
    # Ninguna spec fija esta hora: el plan sólo habla de "la corrida matinal programada".
    ingesta_hora_matinal: str = "11:30"
    ingesta_refresh_minutos: int = 15
    ingesta_rueda_desde: str = "11:00"
    ingesta_rueda_hasta: str = "17:00"

    # F-014 — Supabase Auth no declara settings propios, y eso es un arreglo y no un olvido. El
    # backend valida los JWT contra el JWKS público del proyecto, que cuelga de `supabase_url`:
    # la clave con la que se verifica una firma asimétrica es pública por definición, así que no
    # hay secreto que configurar. Hubo un `SUPABASE_JWT_SECRET` acá mientras la verificación era
    # HS256; ver `app/core/seguridad.py` para por qué ese esquema no validaba ninguna sesión.

    # F-009 — semilla del dato curado. Es una ruta y no un secreto: el archivo está versionado en
    # el repo. Se declara acá porque en el contenedor la raíz del proyecto no está donde el código
    # cree, y porque el CSV no tiene fuente de origen viva —se rescató después de que se borraran
    # los originales—, así que apuntar mal no da un error ruidoso: da una semilla vacía.
    condiciones_csv: str = "data/condiciones_emision.csv"

    # F-010 no declara settings a propósito. Los topes de sanidad (300 % hard-dollar, 100 % de tasa
    # real CER, 500 % de TNA nominal) y el umbral de discordancia entre especies son criterio de
    # dominio verificado, no configuración: hacerlos ajustables por entorno invitaría a subirlos
    # cuando descarten algo molesto, y lo que descartan es dato roto.

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
