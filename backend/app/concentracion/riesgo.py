"""De qué crédito es cada especie: grupo de emisor y clave de riesgo — F-020.

Portado de `tools/segmentos.py:354-388`, donde el motor deriva las mismas tres columnas
(`grupo_emisor`, `es_soberano`, `clave_riesgo`) para poder controlar la concentración.

## El grupo de emisor es el prefijo de tres letras del ticker, y no otra cosa

Es la parte del port que más invita a "mejorarla", así que queda escrito por qué las dos
alternativas obvias son peores:

- **La raíz de emisión (F-011) separa emisiones, no emisores.** YMCHO e YMCIO son dos ONs de YPF:
  agrupar por raíz las contaría como dos créditos distintos y **subestimaría** la concentración,
  que es exactamente el error contra el que existe este módulo.
- **El nombre del emisor crudo tiene 261 grafías distintas** del mismo nombre en la fuente.
  Agrupar por string obligaría a decidir si "S.A." y "S.A.U." son la misma empresa, y esa decisión
  sería un dato inventado con forma de heurística (regla 1 del dominio).

El prefijo está validado sobre los casos que sí traen nombre: **119 grupos, sin colisiones**. El
nombre del emisor se usa **sólo para mostrar**, igual que en el motor.

## `SOBERANO_AR` es la regla 4 del dominio

El Tesoro emite bajo muchos prefijos —GD, AE, DIC, TZX, TY3— y todos son el mismo crédito. La clave
de riesgo los junta a todos bajo `SOBERANO_AR` y ese agregado se mide contra `max_soberano`, no
contra el tope corporativo. Sin esta separación una cartera 100 % soberana pasaba como
diversificada.

## Lo único del motor que este port NO copia: la propagación de sector

`tools/segmentos.py:370-381` rellena el sector faltante con la moda del sector dentro del grupo de
emisor. Acá no. El backend ya decidió lo contrario en F-017: el docstring de
`EspecieUniverso.sector` dice que a un sector no informado "no se le asigna uno por parecido con
otro emisor" — y la ficha de F-020 lo repite para la distribución: *"sector no informado, nunca
repartido"*. Es una divergencia
deliberada contra el original y está declarada en el docstring de
`tests/test_concentracion_paridad_motor.py`, con el mismo criterio con el que
`tests/test_universo_paridad_motor.py` declara el suyo.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.concentracion.perfiles import NOMBRE_SOBERANO, SOBERANO_AR
from app.universo.segmentacion import EspecieUniverso

# Cuántos caracteres del ticker identifican al emisor. Ver el docstring del módulo.
LARGO_GRUPO_EMISOR = 3

# La clase de activo que el universo le pone a lo que emite el Tesoro.
CLASE_SOBERANA = "bono_soberano"


def grupo_emisor(ticker: str) -> str:
    """El prefijo que identifica al emisor. Portado tal cual: `ticker[:3]`."""
    return ticker[:LARGO_GRUPO_EMISOR]


def es_soberano(clase_activo: str) -> bool:
    return clase_activo == CLASE_SOBERANA


def clave_riesgo(ticker: str, clase_activo: str) -> str:
    """Contra qué tope se mide esta especie. Regla 4 del dominio: el Tesoro es una sola clave."""
    return SOBERANO_AR if es_soberano(clase_activo) else grupo_emisor(ticker)


@dataclass(frozen=True, slots=True)
class RiesgoDeEspecie:
    """A qué crédito pertenece una especie, con el nombre que se muestra por ese crédito."""

    ticker: str
    grupo_emisor: str
    es_soberano: bool
    clave_riesgo: str
    """`SOBERANO_AR` o el grupo de emisor. Es la clave por la que se acumula el peso."""

    nombre: str
    """Cómo se llama ese crédito en pantalla. Nunca participa de ningún cálculo."""


def derivar_riesgo(especies: Sequence[EspecieUniverso]) -> dict[str, RiesgoDeEspecie]:
    """La clave de riesgo de cada especie del universo, indexada por ticker.

    El **nombre** de un grupo corporativo sale del emisor de sus especies, y cuando ninguna lo trae
    queda `(sin identificar: XXX)` con el prefijo a la vista: el tope se sigue aplicando igual —el
    crédito existe aunque no sepamos cómo se llama— y quien lea la advertencia puede ir a buscar de
    quién es ese prefijo. Es lo mismo que hace el motor con su `fillna`.

    Entre varias grafías del mismo emisor se toma **la primera en orden de ticker**, que es una
    regla de desempate y no un criterio: no hay forma de saber cuál de "YPF S.A." e "YPF SA" es la
    correcta, y elegir por frecuencia —lo que hace el motor— tampoco lo averigua. Que sea
    determinístico es lo que importa: la misma cartera muestra siempre el mismo nombre.
    """
    nombres: dict[str, str] = {}
    for especie in sorted(especies, key=lambda e: e.ticker):
        grupo = grupo_emisor(especie.ticker)
        if especie.emisor is not None and grupo not in nombres:
            nombres[grupo] = especie.emisor

    riesgos: dict[str, RiesgoDeEspecie] = {}
    for especie in especies:
        grupo = grupo_emisor(especie.ticker)
        soberano = es_soberano(especie.clase_activo)
        riesgos[especie.ticker] = RiesgoDeEspecie(
            ticker=especie.ticker,
            grupo_emisor=grupo,
            es_soberano=soberano,
            clave_riesgo=SOBERANO_AR if soberano else grupo,
            nombre=(
                NOMBRE_SOBERANO
                if soberano
                else nombres.get(grupo, f"(sin identificar: {grupo})")
            ),
        )
    return riesgos
