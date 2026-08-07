"""Resolver una cartera contra el universo del día, en una sola llamada — F-029.

Es el equivalente de `universo/servicio.py`: junta la capa de lectura con la lógica pura y arma lo
que se reporta. La conexión llega por parámetro y no de `app.state`, igual que allá, para que esto
se pueda invocar fuera del ciclo HTTP.

**El universo llega saneado y en su vista viva.** Saneado porque resolver contra la lectura cruda
haría que una posición quedara vinculada a una especie cuyo precio la sanidad ya descartó sin que
nadie se enterara: acá esa especie resuelve igual —el cliente tiene ese bono— pero viaja marcada
`dato_sano: false`. Vivo, es decir `.especies` y no `.emisiones()`, porque la cartera del cliente
tiene la especie que compró: colapsarla contra el representante de su emisión le diría que tiene un
instrumento distinto del que tiene.

**No se pide el contraste de BYMA.** Es lo único de `sanear_universo` que sale a la red y esto no lo
necesita: resolver un ticker no usa el tipo de cambio. Pedirlo acoplaría el resolver de una cartera
a que una fuente externa esté viva, y `descargar_endpoint` reintenta cinco veces con 90 s de
timeout — un BYMA colgado bloquearía hasta ocho minutos una consulta que es puro SQL.
"""

from collections.abc import Sequence
from typing import Any

import structlog

from app.posiciones.lectura import leer_instrumentos
from app.posiciones.resolucion import (
    CarteraResuelta,
    PosicionDeclarada,
    indexar_instrumentos,
    resolver,
)
from app.universo.servicio import sanear_universo

logger = structlog.get_logger()


async def resolver_cartera(conn: Any, posiciones: Sequence[PosicionDeclarada]) -> CarteraResuelta:
    """Lee el universo y los instrumentos y busca cada ticker declarado. No escribe nada.

    Las dos lecturas van **en serie y no en un `gather`**, aunque no dependan una de la otra: son
    dos consultas sobre la misma conexión, y una conexión de asyncpg no admite dos operaciones a la
    vez —la segunda muere con "another operation is in progress"—. El paralelismo de
    `sanear_universo` funciona porque ahí lo que corre al lado es una llamada HTTP, no otro SQL.

    Es determinística sobre el universo del día: las mismas posiciones sobre la misma corrida de
    ingesta resuelven igual. Nada acá consulta el reloj ni la red.
    """
    saneado = await sanear_universo(conn)
    filas = await leer_instrumentos(conn)
    resultado = resolver(
        posiciones,
        saneado.especies,
        indexar_instrumentos(filas),
        saneado.sanidad.descartados,
    )
    logger.info(
        "cartera_resuelta",
        posiciones=resultado.cobertura.posiciones,
        resueltas=resultado.cobertura.resueltas,
        no_resueltas=resultado.cobertura.no_resueltas,
        porcentaje_no_resuelto=resultado.cobertura.porcentaje_no_resuelto,
        posiciones_sin_monto=resultado.cobertura.posiciones_sin_monto,
        universo=len(saneado.especies),
        # No se loguean los tickers declarados: son la cartera de un cliente y los logs se
        # persisten. Lo que hace falta para diagnosticar es cuántos no resolvieron, no cuáles.
    )
    return resultado
