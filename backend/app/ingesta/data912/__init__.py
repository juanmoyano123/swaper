"""Cliente de data912.com — experimento de fuente primaria de precios, con BYMA de respaldo.

Superficie pública del paquete: `ingerir_live()` para correr la ingesta de los cinco tramos y
`ResultadoLive` para tipar lo que devuelve. `cliente.py` y `normalizacion.py` son detalle interno
que `consolidacion/overlay.py` no debería importar directamente.
"""

from app.ingesta.data912.ingesta import ResultadoLive, ingerir_live

__all__ = ["ResultadoLive", "ingerir_live"]
