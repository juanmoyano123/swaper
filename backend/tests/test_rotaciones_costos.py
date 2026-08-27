"""El costo real de rotar — F-035, `app/rotaciones/costos.py`.

Paridad numérica contra `tools/mercado.py::costo_rotacion` (mismo patrón que
`test_rotaciones_paridad_motor.py` con `detectar_swaps.py`), y la divergencia deliberada: un
spread faltante en el CLI da un costo "piso"; acá da `verificable=False` y el costo entero es
`None` — no se asume un spread por defecto (regla 1/11 del dominio).
"""

import sys
from pathlib import Path

import pytest

from app.rotaciones.constantes import ARANCEL_POR_PATA, MAX_RELACION_PUNTAS
from app.rotaciones.costos import calcular_costo, spread_pct

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _costo_rotacion_cli():
    sys.path.insert(0, str(RAIZ_REPO / "tools"))
    import mercado

    return mercado.costo_rotacion


# --- `spread_pct` -------------------------------------------------------------------------------


def test_spread_pct_con_las_dos_puntas_vivas() -> None:
    assert spread_pct(98.0, 102.0) == pytest.approx(4.0)


def test_spread_pct_con_punta_faltante_es_none() -> None:
    assert spread_pct(None, 102.0) is None
    assert spread_pct(98.0, None) is None
    assert spread_pct(None, None) is None


def test_spread_pct_con_bid_cero_o_negativo_es_none() -> None:
    assert spread_pct(0.0, 102.0) is None
    assert spread_pct(-5.0, 102.0) is None


def test_spread_pct_con_puntas_cruzadas_es_none() -> None:
    """`ask <= bid` no es un mercado válido, es una punta invertida o plana."""
    assert spread_pct(102.0, 102.0) is None
    assert spread_pct(102.0, 98.0) is None


def test_spread_pct_con_relacion_excesiva_es_none() -> None:
    """El caso documentado en `tools/mercado.py`: bid 125 / ask 127.000 son escalas distintas, no
    un spread real."""
    assert spread_pct(125.0, 127_000.0) is None
    assert pytest.approx(3.0) == MAX_RELACION_PUNTAS
    justo_al_borde = 100.0 * MAX_RELACION_PUNTAS
    assert spread_pct(100.0, justo_al_borde) is None  # relación == MAX_RELACION_PUNTAS: excluida
    assert spread_pct(100.0, justo_al_borde - 1.0) is not None


# --- Paridad contra `tools/mercado.py::costo_rotacion` -------------------------------------------


def test_total_pct_coincide_con_el_cli_con_las_dos_patas_vivas() -> None:
    costo_cli = _costo_rotacion_cli()
    spread_o_frac, spread_d_frac = 0.0123, 0.0087

    esperado = costo_cli(ARANCEL_POR_PATA, spread_o_frac, spread_d_frac) * 100
    resultado = calcular_costo(spread_o_frac * 100, spread_d_frac * 100, d_rend_pp=2.0)

    assert resultado.verificable is True
    assert resultado.total_pct == pytest.approx(esperado, abs=0.01)


def test_total_pct_es_dos_aranceles_mas_media_punta_de_cada_spread() -> None:
    resultado = calcular_costo(spread_origen=1.0, spread_destino=2.0, d_rend_pp=1.0)

    arancel_pct = ARANCEL_POR_PATA * 100
    esperado = round(2 * arancel_pct + 1.0 / 2 + 2.0 / 2, 2)
    assert resultado.total_pct == pytest.approx(esperado)


# --- La divergencia deliberada contra el CLI ------------------------------------------------------


def test_con_un_spread_faltante_el_cli_da_un_piso_y_esto_da_no_verificable() -> None:
    costo_cli = _costo_rotacion_cli()
    spread_o_frac = 0.0123

    import pandas as pd

    piso_cli = costo_cli(ARANCEL_POR_PATA, spread_o_frac, pd.NA)
    assert piso_cli > 0  # el CLI sigue devolviendo un número: cuenta el faltante como cero

    resultado = calcular_costo(spread_o_frac * 100, None, d_rend_pp=2.0)
    assert resultado.verificable is False
    assert resultado.total_pct is None
    assert resultado.elevado is None
    assert resultado.payback_meses is None
    assert resultado.spread_origen_pct == pytest.approx(spread_o_frac * 100)
    assert resultado.spread_destino_pct is None


def test_sin_ninguna_punta_tambien_es_no_verificable() -> None:
    resultado = calcular_costo(None, None, d_rend_pp=2.0)

    assert resultado.verificable is False
    assert resultado.total_pct is None


# --- `elevado`: borde exacto del 5% ---------------------------------------------------------------


def test_elevado_en_el_borde_exacto_del_cinco_por_ciento() -> None:
    arancel_pct = ARANCEL_POR_PATA * 100  # 0.75
    # total_pct = 2*0.75 + s/2 + s/2 = 1.5 + s -> s = 3.5 da total exactamente 5.0
    spread_al_borde = 5.0 - 2 * arancel_pct

    en_el_borde = calcular_costo(spread_al_borde, spread_al_borde, d_rend_pp=1.0)
    apenas_arriba = calcular_costo(spread_al_borde + 0.02, spread_al_borde, d_rend_pp=1.0)

    assert en_el_borde.total_pct == pytest.approx(5.0)
    assert en_el_borde.elevado is False  # > 5, no >= 5
    assert apenas_arriba.elevado is True


# --- `payback_meses` -------------------------------------------------------------------------------


def test_payback_meses_con_d_rend_pp_no_positivo_es_none() -> None:
    assert calcular_costo(1.0, 1.0, d_rend_pp=0.0).payback_meses is None
    assert calcular_costo(1.0, 1.0, d_rend_pp=-0.5).payback_meses is None


def test_payback_meses_se_calcula_sobre_total_pct_y_d_rend_pp() -> None:
    resultado = calcular_costo(spread_origen=1.0, spread_destino=1.0, d_rend_pp=2.0)

    esperado = round(resultado.total_pct / 2.0 * 12, 1)  # type: ignore[operator]
    assert resultado.payback_meses == pytest.approx(esperado)
