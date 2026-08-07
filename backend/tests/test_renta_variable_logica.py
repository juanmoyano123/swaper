"""Los GWT de F-052 sobre la lógica pura de renta variable, sin Postgres.

`variacion_diaria` y `volumen_en_dolares` viven en `app/renta_variable/especies.py` y no importan
nada del universo ni de la base — se prueban con valores a mano, igual que `cambio.py` prueba su
propia matemática.
"""

import pytest

from app.renta_variable.especies import armar_renta_variable, variacion_diaria, volumen_en_dolares
from app.universo.cambio import TipoDeCambio

# --- variacion_diaria: GWT-3, nunca se estima ----------------------------------------------------


def test_variacion_con_los_dos_datos_es_el_cociente() -> None:
    assert variacion_diaria(103.1, 100.0) == pytest.approx(0.031)


def test_variacion_sin_cierre_anterior_es_none() -> None:
    assert variacion_diaria(103.1, None) is None


def test_variacion_sin_precio_es_none() -> None:
    assert variacion_diaria(None, 100.0) is None


def test_variacion_con_cierre_anterior_no_positivo_es_none() -> None:
    """Un cierre en cero no es un cierre válido, y dividir por él no produciría una variación real
    (sería una variación inventada, no calculada)."""
    assert variacion_diaria(103.1, 0.0) is None


# --- volumen_en_dolares: GWT-2, nunca cae a la regla del sufijo ----------------------------------


def test_volumen_ars_se_divide_por_el_tipo_de_cambio() -> None:
    cambio = TipoDeCambio(valor=1000.0, pares=25)
    assert volumen_en_dolares(cambio, 1_500_000.0, "ARS") == pytest.approx(1_500.0)


def test_volumen_usd_se_conserva_tal_cual() -> None:
    cambio = TipoDeCambio(valor=1000.0, pares=25)
    assert volumen_en_dolares(cambio, 2_000.0, "USD") == 2_000.0


def test_volumen_sin_moneda_declarada_es_none_y_no_cae_al_sufijo_del_ticker() -> None:
    """Es la diferencia con la renta fija: acá no hay regla de sufijo D/C que completar por
    analogía."""
    cambio = TipoDeCambio(valor=1000.0, pares=25)
    assert volumen_en_dolares(cambio, 1_500_000.0, None) is None


def test_volumen_ars_sin_tipo_de_cambio_del_dia_es_none_y_no_el_crudo() -> None:
    cambio = TipoDeCambio()  # sin valor: menos de MIN_PARES_FX pares, FX no disponible
    assert volumen_en_dolares(cambio, 1_500_000.0, "ARS") is None


# --- armar_renta_variable: GWT-1, sin rendimiento, sin naturaleza, sin segmento -------------------


def test_como_dict_no_tiene_rendimiento_ni_naturaleza_ni_segmento() -> None:
    filas = [
        {
            "ticker": "GGAL",
            "clase_activo": "accion",
            "lastPrice": 5000.0,
            "effectiveVolume": 1_500_000_000.0,
            "cierre_anterior": 4850.0,
            "moneda_cotizacion": "ARS",
            "px_bid": 4995.0,
            "px_ask": 5005.0,
            "operaciones": 120,
        }
    ]
    (especie,) = armar_renta_variable(filas, TipoDeCambio())
    cuerpo = especie.como_dict()
    assert "rendimiento" not in cuerpo
    assert "naturaleza" not in cuerpo
    assert "segmento" not in cuerpo
    assert cuerpo["ticker"] == "GGAL"
    assert cuerpo["variacion"] == pytest.approx((5000.0 - 4850.0) / 4850.0)
