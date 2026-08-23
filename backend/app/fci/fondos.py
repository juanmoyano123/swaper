"""Fondos comunes de inversión, tal como se muestran en el monitor — F-057. Dominio puro, probable
sin Postgres.

**Naturaleza propia, no comparable con nada de renta fija.** Un FCI no tiene TIR: tiene variación
de cuotaparte. La regla 2 del dominio prohíbe que comparta eje con una TIR en dólares, una tasa real
CER o una TNA en pesos, así que no entra a `NATURALEZA_TASA` de `app/universo/segmentacion.py` — es
una unidad aparte, declarada acá.

**El VCP viaja tal como la fuente lo publica: por cada mil cuotapartes.** No se divide por mil en
esta capa — dividir es una decisión de quien valúa una posición contra cuotapartes (F-046), no de
quien muestra el fondo en el monitor.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# La unidad de rendimiento de un FCI. No vive en `NATURALEZA_TASA` porque un FCI no pasa por
# `segmentar()`: no tiene tipo de tasa, así que nunca comparte esa función con la renta fija.
NATURALEZA_FCI = "variacion_cuotaparte"
NOMBRE_NATURALEZA_FCI = "Variación de cuotaparte"

# La propia fuente lo declara en el pie del reporte (verificado el 23/08/2026): un fondo que
# distribuyó utilidades tiene la variación subestimada frente a lo que de verdad rindió, y el
# asesor tiene que verlo junto a cualquier variación que se muestre.
ADVERTENCIA_DISTRIBUCION = (
    "Los rendimientos atribuidos en el informe a los distintos Fondos han sido calculados sin "
    "tener en consideración los pagos de distribución de utilidades que pudieran haber ocurrido."
)

# Centinelas de `Plazo Liq.` que no son un plazo interpretable: el espacio de "días para rescatar"
# va vacío para éstos, sin traducirlos a "no aplica" ni a "indefinido" (regla 11).
PLAZOS_NO_INTERPRETABLES = frozenset({999, 9999, 99999, -1})


def _numero(valor: object) -> float | None:
    """`Decimal` de asyncpg, `float` de un test, o `None`. Mismo criterio que `a_numero` de
    `app/universo/segmentacion.py`: no se intenta interpretar un string."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _entero(valor: object) -> int | None:
    numero = _numero(valor)
    return None if numero is None else int(numero)


def _texto(valor: object) -> str | None:
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    return limpio or None


def _fecha_iso(valor: object) -> str | None:
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return None


@dataclass(frozen=True, slots=True)
class FondoFci:
    """Un fondo×clase, tal como viaja al frontend."""

    codigo_cafci: str
    fondo: str
    codigo_cnv: str | None
    seccion: str
    tipo_renta: str
    moneda: str
    region: str | None
    horizonte: str | None

    fecha_vcp: str | None
    """`None` cuando la fuente no publicó fecha para esta fila (medido: 7 de 4.251)."""
    vcp: float | None
    """Por cada mil cuotapartes, tal como la fuente lo declara."""
    vcp_anterior: float | None

    var_diaria_pct: float | None
    var_mes_pct: float | None
    var_anio_pct: float | None
    var_12m_pct: float | None

    cuotapartes: float | None
    cuotapartes_anterior: float | None
    patrimonio: float | None
    patrimonio_anterior: float | None
    market_share: float | None

    gerente: str | None
    depositaria: str | None
    calificacion: str | None
    """`None` significa no informada: la fuente cubre el 47 % de los fondos."""
    calificado: str | None
    tipo_dinero: str | None

    comision_ingreso: float | None
    honorarios_adm_sg: float | None
    honorarios_adm_sd: float | None
    gastos_ord_gestion: float | None
    comision_rescate: float | None
    comision_transferencia: float | None
    honorarios_exito: float | None

    moneda_fondo: str | None
    """Columna "Moneda Fondo": distinta de `moneda` y puede no coincidir. Ver `discrepancia_moneda`."""
    plazo_liq: int | None
    """Crudo, con centinelas. Ver `dias_para_rescatar` para el valor interpretable."""
    minimo_inversion: float | None

    @property
    def discrepancia_moneda(self) -> bool:
        """`Moneda` y `Moneda Fondo` son columnas distintas de la planilla y no siempre coinciden.
        No se elige una como la correcta (regla 11): se declara la discrepancia."""
        return (
            self.moneda_fondo is not None
            and self.moneda_fondo.strip().upper() != self.moneda.strip().upper()
        )

    @property
    def dias_para_rescatar(self) -> int | None:
        """`plazo_liq`, salvo que sea un centinela sin traducción posible: ahí es `None`, no 0 ni
        "no aplica"."""
        if self.plazo_liq is None or self.plazo_liq in PLAZOS_NO_INTERPRETABLES:
            return None
        return self.plazo_liq

    def como_dict(self) -> dict[str, object]:
        return {
            "codigo_cafci": self.codigo_cafci,
            "fondo": self.fondo,
            "codigo_cnv": self.codigo_cnv,
            "seccion": self.seccion,
            "tipo_renta": self.tipo_renta,
            "naturaleza": NATURALEZA_FCI,
            "naturaleza_nombre": NOMBRE_NATURALEZA_FCI,
            "moneda": self.moneda,
            "region": self.region,
            "horizonte": self.horizonte,
            "fecha_vcp": self.fecha_vcp,
            "vcp": self.vcp,
            "vcp_anterior": self.vcp_anterior,
            "var_diaria_pct": self.var_diaria_pct,
            "var_mes_pct": self.var_mes_pct,
            "var_anio_pct": self.var_anio_pct,
            "var_12m_pct": self.var_12m_pct,
            "cuotapartes": self.cuotapartes,
            "cuotapartes_anterior": self.cuotapartes_anterior,
            "patrimonio": self.patrimonio,
            "patrimonio_anterior": self.patrimonio_anterior,
            "market_share": self.market_share,
            "gerente": self.gerente,
            "depositaria": self.depositaria,
            "calificacion": self.calificacion,
            "calificado": self.calificado,
            "tipo_dinero": self.tipo_dinero,
            "comision_ingreso": self.comision_ingreso,
            "honorarios_adm_sg": self.honorarios_adm_sg,
            "honorarios_adm_sd": self.honorarios_adm_sd,
            "gastos_ord_gestion": self.gastos_ord_gestion,
            "comision_rescate": self.comision_rescate,
            "comision_transferencia": self.comision_transferencia,
            "honorarios_exito": self.honorarios_exito,
            "moneda_fondo": self.moneda_fondo,
            "discrepancia_moneda": self.discrepancia_moneda,
            "plazo_liq": self.plazo_liq,
            "dias_para_rescatar": self.dias_para_rescatar,
            "minimo_inversion": self.minimo_inversion,
            "advertencia_distribucion": ADVERTENCIA_DISTRIBUCION,
        }


def fondo_de_fila(fila: dict[str, Any]) -> FondoFci:
    """Una fila cruda de `public.fci` (de asyncpg o de un test), convertida a `FondoFci`."""
    return FondoFci(
        codigo_cafci=str(fila["codigo_cafci"]),
        fondo=str(fila["fondo"]),
        codigo_cnv=_texto(fila.get("codigo_cnv")),
        seccion=str(fila["seccion"]),
        tipo_renta=str(fila["tipo_renta"]),
        moneda=str(fila["moneda"]),
        region=_texto(fila.get("region")),
        horizonte=_texto(fila.get("horizonte")),
        fecha_vcp=_fecha_iso(fila.get("fecha_vcp")),
        vcp=_numero(fila.get("vcp")),
        vcp_anterior=_numero(fila.get("vcp_anterior")),
        var_diaria_pct=_numero(fila.get("var_diaria_pct")),
        var_mes_pct=_numero(fila.get("var_mes_pct")),
        var_anio_pct=_numero(fila.get("var_anio_pct")),
        var_12m_pct=_numero(fila.get("var_12m_pct")),
        cuotapartes=_numero(fila.get("cuotapartes")),
        cuotapartes_anterior=_numero(fila.get("cuotapartes_anterior")),
        patrimonio=_numero(fila.get("patrimonio")),
        patrimonio_anterior=_numero(fila.get("patrimonio_anterior")),
        market_share=_numero(fila.get("market_share")),
        gerente=_texto(fila.get("gerente")),
        depositaria=_texto(fila.get("depositaria")),
        calificacion=_texto(fila.get("calificacion")),
        calificado=_texto(fila.get("calificado")),
        tipo_dinero=_texto(fila.get("tipo_dinero")),
        comision_ingreso=_numero(fila.get("comision_ingreso")),
        honorarios_adm_sg=_numero(fila.get("honorarios_adm_sg")),
        honorarios_adm_sd=_numero(fila.get("honorarios_adm_sd")),
        gastos_ord_gestion=_numero(fila.get("gastos_ord_gestion")),
        comision_rescate=_numero(fila.get("comision_rescate")),
        comision_transferencia=_numero(fila.get("comision_transferencia")),
        honorarios_exito=_numero(fila.get("honorarios_exito")),
        moneda_fondo=_texto(fila.get("moneda_fondo")),
        plazo_liq=_entero(fila.get("plazo_liq")),
        minimo_inversion=_numero(fila.get("minimo_inversion")),
    )


def planilla_como_dict(fila: dict[str, Any] | None) -> dict[str, object] | None:
    """El singleton `fci_planilla`, o `None` si la ingesta nunca corrió."""
    if fila is None:
        return None
    return {
        "fecha_planilla": _fecha_iso(fila.get("fecha_planilla")),
        "fecha_cierre_anterior": _fecha_iso(fila.get("fecha_cierre_anterior")),
        "fecha_base_mes": _fecha_iso(fila.get("fecha_base_mes")),
        "fecha_base_anio": _fecha_iso(fila.get("fecha_base_anio")),
        "fecha_base_12m": _fecha_iso(fila.get("fecha_base_12m")),
        "total_filas": fila.get("total_filas"),
        "capturado_en": (
            fila["capturado_en"].isoformat()
            if isinstance(fila.get("capturado_en"), datetime)
            else None
        ),
        "advertencia_distribucion": ADVERTENCIA_DISTRIBUCION,
    }
