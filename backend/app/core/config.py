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

    # BYMA: la API abierta no lleva token. La base se declara igual para poder apuntar a otro
    # host sin tocar código, y la demora es un dato de la fuente que el snapshot informa.
    byma_base_url: str = "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free"
    byma_demora_minutos: int = 20

    # data912 (experimento): API pública sin auth que arrastra el último cierre conocido aunque
    # la especie no haya operado. No declara demora — la fuente no la publica y no se le inventa
    # una (regla 11) —, así que no hay `data912_demora_minutos`.
    data912_base_url: str = "https://data912.com"

    # IAMC: el informe diario llega por subida manual, no por descarga. Esta ruta es dónde se
    # guardan los que se van subiendo.
    iamc_directorio: str = "fuentes"

    # **El consumo de IAMC está pausado desde el 13/08/2026, y el default es la pausa.** El informe
    # llega a mano: el que estaba cargado en producción era del 05/08 y cada corrida lo volvía a
    # parsear, así que el universo mostraba una TIR de ocho días antes al lado de un precio de hoy
    # y nada lo declaraba —ni `/estado-del-dato` ni la ficha exponen la fecha del informe—. Un dato
    # viejo sin rótulo es peor que un dato ausente: el asesor no tiene cómo saber que lo es.
    #
    # Lo que se pausa es **el consumo**, no el código: el parser, el almacén y `POST /iamc/informe`
    # quedan intactos, y poner esto en True devuelve el comportamiento anterior sin tocar nada más.
    # Se reactiva en Stage 2, cuando la descarga del informe sea automática.
    #
    # Con la pausa activa también se corta el arrastre de las métricas ya guardadas (ver
    # `consolidacion/corrida.py`): sin eso la TIR del último informe seguiría publicándose para
    # siempre, que es exactamente lo que la pausa existe para evitar.
    iamc_habilitado: bool = False

    # **El consumo de Yahoo Finance está pausado desde el 13/08/2026, y el default es la pausa.**
    # Yahoo limita toda esta conexión con HTTP 429 sostenido desde el 08/08 — medido con `curl`
    # puro, fuera de nuestro código: el mismo 429 aparece en el endpoint de cotización, en el de
    # perfil y hasta en el que entrega el crumb sin pedir credencial, sin `Retry-After`. No es una
    # credencial vencida ni un símbolo mal armado, y reintentar no lo destraba.
    #
    # Lo que se pausa es **el consumo**, no el código: el cliente, sus cachés y el job de
    # enriquecimiento quedan intactos, y poner esto en True devuelve el comportamiento anterior sin
    # tocar nada más. Casi todo lo que Yahoo aportaba ya tiene reemplazo propio (nombre, actividad y
    # rubro desde la SEC; apertura/máximo/mínimo/VWAP desde BYMA; el histórico de precios desde
    # data912) — lo que no se reemplaza (PER, valor libro, beta, país, empleados, sitio web) queda
    # declarado ausente en la ficha mientras dure la pausa.
    yahoo_habilitado: bool = False

    # **El consumo de la CNV está pausado por default (F-072, 17/08/2026).** Documentos filed por
    # un emisor —prospectos, suplementos, avisos— vía HTML servido, y el PDF real vía el
    # intercambio de dos pasos con `blob.cnv.gov.ar` (`app/externos/cnv.py`). Mismo criterio que
    # Yahoo: en `False` el bloque llega pausado, sin pegarle a la red, y el frontend no distingue
    # ese caso de un fallo real.
    cnv_habilitado: bool = False

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

    # `precios` y `puntas` tienen PK `(ticker, capturado_en)`, así que cada corrida agregaba una
    # tanda entera en vez de pisar la anterior: ~2.900 filas cada 15 minutos, ~11 MB por día hábil,
    # y nada las borraba. Con esto en False cada corrida deja **una fila por ticker** —la más
    # reciente— y la tabla se estabiliza en el tamaño del universo.
    #
    # En True vuelve el comportamiento original, bit por bit: un snapshot por corrida, con la serie
    # intradiaria reconstruible. Se dejó implementado a pedido del dueño del producto (10/08/2026)
    # porque a futuro puede servir, pero hoy no se usa: la herramienta es para armar carteras
    # —consultar un precio, mirar la TIR, decidir— y no para hacer seguimiento. El único histórico
    # que el producto necesita es el precio al que se armó una cartera, y ese vive en
    # `posiciones.precio_compra`.
    #
    # OJO: esto no es `ingesta_habilitada`. Los precios se siguen actualizando cada 15 minutos; lo
    # que se apaga es la acumulación, no la ingesta.
    serie_historica_habilitada: bool = False

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

    # F-072 — el puente emisor -> CUIT para pedirle documentos a la CNV. Igual criterio que
    # `condiciones_csv`: dato curado, versionado, sin fuente de origen viva por request (se cura
    # una vez con `tools/curar_emisores_cuit.py` contra el buscador de la CNV). A diferencia de
    # `condiciones_csv`, cubre parcialmente el universo de ONs a propósito — 13 de 82 emisores al
    # 17/08/2026 — y eso está bien: lo que no está resuelto se declara, no bloquea la feature.
    emisores_cuit_csv: str = "data/emisores_cuit.csv"

    # F-010 no declara settings a propósito. Los topes de sanidad (300 % hard-dollar, 100 % de tasa
    # real CER, 500 % de TNA nominal) y el umbral de discordancia entre especies son criterio de
    # dominio verificado, no configuración: hacerlos ajustables por entorno invitaría a subirlos
    # cuando descarten algo molesto, y lo que descartan es dato roto.

    log_level: str = "INFO"
    environment: str = "development"

    # CORS: el frontend en Netlify y el navegador local son orígenes distintos del backend
    # (Render, u otro host), así que sin esto el browser bloquea toda request antes de que
    # llegue acá. Lista separada por comas — se sobreescribe por env si el dominio cambia.
    cors_origins: str = "http://localhost:5173,https://swappt.netlify.app"


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
