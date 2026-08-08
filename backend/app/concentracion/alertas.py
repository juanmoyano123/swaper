"""Lo que la concentración tiene para avisar — F-020.

**Todas informan y ninguna bloquea.** Lo dice la ficha de la feature: *"la advertencia no bloquea:
informa"*. Por eso todas salen con `accion_requerida=None`, que en el contrato de
`app/ingesta/alertas.py` significa que no hay nada que una persona tenga que hacer a mano para que
esto se destrabe — el asesor puede dejar la posición como está y proponerla igual.

La severidad es ADVERTENCIA y no ERROR por lo mismo: un tope excedido no es un cálculo que falló,
es un hecho de la cartera que el asesor tiene que ver antes de proponerla. La única INFO es la de
las posiciones que no están en el universo, porque ahí sí no hay ningún tope roto: hay un pedazo de
la cartera sobre el que este panel no puede opinar, y eso se declara en vez de descubrirse.

Cada mensaje nombra **el exceso además del peso**. "Quedó en 68 %" obliga a restar mentalmente
contra un tope que está en otra parte de la pantalla; "68 %, 3 pp por encima del tope de 65 %"
dice de una sola vez cuánto hay que mover.
"""

from collections.abc import Sequence

from app.ingesta.alertas import Alerta, Severidad

CODIGO_CONCENTRACION_SOBERANA = "concentracion_soberana"
CODIGO_CONCENTRACION_EMISOR = "concentracion_emisor"
CODIGO_CONCENTRACION_SECTOR = "concentracion_sector"
CODIGO_DIVERSIFICACION_INSUFICIENTE = "diversificacion_sectorial_insuficiente"
CODIGO_FUERA_DEL_UNIVERSO = "posiciones_fuera_del_universo"

# Cuántas posiciones se nombran en el mensaje antes de cortar. El resto sigue completo en `detalle`.
MUESTRA_ALERTA = 8


def _pp(valor: float) -> str:
    """Un peso en puntos porcentuales, con un decimal. Mismo formato que usa el motor."""
    return f"{valor:.1f}"


def concentracion_soberana(peso: float, tope: float) -> Alerta:
    """El riesgo soberano agregado pasó su propio tope.

    Va separada de la de emisor porque es otro riesgo: no es que un crédito corporativo pesa de
    más, es que la cartera está expuesta al riesgo país por encima de lo que el perfil declara.
    Nombrar el agregado —y no cada bono del Tesoro por su lado— es todo el punto de la regla 4.
    """
    return Alerta(
        codigo=CODIGO_CONCENTRACION_SOBERANA,
        mensaje=(
            f"Riesgo soberano argentino (todas las emisiones del Tesoro) quedó en "
            f"{_pp(peso)} %, {_pp(peso - tope)} pp por encima del tope de {tope:g} % del perfil."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"clave": "SOBERANO_AR", "peso": peso, "tope": tope},
    )


def concentracion_emisor(clave: str, nombre: str, peso: float, tope: float) -> Alerta:
    """Un emisor corporativo pasó el tope. Se nombra el emisor, como pide el GWT-3 de la ficha."""
    return Alerta(
        codigo=CODIGO_CONCENTRACION_EMISOR,
        mensaje=(
            f"{nombre} quedó en {_pp(peso)} %, {_pp(peso - tope)} pp por encima del tope por "
            f"emisor de {tope:g} % del perfil."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"clave": clave, "nombre": nombre, "peso": peso, "tope": tope},
    )


def concentracion_sector(sector: str, peso: float, tope: float) -> Alerta:
    """Un sector económico pasó el tope sectorial.

    Sólo puede dispararla un sector **computable**: los soberanos y subsoberanos están exentos
    porque ya los acota el tope soberano, y las posiciones sin sector informado no se acotan porque
    no se puede acotar lo que no se conoce.
    """
    return Alerta(
        codigo=CODIGO_CONCENTRACION_SECTOR,
        mensaje=(
            f"El sector {sector} quedó en {_pp(peso)} %, {_pp(peso - tope)} pp por encima del "
            f"tope sectorial de {tope:g} % del perfil."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"sector": sector, "peso": peso, "tope": tope},
    )


def diversificacion_insuficiente(
    presentes: Sequence[tuple[str, float]], minimo: int, sin_sector: float
) -> Alerta:
    """La cartera tiene menos sectores de los que el perfil pide. GWT-5 de la ficha.

    Nombra **los sectores presentes con su peso** y no sólo el número, porque el número solo no dice
    qué hacer: "2 de 3 sectores" se arregla igual comprando cualquier cosa, y ver que el 82 % está
    en O&G dice dónde está el bulto.

    El peso sin sector informado se declara aparte cuando existe. No cuenta para el mínimo —no se
    acredita diversificación con un dato que no está— y por eso hay que decir que está: una cartera
    de siete emisores sin sector curado se ve igual que una de dos, y no es lo mismo.
    """
    detalle_presentes = (
        ", ".join(f"{sector} {_pp(peso)} %" for sector, peso in presentes) or "ninguno"
    )
    cola = (
        f" Hay además un {_pp(sin_sector)} % sin sector informado, que no cuenta para el mínimo."
        if sin_sector > 0
        else ""
    )
    return Alerta(
        codigo=CODIGO_DIVERSIFICACION_INSUFICIENTE,
        mensaje=(
            f"La cartera tiene {len(presentes)} sector(es) y el perfil pide al menos {minimo}: "
            f"{detalle_presentes}.{cola}"
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={
            "sectores": [{"sector": sector, "peso": peso} for sector, peso in presentes],
            "min_sectores": minimo,
            "peso_sin_sector": sin_sector,
        },
    )


def fuera_del_universo(tickers: Sequence[str], peso: float) -> Alerta:
    """Posiciones que este panel no puede medir: no están en el universo de renta fija de hoy.

    Son FCI, renta variable y errores de tipeo. No participan de ningún tope ni de ninguna
    distribución —no tienen emisor derivable, ni sector, ni ley, ni naturaleza de tasa— así que lo
    honesto es decir cuánto de la cartera quedó afuera de la medición en vez de medir el resto y
    presentarlo como si fuera el total (regla 11 del dominio).
    """
    muestra = ", ".join(tickers[:MUESTRA_ALERTA])
    resto = f" y {len(tickers) - MUESTRA_ALERTA} más" if len(tickers) > MUESTRA_ALERTA else ""
    return Alerta(
        codigo=CODIGO_FUERA_DEL_UNIVERSO,
        mensaje=(
            f"{len(tickers)} posición(es) no están en el universo de renta fija "
            f"({muestra}{resto}): suman {_pp(peso)} % de la cartera y quedan fuera de "
            "todos los topes."
        ),
        severidad=Severidad.INFO,
        accion_requerida=None,
        detalle={"tickers": list(tickers), "peso": peso},
    )
