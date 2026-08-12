"""Las dos cosas que sólo esta feature puede notar — F-013.

Todo lo demás que la barra muestra ya lo alerta quien lo produce: la sanidad nombra sus descartes,
el tipo de cambio declara su muestra, el calendario mide su cobertura. Acá viven únicamente los dos
huecos que **ninguna de esas features puede ver desde adentro**, porque son la ausencia de su propio
insumo: que no haya ninguna corrida registrada, y que no haya un solo precio en la base.

Se codifican como alertas y no como campos vacíos del payload por la regla 1 del proyecto leída al
revés: un faltante que no se alerta se lee como un cero. Una barra que muestra "último refresh: —"
sin decir nada más se interpreta como "todavía no cargó", que es justo lo contrario de lo que pasa.

## Por qué no hay una alerta de "el dato está viejo"

Sería la alerta más obvia de la barra y **no existe a propósito**. Decir que un snapshot está viejo
exige un umbral, y fijar ese umbral es decidir cuánta desactualización es aceptable para operar —
una decisión de dominio que nadie tomó, y que además depende de si la rueda está abierta, de qué
instrumento se mire y de para qué se lo mire. Es el mismo criterio que `cobertura_del_calendario`
explica en F-015: el número va crudo, con la hora exacta y la demora declarada de la fuente al lado,
y la decisión la toma quien la lee. La barra informa la edad del dato; no la juzga.
"""

from app.ingesta.alertas import Alerta, Severidad

CODIGO_SIN_CORRIDA = "sin_corrida_registrada"
CODIGO_SIN_DATO_DE_MERCADO = "sin_dato_de_mercado"


def sin_corrida_registrada() -> Alerta:
    """No hay ni una fila en `corridas_ingesta`: nada de lo que se ve tiene traza de origen.

    **No dice que el dato falte.** Puede haber precios cargados por otro camino —una consolidación
    disparada a mano antes de que F-008 existiera, o una carga directa— y de hecho eso es lo que
    pasa hoy contra la base real: `precios` tiene datos del 06/08/2026 y `corridas_ingesta` está
    vacía. Lo que falta es poder decir de qué corrida salieron, cuánto tardó, qué fuente aportó cada
    fila y qué alertó cada una en el momento de traerla.

    Sale como advertencia y no como error porque el producto funciona igual: lo que no se puede es
    auditar. Presentarlo como error dejaría la barra en rojo permanente en cualquier entorno donde
    el scheduler todavía no esté habilitado, que es el default de `ingesta_habilitada`.
    """
    return Alerta(
        codigo=CODIGO_SIN_CORRIDA,
        mensaje=(
            "No hay ninguna corrida de ingesta registrada: el dato que se está viendo no tiene "
            "traza de qué fuente lo trajo, cuándo ni con qué alertas."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Habilitar el job programado (INGESTA_HABILITADA=true) o disparar una corrida a mano "
            "con POST /api/v1/jobs/corridas/matinal."
        ),
        detalle={},
    )


def sin_dato_de_mercado(motivo: str) -> Alerta:
    """No hay un solo precio del que sacar la hora del snapshot.

    Es error y no advertencia: sin precios no hay universo, no hay rendimiento y no hay nada que
    proponer. El `motivo` viene de `db/health.py`, que ya distingue los tres casos que se ven
    distinto desde acá y se arreglan distinto —la tabla no existe, existe sin la columna, o está
    vacía— y se pasa tal cual en vez de reescribirse: la redacción de allá ya nombra el archivo de
    migraciones que hay que correr.
    """
    return Alerta(
        codigo=CODIGO_SIN_DATO_DE_MERCADO,
        mensaje=motivo,
        severidad=Severidad.ERROR,
        accion_requerida="Correr una ingesta de mercado antes de usar cualquier pantalla.",
        detalle={},
    )
