"""De dónde salen los atributos por especie que el universo comparable no lleva. Sólo SQL.

Misma partición que en `app/universo/`: acá no se decide nada, la lógica que resuelve vive en
`resolucion.py` y se prueba sin levantar Postgres.

## Por qué esta feature lee `instrumentos` y no le alcanza con el universo saneado

Dos cosas que la resolución necesita no están en `EspecieUniverso`:

1. **El plazo de liquidación** (`settlementType` de BYMA). No está en la vista `resumen` ni en el
   universo saneado, igual que pasaba con `moneda_cotizacion` en F-012: F-007 lo escribió en
   `instrumentos` sin tocar el contrato de 21 columnas de la vista.
2. **Los tickers que existen pero quedaron afuera del universo comparable.** Una acción sale antes
   de segmentar y un bono cuyo tipo de tasa no se reconoce sale en `sin_segmento`: ninguno de los
   dos llega a `UniversoSaneado.especies`. Sin esta lectura, un asesor que carga GGAL leería
   "no está en el universo", que es falso — está, y lo que pasa es que no es renta fija comparable.
   Contestar "no existe" sobre algo que sí existe es tan inventado como aproximar un ticker.

Verificado el 07/08/2026 contra la base: `instrumentos` tiene las mismas 2.894 filas que `resumen`
y ninguna fila de más, así que este índice cubre todo el universo y no agrega nada que la vista no
tenga.
"""

from typing import Any

TABLA_INSTRUMENTOS = "public.instrumentos"

# `clase_activo` es lo que distingue una acción de una ON cuando el ticker no llegó al universo
# comparable; `plazo_liquidacion` es el dato que la resolución tiene que declarar por posición.
COLUMNAS: tuple[str, ...] = ("ticker", "clase_activo", "plazo_liquidacion")

SQL_INSTRUMENTOS = f"SELECT {', '.join(COLUMNAS)} FROM {TABLA_INSTRUMENTOS} ORDER BY ticker"


async def leer_instrumentos(conn: Any) -> list[dict[str, Any]]:
    """Todos los instrumentos conocidos, tal como están en la base, sin filtrar ni derivar nada.

    Se trae entera y no por los tickers de la cartera —que serían diez o veinte— porque la tabla
    son ~2.900 filas de tres columnas y una consulta sola es más barata que armar un `IN` con lo
    que escribió el asesor. Además deja el índice completo disponible para contar cuántas
    posiciones cayeron fuera del universo comparable sin una segunda vuelta a la base.
    """
    filas = await conn.fetch(SQL_INSTRUMENTOS)
    return [dict(fila) for fila in filas]
