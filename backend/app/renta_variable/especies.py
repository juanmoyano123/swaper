"""La lógica de renta variable, pura y probable sin Postgres — F-052.

**Sin campo `rendimiento`.** Una acción no tiene TIR, ni duración, ni cronograma: la regla 2 del
dominio prohíbe presentar cualquier magnitud en el lugar de un rendimiento que no existe, y la
ausencia acá es el contrato, no un TODO.

**La variación nunca se estima.** Es un cociente entre dos datos publicados —el precio y el cierre
anterior de BYMA (`previousClosingPrice`)— y sólo se calcula cuando los dos están. Faltando
cualquiera de los dos, o con un cierre anterior que no es un precio válido, queda `None`.

**El volumen en dólares sólo se calcula sobre monedas que significan algo.** `USD` y `ARS` son ISO
4217; `EXT` es vocabulario propio de BYMA que la fuente no documenta, y desde la regla 11
(08/08/2026) no se convierte ni acá ni en `app.universo.cambio`. Tampoco se deduce del sufijo del
ticker: esa regla es de especies de liquidación de renta fija y aplicarla a una acción sería
completar por analogía. Sin moneda utilizable, `volumen_usd` queda `None` y se cuenta como
faltante — sobre el universo de hoy son 341 CEDEARs y acciones en `EXT`, más las que no declaran.

**Nombre, sector, industria y país (Etapa 4 del rediseño del armador).** Vienen de
`public.perfil_renta_variable`, poblada por un job de enriquecimiento aparte contra Yahoo Finance
(`app/renta_variable/enriquecimiento.py`) — no de BYMA, y no siempre están: el job es incremental
y una especie recién agregada al universo puede no tener fila todavía. `perfil_fuente` y
`perfil_capturado_en` declaran de dónde salió y cuándo, igual que el resto de los datos externos
del proyecto (regla 11): nunca se muestran sin decir su origen.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.renta_variable.agrupamiento import agrupar, aplicar_contraste, hermanas, verificar
from app.universo.cambio import MONEDA_EN_PESOS, MONEDAS_EN_DOLARES, TipoDeCambio
from app.universo.segmentacion import a_numero


@dataclass(frozen=True, slots=True)
class EspecieRentaVariable:
    """Una acción o un CEDEAR, tal como se muestra en el monitor. Nunca lleva rendimiento."""

    ticker: str
    clase_activo: str
    precio: float | None
    moneda_cotizacion: str | None
    cierre_anterior: float | None
    variacion: float | None
    volumen: float | None
    volumen_usd: float | None
    px_bid: float | None
    px_ask: float | None
    operaciones: int | None
    fuente: str | None = None
    """Experimento data912: de dónde salió `precio`. Ver `universo/segmentacion.py:EspecieUniverso.
    fuente` para el vocabulario completo."""

    # Qué papel es esta especie (13/08/2026). Ver `agrupamiento.py` para por qué esto se puede
    # afirmar ahora y no antes, y para los casos que quedan fuera.
    emision: str | None = None
    """El ticker del papel. `AAPL`, `AAPLC` y `AAPLD` comparten `emision: 'AAPL'`."""
    sufijo_liquidacion: str | None = None
    """`'C'` cable, `'D'` MEP, `None` la especie en pesos o sin variantes."""
    hermanas: list[str] = field(default_factory=list)
    """Las otras especies del mismo papel. Vacío para lo no identificado: dos especies que no
    sabemos qué son no se pueden declarar hermanas."""
    no_identificado: bool = False
    """La fuente no explica qué es esta especie — hoy, las que terminan en `B`."""

    # Perfil de empresa (Etapa 4): todos `None` hasta que el job de enriquecimiento pase por este
    # ticker. Valores de Yahoo tal como la fuente los declara, sin traducir (regla 11).
    nombre_corto: str | None = None
    nombre_largo: str | None = None
    sector: str | None = None
    industria: str | None = None
    pais: str | None = None
    perfil_fuente: str | None = None
    perfil_capturado_en: str | None = None

    def como_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "clase_activo": self.clase_activo,
            "precio": self.precio,
            "moneda_cotizacion": self.moneda_cotizacion,
            "cierre_anterior": self.cierre_anterior,
            "variacion": self.variacion,
            "volumen": self.volumen,
            "volumen_usd": self.volumen_usd,
            "px_bid": self.px_bid,
            "px_ask": self.px_ask,
            "operaciones": self.operaciones,
            "fuente": self.fuente,
            "emision": self.emision,
            "sufijo_liquidacion": self.sufijo_liquidacion,
            "hermanas": self.hermanas,
            "no_identificado": self.no_identificado,
            "nombre_corto": self.nombre_corto,
            "nombre_largo": self.nombre_largo,
            "sector": self.sector,
            "industria": self.industria,
            "pais": self.pais,
            "perfil_fuente": self.perfil_fuente,
            "perfil_capturado_en": self.perfil_capturado_en,
        }


def variacion_diaria(precio: float | None, cierre_anterior: float | None) -> float | None:
    """`(precio - cierre_anterior) / cierre_anterior`, como fracción, sólo con los dos datos.

    `0.031` es `+3,1%` — misma convención que `rendimiento` y `paridad` en el resto del API.
    Un cierre anterior que no es un precio válido (`None` o `<= 0`) no produce una variación
    inventada: se propaga `None`.
    """
    if precio is None or cierre_anterior is None or cierre_anterior <= 0:
        return None
    return (precio - cierre_anterior) / cierre_anterior


def volumen_en_dolares(
    cambio: TipoDeCambio, volumen: float | None, moneda_cotizacion: str | None
) -> float | None:
    """El volumen llevado a dólares, sin caer nunca a la regla del sufijo de ticker.

    Sólo dos monedas producen un número: `USD` ya lo está y `ARS` se divide por el implícito. Todo
    lo demás —`EXT`, que BYMA no documenta, y la ausencia de declaración— devuelve `None`. La lista
    de monedas convertibles es cerrada a propósito: escribirla como "si no es dólar, es peso" hacía
    que un código nuevo de la fuente entrara por la rama de pesos sin que nada avisara.
    """
    if volumen is None or moneda_cotizacion is None:
        return None
    declarada = moneda_cotizacion.upper()
    if declarada in MONEDAS_EN_DOLARES:
        return volumen
    if declarada == MONEDA_EN_PESOS:
        return cambio.a_dolares(volumen, en_dolares=False)
    return None


def _texto(valor: object) -> str | None:
    """Un texto de la fuente, recortado, o `None`. No se importa `_texto` de `segmentacion`: es
    privado de ese módulo."""
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    return limpio or None


def _entero(valor: object) -> int | None:
    """`operaciones` como entero, o `None`. Reusa `a_numero` para manejar `Decimal` y `NaN`."""
    numero = a_numero(valor)
    return None if numero is None else int(numero)


def _fecha_iso(valor: object) -> str | None:
    """`perfil_capturado_en` llega de un `timestamptz` como `datetime`, no como texto."""
    return valor.isoformat() if isinstance(valor, datetime) else None


def armar_renta_variable(
    filas: list[dict[str, Any]], cambio: TipoDeCambio
) -> list[EspecieRentaVariable]:
    """Las filas crudas de `leer_renta_variable`, convertidas en especies con variación y USD.

    **El agrupamiento se hace sobre el universo entero de renta variable, no por clase.** Una
    especie sólo se declara variante si su base existe, así que filtrar acciones y CEDEARs por
    separado antes de agrupar dejaría sin base a cualquier papel cuyas especies estuvieran
    repartidas entre las dos clases.
    """
    tickers = {str(f["ticker"]) for f in filas}
    grupos = agrupar(tickers)
    precios = {str(f["ticker"]): a_numero(f.get("lastPrice")) for f in filas}
    monedas = {str(f["ticker"]): _texto(f.get("moneda_cotizacion")) for f in filas}
    # El mercado tiene la última palabra: un grupo cuyo cociente no se parece a ningún tipo de
    # cambio se desarma (`BBD` es Banco Bradesco, no Blackberry en MEP).
    grupos, _alertados = aplicar_contraste(
        grupos, verificar(grupos, precios, monedas, cambio.valor)
    )

    especies: list[EspecieRentaVariable] = []
    for fila in filas:
        precio = a_numero(fila.get("lastPrice"))
        cierre_anterior = a_numero(fila.get("cierre_anterior"))
        volumen = a_numero(fila.get("effectiveVolume"))
        moneda = _texto(fila.get("moneda_cotizacion"))
        especies.append(
            EspecieRentaVariable(
                ticker=str(fila["ticker"]),
                clase_activo=str(fila["clase_activo"]),
                precio=precio,
                moneda_cotizacion=moneda,
                cierre_anterior=cierre_anterior,
                variacion=variacion_diaria(precio, cierre_anterior),
                volumen=volumen,
                volumen_usd=volumen_en_dolares(cambio, volumen, moneda),
                px_bid=a_numero(fila.get("px_bid")),
                px_ask=a_numero(fila.get("px_ask")),
                operaciones=_entero(fila.get("operaciones")),
                fuente=_texto(fila.get("fuente")),
                emision=grupos[str(fila["ticker"])].emision,
                sufijo_liquidacion=grupos[str(fila["ticker"])].sufijo_liquidacion,
                hermanas=hermanas(grupos, str(fila["ticker"])),
                no_identificado=grupos[str(fila["ticker"])].no_identificado,
                nombre_corto=_texto(fila.get("nombre_corto")),
                nombre_largo=_texto(fila.get("nombre_largo")),
                sector=_texto(fila.get("sector")),
                industria=_texto(fila.get("industria")),
                pais=_texto(fila.get("pais")),
                perfil_fuente=_texto(fila.get("perfil_fuente")),
                perfil_capturado_en=_fecha_iso(fila.get("perfil_capturado_en")),
            )
        )
    return especies
