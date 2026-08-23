"""El bloque de renta variable del armado asistido — Tanda de composición RF+RV.

**Por qué es un módulo aparte y no vive dentro de `motor.py`.** El motor arma sobre
`EspecieUniverso`, que no puede representar una acción (`.naturaleza` busca el segmento en
`NATURALEZA_TASA` y una acción no tiene ninguno — ver `app/universo/segmentacion.py`). La renta
variable tiene su propio tipo, `EspecieRentaVariable`, sin rendimiento por diseño (regla 2 del
dominio: una acción no tiene TIR), así que arma con otro criterio: no hay banda de rendimiento que
ordenar, hay liquidez que rankear. `armar_renta_variable()` de acá es la contraparte de
`armar()` de `motor.py` para ese otro universo, y el endpoint (`app/api/v1/armado.py`) es quien
compone los dos resultados en una sola cartera — ver el docstring de ese módulo para el porqué de
que la composición viva ahí y no acá.

## De dónde salen los porcentajes por perfil

`PCT_RV_PERFIL` sale de `referencia/carteras-sugeridas-ifa.xlsx`, el Excel de referencia del IFA:
la cartera conservadora no lleva renta variable, la moderada lleva un cuarto del libro y la
agresiva es mayoritariamente renta variable. Son los mismos tres perfiles que ya usa
`app.concentracion.perfiles.PERFILES`, y `pct_rv` en `ParametrosArmado` puede pisarlos: el default
es una guía, no una regla del dominio.

## El algoritmo, en orden

1. `pct_rv <= 0` o `n_rv <= 0`: no hay bloque de renta variable que armar.
2. Se descartan las especies sin `volumen_usd` medible — sin liquidez comparable no hay con qué
   rankear, y no se le asume cero: es la regla 1 del dominio, no se completa un dato que falta.
3. Con temática activa (`rubro_rv`), se filtra por **igualdad exacta** contra `sic_oficina`, el
   rubro tal como lo nombra la SEC (regla 11: no se traduce ni se normaliza el nombre de la
   fuente). Una especie sin rubro conocido no puede afirmarse que pertenece a la temática, así que
   con temática activa queda afuera — sin temática, en cambio, sí participa del ranking general.
4. Orden determinístico: `volumen_usd` descendente, empate por `ticker` ascendente.
5. Selección greedy en dos pasadas: la primera reparte por rubro todavía no representado (un
   rubro `None` nunca cuenta como rubro nuevo), la segunda completa con lo que quede en el mismo
   orden. Si no alcanza para `n_rv`, se arma con lo que hay — no se rellena con otra naturaleza.
6. Si terminó eligiendo especies y **ninguna** tiene rubro informado, se declara que no se pudo
   diversificar por rubro.
7. Si no quedó ningún candidato tras los filtros, se declara y el bloque vuelve vacío.
8. Equiponderación dentro del bloque: cada posición pesa `pct_rv / len(elegidas)` del total de la
   cartera, y su monto sale de aplicar ese peso a `monto_total` — mismo patrón que usa `armar()` en
   `motor.py` para las posiciones de renta fija.
"""

from collections.abc import Sequence

from app.armado.motor import PosicionArmada
from app.ingesta.alertas import Alerta, Severidad
from app.renta_variable.especies import EspecieRentaVariable

# Ver el punto "De dónde salen los porcentajes por perfil" en el docstring del módulo.
PCT_RV_PERFIL: dict[str, float] = {
    "conservador": 0.0,
    "moderado": 25.0,
    "agresivo": 60.0,
}

CODIGO_RV_SIN_VOLUMEN_USD = "rv_sin_volumen_usd"
CODIGO_RV_SIN_PERFIL_SECTORIAL = "rv_sin_perfil_sectorial"
"""Es la llave con la que el frontend reconoce la alerta: renombrarla la rompería sin cambiar lo
que significa."""
CODIGO_RV_SIN_CANDIDATOS = "rv_sin_candidatos"


def _alerta(codigo: str, mensaje: str, **detalle: object) -> Alerta:
    """Mismo contrato que `app.armado.motor._alerta`: informa, no bloquea."""
    return Alerta(
        codigo=codigo,
        mensaje=mensaje,
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle=detalle,
    )


def armar_renta_variable(
    especies: Sequence[EspecieRentaVariable],
    *,
    pct_rv: float,
    n_rv: int,
    monto_total: float,
    rubro_rv: str | None = None,
) -> tuple[list[PosicionArmada], list[Alerta]]:
    """El bloque de renta variable de la cartera, seleccionado por liquidez y diversificado por
    rubro cuando el dato está. Ver el docstring del módulo por el algoritmo completo."""
    if pct_rv <= 0 or n_rv <= 0:
        return [], []

    alertas: list[Alerta] = []

    con_volumen = [e for e in especies if e.volumen_usd is not None]
    descartadas = len(especies) - len(con_volumen)
    if descartadas > 0:
        alertas.append(
            _alerta(
                CODIGO_RV_SIN_VOLUMEN_USD,
                f"{descartadas} especie(s) de renta variable no tienen volumen en dólares "
                "medible y se descartan del ranking de liquidez.",
                cantidad=descartadas,
            )
        )

    universo = con_volumen
    if rubro_rv is not None:
        universo = [e for e in universo if e.sic_oficina == rubro_rv]

    if not universo:
        alertas.append(
            _alerta(
                CODIGO_RV_SIN_CANDIDATOS,
                f"No hay especies de renta variable candidatas para el bloque de {pct_rv:g}%"
                + (f" en el rubro {rubro_rv}" if rubro_rv is not None else "")
                + ": la cartera queda sin renta variable.",
                pct_rv=pct_rv,
                rubro_rv=rubro_rv,
            )
        )
        return [], alertas

    ordenadas = sorted(universo, key=lambda e: (-(e.volumen_usd or 0.0), e.ticker))

    elegidas: list[EspecieRentaVariable] = []
    rubros_presentes: set[str] = set()
    for especie in ordenadas:
        if len(elegidas) >= n_rv:
            break
        if especie.sic_oficina is not None and especie.sic_oficina not in rubros_presentes:
            elegidas.append(especie)
            rubros_presentes.add(especie.sic_oficina)

    if len(elegidas) < n_rv:
        elegidas_tk = {e.ticker for e in elegidas}
        for especie in ordenadas:
            if len(elegidas) >= n_rv:
                break
            if especie.ticker in elegidas_tk:
                continue
            elegidas.append(especie)
            elegidas_tk.add(especie.ticker)

    if all(e.sic_oficina is None for e in elegidas):
        alertas.append(
            _alerta(
                CODIGO_RV_SIN_PERFIL_SECTORIAL,
                "Ninguna de las especies elegidas para renta variable tiene rubro informado: "
                "no se pudo diversificar por rubro dentro del bloque.",
                cantidad=len(elegidas),
            )
        )

    peso_posicion = pct_rv / len(elegidas)
    posiciones = [
        PosicionArmada(
            ticker=especie.ticker,
            pct_cartera=peso_posicion,
            monto=peso_posicion / 100 * monto_total,
            clase="renta_variable",
        )
        for especie in elegidas
    ]
    return posiciones, alertas
