"""Bolsar — el emisor de las ONs que la ficha técnica de BYMA no cubre.

Es el **último recurso** del barrido de emisores, y las dos razones por las que nunca es la fuente
primaria están medidas (28/08/2026):

1. **Trunca el nombre a 50 caracteres.** `TRANSPORTADORA DE GAS DEL SUR S.A.` entra entero, pero
   una razón social larga llega cortada, y un nombre cortado rompe cualquier cruce posterior contra
   la CNV —que es por CUIT y razón social exacta—. La ficha de BYMA publica el nombre completo.
2. **Sólo responde por especies con sufijo `O`.** Medido sobre 99 tickers: 50 de 50 de las `O`, 0
   de 49 de las `C`/`D`. Las de liquidación en dólares no tienen página.

**Esto es scraping, no un contrato.** No hay API, no hay versionado y nadie nos avisa si mañana el
HTML cambia de forma: se lee una fila `<th>Emisor</th><th>NOMBRE</th>` de una tabla server-rendered.
Por eso el único modo de fallar es devolver `None`. Nunca se arma un nombre "parcial" con lo que se
haya podido reconocer: un emisor a medias es peor que ninguno, porque se muestra como si fuera el
dato y nadie lo audita.
"""

import re
from html import unescape

import httpx
import structlog

from app.ingesta.http import ErrorDeFuente, pedir

logger = structlog.get_logger()

FUENTE = "Bolsar"

URL_OBLIGACION = "https://bolsar.info/infoObligacion.php"

# La fila de la ficha: dos `<th>` en el mismo `<tr>`, el primero con la etiqueta y el segundo con el
# valor. Los atributos varían (`class="odd"` en las filas impares, `style` en la primera), así que
# se aceptan cualesquiera; lo que se ancla es la etiqueta exacta y que el valor no tenga etiquetas
# adentro. Si el HTML deja de tener esta forma, no coincide y se devuelve `None`, que es
# exactamente lo que tiene que pasar.
_FILA_EMISOR = re.compile(
    r"<tr[^>]*>\s*<th[^>]*>\s*Emisor\s*</th>\s*<th[^>]*>([^<]*)</th>", re.I
)


async def emisor_bolsar(cliente: httpx.AsyncClient, ticker: str) -> str | None:
    """El emisor que Bolsar declara para una ON, o `None` si no lo declara o no se lo pudo leer.

    A diferencia de `app.externos.byma_ficha`, acá **un fallo de la fuente también devuelve
    `None`** en vez de propagarse. Es deliberado y es porque el rol es distinto: éste es el
    fallback del fallback, corre sólo para lo que ya quedó sin emisor, y hacer que una caída de
    Bolsar aborte un barrido que ya trajo cientos de emisores de BYMA sería cambiar mucho por poco.
    Lo que se pierde queda declarado igual: el instrumento se marca como consultado sin emisor y
    vuelve a la cola cuando alguien reabra la pregunta.
    """
    try:
        respuesta = await pedir(
            cliente, "GET", f"{URL_OBLIGACION}?on={ticker}", fuente=FUENTE
        )
    except ErrorDeFuente as exc:
        logger.warning("bolsar_sin_respuesta", ticker=ticker, motivo=exc.motivo)
        return None

    coincidencia = _FILA_EMISOR.search(respuesta.text)
    if coincidencia is None:
        # Incluye el caso normal: Bolsar sirve una página igual para un ticker que no conoce, sólo
        # que sin la fila. No es un error, es que no lo tiene.
        return None

    nombre = unescape(coincidencia.group(1)).strip()
    return nombre or None
