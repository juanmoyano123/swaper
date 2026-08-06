"""Canario contra la fuente real de BYMA. Marcado `integration`, fuera de la corrida por defecto.

Si BYMA cambia de forma otra vez (como pasó entre el 05 y el 06/08/2026, cuando la ficha original
resultó ser tamaños de página) o si el certificado deja de validar, este test lo dice. Una corrida
muda de la suite no lo detectaría: los tests con respx sólo prueban que el cliente hace lo correcto
con lo que se le da, no que lo que se le da siga siendo cierto.
"""

import pytest

from app.ingesta.byma.ingesta import ingerir_rueda


@pytest.mark.integration
async def test_la_fuente_real_responde_y_el_snapshot_queda_completo() -> None:
    resultado = await ingerir_rueda()

    assert resultado.snapshot.total_filas > 3000
    assert set(resultado.snapshot.filas_por_tramo) == {
        "negociable-obligations",
        "public-bonds",
        "cedears",
        "general-equity",
        "leading-equity",
        "index-price",
    }
    assert resultado.snapshot.filas_por_tramo["index-price"] == 16
    # public-bonds es el caso que la ficha original tenía mal: 1106 filas, no 189.
    assert resultado.snapshot.filas_por_tramo["public-bonds"] > 1000
    # El panel líder es chico y es el que faltaba: sin él no hay ALUA, BBAR, BMA ni GGAL.
    assert resultado.snapshot.filas_por_tramo["leading-equity"] > 30
    lideres = {f["ticker"] for f in resultado.especies_por_endpoint["leading-equity"]}
    assert {"ALUA", "BBAR", "BMA"} <= lideres
