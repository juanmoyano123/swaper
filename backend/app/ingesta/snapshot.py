"""El resultado de una corrida de ingesta, con todo lo que hace falta para saber si sirve.

Un snapshot no es sólo "los datos que trajimos". Es también cuándo se capturaron, cuán viejos son en
origen, cuántas filas vino cada tramo, qué campos quedaron incompletos y qué falló. Sin eso, mirar
una tabla de precios no permite distinguir un mercado sin operaciones de una ingesta que se cortó a
la mitad.

La demora declarada es un atributo del snapshot y no una nota al pie: la API abierta de BYMA publica
con veinte minutos de retraso, y un precio de hace veinte minutos presentado como "el precio de
ahora" es un dato mal etiquetado.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.ingesta.alertas import Alerta, Severidad
from app.ingesta.cobertura import Cobertura


def _ahora() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Snapshot:
    """Lo que una fuente entregó en una corrida.

    Se construye vacío al empezar y se va llenando: así, si la corrida se corta por la mitad, lo que
    quedó registrado hasta ahí sigue siendo cierto.
    """

    fuente: str
    """Nombre de la fuente tal como se le muestra a una persona: "BYMA", "IAMC", "data912"."""

    capturado_en: datetime = field(default_factory=_ahora)
    """Cuándo corrió la ingesta. No es cuándo se generó el dato en origen."""

    demora_declarada_minutos: int = 0
    """Cuánto atrasa la fuente respecto del mercado, según la propia fuente."""

    filas_por_tramo: dict[str, int] = field(default_factory=dict)
    """Filas efectivamente traídas por endpoint, sección o pestaña. El criterio de aceptación de
    F-004 pide que este conteo quede registrado, y es lo que delata una página que no se pidió."""

    alertas: list[Alerta] = field(default_factory=list)
    cobertura: list[Cobertura] = field(default_factory=list)

    def registrar_tramo(self, nombre: str, filas: int) -> None:
        self.filas_por_tramo[nombre] = filas

    def alertar(self, alerta: Alerta) -> None:
        self.alertas.append(alerta)

    @property
    def total_filas(self) -> int:
        return sum(self.filas_por_tramo.values())

    @property
    def hubo_errores(self) -> bool:
        return any(a.severidad is Severidad.ERROR for a in self.alertas)

    @property
    def completo(self) -> bool:
        """Trajo algo y nada falló. Una corrida incompleta se usa igual, pero se declara."""
        return self.total_filas > 0 and not self.hubo_errores

    @property
    def dato_valido_hasta(self) -> datetime:
        """Hasta qué momento del mercado refleja este snapshot, descontando la demora de origen."""
        from datetime import timedelta

        return self.capturado_en - timedelta(minutes=self.demora_declarada_minutos)

    def como_dict(self) -> dict[str, object]:
        """Forma serializable, que es la que consumen la API y el log."""
        return {
            "fuente": self.fuente,
            "capturado_en": self.capturado_en.isoformat(),
            "demora_declarada_minutos": self.demora_declarada_minutos,
            "dato_valido_hasta": self.dato_valido_hasta.isoformat(),
            "filas_por_tramo": dict(self.filas_por_tramo),
            "total_filas": self.total_filas,
            "completo": self.completo,
            "alertas": [a.como_dict() for a in self.alertas],
            "cobertura": [c.como_dict() for c in self.cobertura],
        }
