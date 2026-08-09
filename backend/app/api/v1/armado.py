"""Endpoints del armado asistido — F-019, Tanda 10.

`POST /armado` precarga una cartera de arranque a partir del mandato del cliente: monto, moneda de
referencia, objetivo de cobertura, perfil y horizonte. Es el punto de partida, no un resultado
final — el asesor la sigue editando a mano en `CarteraEditable` (F-018).

## Por qué el universo que entra a `armar()` no es `saneado.especies` tal cual

El plan de la feature ilustraba el endpoint pasando `saneado.especies` directo a `armar()`. Eso
divergía de dos cosas a la vez y se corrigió acá:

1. **El motor arma con `dedup=True`.** `tools/armar_cartera.py::cargar_universo` lo dice en su
   propio docstring: *"el armador necesita deduplicar (comprar MR46O y MR46D es comprar el mismo
   bono dos veces creyendo que se diversifica)"*. `saneado.especies` es la vista viva —una fila por
   especie de liquidación—, y proponer sus tres especies como si fueran tres candidatos distintos
   infla la diversificación exactamente del modo que esa línea describe. `UniversoDeduplicado.
   colapsado()` es, en palabras de su propio docstring, "la vista del armador": una fila por
   emisión. Es la que se usa acá, igual que ya la usa `calendario_del_universo` (F-015) para el
   mismo propósito (elegir qué comprar).
2. **El motor filtra por `filtrar_operables` antes de proponer un candidato**: rendimiento
   publicado, precio publicado, sin problema de sanidad. Es un filtro que no depende del segmento,
   así que aplicarlo acá una sola vez (en vez de adentro de `candidatos_del_segmento`, una vez por
   cada uno de los ~6 segmentos) da el mismo resultado final con menos trabajo repetido.

La consecuencia práctica de las dos correcciones es la que hace pasar la paridad de
`tests/test_armado_paridad_motor.py` contra `tools/armar_cartera.py::armar()`, que arma siempre
sobre el universo deduplicado y operable.

## Por qué `origen_mix` y las alertas de `resolver_mix`/`filtrar_por_moneda` se agregan con
## `replace`

La firma de `armar()` no recibe `origen_mix` -- lo produce un paso antes, `resolver_mix`, y
`armar()` no tiene forma de reconstruirlo sin duplicar esa lógica. Se arma el resultado sin esa
parte y se completa con `dataclasses.replace`, el mismo patrón que ya usa
`evaluar_concentracion` en `app/concentracion/servicio.py` para juntar el veredicto con sus
advertencias.
"""

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.armado.motor import armar, filtrar_por_moneda, resolver_mix
from app.armado.parametros import ParametrosArmado
from app.concentracion.perfiles import PERFILES
from app.concentracion.riesgo import derivar_riesgo
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/armado", tags=["armado"])


@router.post(
    "",
    summary="Precarga una cartera de arranque a partir del mandato del cliente",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def armado_asistido(
    conn: Annotated[object, Depends(get_db)],
    entrada: ParametrosArmado,
) -> dict[str, object]:
    """Arma una cartera de arranque, editable después posición por posición.

    **Siempre 200**, igual que `/concentracion`: una cartera parcial, o una que no llega al
    `min_sectores` del perfil, es un resultado válido del dominio y no un error del pedido — se
    declara con una alerta, nunca se rellena con otra naturaleza para completar el mix o el mínimo
    (regla 1 del dominio).

    El único 422 es cuando el mix pedido no tiene ningún segmento en la moneda pedida
    (`--moneda usd` sobre un mix 100% en pesos, por ejemplo): eso sí es un pedido mal formado, no
    un hecho de la cartera.
    """
    saneado = await sanear_universo(conn)
    descartados = saneado.sanidad.descartados
    universo = [
        especie
        for especie in saneado.emisiones().colapsado()
        if especie.rendimiento is not None
        and especie.precio is not None
        and especie.ticker not in descartados
    ]
    riesgos = derivar_riesgo(saneado.especies)

    mix, origen_mix, alertas_mix = resolver_mix(entrada)
    try:
        mix, alertas_moneda = filtrar_por_moneda(mix, entrada.moneda)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    resultado = armar(universo, mix, PERFILES[entrada.perfil], entrada.perfil, entrada, riesgos)
    resultado = replace(
        resultado,
        origen_mix=origen_mix,
        alertas=[*alertas_mix, *alertas_moneda, *resultado.alertas],
    )
    return resultado.como_dict()
