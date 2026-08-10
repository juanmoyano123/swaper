"""Orquestación con base: arma el universo, el cronograma y corre el motor puro — F-032.

Mismo patrón que `app/concentracion/servicio.py` y `app/armado/motor.py::armar` llamado desde su
endpoint: la conexión se resuelve acá, y `detectar()` (`app/rotaciones/motor.py`) es pura.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from app.calendario.cupones import (
    Cronograma,
    flujos_por_peso,
    indexar_cronograma,
    indexar_paridades,
)
from app.calendario.lectura import leer_cashflow, leer_paridades
from app.calendario.metricas import retorno_por_tir
from app.concentracion.riesgo import derivar_riesgo
from app.ingesta.alertas import Alerta, Severidad
from app.rotaciones.constantes import (
    ARANCEL_POR_PATA,
    ESCENARIOS_TIR,
    FACTOR_VOLUMEN,
    MAX_MAS_DURACION,
    MIN_DTIR,
    MIN_REND,
    TOP_N,
    UMBRAL_NEUTRO,
    NombreDePerfil,
    ParametrosRotacion,
)
from app.rotaciones.costos import calcular_costo, spread_pct
from app.rotaciones.emisores import clave_emisor_swap, nombre_emisor
from app.rotaciones.frecuencia import frecuencia_por_raiz
from app.rotaciones.legislacion import ParDeLey, premio_por_legislacion
from app.rotaciones.motor import Candidata, detectar
from app.rotaciones.puntas import leer_puntas
from app.universo.servicio import sanear_universo

CODIGO_COSTO_NO_VERIFICABLE = "costo_no_verificable"


@dataclass(frozen=True, slots=True)
class ResultadoRotaciones:
    """El veredicto completo de una corrida: candidatas, contexto y advertencias."""

    perfil: str
    parametros: ParametrosRotacion
    candidatas: list[Candidata]
    origenes_evaluados: list[str]
    fuera_del_universo: list[str]
    sin_rendimiento: list[str]
    premio_legislacion: tuple[list[ParDeLey], dict[str, int]]
    sensibilidad: list[dict[str, object]]
    alertas: list[Alerta] = field(default_factory=list)

    def como_dict(self) -> dict[str, object]:
        pares, medianas = self.premio_legislacion
        return {
            "perfil": self.perfil,
            "parametros": {
                "percentil_liquidez": self.parametros.percentil_liquidez,
                "tope_distress": dict(self.parametros.tope_distress),
                "min_dtir_pp": round(MIN_DTIR * 100, 3),
                "max_mas_duracion": MAX_MAS_DURACION,
                "umbral_neutro_pp": round(UMBRAL_NEUTRO * 100, 3),
                "top_n": TOP_N,
                "min_rend": MIN_REND,
                "factor_volumen": FACTOR_VOLUMEN,
                "arancel_pct_por_pata": round(ARANCEL_POR_PATA * 100, 2),
            },
            "candidatas": [c.como_dict() for c in self.candidatas],
            "origenes_evaluados": list(self.origenes_evaluados),
            "fuera_del_universo": list(self.fuera_del_universo),
            "sin_rendimiento": list(self.sin_rendimiento),
            "premio_legislacion": {
                "pares": [p.como_dict() for p in pares],
                "medianas_bps": dict(medianas),
            },
            "sensibilidad": list(self.sensibilidad),
            "alertas": [a.como_dict() for a in self.alertas],
        }


def _alerta_costo_no_verificable(pares: Sequence[tuple[str, str]]) -> Alerta:
    """Alguna candidata quedó sin costo verificable: le falta punta viva en alguna pata. No se
    asume un spread por defecto (regla 1/11 del dominio), así que se avisa con los pares afectados
    en vez de completar el hueco."""
    detalle_pares = [f"{origen}→{destino}" for origen, destino in pares]
    return Alerta(
        codigo=CODIGO_COSTO_NO_VERIFICABLE,
        mensaje=(
            f"{len(pares)} rotación(es) candidata(s) sin dos puntas vivas en alguna pata: el "
            "costo real de rotar no se puede verificar y no se calcula "
            f"({', '.join(detalle_pares)})."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"pares": detalle_pares},
    )


def _sensibilidad(
    candidatas: Sequence[Candidata], cronograma: Cronograma, hoy: date
) -> list[dict[str, object]]:
    """`hoja_sensibilidad` compuesta sobre `retorno_por_tir`, ya portado por F-040.

    Un ticker sin cashflow o sin TIR queda afuera en silencio: es informativo de la hoja y no una
    alerta de la corrida (decisión menor del plan; el CLI lo cuenta en su lista plana de avisos,
    pero acá no hay un lugar estructurado para una nota que no es ni alerta de dominio ni dato de
    la candidata, así que se omite en vez de forzarla en un campo que no le corresponde).
    """
    roles: dict[str, set[str]] = {}
    especies = {}
    for candidata in candidatas:
        roles.setdefault(candidata.origen.ticker, set()).add("SALE")
        especies[candidata.origen.ticker] = candidata.origen
        roles.setdefault(candidata.destino.ticker, set()).add("ENTRA")
        especies[candidata.destino.ticker] = candidata.destino

    filas: list[dict[str, object]] = []
    for ticker, rol in roles.items():
        especie = especies[ticker]
        pagos = cronograma.pagos_de(especie.raiz)
        resultado = retorno_por_tir(pagos, especie.rendimiento, ESCENARIOS_TIR, hoy)
        if resultado is None:
            continue
        filas.append(
            {
                "ticker": ticker,
                "rol": " / ".join(sorted(rol)),
                "segmento": especie.segmento,
                "tir_actual": especie.rendimiento,
                "duracion": especie.duracion,
                "escenarios": {str(delta): valor for delta, valor in resultado.items()},
            }
        )
    return sorted(filas, key=lambda f: (f["segmento"], -(f["tir_actual"] or 0.0)))  # type: ignore[operator]


async def detectar_rotaciones(
    conn: Any,
    tickers: Sequence[str],
    perfil: NombreDePerfil,
    *,
    hoy: date | None = None,
) -> ResultadoRotaciones:
    hoy = hoy or date.today()
    saneado = await sanear_universo(conn)
    vivas = {e.ticker: e for e in saneado.especies}

    origenes = [vivas[t] for t in tickers if t in vivas]
    fuera_del_universo = [t for t in tickers if t not in vivas]
    origenes_con_rendimiento = [e for e in origenes if e.rendimiento is not None]
    sin_rendimiento = [e.ticker for e in origenes if e.rendimiento is None]

    riesgos = derivar_riesgo(saneado.especies)
    claves_emisor = {t: clave_emisor_swap(e, riesgos) for t, e in vivas.items()}
    nombres_emisor = {t: nombre_emisor(e, claves_emisor[t]) for t, e in vivas.items()}

    cronograma = indexar_cronograma(await leer_cashflow(conn))
    paridades = indexar_paridades(await leer_paridades(conn))
    flujos = flujos_por_peso(saneado.especies, cronograma, paridades, hoy)
    frecuencias = frecuencia_por_raiz(cronograma, hoy)

    params = ParametrosRotacion.de_perfil(perfil)
    operables = saneado.operables()
    premio = premio_por_legislacion(operables, claves_emisor)

    candidatas, alertas = detectar(
        origenes_con_rendimiento,
        operables,
        claves_emisor=claves_emisor,
        nombres_emisor=nombres_emisor,
        frecuencias=frecuencias,
        flujos=flujos,
        hoy=hoy,
        medianas_ley=premio[1],
        params=params,
    )

    tickers_puntas = sorted({t for c in candidatas for t in (c.origen.ticker, c.destino.ticker)})
    puntas = await leer_puntas(conn, tickers_puntas)

    candidatas_con_costo: list[Candidata] = []
    no_verificables: list[tuple[str, str]] = []
    for candidata in candidatas:
        bid_o, ask_o = puntas.get(candidata.origen.ticker, (None, None))
        bid_d, ask_d = puntas.get(candidata.destino.ticker, (None, None))
        costo = calcular_costo(
            spread_pct(bid_o, ask_o), spread_pct(bid_d, ask_d), candidata.d_rend_pp
        )
        if not costo.verificable:
            no_verificables.append((candidata.origen.ticker, candidata.destino.ticker))
        candidatas_con_costo.append(replace(candidata, costo=costo))
    candidatas = candidatas_con_costo

    if no_verificables:
        alertas.append(_alerta_costo_no_verificable(no_verificables))

    sensibilidad = _sensibilidad(candidatas, cronograma, hoy)

    return ResultadoRotaciones(
        perfil=perfil,
        parametros=params,
        candidatas=candidatas,
        origenes_evaluados=[e.ticker for e in origenes_con_rendimiento],
        fuera_del_universo=fuera_del_universo,
        sin_rendimiento=sin_rendimiento,
        premio_legislacion=premio,
        sensibilidad=sensibilidad,
        alertas=alertas,
    )
