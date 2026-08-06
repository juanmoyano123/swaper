"""La emisión decide, no la especie: herencia entre especies y conflictos. Función pura.

AL30, AL30D y AL30C son el mismo bono. La ley bajo la que se emitió, la moneda en la que paga, la
lámina mínima, la calificación, el sector y el emisor son atributos de **la emisión**, así que si
una especie los declara valen para las tres. El precio, la TIR y la moneda de cotización no se
tocan acá: ésos sí son de cada especie.

Conserva la semántica de `tools/merge_condiciones.py`, que hacía las dos cosas sobre un CSV. El
backend no importa de `tools/`: la lógica está portada, no reutilizada.

**El orden entre herencia y conflicto, que es la pregunta de fondo.** Un valor heredado no puede
entrar en conflicto con su propia fuente, y acá esa pregunta directamente no llega a existir,
porque las dos operaciones no se encadenan: son dos ramas de una única resolución por (emisión,
campo). Se juntan los valores **declarados** —los que vinieron del artefacto curado, nunca los
heredados— y se mira cuántos distintos hay:

- **más de uno → conflicto.** Se vacían todos, se reporta con los valores en pugna, y no se hereda
  nada: una emisión que no sabe cuál es su lámina no tiene ninguna para prestarle a sus especies.
- **exactamente uno → ése es el valor de la emisión.** Las especies que no lo declaran lo heredan.
- **ninguno → no hay nada que hacer.**

Invertir el orden —heredar primero y buscar conflictos después— obligaría a elegir qué valor
propagar antes de saber si hay uno solo, que es justamente lo que el sistema no hace nunca. El
vocabulario cerrado se aplica antes que todo esto, en `semilla.py`: un valor que el proyecto no
maneja no es un valor, no se hereda y tampoco es parte de un conflicto.

**El sistema no elige. Nunca.** No hay precedencia entre fuentes, no gana el más reciente y no hay
desempate. Elegir requeriría un criterio que nadie estableció, y aplicarlo por cuenta propia sería
presentar una preferencia inventada como si fuera el dato.

**Quién figura como donante en `herencia de X`.** El ticker igual a la raíz si declara el valor, y
si no el primero en orden alfabético entre los que lo declaran. Todos declaran lo mismo —si no,
sería conflicto—, así que la elección no cambia el valor: cambia el rótulo, y el rótulo tiene que
nombrar a alguien que efectivamente lo declare. **La fecha del valor heredado es la del donante**,
no la de hoy: el heredero no sabe más de lo que sabía quien se lo prestó.

**Se hereda por raíz de emisión y por nada más.** Se midió sobre el CSV real: propagar `sector`
por emisor además de por raíz no completa ni una celda más, y `lamina`, `calificacion`, `ley` y
`moneda_pago` por emisor entrarían en conflicto en decenas de emisores, porque un emisor tiene
varias emisiones y no comparten lámina ni calificación. Herencia por emisor sería inventar.

**Dos valores se comparan como llegan.** Después del strip de la lectura, "Servicios" y "servicios"
son distintos y por lo tanto son un conflicto. Unificarlos por mayúsculas obligaría a elegir cuál
de las dos grafías se guarda, que es la decisión que este módulo tiene prohibida.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.condiciones.semilla import CAMPOS, Condiciones, Valor
from app.ingesta.alertas import Alerta, condiciones_en_conflicto
from app.ingesta.consolidacion import raiz_emision

PREFIJO_HERENCIA = "herencia de"


@dataclass(frozen=True, slots=True)
class Conflicto:
    """Dos especies de la misma emisión declarando lo que no puede ser distinto.

    Se guardan los dos valores en pugna con el ticker que los declara: sin eso el reporte diría
    que algo está mal sin decir qué hay que mirar, y esto se resuelve a mano o no se resuelve.
    """

    campo: str
    raiz: str
    valores: dict[str, object]

    def como_dict(self) -> dict[str, object]:
        return {
            "campo": self.campo,
            "emision": self.raiz,
            "valores": {ticker: valor for ticker, valor in sorted(self.valores.items())},
        }


@dataclass(frozen=True, slots=True)
class Resolucion:
    """Las filas ya resueltas y la cuenta de qué le pasó a cada campo."""

    filas: list[Condiciones] = field(default_factory=list)
    conflictos: list[Conflicto] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    heredados_por_campo: dict[str, int] = field(default_factory=dict)
    vaciados_por_campo: dict[str, int] = field(default_factory=dict)


def resolver(filas: Sequence[Condiciones]) -> Resolucion:
    """Resuelve cada campo a nivel de emisión y devuelve las filas con la herencia aplicada.

    No modifica lo que recibe: las filas de entrada siguen declarando lo que declaraban, que es lo
    que hace que la resolución sea reejecutable y que un test pueda comparar antes contra después.
    """
    valores: dict[str, dict[str, Valor]] = {fila.ticker: dict(fila.valores) for fila in filas}

    por_raiz: dict[str, list[str]] = defaultdict(list)
    for ticker in valores:
        por_raiz[raiz_emision(ticker)].append(ticker)

    conflictos: list[Conflicto] = []
    alertas: list[Alerta] = []
    heredados = dict.fromkeys(CAMPOS, 0)
    vaciados = dict.fromkeys(CAMPOS, 0)

    for raiz in sorted(por_raiz):
        # Orden estable: el donante de la herencia no puede depender del orden del archivo.
        tickers = sorted(por_raiz[raiz])
        for campo in CAMPOS:
            declarados = {
                ticker: valores[ticker][campo] for ticker in tickers if campo in valores[ticker]
            }
            if not declarados:
                continue

            distintos = {declarado.valor for declarado in declarados.values()}
            if len(distintos) > 1:
                en_pugna: dict[str, object] = {
                    ticker: declarado.valor for ticker, declarado in declarados.items()
                }
                conflictos.append(Conflicto(campo=campo, raiz=raiz, valores=en_pugna))
                alertas.append(condiciones_en_conflicto(campo, raiz, en_pugna))
                for ticker in declarados:
                    del valores[ticker][campo]
                vaciados[campo] += len(declarados)
                continue

            donante = raiz if raiz in declarados else min(declarados)
            fuente = declarados[donante]
            for ticker in tickers:
                if campo in valores[ticker]:
                    continue
                valores[ticker][campo] = Valor(
                    valor=fuente.valor,
                    origen=f"{PREFIJO_HERENCIA} {donante}",
                    fecha=fuente.fecha,
                )
                heredados[campo] += 1

    return Resolucion(
        filas=[Condiciones(ticker=fila.ticker, valores=valores[fila.ticker]) for fila in filas],
        conflictos=conflictos,
        alertas=alertas,
        heredados_por_campo=heredados,
        vaciados_por_campo=vaciados,
    )
