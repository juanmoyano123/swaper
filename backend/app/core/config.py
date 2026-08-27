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

    # F-057 — la planilla diaria de CAFCI (fondos comunes de inversión). API pública sin token que
    # siempre devuelve el último día hábil: no hay parámetro de fecha que pedir (verificado el
    # 23/08/2026 contra `?fecha=`, `?date=`, `?f=`, `?tipo=`). Con esto en `False` la corrida
    # matinal no la pide y el segmento FCI del monitor queda vacío, declarado: una fuente apagada
    # se nombra, no se disimula con un panel que parece completo.
    cafci_habilitado: bool = False
    cafci_url: str = "https://api.pub.cafci.org.ar/pb_get"

    # **El consumo de la CNV está pausado por default (F-072, 17/08/2026).** Documentos filed por
    # un emisor —prospectos, suplementos, avisos— vía HTML servido, y el PDF real vía el
    # intercambio de dos pasos con `blob.cnv.gov.ar` (`app/externos/cnv.py`). En `False` el bloque
    # llega pausado, sin pegarle a la red, y el frontend no distingue ese caso de un fallo real.
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
    # 20 y no 15: es exactamente la demora que la API abierta declara (`byma_demora_minutos`).
    # Refrescar cada 15 pedía tres veces por hora un dato que se renueva dos veces y media: una de
    # cada seis corridas traía lo mismo que la anterior. Alinear los dos números hace que cada
    # corrida traiga una foto nueva del mercado. Decisión del dueño del producto, 23/08/2026.
    ingesta_refresh_minutos: int = 20
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
    # una vez con `tools/curar_emisores_cuit.py`, contra el listado oficial de emisoras de la CNV
    # más su buscador). A diferencia de `condiciones_csv`, cubre parcialmente el universo de ONs a
    # propósito — 105 nombres de emisor, 80 CUITs distintos, que resuelven 277 de las 373 emisiones
    # ON al 17/08/2026 — y eso está bien: lo que no está resuelto se declara, no bloquea la feature.
    # El grueso de lo que falta no es del puente sino de más arriba: 89 emisiones no tienen emisor
    # declarado en ninguna fuente, así que no hay nombre con el cual buscar un CUIT.
    emisores_cuit_csv: str = "data/emisores_cuit.csv"

    # F-072 — el otro puente al CUIT, el fuerte: raíz de emisión -> CUIT, curado desde la tabla de
    # valuación de Bienes Personales de ARCA con `tools/curar_emisores_arca.py`. La clave es el
    # código de especie y no el nombre, así que resuelve también las emisiones que no traen emisor
    # declarado en ninguna fuente: 233 de las 373 emisiones ON al 18/08/2026, 38 de ellas sin
    # emisor. El endpoint lo consulta primero y cae al de por nombre cuando no está — la tabla
    # valúa al 31/12 y no puede traer una emisión que salió a cotizar después.
    emisores_arca_csv: str = "data/emisores_arca.csv"

    # F-057 — el puente codigo_cnv -> id interno de la CNV, para linkear desde la ficha de un FCI a
    # su "COMPOSICIÓN DE CARTERA" pública (artículo 34). Igual criterio que `emisores_cuit_csv`:
    # dato curado, versionado, sin fuente de origen viva por request (se cura una vez con
    # `tools/curar_fci_cnv.py`, matcheando por nombre normalizado la planilla de CAFCI contra el
    # listado de fondos de la CNV). Cubre 922 de 1.197 fondos padre al 23/08/2026 — lo que no está
    # resuelto se declara sin enlace, no bloquea la ficha.
    fci_cnv_csv: str = "data/fci_cnv_ids.csv"

    # F-010 no declara settings a propósito. Los topes de sanidad (300 % hard-dollar, 100 % de tasa
    # real CER, 500 % de TNA nominal) y el umbral de discordancia entre especies son criterio de
    # dominio verificado, no configuración: hacerlos ajustables por entorno invitaría a subirlos
    # cuando descarten algo molesto, y lo que descartan es dato roto.

    # Tanda 3 — el secreto con el que un cron externo dispara los jobs de ingesta. Hasta el
    # 26/08/2026 `POST /api/v1/jobs/*` y `POST /api/v1/consolidar` estaban abiertos a internet:
    # cualquiera podía forzar una corrida completa contra BYMA y escribir en la base.
    #
    # **Opcional a propósito, con el camino cerrado cuando falta.** Sin la variable, el camino
    # "token de cron" queda deshabilitado entero —nunca se compara contra vacío ni contra None— y
    # los endpoints sólo se abren con sesión de asesor. Hacerla obligatoria obligaría a inventar
    # un default, que sería un secreto conocido; y rompería el desarrollo local y los tests sin
    # ganar nada. Con este diseño, un deploy al que se le olvidó la variable queda cerrado, no
    # abierto: el peor caso es que el cron no pueda disparar, no que pueda disparar cualquiera.
    cron_secret: str | None = None

    log_level: str = "INFO"
    environment: str = "development"

    # CORS: qué orígenes pueden llamar al backend desde un navegador. Lista separada por comas,
    # se sobreescribe por env si aparece un dominio nuevo.
    #
    # En el deploy actual de Vercel esto no se ejercita: los rewrites de `vercel.json` sirven el
    # frontend y el backend bajo el mismo host, así que las llamadas son same-origin y el browser
    # ni manda `Origin`. El dominio está igual en la lista porque el día que el backend se mude a
    # otro host —el escenario para el que este middleware existe— el default tiene que ser el
    # correcto y no el de un deploy anterior: hasta el 26/08/2026 acá figuraba sólo Netlify, que
    # habría bloqueado el 100 % de las requests sin que nadie lo notara hasta ese momento.
    cors_origins: str = (
        "http://localhost:5173,https://swaper-snowy.vercel.app,https://swappt.netlify.app"
    )


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
