"""Cliente del feed de cashflow de Docta — F-006.

Único consumo de Docta que queda en el producto: el cronograma completo de pagos futuros por
ticker, con separación de interés y capital. F-006 trae y normaliza; F-007 (consolidador) es quien
persiste — ver el docstring de `ResultadoCashflow` para el contrato exacto entre las dos.
"""

from app.ingesta.docta.ingesta import ResultadoCashflow, ingerir_cashflow
from app.ingesta.docta.url import ConfiguracionFaltante

__all__ = ["ConfiguracionFaltante", "ResultadoCashflow", "ingerir_cashflow"]
