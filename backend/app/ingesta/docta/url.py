"""Arma la URL efectiva del feed de cashflow: configurada → expandida → con ventana móvil.

`pydantic-settings` **no** expande `${VAR}` dentro de un valor de `.env` — a diferencia del parser
casero de `tools/consolidar_universo.py`, que sí lo hacía. Los links de Docta se guardan en `.env`
con el placeholder literal `${DOCTA_API_TOKEN}` (así los pega Docta Terminal), así que sin esta
expansión explícita el request saldría con el placeholder crudo en la query string y la fuente
respondería token inválido — un fallo indistinguible de un token realmente vencido, y mucho más
difícil de diagnosticar.
"""

import re
from datetime import date, timedelta

PLACEHOLDER_TOKEN = "${DOCTA_API_TOKEN}"

DIAS_VENTANA_POR_DEFECTO = 15
"""Constante medida en el motor: una ventana amplia absorbe la inestabilidad errática de la serie
(la misma consulta que devuelve 0 filas trae 1.660 segundos después)."""


class ConfiguracionFaltante(Exception):
    """Falta una variable de entorno sin la que no se puede intentar la corrida.

    Nombra la variable tal como se escribe en `.env`, con el mismo espíritu que
    `app.core.config`: un servicio a medio configurar falla nombrando lo que falta, no adivinando.
    """

    def __init__(self, variable: str):
        super().__init__(f"Falta configurar {variable}.")
        self.variable = variable


def url_efectiva(
    url_configurada: str | None,
    token: str | None,
    *,
    dias_ventana: int = DIAS_VENTANA_POR_DEFECTO,
) -> str:
    """La URL con la que efectivamente se llama a Docta: sin placeholder y con `fromDate` fresco."""
    if not url_configurada:
        raise ConfiguracionFaltante("DOCTA_CASHFLOW_URL")
    expandida = _expandir_token(url_configurada, token)
    return url_con_ventana_movil(expandida, dias=dias_ventana)


def _expandir_token(url: str, token: str | None) -> str:
    if PLACEHOLDER_TOKEN not in url:
        return url
    if not token:
        raise ConfiguracionFaltante("DOCTA_API_TOKEN")
    return url.replace(PLACEHOLDER_TOKEN, token)


def url_con_ventana_movil(url: str, dias: int = DIAS_VENTANA_POR_DEFECTO) -> str:
    """Reescribe `fromDate` a `hoy - dias`.

    El link que genera Docta Terminal trae `fromDate` hardcodeado a la fecha del día en que se
    generó. Con el correr de los días esa fecha queda vieja y el endpoint empieza a devolver 0
    filas **sin ningún error** — el pipeline se rompía en silencio. Por eso la única fecha de esta
    función es relativa al momento de la corrida (`date.today()`); no hay ninguna fecha fija en el
    código, que es exactamente el criterio de aceptación (GWT-4).

    Si la URL no trae `fromDate=` se devuelve intacta: no todos los links de Docta lo llevan.
    """
    if "fromDate=" not in url:
        return url
    desde = (date.today() - timedelta(days=dias)).strftime("%Y-%m-%d")
    return re.sub(r"fromDate=[^&]*", f"fromDate={desde}", url)
