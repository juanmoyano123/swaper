"""De qué crédito es cada especie, para el swap — port de `preparar_universo` — F-032.

`clave_emisor_swap` reusa `derivar_riesgo` (`app.concentracion.riesgo`), que ya agrupa por prefijo
de ticker y junta todo el Tesoro bajo `SOBERANO_AR`. Lo único que este módulo agrega es la
separación del Bopreal: lo emite el BCRA, no el Tesoro, y para "mismo emisor" en un swap
Tesoro→Bopreal es un cambio de emisor aunque los dos compartan `clase_activo='bono_soberano'`
(la misma clase que hace que F-020 los cuente juntos bajo `SOBERANO_AR` en concentración — esa
decisión no se toca acá, es otro eje). Derivarlo del prefijo del ticker sería la inferencia que la
regla 1 del dominio prohíbe; `tipo_tasa` es un dato declarado por la fuente.
"""

from collections.abc import Mapping

from app.concentracion.perfiles import SOBERANO_AR
from app.concentracion.riesgo import RiesgoDeEspecie
from app.universo.segmentacion import EspecieUniverso

CLAVE_BCRA = "BCRA"


def clave_emisor_swap(especie: EspecieUniverso, riesgos: Mapping[str, RiesgoDeEspecie]) -> str:
    """`'BCRA'` si `especie.tipo_tasa == 'bopreal'`, si no la `clave_riesgo` de `derivar_riesgo`."""
    if especie.tipo_tasa == "bopreal":
        return CLAVE_BCRA
    return riesgos[especie.ticker].clave_riesgo


def nombre_emisor(especie: EspecieUniverso, clave: str) -> str:
    """El nombre para mostrar, cuando `especie.emisor` es `None` (los soberanos nunca lo traen)."""
    if especie.emisor is not None:
        return especie.emisor
    if clave == SOBERANO_AR:
        return "Gobierno Argentino"
    if clave == CLAVE_BCRA:
        return "BCRA"
    return f"(sin identificar: {clave})"
