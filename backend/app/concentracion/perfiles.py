"""Los tres perfiles de riesgo, portados de `tools/armar_cartera.py:70-81` — F-020.

El backend **no importa de `tools/`**: los números se copian con la razón por la que están
calibrados así, y `tests/test_concentracion_paridad_motor.py` corre las dos implementaciones sobre
la misma cartera para que no diverjan en silencio. Es el mismo arreglo que F-010, F-011 y F-015.

## Se portan los cinco campos, no los tres de concentración

`tope_rend_usd` y `percentil_liquidez` no los usa F-020 y aun así están acá. Son del mismo perfil:
partirlo en dos lugares —los topes acá, los proxies de crédito en el módulo del armado asistido—
haría que alguien pueda cambiar "moderado" en un archivo y no en el otro, y entonces "moderado"
significaría dos cosas distintas según qué pantalla lo mire. F-019 los lee de acá.

El porqué de cada uno, tal como lo escribe el motor:

- **Sin ratings crediticios en la fuente se usan proxies observables.** Un rendimiento muy por
  encima de sus pares en dólares es distress, no oportunidad (`tope_rend_usd`); la liquidez mínima
  se pide por percentil del propio universo (`percentil_liquidez`).
- **`max_emisor` aplica a emisores corporativos.** El soberano tiene tope propio (`max_soberano`)
  porque en el mercado argentino los segmentos en pesos —CER, tasa fija— son casi íntegramente
  soberanos: exigirles el límite corporativo haría inviable cualquier cartera en pesos. El riesgo
  soberano se acota, pero como riesgo país agregado y no como concentración de crédito corporativo.
- **`max_sector` es más laxo que el de emisor** porque un sector agrupa varios emisores y en el
  mercado local O&G concentra el 40 % de las ONs: un tope duro dejaría sin candidatos al segmento
  hard-dollar.

## `min_sectores` es campo nuevo y no viene del motor

El motor no tiene mínimo de diversificación sectorial: acota por arriba y no por abajo. F-020 lo
agrega porque su ficha pide advertir cuando la cartera queda por debajo del mínimo del perfil, y
F-019 lo reusa en la selección.

Los valores —4 / 3 / 2— salen de dos GWT del plan y no de una preferencia: el de F-020 dice que una
cartera con **sólo 2 sectores en perfil moderado** se advierte (⇒ moderado ≥ 3) y el de F-019
menciona un perfil con `min_sectores` = 4, que sólo puede ser el conservador. Agresivo queda en 2:
un mínimo de 1 no sería un mínimo.

Que un mínimo sea *deseable* no lo hace *alcanzable*, y por eso `test_concentracion_perfiles.py` lo
verifica contra el universo real: si algún día el dato curado de sector se achica hasta que no haya
cuatro sectores con emisores operables, el test lo declara en vez de que el conservador empiece a
advertir siempre por una razón que no es la cartera.
"""

from typing import TypedDict

# La clave única bajo la que se agrupa todo el riesgo del Tesoro. Regla 4 del dominio: GD, AE, DIC,
# TZX y TY3 son prefijos distintos del **mismo** crédito, y agruparlos por prefijo dejaba pasar una
# cartera íntegramente soberana como si estuviera diversificada.
SOBERANO_AR = "SOBERANO_AR"

# Cómo se nombra ese riesgo en pantalla. Texto del motor, palabra por palabra: nombrarlo
# "SOBERANO_AR" a secas obligaría al lector a saber que esa clave junta emisiones de cinco prefijos.
NOMBRE_SOBERANO = "Riesgo soberano argentino (todas las emisiones del Tesoro)"

# Sectores que no participan del límite sectorial: el riesgo soberano ya tiene su propio tope y
# meterlo también acá lo acotaría dos veces. **Es la exención del tope, no de la existencia**: un
# soberano sigue contando como sector presente para `min_sectores`.
SECTORES_EXENTOS = frozenset({"Soberano", "Subsoberano"})

# Holgura con la que se compara contra el tope, portada del motor (`pct > tope + 0.01`). Existe
# porque los pesos salen de una reponderación en punto flotante y un exceso de una centésima de
# punto porcentual no es un exceso: es el redondeo.
TOLERANCIA_TOPE = 0.01


class Perfil(TypedDict):
    """Los cinco números que definen un perfil. Ver el docstring del módulo por cada uno."""

    tope_rend_usd: float
    percentil_liquidez: int
    max_emisor: float
    max_soberano: float
    max_sector: float
    min_sectores: int


PERFILES: dict[str, Perfil] = {
    "conservador": {
        "tope_rend_usd": 0.12,
        "percentil_liquidez": 50,
        "max_emisor": 10,
        "max_soberano": 50,
        "max_sector": 30,
        "min_sectores": 4,
    },
    "moderado": {
        "tope_rend_usd": 0.15,
        "percentil_liquidez": 25,
        "max_emisor": 15,
        "max_soberano": 65,
        "max_sector": 40,
        "min_sectores": 3,
    },
    "agresivo": {
        "tope_rend_usd": 0.20,
        "percentil_liquidez": 10,
        "max_emisor": 20,
        "max_soberano": 80,
        "max_sector": 55,
        "min_sectores": 2,
    },
}

NOMBRES_DE_PERFIL = tuple(PERFILES)


def sector_computable(sector: str | None) -> str | None:
    """El sector que participa del límite sectorial, o `None` si no aplica. Portado del motor.

    `None` en los dos casos por los que no se puede acotar: cuando el dato falta —no se acota lo que
    no se conoce, y **no se reparte entre los conocidos** (reglas 1 y 11 del dominio)— y cuando el
    sector ya está acotado por el tope soberano.
    """
    if sector is None or sector in SECTORES_EXENTOS:
        return None
    return sector
