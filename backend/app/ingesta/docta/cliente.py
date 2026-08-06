"""Baja el Excel del feed de cashflow y lo parsea: una sola operación reintentable.

`pedir()` de la base común ya traduce lo que puede salir mal a nivel HTTP (timeouts, status,
credencial vencida) a `ErrorDeFuente` / `CredencialVencida`. Lo que agrega este módulo son los dos
fallos que sólo se ven *después* de que el HTTP salió bien, y que el motor viejo tuvo que aprender
a mano: un cuerpo con status 200 que no es un Excel válido (pasó como HTML de error) y un Excel
válido con cero filas (la inestabilidad errática medida del feed — la misma consulta que devuelve
vacío trae 1.660 segundos después). Las dos se tratan como `ErrorDeFuente` reintentable, para que
`con_reintentos` las cubra igual que a un fallo de transporte.
"""

import io
import logging

import httpx
import pandas as pd

from app.ingesta.http import ErrorDeFuente, pedir

FUENTE = "Docta cash-flow"

# httpx tiene su propio log ("HTTP Request: GET <url> ...") a nivel INFO, por fuera de structlog
# y sin pasar por el redactor de secretos del logger del proyecto. Para cualquier otra fuente eso
# es ruido; para Docta es una fuga: la URL lleva el token embebido en la query string. Subir el
# nivel acá es la única forma de garantizar la regla "la URL nunca se loguea" sin tocar la
# política de logging compartida (`app/core/logging.py`), que no la contempla.
logging.getLogger("httpx").setLevel(logging.WARNING)


async def bajar_cashflow(cliente: httpx.AsyncClient, url: str) -> pd.DataFrame:
    """Un intento de bajar y parsear el Excel de cashflow. Se le pasa a `con_reintentos`."""
    respuesta = await pedir(cliente, "GET", url, fuente=FUENTE)

    try:
        hojas = pd.read_excel(io.BytesIO(respuesta.content), sheet_name=None)
    except Exception as exc:
        raise ErrorDeFuente(
            f"la respuesta de {FUENTE} no es un Excel válido ({exc.__class__.__name__})"
        ) from exc

    primera_hoja = next(iter(hojas.values()), None)
    if primera_hoja is None or len(primera_hoja) == 0:
        raise ErrorDeFuente(f"{FUENTE} devolvió cero filas")

    return primera_hoja
