"""Contrato de columnas del cashflow de Docta: las nueve obligatorias, el passthrough de las
extras y el tipado (huecos a `None`, ceros conservados).
"""

from datetime import date

import numpy as np
import pandas as pd

from app.ingesta.docta.normalizacion import (
    COLUMNAS_CONTRACTUALES,
    columnas_faltantes,
    normalizar_filas,
)

FILA_COMPLETA = {
    "ticker": "AL30",
    "type": "AMORT",
    "issue_date": pd.Timestamp("2020-09-04"),
    "payment_date": pd.Timestamp("2026-01-09"),
    "capital": 1.75,
    "interest_rate": 0.0125,
    "interest_amount": 0.0,
    "residual_value": 98.25,
    "cash_flow": 1.75,
    "days_convention": "30/360",
    "theoretical_payment_date": pd.Timestamp("2026-01-09"),
    "theoretical_days_before": 0,
}


def _df(filas: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(filas)


def test_las_nueve_columnas_contractuales_no_faltan_cuando_estan_todas() -> None:
    assert columnas_faltantes(_df([FILA_COMPLETA])) == []


def test_detecta_exactamente_las_columnas_contractuales_que_faltan() -> None:
    incompleta = {k: v for k, v in FILA_COMPLETA.items() if k not in ("capital", "cash_flow")}

    faltan = columnas_faltantes(_df([incompleta]))

    assert set(faltan) == {"capital", "cash_flow"}


def test_las_tres_columnas_no_documentadas_viajan_intactas() -> None:
    (fila,) = normalizar_filas(_df([FILA_COMPLETA]))

    assert fila["days_convention"] == "30/360"
    assert fila["theoretical_days_before"] == 0
    assert fila["theoretical_payment_date"] == pd.Timestamp("2026-01-09")


def test_ticker_y_type_quedan_como_texto_sin_espacios() -> None:
    fila = dict(FILA_COMPLETA)
    fila["ticker"] = "  AL30  "

    (normalizada,) = normalizar_filas(_df([fila]))

    assert normalizada["ticker"] == "AL30"


def test_las_fechas_de_pandas_se_convierten_a_date() -> None:
    (fila,) = normalizar_filas(_df([FILA_COMPLETA]))

    assert fila["issue_date"] == date(2020, 9, 4)
    assert fila["payment_date"] == date(2026, 1, 9)
    assert isinstance(fila["issue_date"], date)


def test_una_fecha_que_llega_como_texto_iso_tambien_se_convierte() -> None:
    """Verificado contra el feed real: `issue_date`/`payment_date` llegan como texto, no como
    datetime de pandas — pandas no siempre infiere el tipo de una columna de fechas ajena."""
    fila = dict(FILA_COMPLETA)
    fila["issue_date"] = "2020-09-04"
    fila["payment_date"] = "2026-01-09"

    (normalizada,) = normalizar_filas(_df([fila]))

    assert normalizada["issue_date"] == date(2020, 9, 4)
    assert normalizada["payment_date"] == date(2026, 1, 9)


def test_un_monto_que_llega_como_texto_con_el_escape_de_excel_se_limpia() -> None:
    """Verificado contra el feed real (06/08/2026): `capital` llega como texto en las 6.150 filas,
    y al menos un valor trae un retorno de carro incrustado que Excel escapa como `_x000D_`."""
    fila = dict(FILA_COMPLETA)
    fila["capital"] = "3.125_x000D_\n"

    (normalizada,) = normalizar_filas(_df([fila]))

    assert normalizada["capital"] == 3.125


def test_un_monto_que_llega_como_texto_limpio_tambien_se_convierte() -> None:
    fila = dict(FILA_COMPLETA)
    fila["capital"] = "0.0000"

    (normalizada,) = normalizar_filas(_df([fila]))

    assert normalizada["capital"] == 0.0


def test_nat_en_una_fecha_contractual_se_normaliza_a_none() -> None:
    fila = dict(FILA_COMPLETA)
    fila["payment_date"] = pd.NaT

    (normalizada,) = normalizar_filas(_df([fila]))

    assert normalizada["payment_date"] is None


def test_nan_en_un_monto_se_normaliza_a_none_pero_cero_se_conserva() -> None:
    fila = dict(FILA_COMPLETA)
    fila["residual_value"] = np.nan
    fila["interest_amount"] = 0.0

    (normalizada,) = normalizar_filas(_df([fila]))

    assert normalizada["residual_value"] is None
    assert normalizada["interest_amount"] == 0.0, "un pago de capital 0 en cupón puro es dato"


def test_normaliza_varias_filas_preservando_orden() -> None:
    fila_2 = dict(FILA_COMPLETA)
    fila_2["ticker"] = "GD30"

    filas = normalizar_filas(_df([FILA_COMPLETA, fila_2]))

    assert [f["ticker"] for f in filas] == ["AL30", "GD30"]


def test_las_nueve_claves_contractuales_estan_garantizadas_presentes() -> None:
    (fila,) = normalizar_filas(_df([FILA_COMPLETA]))

    assert set(COLUMNAS_CONTRACTUALES) <= fila.keys()
