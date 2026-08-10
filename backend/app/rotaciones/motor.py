"""El motor de rotaciones, puro — port de `evaluar_par`/`detectar` de `tools/detectar_swaps.py`
(líneas 283-508) — F-032.

Genera rotaciones candidatas **dentro del mismo segmento**: un cruce CER → hard-dollar es visión
macro humana, no un swap, y el motor no lo propone (spec de la ficha). Trabaja sobre la vista viva
de especies (`saneado.especies`, sin deduplicar) porque los swaps de perfil rotan entre especies de
la misma emisión (MEP → Cable, ej. TLCWO → TLCMO).

Trae el bloque de costo real de rotar (arancel + spread bid/ask de las dos patas) — F-035, tanda 13
— pero no lo calcula: `Candidata.costo` viaja vacío desde acá y lo completa `servicio.py` después de
`detectar()`, porque leer las puntas es I/O y este módulo es puro. Divergencia deliberada contra
`tools/detectar_swaps.py`: el CLI cuenta un spread faltante como cero (costo "piso"); acá, sin dos
puntas vivas en alguna pata, el costo entero es `None` y la candidata queda `verificable=False` — no
se asume un spread por defecto (regla 1/11 del dominio). El detalle vive en `app/rotaciones/costos.py`.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date

from app.armado.motor import percentil_lineal
from app.calendario.cupones import Flujos
from app.ingesta.alertas import Alerta, Severidad
from app.rotaciones.constantes import (
    BANDA_RENDIMIENTO_PP,
    DIAS_CUPON,
    FACTOR_VOLUMEN,
    LEY_LOCAL,
    MAX_MAS_DURACION,
    MIN_DTIR,
    MIN_OPERABLES_PERCENTIL,
    MIN_REND,
    PERCENTIL_DISTRESS,
    TOP_N,
    UMBRAL_NEUTRO,
    ParametrosRotacion,
    es_extranjera,
)
from app.rotaciones.costos import CostoRotacion
from app.rotaciones.frecuencia import MESES_DESCONOCIDO, proximo_cupon
from app.universo.segmentacion import EspecieUniverso

# Soberano / subsoberano / corporativo, del mismo mapeo que usa el CLI (`categoria_credito`). Al
# abrir la segmentación a todo el universo, los segmentos en pesos dejaron de ser 100% soberanos, y
# un swap Nación → provincia → ON tiene que quedar señalado como cambio de tipo de riesgo.
_CATEGORIA_CREDITO: dict[str, str] = {
    "bono_soberano": "soberano",
    "bono_subsoberano": "subsoberano",
}

CODIGO_ORIGEN_SIN_RENDIMIENTO = "origen_sin_rendimiento"
CODIGO_LIQUIDEZ_EXCLUYE_DESTINOS = "liquidez_excluye_destinos"
CODIGO_PERCENTIL_LIQUIDEZ_NO_APLICA = "percentil_liquidez_no_aplica"
CODIGO_SEGMENTO_SIN_TOPE_DISTRESS = "segmento_sin_tope_distress"


def _categoria_credito(especie: EspecieUniverso) -> str:
    return _CATEGORIA_CREDITO.get(especie.clase_activo, "corporativo")


def _alerta(codigo: str, mensaje: str, **detalle: object) -> Alerta:
    """Toda alerta de este módulo informa y no bloquea, igual que las de F-019/F-020:
    `accion_requerida` siempre `None`."""
    return Alerta(
        codigo=codigo,
        mensaje=mensaje,
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle=detalle,
    )


@dataclass(frozen=True, slots=True)
class Candidata:
    """Una rotación candidata: origen (lo que rinde mal) → destino (lo que puede rendir mejor)."""

    tipo: str  # "mejora_rendimiento" | "mejora_perfil"
    segmento: str
    origen: EspecieUniverso
    destino: EspecieUniverso
    emisor_origen: str
    emisor_destino: str
    d_rend_pp: float
    d_duracion: float | None
    mismo_emisor: bool
    pasa_a_cable: bool
    mejora_ley: bool
    empeora_ley: bool
    mejora_volumen: bool
    posible_distress: bool
    premio_ley_bps: int | None
    premio_ley_vs_mediana_bps: int | None
    riesgo_nota: str
    frec_meses: int
    cupon_dias: int | None
    cupon_pct: float | None
    cupon_nota: str | None
    frecuencia_origen: str | None
    """La etiqueta de `frecuencia_por_raiz` para el origen y el destino. No está en la lista de
    campos del plan (que sólo trae `frec_meses`, usado para ordenar), pero el contrato del
    endpoint pide `frecuencia_cupon` en los dos lados del par y `Candidata` ya guarda las dos
    especies enteras: es más simple resolverlo acá, una vez, que threadear el mapeo de
    frecuencias hasta la serialización."""
    frecuencia_destino: str | None
    costo: CostoRotacion | None = None
    """El costo real de rotar. Vacío al salir de `evaluar_par`/`detectar` (motor puro, sin I/O);
    lo completa `servicio.py` después de leer las puntas de mercado."""
    cupon_fecha: date | None = None
    """La fecha del próximo cupón que cobra el origen, si tiene uno futuro con renta > 0 — la
    misma condición que ya habilita `cupon_dias`/`cupon_pct`, ver `evaluar_par`."""

    def como_dict(self) -> dict[str, object]:
        return {
            "tipo": self.tipo,
            "segmento": self.segmento,
            "origen": _especie_como_dict(self.origen, self.emisor_origen, self.frecuencia_origen),
            "destino": _especie_como_dict(
                self.destino, self.emisor_destino, self.frecuencia_destino
            ),
            "delta": {"rendimiento_pp": self.d_rend_pp, "duracion": self.d_duracion},
            "flags": {
                "mismo_emisor": self.mismo_emisor,
                "pasa_a_cable": self.pasa_a_cable,
                "mejora_ley": self.mejora_ley,
                "empeora_ley": self.empeora_ley,
                "mejora_volumen": self.mejora_volumen,
                "posible_distress": self.posible_distress,
            },
            "premio_ley": (
                {"bps": self.premio_ley_bps, "vs_mediana_bps": self.premio_ley_vs_mediana_bps}
                if self.premio_ley_bps is not None
                else None
            ),
            "riesgo_nota": self.riesgo_nota,
            "cupon": (
                {
                    "dias": self.cupon_dias,
                    "pct": self.cupon_pct,
                    "fecha": self.cupon_fecha.isoformat() if self.cupon_fecha is not None else None,
                    "nota": self.cupon_nota,
                }
                if self.cupon_dias is not None
                else None
            ),
            "costo": self.costo.como_dict() if self.costo is not None else None,
        }


def _especie_como_dict(
    especie: EspecieUniverso, emisor: str, frecuencia: str | None
) -> dict[str, object]:
    return {
        "ticker": especie.ticker,
        "emisor": emisor,
        "rendimiento": especie.rendimiento,
        "duracion": especie.duracion,
        "moneda_cupon": especie.moneda_cupon,
        "ley": especie.ley,
        "calificacion": especie.calificacion,
        "lamina": especie.lamina,
        "frecuencia_cupon": frecuencia,
        "volumen_usd": especie.volumen_usd,
    }


def evaluar_par(
    origen: EspecieUniverso,
    destino: EspecieUniverso,
    *,
    claves_emisor: Mapping[str, str],
    nombres_emisor: Mapping[str, str],
    frecuencias: Mapping[str, tuple[str, int]],
    flujos: Flujos,
    hoy: date,
    medianas_ley: Mapping[str, int],
    params: ParametrosRotacion,
) -> Candidata | None:
    """Evalúa un par origen→destino. Devuelve la candidata o `None` si no pasa ningún criterio.

    `params` viaja por firma para que la función tenga el mismo contexto que `detectar()` — hoy no
    lee ninguno de sus campos: `percentil_liquidez` y `tope_distress` sólo se aplican al filtrar
    destinos, un paso antes de llegar acá.
    """
    del params
    if origen.rendimiento is None or destino.rendimiento is None:
        return None
    d_rend = destino.rendimiento - origen.rendimiento

    d_dur: float | None = None
    if origen.duracion is not None and destino.duracion is not None:
        d_dur = destino.duracion - origen.duracion
        if d_dur > MAX_MAS_DURACION:
            return None  # estira demasiado la duración

    mismo_emisor = claves_emisor[origen.ticker] == claves_emisor[destino.ticker]
    pasa_a_cable = origen.moneda_cupon in ("MEP", "ARS") and destino.moneda_cupon == "CCL"
    mejora_ley = origen.ley == LEY_LOCAL and es_extranjera(destino.ley)
    empeora_ley = es_extranjera(origen.ley) and destino.ley == LEY_LOCAL

    # Volumen en NOMINALES (ya llevados a USD), no en plata cruda: rotar de una especie en dólares
    # a una en pesos marcaría "mucho más volumen" por el tipo de cambio y no por liquidez real.
    vol_o, vol_d = origen.volumen_usd, destino.volumen_usd
    mejora_volumen = (
        vol_d is not None
        and vol_d > 0
        and (vol_o is None or vol_o <= 0 or vol_d >= FACTOR_VOLUMEN * vol_o)
    )

    if d_rend >= MIN_DTIR:
        tipo = "mejora_rendimiento"
    elif (
        mismo_emisor and d_rend >= UMBRAL_NEUTRO and (pasa_a_cable or mejora_ley or mejora_volumen)
    ):
        tipo = "mejora_perfil"
    else:
        return None

    # Premio por legislación: sólo informativo cuando la ley efectivamente cambia. Positivo = se
    # resigna tasa para ganar Ley N.Y.
    premio_ley_bps: int | None = None
    premio_ley_vs_mediana_bps: int | None = None
    if mejora_ley or empeora_ley:
        premio_ley_bps = round((origen.rendimiento - destino.rendimiento) * 10000)
        mediana = medianas_ley.get(origen.segmento)
        if mediana is not None:
            referencia = mediana if mejora_ley else -mediana
            premio_ley_vs_mediana_bps = round(premio_ley_bps - referencia)

    # Regla 8 del dominio: nunca se propone una mejora de TIR sin nombrar qué riesgo se asume.
    cat_o, cat_d = _categoria_credito(origen), _categoria_credito(destino)
    if mismo_emisor:
        riesgo = "mismo emisor — mismo riesgo crediticio"
    elif cat_o != cat_d:
        riesgo = f"cambia riesgo {cat_o} → {cat_d} — verificar"
    else:
        riesgo = f"distinto emisor ({cat_d}) — verificar calidad crediticia"
    # Regla 11 del dominio: la calificación es texto libre, nunca se ordena. Sólo se muestra el
    # salto cuando las dos están cargadas y cambian.
    cal_o, cal_d = origen.calificacion, destino.calificacion
    if not mismo_emisor and cal_o is not None and cal_d is not None and cal_o != cal_d:
        riesgo += f" [{cal_o} → {cal_d}]"
    if empeora_ley:
        riesgo += " | ATENCION: pasa de Ley N.Y. a Ley Argentina"

    frecuencia_origen = frecuencias.get(origen.raiz, (None, MESES_DESCONOCIDO))[0]
    frecuencia_destino, frec_meses = frecuencias.get(destino.raiz, (None, MESES_DESCONOCIDO))

    # Cupón próximo del bono que se vende: no bloquea, informa cuánto se resigna por salir antes
    # del pago.
    cupon_nota: str | None = None
    cupon_dias: int | None = None
    cupon_pct: float | None = None
    cupon_fecha: date | None = None
    prox = proximo_cupon(flujos, origen.ticker, hoy)
    if prox is not None:
        cupon_dias = int(prox["dias"])  # type: ignore[arg-type]
        cupon_pct = float(prox["pct_renta"])  # type: ignore[arg-type]
        cupon_fecha = prox["fecha"]  # type: ignore[assignment]
        if cupon_dias <= DIAS_CUPON:
            fecha = prox["fecha"]
            cupon_nota = (
                f"paga cupón en {cupon_dias} días ({fecha:%d/%m/%Y}): se resigna "
                f"{cupon_pct:.2%} del capital invertido. Conviene esperar al cobro."
            )

    return Candidata(
        tipo=tipo,
        segmento=origen.segmento,
        origen=origen,
        destino=destino,
        emisor_origen=nombres_emisor[origen.ticker],
        emisor_destino=nombres_emisor[destino.ticker],
        d_rend_pp=round(d_rend * 100, 2),
        d_duracion=round(d_dur, 2) if d_dur is not None else None,
        mismo_emisor=mismo_emisor,
        pasa_a_cable=pasa_a_cable,
        mejora_ley=mejora_ley,
        empeora_ley=empeora_ley,
        mejora_volumen=mejora_volumen,
        posible_distress=False,  # `detectar` lo marca después, sobre destinos_ok por segmento
        premio_ley_bps=premio_ley_bps,
        premio_ley_vs_mediana_bps=premio_ley_vs_mediana_bps,
        riesgo_nota=riesgo,
        frec_meses=frec_meses,
        cupon_dias=cupon_dias,
        cupon_pct=cupon_pct,
        cupon_nota=cupon_nota,
        frecuencia_origen=frecuencia_origen,
        frecuencia_destino=frecuencia_destino,
        cupon_fecha=cupon_fecha,
    )


def _orden_destinos(candidata: Candidata) -> tuple[int, int, float]:
    """Mejor rendimiento primero; entre destinos parejos (banda de 0.5pp), el que paga más seguido.

    Es la misma banda con la que la mesa evalúa si una diferencia de tasa justifica mover.
    """
    banda = -math.floor(candidata.d_rend_pp / BANDA_RENDIMIENTO_PP)
    return (banda, candidata.frec_meses, -candidata.d_rend_pp)


def _alerta_origen_sin_rendimiento(ticker: str) -> Alerta:
    return _alerta(
        CODIGO_ORIGEN_SIN_RENDIMIENTO,
        f"{ticker}: sin rendimiento parseable, se saltea como origen.",
        ticker=ticker,
    )


def _alerta_liquidez(detalle: dict[str, int]) -> Alerta:
    texto = ", ".join(f"{s}: {n}" for s, n in sorted(detalle.items()))
    return _alerta(
        CODIGO_LIQUIDEZ_EXCLUYE_DESTINOS,
        f"Destinos excluidos por volumen operado bajo el piso de liquidez de su segmento "
        f"({texto}).",
        por_segmento=detalle,
    )


def _alerta_percentil_no_aplica(segmentos: Sequence[str]) -> Alerta:
    return _alerta(
        CODIGO_PERCENTIL_LIQUIDEZ_NO_APLICA,
        f"Segmentos con menos de {MIN_OPERABLES_PERCENTIL} candidatos, donde el percentil de "
        f"liquidez no aplica ({', '.join(segmentos)}): revisar a mano el volumen del destino "
        "antes de operar.",
        segmentos=list(segmentos),
    )


def _alerta_sin_tope(segmentos: Sequence[str]) -> Alerta:
    return _alerta(
        CODIGO_SEGMENTO_SIN_TOPE_DISTRESS,
        f"Segmentos sin tope anti-distress: {', '.join(segmentos)}. Los destinos que rindan muy "
        "por encima de sus pares entran igual, marcados como posible distress.",
        segmentos=list(segmentos),
    )


def _agrupar_por_segmento(
    especies: Sequence[EspecieUniverso],
) -> dict[str, list[EspecieUniverso]]:
    por_segmento: dict[str, list[EspecieUniverso]] = {}
    for especie in especies:
        por_segmento.setdefault(especie.segmento, []).append(especie)
    return por_segmento


def _filtrar_por_liquidez(
    destinos: list[EspecieUniverso], percentil_liquidez: float
) -> tuple[list[EspecieUniverso], list[Alerta]]:
    """Piso de liquidez POR SEGMENTO, sobre `volumen_usd`. Sólo filtra destinos: una posición
    ilíquida del cliente se analiza igual como origen."""
    alertas: list[Alerta] = []
    if not (0 < percentil_liquidez < 100) or not any(e.volumen_usd is not None for e in destinos):
        return destinos, alertas

    excluidos: dict[str, int] = {}
    excluidos_tickers: set[str] = set()
    chicos: list[str] = []
    for segmento, grupo in _agrupar_por_segmento(destinos).items():
        if len(grupo) < MIN_OPERABLES_PERCENTIL:
            chicos.append(f"{segmento} ({len(grupo)})")
            continue
        volumenes = [e.volumen_usd for e in grupo if e.volumen_usd is not None]
        if not volumenes:
            continue
        piso = percentil_lineal(volumenes, percentil_liquidez / 100.0)
        fuera = [e for e in grupo if (e.volumen_usd or 0.0) < piso]
        if fuera:
            excluidos[segmento] = len(fuera)
            excluidos_tickers.update(e.ticker for e in fuera)

    if excluidos_tickers:
        destinos = [e for e in destinos if e.ticker not in excluidos_tickers]
        alertas.append(_alerta_liquidez(excluidos))
    if chicos:
        alertas.append(_alerta_percentil_no_aplica(sorted(chicos)))
    return destinos, alertas


def _marcar_distress(destinos: Sequence[EspecieUniverso]) -> set[str]:
    """Señalamiento informativo: destino que cae en la cola alta de rendimiento de su propio
    segmento (percentil `PERCENTIL_DISTRESS`). No descarta, sólo se usa para marcar la candidata."""
    if not (0 < PERCENTIL_DISTRESS < 100):
        return set()
    tickers: set[str] = set()
    for grupo in _agrupar_por_segmento(destinos).values():
        if len(grupo) < MIN_OPERABLES_PERCENTIL:
            continue
        rendimientos = [e.rendimiento for e in grupo if e.rendimiento is not None]
        if not rendimientos:
            continue
        umbral = percentil_lineal(rendimientos, PERCENTIL_DISTRESS / 100.0)
        tickers.update(e.ticker for e in grupo if (e.rendimiento or 0.0) > umbral)
    return tickers


def detectar(
    origenes: Sequence[EspecieUniverso],
    universo_operable: Sequence[EspecieUniverso],
    *,
    claves_emisor: Mapping[str, str],
    nombres_emisor: Mapping[str, str],
    frecuencias: Mapping[str, tuple[str, int]],
    flujos: Flujos,
    hoy: date,
    medianas_ley: Mapping[str, int],
    params: ParametrosRotacion,
) -> tuple[list[Candidata], list[Alerta]]:
    """Las rotaciones candidatas para cada origen, rankeadas y con el filtro de liquidez y de
    rendimiento mínimo ya aplicados a los destinos."""
    alertas: list[Alerta] = []

    piso_rend = MIN_REND / 100.0
    destinos_ok = [
        e for e in universo_operable if e.rendimiento is not None and e.rendimiento > piso_rend
    ]
    destinos_ok, alertas_liquidez = _filtrar_por_liquidez(destinos_ok, params.percentil_liquidez)
    alertas.extend(alertas_liquidez)

    distress_tickers = _marcar_distress(destinos_ok)

    candidatas: list[Candidata] = []
    sin_tope: set[str] = set()
    for origen in origenes:
        if origen.rendimiento is None:
            alertas.append(_alerta_origen_sin_rendimiento(origen.ticker))
            continue

        candidatos = [
            e for e in destinos_ok if e.segmento == origen.segmento and e.ticker != origen.ticker
        ]
        tope = params.tope_distress.get(origen.segmento)
        if tope is not None:
            candidatos = [e for e in candidatos if (e.rendimiento or 0.0) <= tope]
        else:
            sin_tope.add(origen.segmento)

        evaluadas: list[Candidata] = []
        for destino in candidatos:
            candidata = evaluar_par(
                origen,
                destino,
                claves_emisor=claves_emisor,
                nombres_emisor=nombres_emisor,
                frecuencias=frecuencias,
                flujos=flujos,
                hoy=hoy,
                medianas_ley=medianas_ley,
                params=params,
            )
            if candidata is None:
                continue
            if candidata.destino.ticker in distress_tickers:
                candidata = replace(candidata, posible_distress=True)
            evaluadas.append(candidata)

        # top_n POR TIPO: las ideas de perfil (mismo emisor) no compiten por cupo con las de
        # rendimiento — son propuestas distintas.
        for tipo in ("mejora_rendimiento", "mejora_perfil"):
            del_tipo = sorted((c for c in evaluadas if c.tipo == tipo), key=_orden_destinos)
            candidatas.extend(del_tipo[:TOP_N])

    if sin_tope:
        alertas.append(_alerta_sin_tope(sorted(sin_tope)))

    return candidatas, alertas
