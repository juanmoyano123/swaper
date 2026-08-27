"""Qué queda afuera del calendario y por qué, dicho con nombre y apellido — F-015.

Los códigos y los constructores viven acá y no en `app/ingesta/alertas.py` por la misma razón que
los de `app/universo/emisiones.py`: no hablan de una fuente que falló en una corrida de ingesta,
hablan de cómo quedó armado el calendario de hoy. Quien las agrupe o las filtre usa estos códigos.

**Un instrumento que no entra al calendario se nombra.** Es la regla 1 del proyecto leída del lado
del faltante: no se le inventa un cronograma parecido al de un bono hermano, no se le estima una
paridad y no desaparece en silencio. La grilla de doce meses es criterio de armado (regla 5), así
que un bono ausente de la grilla es un bono que el asesor no va a poder elegir — y tiene derecho a
saber que existe y por qué no está.

## Por qué la cobertura y los faltantes son dos alertas y no una

`sin_paridad` **nombra casos con apellido** para que alguien los revise, y por eso lista sólo a los
que declaran rendimiento o duración: son los que alguna vez fueron candidatos, y listarlos a todos
convertiría la alerta en un padrón del universo entero donde nadie miraría ninguno. Es el criterio
del motor y se mantiene tal cual.

`cobertura_del_calendario` **mide si el servicio sirve para lo que lo van a usar**, y por eso no
nombra a nadie: es un agregado. La distinción no es de estilo — con el criterio del motor solo, el
caso real del 7 de agosto de 2026 era una grilla que mostraba 70 de 431 emisiones y devolvía la
lista de alertas **vacía**, porque ninguno de los 360 faltantes declara un solo número. Un servicio
que cubre el 16 % de lo que dice cubrir tiene que decirlo aunque no haya un solo caso que revisar:
quien lee la barra de estado del dato (F-013) está preguntando "¿puedo confiar en lo que veo?", y
esa pregunta no se contesta con la lista de nombres sino con la proporción.
"""

from collections.abc import Mapping, Sequence

from app.ingesta.alertas import Alerta, Severidad

CODIGO_COBERTURA = "cobertura_del_calendario"
CODIGO_SIN_CRONOGRAMA = "instrumento_sin_cronograma"
CODIGO_SIN_PARIDAD = "instrumento_sin_paridad"
CODIGO_FUERA_DEL_UNIVERSO = "posicion_fuera_del_universo"
CODIGO_POSICION_SIN_CALENDARIO = "posicion_sin_calendario"

# Cuántos tickers se nombran en el cuerpo de una alerta. La lista entera va en el detalle, igual que
# en `emisiones.py`: el cuerpo es para leer, el detalle es para auditar.
MUESTRA_ALERTA = 6


def cobertura_del_calendario(
    *, emisiones: int, con_calendario: int, sin_paridad: int, sin_cronograma: int, vencidos: int
) -> Alerta:
    """Cuánto del universo llega a la grilla de doce meses. Es un agregado y no nombra a nadie.

    Existe porque la grilla-selector de F-016 es la pantalla donde el asesor mira **el universo**
    para elegir, y mostrar un subconjunto sin decir que lo es haría creer que lo que no está no
    existe. La regla 1 del proyecto es "si falta, se deja vacío **y se alerta**", y la segunda mitad
    también aplica cuando el faltante es de a cientos.

    **No hay umbral.** Sale como advertencia en cuanto queda una emisión afuera, y como información
    cuando entran todas. Elegir un piso —"avisar sólo si cubre menos del 80 %"— sería fijar cuánta
    ceguera es aceptable, y eso es una decisión de dominio que nadie tomó. El número va crudo, con
    su proporción, para que la tome quien corresponde.

    No lleva la lista de tickers a propósito: para eso está `sin_paridad`, que nombra a los que
    alguien puede ir a revisar. Ver el docstring del módulo.
    """
    proporcion = con_calendario / emisiones if emisiones else 0.0
    afuera = emisiones - con_calendario
    return Alerta(
        codigo=CODIGO_COBERTURA,
        mensaje=(
            f"El calendario cubre {con_calendario} de {emisiones} emisiones del universo "
            f"({proporcion:.0%}): {sin_paridad} quedan afuera por no declarar paridad, "
            f"{sin_cronograma} por no tener cronograma en la fuente y {vencidos} por no tener "
            "pagos futuros. La grilla de doce meses muestra ese subconjunto, no el universo entero."
        ),
        severidad=Severidad.ADVERTENCIA if afuera else Severidad.INFO,
        accion_requerida=(
            "La paridad sale del cálculo propio y sólo se puede calcular donde el precio y el "
            "flujo comparten moneda: no hay nada que corregir en el dato. Si la grilla tiene que "
            "cubrir más universo, lo que hay que decidir es el criterio de qué especie representa "
            "a una emisión (F-011)."
        )
        if afuera
        else None,
        detalle={
            "emisiones": emisiones,
            "con_calendario": con_calendario,
            "cobertura": proporcion,
            "sin_paridad": sin_paridad,
            "sin_cronograma": sin_cronograma,
            "vencidos": vencidos,
        },
    )


def sin_cronograma(tickers: Sequence[str]) -> Alerta:
    """Instrumentos cuya emisión no tiene ningún pago cargado en la fuente.

    **El cruce es por raíz de emisión y es un lookup, nunca una generación.** El cronograma indexa
    una sola especie por emisión —RUCEO, no RUCED ni RUCEC— así que buscar el de RUCED por su raíz
    `RUCE` es la única forma de encontrarlo. Lo que no se hace jamás es el camino inverso: si la
    raíz no encuentra cronograma, el instrumento queda afuera del calendario y se lo nombra acá.
    Derivar un ticker cortando strings ya produjo una vez 121 tickers inexistentes que hubo que
    revertir.
    """
    return Alerta(
        codigo=CODIGO_SIN_CRONOGRAMA,
        mensaje=(
            f"{len(tickers)} instrumentos no tienen cronograma de pagos en la fuente "
            f"({', '.join(tickers[:MUESTRA_ALERTA])}): no entran al calendario de doce meses."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar si la fuente de cashflow los publica bajo otra especie de la misma emisión. "
            "No se les asigna el cronograma de un bono parecido."
        ),
        detalle={"cantidad": len(tickers), "tickers": list(tickers)},
    )


def sin_paridad(tickers: Sequence[str]) -> Alerta:
    """Instrumentos con cronograma pero sin paridad utilizable.

    Sin paridad no hay precio sucio, y sin precio sucio el cupón no se puede expresar como fracción
    del monto invertido. Lo único que lo reemplazaría es un tipo de cambio traído de afuera, que es
    exactamente lo que la regla 3 del proyecto prohíbe.

    Se nombran **sólo los que cotizan** —los que declaran rendimiento o duración—: un instrumento
    sin ninguno de los tres números no iba a ser candidato de cartera de todos modos, y listarlo acá
    convertiría la alerta en un padrón del universo entero. Es el mismo criterio del motor
    (`tools/cupones.py:139-143`).
    """
    return Alerta(
        codigo=CODIGO_SIN_PARIDAD,
        mensaje=(
            f"{len(tickers)} instrumentos que cotizan no tienen paridad utilizable "
            f"({', '.join(tickers[:MUESTRA_ALERTA])}): no se puede convertir su cupón a plata sin "
            "inventar un tipo de cambio, así que quedan fuera del calendario."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"cantidad": len(tickers), "tickers": list(tickers)},
    )


def posiciones_sin_calendario(motivos: Mapping[str, str]) -> Alerta:
    """Posiciones que están en el universo pero cuyo calendario no se pudo calcular.

    **Es la alerta más importante de la vista de cartera y no existe en el motor.** El motor sólo
    nombra a los faltantes "que cotizan" —los que declaran rendimiento o duración— porque asume que
    lo demás nunca iba a ser candidato de cartera. Ese atajo es falso en cuanto la pregunta cambia:
    un bono que el asesor **ya tiene** importa aunque hoy no publique un solo número.

    Sin esto, el caso real es una cartera que devuelve doce meses de renta cero, sin una sola
    alerta, y que se lee como "este bono no paga nada" cuando lo que pasa es que no se lo pudo
    valuar. Medido contra la base del 7 de agosto de 2026: RUCED, SBC2D, CS47D y LOC5D —las cuatro
    posiciones del GWT-4 de la spec— caían exactamente ahí cuando se midió, porque las métricas del
    día estaban escritas en la especie O de cada emisión y no en la D.
    """
    nombrados = ", ".join(f"{ticker} ({motivo})" for ticker, motivo in sorted(motivos.items())[:3])
    return Alerta(
        codigo=CODIGO_POSICION_SIN_CALENDARIO,
        mensaje=(
            f"{len(motivos)} posiciones de la cartera están en el universo pero no se les pudo "
            f"calcular el calendario ({nombrados}): su renta no aparece en la grilla, así que el "
            "total de cada mes sale más chico de lo que la cartera cobra."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar si la especie tiene métricas publicadas hoy: puede que el dato del día esté "
            "en otra especie de la misma emisión."
        ),
        detalle={"cantidad": len(motivos), "motivos": dict(sorted(motivos.items()))},
    )


def fuera_del_universo(tickers: Sequence[str]) -> Alerta:
    """Posiciones de una cartera que hoy no están en el universo.

    Es más grave que un faltante del universo: acá el asesor **tiene** el bono. Que no esté en el
    universo del día puede ser que no haya cotizado, que la ingesta no lo haya traído o que el
    ticker esté mal escrito, y distinguirlo requiere mirarlo. Lo que no se hace es calcular la
    cartera como si esas posiciones no existieran sin decirlo: la renta del mes saldría más chica de
    lo que es.
    """
    return Alerta(
        codigo=CODIGO_FUERA_DEL_UNIVERSO,
        mensaje=(
            f"{len(tickers)} posiciones de la cartera no están en el universo de hoy "
            f"({', '.join(tickers[:MUESTRA_ALERTA])}): no aportan al calendario, así que la renta "
            "proyectada de la cartera está incompleta."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar si el ticker está bien escrito o si la especie no cotizó en la última rueda."
        ),
        detalle={"cantidad": len(tickers), "tickers": list(tickers)},
    )
