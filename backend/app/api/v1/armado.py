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

## Por qué la composición renta fija + renta variable vive acá y no en el motor

`armar()` es el port de `tools/armar_cartera.py::armar()` y `test_armado_paridad_motor.py` lo
mantiene bit a bit igual a la CLI -- meterle renta variable adentro le habría hecho perder esa
paridad, o habría obligado a duplicar la función para las dos formas de llamarla. En cambio, el
bloque de renta variable se arma aparte (`app.armado.renta_variable.armar_renta_variable`, sobre
`EspecieRentaVariable`, que ni siquiera es del mismo tipo que `EspecieUniverso`) y acá se
reparten los cupos: `pct_rv` de la cartera para renta variable, el resto para `armar()`, que arma
sobre `n_rf = n_total - n_rv` posiciones en vez de `n_total`. `armar()` sigue sin saber que la
renta variable existe.

`pct_rv` explícito pisa el default del perfil (`PCT_RV_PERFIL`); si no se manda, moderado y
agresivo arman con renta variable aunque el pedido no la nombre -- son los números del Excel de
referencia del IFA, no un capricho de este endpoint.

**`moneda` no filtra la renta variable.** El parámetro decide en qué moneda *cobra* el segmento de
renta fija (regla 3: precio y volumen de cada especie ya vienen en su propia moneda de cotización,
y filtrar por moneda ahí tiene sentido porque los segmentos de renta fija están clasificados por
en qué moneda paga el cupón). La renta variable no tiene esa clasificación -- una acción en pesos y
un CEDEAR en dólares compiten en el mismo ranking de liquidez, ya llevado a dólares por
`saneado.cambio` -- así que `moneda` no la toca.

**Los topes de renta variable se resuelven acá, no adentro del armado** (F-078). `topes_del_perfil`
elige entre lo que mandó el pedido y el default del perfil, exactamente como estas mismas líneas ya
resuelven `pct_rv` contra `PCT_RV_PERFIL`. `armar_renta_variable` recibe topes, no perfiles: no
tiene por qué saber qué perfil pidió la cartera, y así el mismo bloque se puede armar desde un test
o desde `tools/` sin arrastrar la tabla de perfiles. **Cambia lo que el endpoint propone**: un
pedido sin `topes_rv` que antes armaba sin ninguna restricción ahora arma con los del perfil.

**Si la renta variable queda vacía, la renta fija no se reescala.** `armar()` ya devuelve su
resultado sumando 100% con lo que pudo cubrir (regla 1: cartera parcial, nunca se rellena con otra
naturaleza), así que si `armar_renta_variable` no encuentra candidatos la cartera queda sumando
100% igual, `pct_rv_aplicado` sale en `0` y la alerta `rv_sin_candidatos` explica por qué. La
alternativa -- reescalar la renta fija a 100% *de nuevo*, ahora sobre `n_rf` posiciones en vez de
`n_total` -- exigiría rearmar con más candidatos que `armar()` nunca buscó, y esta feature no lo
hace: se declara la posición parcial en vez de fingir que nunca se reservó cupo para renta
variable.
"""

from dataclasses import replace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.armado.motor import (
    PosicionArmada,
    ResultadoArmado,
    armar,
    filtrar_por_moneda,
    resolver_mix,
)
from app.armado.parametros import ParametrosArmado
from app.armado.renta_variable import PCT_RV_PERFIL, topes_del_perfil
from app.armado.renta_variable import armar_renta_variable as seleccionar_renta_variable
from app.concentracion.perfiles import PERFILES
from app.concentracion.riesgo import derivar_riesgo
from app.ingesta.alertas import Alerta
from app.renta_variable import armar_renta_variable as construir_especies_rv
from app.renta_variable import leer_geografia_etfs, leer_paises, leer_renta_variable
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

    # Cuánto de la cartera pedida va a renta variable, y cuántas posiciones le tocan a cada bloque.
    # `pct_rv=0` (o sin candidatos de renta variable) no dispara ninguna consulta nueva: es el caso
    # que tiene que reproducir el comportamiento de antes de esta feature bit a bit.
    pct_rv_efectivo = (
        entrada.pct_rv if entrada.pct_rv is not None else PCT_RV_PERFIL[entrada.perfil]
    )
    n_rv = max(1, round(entrada.n_total * pct_rv_efectivo / 100)) if pct_rv_efectivo > 0 else 0
    n_rf = entrada.n_total - n_rv

    if n_rf > 0:
        entrada_rf = entrada.model_copy(update={"n_total": n_rf})
        resultado = armar(
            universo, mix, PERFILES[entrada.perfil], entrada.perfil, entrada_rf, riesgos
        )
    else:
        # Todo el cupo se lo llevó renta variable (`pct_rv` pedido en 100): no hay nada que armar()
        # tenga que resolver, y llamarlo con `n_total=0` lo haría igual buscar una posición por
        # segmento (`max(1, ...)` en `armar()`), que no es lo que pide este caso límite.
        resultado = ResultadoArmado(
            posiciones=[],
            alertas=[],
            mix_aplicado=mix,
            origen_mix="",
            perfil=entrada.perfil,
            sectores_presentes=0,
            min_sectores=PERFILES[entrada.perfil]["min_sectores"],
        )

    posiciones_rv: list[PosicionArmada] = []
    alertas_rv: list[Alerta] = []
    if n_rv > 0:
        filas_rv = await leer_renta_variable(conn)
        # El curado de países, para que los topes de país y región tengan qué medir: sin esto
        # `pais` sale `None` en todo el bloque, los dos ejes caen por "categoría faltante no
        # computa" y el armador declararía `rv_tope_sin_dato_en_eje` para siempre, aun con el CSV
        # ya sembrado. Va acá adentro y no arriba porque con `pct_rv=0` no hay renta variable que
        # armar y el endpoint tiene que seguir haciendo una sola consulta.
        paises = await leer_paises(conn)
        # Mismo criterio para la geografía de ETFs (F-079, D3): tabla chica, join por papel en
        # Python, y sin ella los campos `etf_*` quedan declarados faltantes en vez de romper nada.
        geografia_etfs = await leer_geografia_etfs(conn)
        # Sólo CEDEARs (14/08/2026): las acciones argentinas dejaron de ser descubribles desde el
        # picker del armador manual, y el armado automático no puede sugerir algo que el asesor no
        # puede ni buscar. La ingesta y la clasificación de acciones siguen igual — este filtro es
        # sólo del armado, no del universo (ver `app/renta_variable/lectura.py`, sin cambios).
        especies_rv = [
            e
            for e in construir_especies_rv(filas_rv, saneado.cambio, paises, geografia_etfs)
            if e.clase_activo == "cedear"
        ]
        posiciones_rv, alertas_rv = seleccionar_renta_variable(
            especies_rv,
            pct_rv=pct_rv_efectivo,
            n_rv=n_rv,
            monto_total=entrada.monto,
            rubro_rv=entrada.rubro_rv,
            # Los topes del perfil aplican solos cuando el pedido no los trae -- misma resolución
            # que `pct_rv_efectivo` unas líneas más arriba y por la misma razón: no hay número que
            # signifique "usá el default", así que la ausencia es la señal (F-078).
            topes_rv=topes_del_perfil(entrada.perfil, entrada.topes_rv),
            filtro_rv=entrada.filtro_rv,
        )

    # Sin candidatos de renta variable la cartera queda sumando 100% con lo que armó armar() --
    # ver "Si la renta variable queda vacía..." en el docstring del módulo.
    posiciones_rf = resultado.posiciones
    pct_rv_aplicado = 0.0
    if posiciones_rv:
        pct_rv_aplicado = pct_rv_efectivo
        factor_rf = (100 - pct_rv_aplicado) / 100
        posiciones_rf = [
            replace(p, pct_cartera=p.pct_cartera * factor_rf, monto=p.monto * factor_rf)
            for p in posiciones_rf
        ]

    resultado = replace(
        resultado,
        posiciones=[*posiciones_rf, *posiciones_rv],
        origen_mix=origen_mix,
        alertas=[*alertas_mix, *alertas_moneda, *resultado.alertas, *alertas_rv],
        pct_rv_aplicado=pct_rv_aplicado,
    )
    return resultado.como_dict()
