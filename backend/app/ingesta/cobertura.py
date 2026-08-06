"""Cuánto del dato llegó completo, campo por campo.

Es la contracara operativa de la regla del proyecto: un dato que falta se muestra faltante. Para
poder mostrarlo hay que contarlo, y para contarlo hay que medirlo en el momento en que la fuente
entrega —no después, cuando ya se mezcló con otras y no se sabe cuál lo trajo.

La cobertura no es una métrica de calidad para un tablero: es lo que le dice al asesor si puede
confiar en una comparación. Filtrar por calificación cuando sólo el 39 % del universo la tiene
declarada devuelve un resultado que parece completo y no lo es.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Cobertura:
    """Cuántos valores presentes de cuántas filas, para un campo."""

    campo: str
    presentes: int
    total: int

    @property
    def faltantes(self) -> int:
        return self.total - self.presentes

    @property
    def porcentaje(self) -> float:
        """0.0 cuando no hay filas: sin universo no hay cobertura que reportar, y no es 100 %."""
        if self.total == 0:
            return 0.0
        return self.presentes / self.total * 100

    def como_dict(self) -> dict[str, object]:
        return {
            "campo": self.campo,
            "presentes": self.presentes,
            "total": self.total,
            "faltantes": self.faltantes,
            "porcentaje": round(self.porcentaje, 1),
        }


def _esta_presente(valor: object) -> bool:
    """Vacío es faltante, pero cero no.

    Un precio de cero, un cupón de cero y un volumen de cero son datos: dicen algo del instrumento.
    Contarlos como faltantes escondería instrumentos que no operaron, que es justo lo que hay que
    poder ver. La cadena vacía y los espacios sí son ausencia: es como las fuentes escriben "no sé".
    """
    if valor is None:
        return False
    if isinstance(valor, str):
        return valor.strip() != ""
    # NaN de pandas/numpy: distinto de sí mismo, y es como llega un hueco en una planilla.
    return not (isinstance(valor, float) and valor != valor)


def medir_cobertura(
    filas: Iterable[Mapping[str, object]],
    campos: Iterable[str],
) -> list[Cobertura]:
    """Cobertura de cada campo pedido sobre el conjunto de filas.

    Se piden los campos explícitamente en vez de deducirlos de las filas: un campo que ninguna fila
    trae tiene que reportar 0 de N, y si se dedujeran de los datos ese campo simplemente no
    aparecería. Justamente el caso que hay que ver.
    """
    campos = list(campos)
    presentes = dict.fromkeys(campos, 0)
    total = 0

    for fila in filas:
        total += 1
        for campo in campos:
            if _esta_presente(fila.get(campo)):
                presentes[campo] += 1

    return [Cobertura(campo=campo, presentes=presentes[campo], total=total) for campo in campos]
