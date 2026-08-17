"""Qué campos son críticos, por qué lo son, y cuánto del universo los trae — F-013.

`medir_cobertura` de F-004 ya sabe contar presentes sobre totales. Lo que falta y vive acá es la
otra mitad: **contra qué se lee ese número**. Un 8 % de cobertura no dice nada por sí solo; "8 % de
`paridad`, y sin paridad el cupón no se puede pasar a plata" dice qué deja de funcionar.

Por eso cada campo viaja con su `por_que`, que no es documentación: es lo que la barra muestra al
lado del porcentaje. Un tablero de porcentajes sin esa columna es exactamente la métrica decorativa
que el docstring de `ingesta/cobertura.py` advierte que no hay que construir.

**Los campos son de la vista `resumen`, con el nombre de la fuente.** No se traducen a un nombre
"lindo" en el backend: quien vea `couponCurrency` al 39 % tiene que poder ir a buscar esa columna
sin adivinar cuál era. El rótulo legible lo pone la interfaz.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.ingesta.alertas import Alerta, campo_sin_cobertura
from app.ingesta.cobertura import Cobertura, medir_cobertura


@dataclass(frozen=True, slots=True)
class CampoCritico:
    """Una columna del universo y qué se rompe cuando falta."""

    campo: str
    """El nombre de la columna tal como la publica la vista `resumen`."""

    rotulo: str
    por_que: str
    """Qué deja de poder hacerse con la especie que no lo trae. Se muestra junto al porcentaje."""


# El orden es el de la barra, y va de lo que rompe más a lo que rompe menos: sin tipo de tasa la
# especie ni siquiera entra al universo comparable; sin ley se pierde un eje de riesgo pero el
# instrumento sigue siendo elegible.
CAMPOS_CRITICOS: tuple[CampoCritico, ...] = (
    CampoCritico(
        campo="tipo_tasa",
        rotulo="Tipo de tasa",
        por_que=(
            "Sin tipo de tasa no hay segmento, y sin segmento la especie no se compara con nadie "
            "ni pasa por las dos capas de sanidad: queda fuera del universo comparable."
        ),
    ),
    CampoCritico(
        campo="tir",
        rotulo="TIR",
        por_que=(
            "Es el rendimiento de todos los segmentos menos tasa fija. Sin él la especie no se "
            "propone: no se estima a partir del precio ni se hereda de una especie hermana."
        ),
    ),
    CampoCritico(
        campo="tna",
        rotulo="TNA",
        por_que=(
            "Es el rendimiento del segmento de tasa fija, que cotiza por TNA y no por TIR. No se "
            "reemplaza una con la otra: son unidades distintas."
        ),
    ),
    CampoCritico(
        campo="paridad",
        rotulo="Paridad",
        por_que=(
            "Sin paridad no hay precio sucio, y sin precio sucio el cupón no se puede expresar "
            "como fracción del monto invertido: la especie no entra al calendario de doce meses."
        ),
    ),
    CampoCritico(
        campo="lastPrice",
        rotulo="Último precio",
        por_que=(
            "Es la punta del cociente del que se deriva el tipo de cambio implícito, y sin tipo de "
            "cambio no se comparan volúmenes entre monedas."
        ),
    ),
    CampoCritico(
        campo="effectiveVolume",
        rotulo="Volumen operado",
        por_que=(
            "Es el eje de liquidez del riesgo, y el desempate de qué especie representa a una "
            "emisión."
        ),
    ),
    CampoCritico(
        campo="moneda_cotizacion",
        rotulo="Moneda de cotización",
        por_que=(
            "Dice en qué unidad están el precio y el volumen. Sin ella el número existe pero no se "
            "sabe con qué se puede comparar: no se deduce del sufijo del ticker (regla 11), así "
            "que una especie sin moneda declarada queda fuera de toda comparación."
        ),
    ),
    CampoCritico(
        campo="duration",
        rotulo="Duración",
        por_que=(
            "Es el eje de duración del riesgo, y el chequeo que decide si un grupo de especies con "
            "la misma raíz es de verdad la misma emisión."
        ),
    ),
    CampoCritico(
        campo="maturity",
        rotulo="Vencimiento",
        por_que="Sin vencimiento no se sabe cuándo termina el flujo ni se puede ordenar por plazo.",
    ),
    CampoCritico(
        campo="law",
        rotulo="Ley",
        por_que=(
            "Es el eje de legislación del riesgo. Lo que la fuente no dice queda vacío y no se "
            "infiere."
        ),
    ),
    CampoCritico(
        campo="couponCurrency",
        rotulo="Moneda de pago",
        por_que="Es el eje de moneda del riesgo: en qué moneda cobra de verdad el inversor.",
    ),
)

# `paridad` no viaja en las columnas de `universo/lectura.py`: la lee F-015 aparte, con su propia
# consulta contra la misma vista. Se mide sobre esas filas y no sobre las del universo, que es la
# única forma de contarla sin agregar una tercera lectura de `resumen`.
CAMPO_PARIDAD = "paridad"

POR_CAMPO: dict[str, CampoCritico] = {c.campo: c for c in CAMPOS_CRITICOS}


def medir_campos_criticos(
    filas_universo: Sequence[Mapping[str, object]],
    filas_paridad: Sequence[Mapping[str, object]],
) -> list[Cobertura]:
    """La cobertura de cada campo crítico, en el orden de `CAMPOS_CRITICOS`.

    Se mide sobre el universo **entero**, no sobre las especies segmentadas: contar `tipo_tasa`
    sólo entre las filas que ya tienen segmento daría 100 % siempre, porque tener segmento es
    justamente haber tenido tipo de tasa. La pregunta de la barra es cuánto del dato llegó, y el
    denominador de esa pregunta es todo lo que la fuente publicó.

    Las dos listas de filas salen de la misma vista y tienen el mismo largo. Llegan separadas
    porque las lee código de dos features distintas, y unirlas acá con un diccionario intermedio
    sería armar un join en Python para no cambiar dos módulos ajenos.
    """
    del_universo = [c.campo for c in CAMPOS_CRITICOS if c.campo != CAMPO_PARIDAD]
    medidas = {
        cobertura.campo: cobertura for cobertura in medir_cobertura(filas_universo, del_universo)
    }
    medidas.update(
        {c.campo: c for c in medir_cobertura(filas_paridad, [CAMPO_PARIDAD])},
    )
    return [medidas[c.campo] for c in CAMPOS_CRITICOS]


def alertas_de_cobertura(coberturas: Sequence[Cobertura]) -> list[Alerta]:
    """Una alerta por cada campo crítico que **ninguna** fila trae.

    Sólo el cero, y no un umbral bajo: un campo al 8 % es un campo que alguna fuente publica para
    algunas especies, y decidir a partir de qué porcentaje eso es un problema sería fijar cuánta
    ceguera es aceptable. Un campo al 0 % es otra cosa —está en el esquema, alguien lo lee y
    ninguna fuente lo llena— y es la forma más silenciosa de perder información, porque las
    consultas siguen andando y devuelven vacío.

    Verificado contra la base del 07/08/2026: `tna` es 0 de 2.894 y es la única que dispara. Es
    dato correcto y no un bug de la ingesta —ninguna fuente publica TNA hoy— pero significa que las
    9 especies del segmento de tasa fija no tienen rendimiento con el que proponerse, y hasta ahora
    eso no se veía en ninguna pantalla.
    """
    return [
        campo_sin_cobertura(POR_CAMPO[c.campo].rotulo.lower(), c.total, columna=c.campo)
        for c in coberturas
        if c.presentes == 0
    ]


def como_dict(cobertura: Cobertura) -> dict[str, object]:
    """La cobertura con el rótulo y el porqué del campo pegados: es como la barra la muestra."""
    campo = POR_CAMPO[cobertura.campo]
    return {**cobertura.como_dict(), "rotulo": campo.rotulo, "por_que": campo.por_que}
