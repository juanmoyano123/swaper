"""El calendario de cobros como servicio: la matemática de `tools/cupones.py` portada al backend.

**El calendario de cupones es criterio de armado, no reporte.** Es la regla 5 del proyecto: *"la
predecibilidad del cashflow es la piedra fundamental sobre la que fomentamos la inversión en
bonos"*. Por eso esta grilla no se calcula en cada pantalla que la necesite — la calculan acá F-016
(la grilla-selector), F-021 (el panel de renta de una cartera) y F-036, las tres sobre la misma
estructura, para que no puedan diferir en qué mes queda descubierto.

El backend **no importa de `tools/`**: la matemática se copia con su docstring citando el origen, y
`tests/test_calendario_paridad_motor.py` la corre contra el motor sobre el mismo cronograma
versionado para que las dos copias no diverjan en silencio. Es el mismo arreglo que F-010 y F-011.

## La forma del paquete

    lectura.py    la tabla `cashflow` y la paridad de la vista `resumen`. Sólo SQL.
    cupones.py valor técnico, intereses corridos y flujos como fracción del monto invertido. Puro.
    grilla.py     el reparto en los doce meses que vienen, con sus totales. Puro.
    alertas.py    qué instrumento quedó afuera y por qué, con nombre y apellido.
    servicio.py   la corrida: leer, cruzar y armar. → `Calendario`.

## Las tres cosas que este paquete no negocia

1. **Renta y amortización no se suman, en ningún nivel.** Cobrar amortización no es renta: es la
   devolución del capital. No existe un campo que los junte.
2. **Los doce meses están siempre**, con cero explícito donde no se cobra. El mes vacío es
   justamente el que hay que ver, y una fila ausente se lee como si el mes no existiera.
3. **Nada se compara ni se suma entre monedas.** Los `pct` son adimensionales; la plata aparece al
   multiplicar por el monto de una posición y queda en la moneda de esa posición, así que los
   totales del mes vienen abiertos por moneda de cobro y nunca sumados.

## El cruce por raíz de emisión

El cronograma indexa una sola especie por emisión (RUCEO, no RUCED), así que se lo busca por raíz.
**Es un lookup y nunca genera un ticker**: si la raíz no encuentra cronograma, el instrumento queda
fuera del calendario y sale nombrado en una alerta. Ver `cupones.py`, que lo explica con el
antecedente que puso esa regla.
"""

from app.calendario.cupones import (
    Cronograma,
    FlujoPorPeso,
    Flujos,
    Pago,
    flujos_por_peso,
    indexar_cronograma,
    indexar_paridades,
    valor_tecnico,
)
from app.calendario.grilla import (
    HORIZONTE_MESES,
    Calendario,
    InstrumentoDelMes,
    MesDelCalendario,
    armar_calendario,
    ventana,
)
from app.calendario.servicio import calendario_de_cartera, calendario_del_universo

__all__ = [
    "HORIZONTE_MESES",
    "Calendario",
    "Cronograma",
    "FlujoPorPeso",
    "Flujos",
    "InstrumentoDelMes",
    "MesDelCalendario",
    "Pago",
    "armar_calendario",
    "calendario_de_cartera",
    "calendario_del_universo",
    "flujos_por_peso",
    "indexar_cronograma",
    "indexar_paridades",
    "valor_tecnico",
    "ventana",
]
