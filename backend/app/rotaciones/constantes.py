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

TOPE_DISTRESS_DEFAULT: dict[str, float] = {"usd_hard": 0.15}

# La fuente publica dos leyes: Argentina y N.Y. En el archivo cargado a mano sobreviven cuatro
# tickers con "Extranjera" y "Ley Europea" de una carga previa; se los cuenta como extranjera
# porque para el tenedor el punto es la jurisdicción (un default se litiga afuera).
LEY_LOCAL = "Ley Argentina"
LEYES_EXTRANJERAS = frozenset({"Ley N.Y.", "Ley Europea", "Extranjera"})


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
