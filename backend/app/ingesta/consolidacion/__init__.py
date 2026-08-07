"""F-007 · El consolidador multi-fuente: las tres fuentes se vuelven el universo del producto.

Superficie pública mínima a propósito. `consolidar` es la corrida completa (fuentes + armado +
escritura) y es lo que F-008 va a orquestar; `armar_consolidacion` es la parte pura, expuesta
porque es donde vive toda la lógica de precedencia y es lo que hay que poder probar sin base.
`raiz_emision` la necesita cualquier feature que cruce especies de la misma emisión.
"""

from app.ingesta.consolidacion.armado import Consolidacion, armar_consolidacion
from app.ingesta.consolidacion.corrida import ResultadoConsolidacion, consolidar
from app.ingesta.raiz import raiz_emision

__all__ = [
    "Consolidacion",
    "ResultadoConsolidacion",
    "armar_consolidacion",
    "consolidar",
    "raiz_emision",
]
