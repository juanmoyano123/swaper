"""GWT-2 de la spec y las reglas de normalización que la sostienen.

`claude-docs/planning/plan.md:260-299`: "la moneda de cotización queda en USD por el campo
declarado, y en ningún punto del código se deriva del sufijo del ticker". Los tickers usados acá
llevan sufijos que "parecen" indicar moneda (D de dólares, C de pesos) a propósito: si algún día
alguien agrega una inferencia por sufijo, estos tests la delatan.
"""

from app.ingesta.byma.normalizacion import normalizar_fila_indice, normalizar_fila_rueda
from app.ingesta.cobertura import medir_cobertura


def test_la_moneda_sale_de_denomination_ccy_y_no_del_sufijo_del_ticker() -> None:
    fila_con_sufijo_enganoso = normalizar_fila_rueda({"symbol": "XXXD", "denominationCcy": "ARS"})
    fila_sin_sufijo = normalizar_fila_rueda({"symbol": "PNDC", "denominationCcy": "USD"})

    assert fila_con_sufijo_enganoso["moneda_cotizacion"] == "ARS"
    assert fila_sin_sufijo["moneda_cotizacion"] == "USD"


def test_sin_denomination_ccy_la_moneda_queda_vacia_y_cuenta_como_faltante() -> None:
    fila = normalizar_fila_rueda({"symbol": "AL30"})

    assert fila["moneda_cotizacion"] is None

    (cobertura,) = medir_cobertura([fila], ["moneda_cotizacion"])
    assert cobertura.presentes == 0
    assert cobertura.faltantes == 1


def test_los_tres_valores_observados_de_moneda_viajan_tal_cual() -> None:
    """ARS, USD y EXT: ninguno se traduce ni se mapea a MEP/CCL en esta feature (decisión 5)."""
    for valor in ("ARS", "USD", "EXT"):
        fila = normalizar_fila_rueda({"symbol": "X", "denominationCcy": valor})
        assert fila["moneda_cotizacion"] == valor


def test_un_cero_numerico_se_conserva_como_dato_no_como_faltante() -> None:
    """Un bono que no operó tiene monto cero: es dato, no un hueco."""
    fila = normalizar_fila_rueda({"symbol": "AL30", "volumeAmount": 0})

    assert fila["monto_operado"] == 0.0

    (cobertura,) = medir_cobertura([fila], ["monto_operado"])
    assert cobertura.presentes == 1
    assert cobertura.faltantes == 0


def test_un_campo_ausente_o_vacio_queda_none() -> None:
    fila = normalizar_fila_rueda({"symbol": "AL30", "maturityDate": ""})

    assert fila["precio_cierre"] is None, "closingPrice ni siquiera vino en el crudo"
    assert fila["vencimiento"] is None, "una cadena vacía es la forma en que la fuente dice 'no sé'"


def test_un_string_donde_se_esperaba_un_numero_queda_none() -> None:
    """No se adivina: un valor no numérico donde iba un número no se intenta convertir."""
    fila = normalizar_fila_rueda({"symbol": "AL30", "closingPrice": "no disponible"})

    assert fila["precio_cierre"] is None


def test_settlement_type_viaja_tal_cual_sin_traducir() -> None:
    fila_1 = normalizar_fila_rueda({"symbol": "AL30", "settlementType": "1"})
    fila_2 = normalizar_fila_rueda({"symbol": "GD30", "settlementType": "2"})

    assert fila_1["plazo_liquidacion"] == "1"
    assert fila_2["plazo_liquidacion"] == "2"


def test_los_campos_crudos_fuera_del_mapeo_no_viajan_en_la_fila_canonica() -> None:
    """openInterest, tickDirection, etc. quedan fuera a propósito: sumarlos después es aditivo."""
    fila = normalizar_fila_rueda({"symbol": "AL30", "openInterest": 999, "tickDirection": "up"})

    assert "openInterest" not in fila
    assert "tickDirection" not in fila


def test_normaliza_una_fila_de_index_price() -> None:
    fila = normalizar_fila_indice(
        {
            "symbol": "IDD",
            "description": "Índice Dólar",
            "price": 1234.5,
            "previousClosingPrice": 1230.0,
            "variation": 0.37,
            "isRate": False,
        }
    )

    assert fila["indice"] == "IDD"
    assert fila["valor"] == 1234.5
    assert fila["cierre_anterior"] == 1230.0
    assert fila["es_tasa"] is False


def test_index_price_sin_valor_cuenta_como_faltante_en_la_cobertura() -> None:
    fila = normalizar_fila_indice({"symbol": "IDD"})

    (cobertura,) = medir_cobertura([fila], ["valor"])
    assert cobertura.faltantes == 1
