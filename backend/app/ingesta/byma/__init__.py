"""Cliente de la API abierta de BYMA — F-004.

Superficie pública del paquete: `ingerir_rueda()` para correr la ingesta de los cinco endpoints y
`ResultadoRueda` para tipar lo que devuelve. Todo lo demás (`cliente.py`, `normalizacion.py`) es
detalle interno que F-007 no debería importar directamente.
"""

from app.ingesta.byma.ingesta import ResultadoRueda, ingerir_rueda

__all__ = ["ResultadoRueda", "ingerir_rueda"]
