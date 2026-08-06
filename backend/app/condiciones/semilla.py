"""El CSV curado se vuelve valores con origen y fecha. Función pura: sin base y sin reloj.

**Se siembra desde un solo archivo, y es una decisión declarada.** La spec de F-009 nombra tres
CSV —`condiciones_estaticas.csv` (272 tickers), `condiciones_monitor.csv` (526) y el curado de
823—, pero de los tres sólo existe `data/condiciones_emision.csv`: se verificó el árbol entero del
repositorio y los otros dos no están en ninguna parte. Es consistente con lo que dice `CLAUDE.md`,
que el curado "se rescató del universo consolidado después de que se borraran los CSV originales" y
que hay que tratarlo como irrecuperable. La lectura razonable es que el curado ya los trae
fusionados: `merge_condiciones.py` era exactamente lo que los fusionaba. No se buscó reconstruirlos
ni generar datos para suplirlos — eso sería inventar, que es la regla 1.

**El origen nombra al artefacto y la fecha es la del artefacto, no la del dato.** El CSV no trae
una fecha por valor: no sabemos cuándo fue cierta cada lámina ni cada calificación. La base exige
por CHECK que todo valor no nulo traiga origen y fecha, así que hay que poner algo, y lo único que
sabemos con certeza es cuándo quedó fijado el archivo. Poner una fecha por valor sería justo lo que
la regla 1 prohíbe: un dato con fecha inventada parece más preciso que un rótulo que dice la verdad
—"esto es lo que sabíamos a esta fecha"— y por eso es peor.

**La fecha está declarada acá y no se lee del sistema de archivos.** El mtime de un archivo
versionado es la fecha del checkout, no la del dato: en un clon nuevo o en el contenedor daría hoy,
y cada deploy rejuvenecería la semilla entera sin que nadie hubiera tocado un valor. Si algún día
se reemplaza el CSV, la constante se actualiza en el mismo commit.

**El vocabulario cerrado se hereda de `tools/merge_condiciones.py`.** Ley y moneda de pago tienen
un conjunto finito de valores que el proyecto maneja; cualquier otro se descarta y se reporta en
vez de cargarse. Puede ser correcto, pero no hay con qué confirmarlo, y un dato sin respaldo no se
usa. El antecedente está en `CLAUDE.md`: una vez se tradujo un código de la fuente como "Ley
Inglesa", una categoría que no existe.

**Se lee con el `csv` de la stdlib y no con pandas.** El backend usa pandas sólo donde la fuente lo
entrega así (Docta). Para 823 filas de texto plano, pandas agrega la ambigüedad del NaN —que
obliga a distinguir hueco de cero en cada columna— sin aportar nada a cambio.
"""

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app.ingesta.alertas import Alerta, Severidad, formato_inesperado

ORIGEN_SEMILLA = "condiciones_emision.csv (curado)"
"""Qué nombra: el artefacto, no una fuente viva. El CSV no tiene una."""

FECHA_ARTEFACTO = date(2026, 8, 5)
"""Fecha del artefacto curado tal como está versionado en el repo (último commit que lo tocó).

**No es la fecha de cada dato**: es la fecha hasta la cual el archivo refleja lo que se sabía. Se
declara acá a mano porque el mtime de un archivo versionado es la fecha del checkout.
"""

CAMPOS: tuple[str, ...] = (
    "ley",
    "moneda_pago",
    "lamina",
    "calificacion",
    "sector",
    "underlying",
)
"""Los seis campos trazables, en el orden en que los declara la tabla."""

CAMPOS_NUMERICOS = frozenset({"lamina"})

# Las únicas dos leyes que el proyecto maneja, traídas de `tools/merge_condiciones.py`.
LEYES_VALIDAS = frozenset({"Ley Argentina", "Ley N.Y."})

# MEP y CCL son las dos que el curado trae; ARS queda porque el vocabulario del motor la contempla
# y una ON en pesos no tiene por qué ser un error de carga.
MONEDAS_PAGO_VALIDAS = frozenset({"MEP", "CCL", "ARS"})

VOCABULARIOS: dict[str, frozenset[str]] = {
    "ley": LEYES_VALIDAS,
    "moneda_pago": MONEDAS_PAGO_VALIDAS,
}

CODIGO_SEMILLA_AUSENTE = "semilla_no_encontrada"
CODIGO_FUERA_DE_VOCABULARIO = "valor_fuera_de_vocabulario"
CODIGO_VALOR_ILEGIBLE = "valor_ilegible_en_semilla"
CODIGO_TICKER_REPETIDO = "ticker_repetido_en_semilla"

ACCION_REVISAR_CSV = (
    "Revisar data/condiciones_emision.csv: es dato curado sin fuente de origen viva y "
    "el proyecto lo trata como irrecuperable."
)


@dataclass(frozen=True, slots=True)
class Valor:
    """Un valor curado con su trazabilidad. La base exige los tres juntos o ninguno."""

    valor: object
    origen: str
    fecha: date


@dataclass(frozen=True, slots=True)
class Condiciones:
    """Lo que se sabe de una especie.

    Un campo ausente del dict es un campo que no se sabe, y es distinto de un campo presente con
    valor vacío: eso último no existe acá justamente para que no se pueda escribir un valor sin
    origen ni fecha.
    """

    ticker: str
    valores: dict[str, Valor] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Semilla:
    """Lo que se pudo leer del artefacto, con lo que salió mal declarado al lado."""

    filas: list[Condiciones] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    archivo: str | None = None
    fecha: date = FECHA_ARTEFACTO


def semilla_ausente(ruta: Path) -> Alerta:
    """El archivo no está donde `settings.condiciones_csv` dice.

    Es un ERROR y no una advertencia: sin semilla no hay nada que sembrar, y una corrida que
    escribiera igual dejaría la tabla vacía pisando lo que ya estaba. Que apuntar mal no dé un
    error ruidoso —da una semilla vacía— es la razón por la que la ruta es configurable y esta
    alerta existe.
    """
    return Alerta(
        codigo=CODIGO_SEMILLA_AUSENTE,
        mensaje=f"No se encontró el CSV curado de condiciones de emisión en {ruta}.",
        severidad=Severidad.ERROR,
        accion_requerida=(
            "Verificar CONDICIONES_CSV y que data/condiciones_emision.csv esté en el repo: "
            "el archivo no tiene fuente de origen viva y no se puede regenerar."
        ),
        detalle={"ruta": str(ruta)},
    )


def _valor_descartado(codigo: str, campo: str, motivo: str, valores: dict[str, str]) -> Alerta:
    """Un valor del artefacto que no se carga, dicho con nombre y apellido.

    Los dos motivos posibles —fuera del vocabulario y no interpretable— comparten forma porque
    comparten consecuencia: el hueco queda y alguien tiene que mirar el CSV. Lo que cambia es qué
    hay que mirar, y eso va en `motivo` y en el código.
    """
    muestra = ", ".join(f"{ticker}={valor!r}" for ticker, valor in sorted(valores.items())[:8])
    return Alerta(
        codigo=codigo,
        mensaje=f"{len(valores)} especies declaran un {campo} {motivo} ({muestra}): no se carga.",
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=ACCION_REVISAR_CSV,
        detalle={"campo": campo, "valores": valores},
    )


def _ticker_repetido(tickers: dict[str, int]) -> Alerta:
    """El CSV trae el mismo ticker dos veces. Se queda la primera aparición.

    No se fusionan las filas: fusionar sería decidir cuál de las dos versiones vale para cada
    campo, y eso es exactamente lo que el sistema no hace por cuenta propia.
    """
    muestra = ", ".join(f"{ticker} (x{veces})" for ticker, veces in sorted(tickers.items())[:8])
    return Alerta(
        codigo=CODIGO_TICKER_REPETIDO,
        mensaje=(
            f"{len(tickers)} tickers aparecen más de una vez en la semilla ({muestra}): "
            f"se conserva la primera aparición y las demás se descartan."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=ACCION_REVISAR_CSV,
        detalle={"tickers": tickers},
    )


def _leer_numero(texto: str) -> float | None:
    try:
        return float(texto)
    except ValueError:
        return None


def leer_semilla(ruta: Path, fecha_artefacto: date = FECHA_ARTEFACTO) -> Semilla:
    """Lee el CSV curado y devuelve una fila por especie, con cada valor ya trazado.

    Nunca lanza: un archivo ausente o mal formado vuelve como alerta y con cero filas, que es lo
    que la corrida necesita para no escribir nada en vez de vaciar la tabla.
    """
    if not ruta.is_file():
        return Semilla(alertas=[semilla_ausente(ruta)], fecha=fecha_artefacto)

    # utf-8-sig y no utf-8: el CSV se editó en planillas que dejan BOM al principio, y con utf-8
    # la primera columna pasa a llamarse "﻿ticker" y no matchea con nada.
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = set(lector.fieldnames or ())
        faltantes = sorted({"ticker", *CAMPOS} - columnas)
        if faltantes:
            return Semilla(
                alertas=[
                    formato_inesperado(
                        "La semilla curada",
                        f"le faltan columnas ({', '.join(faltantes)})",
                        archivo=ruta.name,
                        faltantes=faltantes,
                    )
                ],
                archivo=ruta.name,
                fecha=fecha_artefacto,
            )
        crudas = list(lector)

    filas: list[Condiciones] = []
    vistos: dict[str, int] = {}
    repetidos: dict[str, int] = {}
    fuera_de_vocabulario: dict[str, dict[str, str]] = {}
    ilegibles: dict[str, dict[str, str]] = {}

    for cruda in crudas:
        ticker = (cruda.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        vistos[ticker] = vistos.get(ticker, 0) + 1
        if vistos[ticker] > 1:
            repetidos[ticker] = vistos[ticker]
            continue

        valores: dict[str, Valor] = {}
        for campo in CAMPOS:
            texto = (cruda.get(campo) or "").strip()
            if not texto:
                continue

            vocabulario = VOCABULARIOS.get(campo)
            if vocabulario is not None and texto not in vocabulario:
                fuera_de_vocabulario.setdefault(campo, {})[ticker] = texto
                continue

            valor: object = texto
            if campo in CAMPOS_NUMERICOS:
                numero = _leer_numero(texto)
                if numero is None:
                    ilegibles.setdefault(campo, {})[ticker] = texto
                    continue
                valor = numero

            valores[campo] = Valor(valor=valor, origen=ORIGEN_SEMILLA, fecha=fecha_artefacto)

        filas.append(Condiciones(ticker=ticker, valores=valores))

    alertas: list[Alerta] = []
    if repetidos:
        alertas.append(_ticker_repetido(repetidos))
    for campo, valores_malos in fuera_de_vocabulario.items():
        alertas.append(
            _valor_descartado(
                CODIGO_FUERA_DE_VOCABULARIO,
                campo,
                "que el proyecto no tiene en su vocabulario",
                valores_malos,
            )
        )
    for campo, valores_malos in ilegibles.items():
        alertas.append(
            _valor_descartado(CODIGO_VALOR_ILEGIBLE, campo, "que no es un número", valores_malos)
        )

    return Semilla(filas=filas, alertas=alertas, archivo=ruta.name, fecha=fecha_artefacto)
