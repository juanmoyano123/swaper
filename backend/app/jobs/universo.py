"""Lo que el refresh intra-rueda necesita leer del universo ya persistido, para no volver a
consultar IAMC ni Docta.

Dos cosas puntuales:

- **Qué tickers ya están en `instrumentos`.** `precios` tiene FK a `instrumentos` (ver
  `supabase/migrations/20260806151113_mercado.sql`) y un refresh no crea instrumentos nuevos —eso
  es tarea de la corrida matinal—, así que un precio de un ticker que todavía no existe se
  descarta y se declara, en vez de reventar el lote entero.

- **El `type` de cada emisión, tal como quedó del último cronograma persistido.** `public-bonds`
  —soberanos y subsoberanos— sólo se puede clasificar cruzando ese `type` (ver
  `app/ingesta/consolidacion/clasificacion.py`), y sin él `armar_consolidacion` los deja afuera
  del universo entero, puntas incluidas. Leerlo de `cashflow` en vez de volver a pedirlo a Docta es
  lo que permite refrescar soberanos en cada rueda sin tocar la fuente que F-008 tiene prohibido
  volver a consultar.
"""

from typing import Any

SQL_TICKERS_EXISTENTES = "SELECT ticker FROM public.instrumentos"
SQL_TIPOS_CRONOGRAMA = "SELECT DISTINCT ticker, type FROM public.cashflow"


async def leer_tickers_existentes(conn: Any) -> set[str]:
    filas = await conn.fetch(SQL_TICKERS_EXISTENTES)
    return {fila["ticker"] for fila in filas}


async def leer_tipos_cronograma(conn: Any) -> list[dict[str, object]]:
    filas = await conn.fetch(SQL_TIPOS_CRONOGRAMA)
    return [dict(fila) for fila in filas]


def filtrar_precios_al_universo(
    filas_precios: list[dict[str, object]], tickers_existentes: set[str]
) -> tuple[list[dict[str, object]], list[str]]:
    """Separa los precios de tickers que ya están en `instrumentos` de los que todavía no.

    Devuelve `(en_universo, fuera_de_universo)`. Lo segundo no se descarta en silencio: quien
    llama lo convierte en alerta, porque una especie nueva que aparece a mitad de rueda es
    exactamente el tipo de cosa que no puede quedar fuera del registro de la corrida.
    """
    en_universo = [fila for fila in filas_precios if fila["ticker"] in tickers_existentes]
    fuera = sorted(
        fila["ticker"] for fila in filas_precios if fila["ticker"] not in tickers_existentes
    )
    return en_universo, fuera
