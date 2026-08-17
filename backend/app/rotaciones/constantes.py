"""Los parámetros del motor, portados de `tools/detectar_swaps.py` con su porqué — F-032.

Esta tanda no expone ningún flag de `detectar_swaps.py` como parámetro del endpoint (la ficha lo
dice explícito): los defaults del CLI quedan fijos acá como constantes de módulo, y lo único que
varía por corrida es lo que ya deriva del perfil —`percentil_liquidez` y `tope_distress`—, que es
lo que `ParametrosRotacion` carga.
"""

from dataclasses import dataclass
from typing import Literal

from app.concentracion.perfiles import PERFILES

NombreDePerfil = Literal["conservador", "moderado", "agresivo"]

MIN_DTIR = 0.005  # 0.5 pp — CLI --min-dtir default
MAX_MAS_DURACION = 1.5  # años — CLI --max-mas-duration default
UMBRAL_NEUTRO = -0.003  # -0.3 pp — CLI --umbral-neutro default
FACTOR_VOLUMEN = 3.0  # CLI --factor-volumen default
TOP_N = 3  # CLI --top-n default, por tipo
PERCENTIL_DISTRESS = 95  # CLI --percentil-distress default
MIN_OPERABLES_PERCENTIL = 10  # con menos, el percentil no dice nada
BANDA_RENDIMIENTO_PP = 0.5  # para ordenar destinos parejos
TOL_DURACION_LEY = 0.25  # años, para emparejar ley local vs extranjera
MIN_REND = 0.0  # CLI --min-rend default
DIAS_CUPON = 45  # CLI --dias-cupon default
ESCENARIOS_TIR: tuple[float, ...] = (-0.05, -0.04, -0.03, -0.02, -0.01, 0.0, 0.01, 0.02)

# Costo real de rotar — F-035.
# Parámetro asumido del motor, no un dato de mercado ni publicado por el bróker: es el default que
# ya traía `tools/detectar_swaps.py` (`--arancel`), sin una fuente que lo declare. El frontend lo
# rotula "estimado" (ver `NotaCosto` en `compartidos.tsx`) para no presentarlo como una medición.
ARANCEL_POR_PATA = 0.0075  # 0,75% en fracción — CLI --arancel default (0.75/100)
UMBRAL_COSTO_ELEVADO = 0.05  # 5% — GWT-2 de F-035: por encima de esto, la propuesta queda marcada
MAX_RELACION_PUNTAS = 3.0  # ver tools/mercado.py: bid/ask con esta relación son escalas distintas,
# no un spread real (caso observado: bid 125 / ask 127.000)

TOPE_DISTRESS_DEFAULT: dict[str, float] = {"usd_hard": 0.15}

# La fuente publica dos leyes y el CHECK de `instrumentos.law` (`mercado.sql`) sólo admite esas
# dos: "Ley Argentina" y "Ley N.Y." — el mismo vocabulario cerrado que `LEYES_VALIDAS` en
# `condiciones/semilla.py`. "Extranjera" y "Ley Europea" venían de un archivo cargado a mano de
# `tools/detectar_swaps.py`, previo al pipeline curado actual: ninguna de las dos puede llegar a
# `EspecieUniverso.ley` hoy (relevamiento de confiabilidad de datos, 16/08/2026 — verificado contra
# `data/condiciones_emision.csv`, cero ocurrencias). Se sacan del set en vez de quedar como una
# rama que nunca se ejecuta y que alguien podría leer como vigente.
LEY_LOCAL = "Ley Argentina"
LEYES_EXTRANJERAS = frozenset({"Ley N.Y."})


def es_extranjera(ley: str | None) -> bool:
    return str(ley) in LEYES_EXTRANJERAS


@dataclass(frozen=True, slots=True)
class ParametrosRotacion:
    """Los parámetros del motor para una corrida, derivados del perfil (D6 del plan de la tanda).

    `PERFILES["moderado"]` trae `percentil_liquidez=25`, `tope_rend_usd=0.15` — exactamente los
    defaults del CLI (`--percentil-liquidez 25`, `usd_hard: 0.15`). Es lo que hace gratis la
    paridad con perfil moderado en el test.
    """

    percentil_liquidez: float
    tope_distress: dict[str, float]

    @classmethod
    def de_perfil(cls, nombre: NombreDePerfil) -> "ParametrosRotacion":
        perfil = PERFILES[nombre]
        return cls(
            percentil_liquidez=float(perfil["percentil_liquidez"]),
            tope_distress={**TOPE_DISTRESS_DEFAULT, "usd_hard": perfil["tope_rend_usd"]},
        )
