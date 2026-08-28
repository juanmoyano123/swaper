"""Guardas sobre la forma de una corrida: lo que la fuente no declara como error y aun así está mal.

**El hallazgo del 28/08/2026.** El endpoint `public-bonds` de BYMA devolvió 5 filas —medido cuatro
veces seguidas, HTTP 200, con `content.total_elements_count = 5`, idéntico con `excludeZeroPxAndQty`
en `true` y en `false`— cuando el día anterior había devuelto 1.116. Nada lo detectó:
`paginacion_incompleta` (`app/ingesta/byma/cliente.py`) compara lo bajado contra el total que **la
propia fuente declara**, y 5 filas contra 5 declaradas cierra perfecto. Una corrida matinal en ese
estado deja todo el universo soberano sin refrescar, en silencio y registrada como `completa`.

El umbral tampoco puede ir sobre el total de la fuente: esas 1.111 filas que faltaron son ~10 % de
las 5.771 que BYMA trajo en la matinal del día anterior (corrida id=339), así que un porcentaje
sobre el agregado no las ve. La comparación tiene que ser panel contra panel, y por eso el conteo
por endpoint —que hasta ahora vivía sólo en `Snapshot.filas_por_tramo`, en memoria— pasa a
persistirse en `corridas_ingesta.filas_por_fuente`.

**Por qué esto no aborta la corrida.** La poda de `sql_poda`
(`app/ingesta/consolidacion/persistencia.py`) borra sólo lo anterior a la fila más reciente **de
cada ticker**, correlacionado: una especie que el panel dejó de declarar conserva su última fila y
se la sigue publicando. No se pierde dato — lo que faltaba era el aviso. Así que las filas que sí
llegaron se persisten igual, y esto es una alerta y no una excepción.
"""

from app.ingesta.alertas import Alerta, Severidad

PREFIJO_TRAMO_BYMA = "byma:"
"""Cómo se guarda el conteo por endpoint dentro de `filas_por_fuente`, que es un `jsonb` plano
compartido con los agregados por fuente (`byma`, `data912`, `cafci`). El prefijo es lo único que
distingue un panel de una fuente entera, y vive únicamente en el borde que escribe
(`claves_de_tramos`) y en el que lee (`registro.tramos_byma_previos`): de la puerta para adentro,
acá y en `Snapshot.filas_por_tramo`, las claves son el nombre pelado del endpoint."""

UMBRAL_CAIDA_PANEL = 0.5
"""Debajo de la mitad de lo que el mismo panel trajo la corrida anterior se avisa. Holgado a
propósito: un panel de renta variable puede encoger de verdad de un día para el otro, y el caso que
importa —1.116 a 5— cae dos órdenes de magnitud por debajo del umbral."""

CODIGO_PANEL_COLAPSADO = "panel_colapsado"


def claves_de_tramos(filas_por_tramo: dict[str, int]) -> dict[str, int]:
    """`{'public-bonds': 1116}` -> `{'byma:public-bonds': 1116}`, para mezclarlo en
    `filas_por_fuente` sin pisar la clave `byma` del agregado."""
    return {f"{PREFIJO_TRAMO_BYMA}{tramo}": filas for tramo, filas in filas_por_tramo.items()}


def _porcentaje(obtenidas: int, previas: int) -> str:
    """El cociente con coma decimal, como se escribe en castellano."""
    return f"{obtenidas / previas * 100:.1f}".replace(".", ",")


def _panel_colapsado(endpoint: str, previas: int, obtenidas: int, umbral: float) -> Alerta:
    return Alerta(
        codigo=CODIGO_PANEL_COLAPSADO,
        mensaje=(
            f"BYMA entregó {obtenidas} filas en {endpoint} contra {previas} de la corrida anterior "
            f"({_porcentaje(obtenidas, previas)} %): el panel puede haber colapsado en la fuente. "
            f"Las filas traídas se persisten igual; la poda por ticker conserva lo que el panel "
            f"dejó de declarar."
        ),
        # ERROR, el mismo nivel que `paginacion_incompleta`: las dos dicen "esta corrida no trajo el
        # panel entero". La consecuencia buscada es que `Snapshot.completo` dé `False` y la corrida
        # quede `parcial` en vez de `completa`, que es exactamente lo que el 28/08 no pasó.
        severidad=Severidad.ERROR,
        accion_requerida=None,
        detalle={
            "endpoint": endpoint,
            "previas": previas,
            "obtenidas": obtenidas,
            "umbral": umbral,
        },
    )


def paneles_colapsados(
    previas: dict[str, int],
    actuales: dict[str, int],
    *,
    umbral: float = UMBRAL_CAIDA_PANEL,
) -> list[Alerta]:
    """Los paneles que trajeron menos de `umbral` de lo que ellos mismos trajeron la vez anterior.

    Los dos conteos hablan en nombres de endpoint pelados (`public-bonds`), no en claves prefijadas:
    `filas_por_tramo` del snapshot entra tal cual, y `tramos_byma_previos` saca el prefijo al leer.

    Dos exclusiones, cada una porque el caso ya está cubierto en otro lado:

    - **Panel en cero.** `ingerir_rueda` (`app/ingesta/byma/ingesta.py`) ya emite `respuesta_vacia`
      o `fuente_caida` con el endpoint en el detalle cuando un tramo no trajo nada. Alertar acá
      también sería contar dos veces el mismo hecho en la barra de estado.
    - **Panel sin conteo previo.** No hay contra qué comparar y no se inventa una línea de base: es
      la primera corrida después de este cambio, o un endpoint recién agregado que se estrena sin
      historia. La comparación empieza a valer en la corrida siguiente.
    """
    alertas: list[Alerta] = []
    # Ordenado por endpoint: estas alertas se serializan a `corridas_ingesta.alertas` y se comparan
    # entre corridas, así que su orden no puede depender del que devolvió la fuente.
    for endpoint, obtenidas in sorted(actuales.items()):
        anteriores = previas.get(endpoint, 0)
        if obtenidas == 0 or anteriores == 0:
            continue
        if obtenidas < anteriores * umbral:
            alertas.append(_panel_colapsado(endpoint, anteriores, obtenidas, umbral))
    return alertas
