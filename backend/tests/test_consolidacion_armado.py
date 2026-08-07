"""Los GWT de F-007 (`claude-docs/planning/plan.md:406-423`), sobre la función pura que decide todo.

No hay base ni red en este archivo: `armar_consolidacion` recibe filas y devuelve filas, así que
las cuatro reglas que la spec pide verificar se pueden mirar de frente. Lo que se prueba no es que
los datos viajen, es que **no** viajen cuando no corresponde: que la TIR de una especie no aparezca
en su hermana, que un atributo contradictorio no se propague, y que lo que ninguna fuente declara
quede vacío en vez de estimado.
"""

from datetime import date

import pytest

from app.ingesta.alertas import CODIGO_CAMPO_SIN_COBERTURA, Severidad
from app.ingesta.byma.normalizacion import normalizar_fila_rueda
from app.ingesta.consolidacion.armado import (
    CODIGO_ESPECIE_REPETIDA,
    CODIGO_HERENCIA_CONTRADICTORIA,
    armar_consolidacion,
)
from app.ingesta.consolidacion.clasificacion import (
    CODIGO_CLASE_DISCREPANTE,
    CODIGO_CLASE_SIN_MAPEO,
)
from app.ingesta.consolidacion.metricas import (
    CODIGO_METRICAS_FUERA_DE_NATURALEZA,
)
from app.ingesta.iamc.parser import FilaInforme

FECHA_INFORME = date(2026, 8, 5)

# El día de la corrida. Fijo, porque de él dependen los corridos y los plazos al descuento.
HOY = date(2026, 8, 7)


# --- Fábricas de filas -------------------------------------------------------------------------


def especie(ticker: str, *, moneda="ARS", plazo="2", ultimo=100.0, monto=1000.0, **extra):
    """Fila de BYMA con las claves crudas, pasada por el normalizador real de F-004."""
    crudo = {
        "symbol": ticker,
        "denominationCcy": moneda,
        "settlementType": plazo,
        "trade": ultimo,
        "volumeAmount": monto,
        "bidPrice": 99.0,
        "offerPrice": 101.0,
        "numberOfOrders": 5,
        "maturityDate": "2030-07-09",
        **extra,
    }
    return normalizar_fila_rueda(crudo)


def informe(ticker: str, **overrides) -> FilaInforme:
    """Fila de IAMC con los campos que la consolidación mira; el resto en su valor vacío."""
    base = dict.fromkeys(FilaInforme.__annotations__)
    base.update(
        {
            "ticker": ticker,
            "seccion": "DEUDA CORPORATIVA EN USD - LEY ARG",
            "fecha_informe": date(2026, 8, 5),
            "emisor": "YPF S.A.",
            "ley": "Ley Argentina",
            "moneda_pago": "USD",
            "estructura_cupon": "Tasa Fija",
            "tir": 7.92,
            "paridad_pct": 98.5,
            "duracion_modificada": 6.7,
            "convexidad": 0.55,
            "valor_residual": 100.0,
        }
    )
    base.update(overrides)
    return base  # type: ignore[return-value]


def cashflow(
    ticker: str, tipo: str, payment_date=date(2027, 1, 1), *, capital: float = 0.0
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "type": tipo,
        "payment_date": payment_date,
        "issue_date": date(2020, 1, 1),
        "capital": capital,
        "interest_rate": 5.0,
        "interest_amount": 2.5,
        "residual_value": 100.0 - capital,
        "cash_flow": 2.5 + capital,
        "days_convention": "30/360",
    }


def por_ticker(filas):
    return {f["ticker"]: f for f in filas}


# --- GWT-1: las tres especies heredan de la raíz, cada una conserva lo suyo ---------------------


def test_las_tres_especies_heredan_los_atributos_de_la_emision() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie("AL30", moneda="ARS", ultimo=86320.0),
                especie("AL30D", moneda="USD", ultimo=56.7),
                especie("AL30C", moneda="EXT", ultimo=54.05),
            ]
        },
        filas_iamc=[informe("AL30", ley="Ley Argentina", moneda_pago="USD")],
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    assert set(instrumentos) == {"AL30", "AL30D", "AL30C"}
    for ticker in ("AL30", "AL30D", "AL30C"):
        fila = instrumentos[ticker]
        assert fila["law"] == "Ley Argentina", f"{ticker} no heredó la ley de la emisión"
        assert fila["coupon_currency"] == "USD"
        assert fila["estructura_cupon"] == "Tasa Fija"
        assert fila["clase_activo"] == "bono_soberano"
        assert fila["tipo_tasa"] == "hard-dollar"


def test_cada_especie_conserva_su_precio_su_punta_y_su_moneda() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie("AL30", moneda="ARS", ultimo=86320.0),
                especie("AL30D", moneda="USD", ultimo=56.7),
                especie("AL30C", moneda="EXT", ultimo=54.05),
            ]
        },
        filas_iamc=[informe("AL30")],
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    precios = por_ticker(resultado.filas_precios)

    assert instrumentos["AL30"]["moneda_cotizacion"] == "ARS"
    assert instrumentos["AL30D"]["moneda_cotizacion"] == "USD"
    assert instrumentos["AL30C"]["moneda_cotizacion"] == "EXT"
    assert precios["AL30"]["last_price"] == 86320.0
    assert precios["AL30D"]["last_price"] == 56.7
    assert len(resultado.filas_puntas) == 3


def test_un_cedear_no_hereda_de_un_bono_que_comparte_raiz() -> None:
    """AALD es la especie MEP de un CEDEAR y comparte raíz con un bono. No tienen nada que ver."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [especie("AAL")],
            "cedears": [especie("AALD")],
        },
        filas_iamc=[informe("AAL", ley="Ley N.Y.")],
        filas_cashflow=[cashflow("AAL", "HARD_DOLLAR")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    assert instrumentos["AAL"]["law"] == "Ley N.Y."
    assert instrumentos["AALD"]["clase_activo"] == "cedear"
    assert instrumentos["AALD"]["law"] is None, "propagar entre familias inventa un dato"
    assert instrumentos["AALD"]["tipo_tasa"] is None, "un CEDEAR no tiene tasa"


# --- GWT-2: lo que BYMA trae y IAMC no ---------------------------------------------------------


def test_un_instrumento_ausente_del_informe_queda_con_precio_y_sin_atributos() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("YMCXO", ultimo=168500.0)]},
        filas_iamc=[informe("PLC7O")],
        filas_cashflow=[cashflow("YMCX", "ON"), cashflow("PLC7", "ON")],
    )

    (instrumento,) = resultado.filas_instrumentos
    (precio,) = resultado.filas_precios
    assert instrumento["ticker"] == "YMCXO"
    assert instrumento["law"] is None
    assert instrumento["coupon_currency"] is None
    assert precio["last_price"] == 168500.0
    assert resultado.filas_puntas[0]["px_bid"] == 99.0

    cobertura = {c.campo: c for c in resultado.cobertura}
    assert cobertura["law"].faltantes == 1
    assert cobertura["coupon_currency"].faltantes == 1
    assert cobertura["last_price"].presentes == 1


def test_sin_informe_el_universo_entra_completo_pero_sin_atributos_de_emision() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("YMCXO"), especie("PLC7O")]},
        filas_iamc=None,
        filas_cashflow=[cashflow("YMCX", "ON"), cashflow("PLC7", "ON_TAMAR")],
    )

    assert len(resultado.filas_instrumentos) == 2
    assert all(f["law"] is None for f in resultado.filas_instrumentos)
    codigos = {a.codigo for a in resultado.alertas}
    assert CODIGO_CAMPO_SIN_COBERTURA in codigos, "un campo que nadie llenó tiene que declararse"


# --- GWT-3: la TIR es de IAMC y sólo del ticker que IAMC nombra ---------------------------------


def test_la_tir_se_persiste_desde_el_informe_y_la_fuente_lo_registra() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
        filas_iamc=[informe("PLC7O", tir=7.92, paridad_pct=98.5, duracion_modificada=6.7)],
        filas_cashflow=[cashflow("PLC7", "ON")],
        fecha_informe=FECHA_INFORME,
    )

    (precio,) = resultado.filas_precios
    # El contrato del Resumen guarda la TIR en fracción y IAMC la publica en puntos porcentuales.
    assert precio["tir"] == pytest.approx(0.0792)
    assert precio["paridad"] == pytest.approx(0.985)
    assert precio["duration"] == 6.7, "la duración ya viene en años, no se convierte"
    assert precio["residual_value"] == 100.0, "el valor residual ya viene en base 100"
    assert precio["fuente"] == "byma+iamc"


def test_la_tir_de_una_especie_no_se_copia_a_sus_hermanas() -> None:
    """AL30 y AL30D tienen TIR distintas: el precio está en otra moneda. Copiarla sería inventar.

    Con F-051 la invariante se prueba más fuerte que antes. AL30D cotiza en dólares como paga su
    flujo, así que **calcula** su propia TIR; AL30 cotiza en pesos y conserva la de IAMC. Que los
    dos números existan y sean distintos es la prueba de que ninguno viajó de una especie a la otra.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie("AL30", moneda="ARS", ultimo=86_320.0),
                especie("AL30D", moneda="USD", ultimo=56.7),
            ]
        },
        filas_iamc=[informe("AL30", tir=7.92)],
        filas_cashflow=[
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2027, 1, 9)),
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2028, 1, 9)),
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2029, 1, 9), capital=100.0),
        ],
        fecha_informe=FECHA_INFORME,
    )

    precios = por_ticker(resultado.filas_precios)
    # La especie en pesos no se calcula —su flujo está en dólares— y conserva lo publicado.
    assert precios["AL30"]["tir"] == pytest.approx(0.0792)
    assert precios["AL30"]["fuente"] == "byma+iamc"
    # La especie en dólares calcula la suya, contra su propio precio.
    assert precios["AL30D"]["tir"] is not None
    assert precios["AL30D"]["tir"] != pytest.approx(0.0792), "no es la de IAMC con otro nombre"
    # Sin `iamc` en la fuente: IAMC nombra a AL30, no a AL30D, y esta fila no le debe nada.
    assert precios["AL30D"]["fuente"] == "byma+calculo"
    # Pero la ley sí se hereda: es de la emisión, no de la especie.
    assert por_ticker(resultado.filas_instrumentos)["AL30D"]["law"] == "Ley Argentina"


def test_una_especie_que_cotiza_en_otra_moneda_que_su_flujo_no_se_calcula() -> None:
    """La regla que gobierna el cálculo: sin precio y flujo en la misma moneda no hay rendimiento,
    y el tipo de cambio que haría falta saldría de la propia emisión — o sea, de la hermana."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("AL30", moneda="ARS", ultimo=86_320.0)]},
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR", payment_date=date(2029, 1, 9))],
    )

    (precio,) = resultado.filas_precios
    assert precio["tir"] is None and precio["paridad"] is None
    assert precio["fuente"] == "byma"
    alerta = next(a for a in resultado.alertas if a.codigo == CODIGO_METRICAS_FUERA_DE_NATURALEZA)
    assert "AL30" in alerta.detalle["por_motivo"]["moneda_cruzada"]["tickers"]


def test_la_tna_queda_vacia_y_se_declara() -> None:
    """Ninguna fuente de F-007 la publica. Que quede nula en silencio sería el peor resultado."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
        filas_iamc=[informe("PLC7O")],
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    assert resultado.filas_precios[0]["tna"] is None
    sin_cobertura = [a for a in resultado.alertas if a.codigo == CODIGO_CAMPO_SIN_COBERTURA]
    assert any(a.detalle["campo"] == "tna" for a in sin_cobertura)


# --- Clasificación y exclusiones ---------------------------------------------------------------


def test_un_bono_publico_sin_cronograma_no_entra_pero_su_punta_si() -> None:
    """Es el caso de AL30X. `puntas` no tiene FK justamente para no perder este dato."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("AL30"), especie("AL30X", ultimo=12345.0)]},
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    assert [f["ticker"] for f in resultado.filas_instrumentos] == ["AL30"]
    assert [f["ticker"] for f in resultado.filas_precios] == ["AL30"]
    assert {f["ticker"] for f in resultado.filas_puntas} == {"AL30", "AL30X"}

    (alerta,) = [a for a in resultado.alertas if a.codigo == CODIGO_CLASE_SIN_MAPEO]
    assert alerta.detalle["especies"] == 1
    assert alerta.severidad is Severidad.ADVERTENCIA


def test_una_on_cuyo_cronograma_declara_otra_clase_se_declara_y_conserva_la_del_endpoint() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("RAROO")]},
        filas_cashflow=[cashflow("RAROO", "SUB_SOBERANO")],
    )

    (instrumento,) = resultado.filas_instrumentos
    assert instrumento["clase_activo"] == "on_corporativo"
    assert any(a.codigo == CODIGO_CLASE_DISCREPANTE for a in resultado.alertas)


def test_los_soberanos_reciben_emisor_y_sector_por_definicion() -> None:
    """No son datos que falten: la clase ya los determina, igual que en el motor viejo."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("AL30"), especie("BA37D")]},
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR"), cashflow("BA37", "SUB_SOBERANO")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    assert instrumentos["AL30"]["underlying"] == "Gobierno Argentino"
    assert instrumentos["AL30"]["sector"] == "Soberano"
    assert instrumentos["BA37D"]["sector"] == "Subsoberano"
    assert instrumentos["BA37D"]["underlying"] is None, "una provincia no es el Tesoro"


def test_el_subtipo_se_deriva_cuando_hay_ley() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("GD30"), especie("AL30")]},
        filas_iamc=[
            informe("GD30", ley="Ley N.Y."),
            informe("AL30", ley="Ley Argentina"),
        ],
        filas_cashflow=[cashflow("GD30", "HARD_DOLLAR"), cashflow("AL30", "HARD_DOLLAR")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    assert instrumentos["GD30"]["subtipo"] == "global"
    assert instrumentos["AL30"]["subtipo"] == "bonar"


# --- Colapso por plazo -------------------------------------------------------------------------


def test_una_especie_en_dos_plazos_entra_una_sola_vez_y_queda_marcada() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie("AL30", plazo="1", ultimo=86320.0, monto=165561479768.4),
                especie("AL30", plazo="2", ultimo=86350.0, monto=73719164497.9),
            ]
        },
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    (instrumento,) = resultado.filas_instrumentos
    (precio,) = resultado.filas_precios
    assert instrumento["duplicado"] is True
    assert instrumento["plazo_liquidacion"] == "2", "el plazo estándar de liquidación gana"
    assert precio["last_price"] == 86350.0
    assert len(resultado.filas_puntas) == 1, "la PK de puntas es (ticker, capturado_en)"


def test_a_igualdad_de_plazo_gana_la_que_mas_opero() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie("AL30", plazo="2", ultimo=1.0, monto=10.0),
                especie("AL30", plazo="2", ultimo=2.0, monto=999.0),
            ]
        },
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    assert resultado.filas_precios[0]["last_price"] == 2.0


def test_una_especie_que_solo_cotiza_en_un_plazo_no_se_marca_duplicada() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("AL30", plazo="1")]},
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    assert resultado.filas_instrumentos[0]["duplicado"] is False


def test_una_especie_en_dos_endpoints_se_declara() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "general-equity": [especie("GGAL")],
            "leading-equity": [especie("GGAL")],
        },
    )

    assert len(resultado.filas_instrumentos) == 1
    assert any(a.codigo == CODIGO_ESPECIE_REPETIDA for a in resultado.alertas)


# --- Herencia contradictoria -------------------------------------------------------------------


def test_dos_especies_de_la_misma_emision_con_leyes_distintas_no_propagan_ninguna() -> None:
    """No se elige una por cuenta propia. Vaciar lo ya guardado es tarea de F-009, no de acá."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O"), especie("PLC7D")]},
        filas_iamc=[
            informe("PLC7O", ley="Ley Argentina", moneda_pago="USD"),
            informe("PLC7D", ley="Ley N.Y.", moneda_pago="USD"),
        ],
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    assert all(f["law"] is None for f in instrumentos.values()), "no se eligió una de las dos"
    assert all(f["coupon_currency"] == "USD" for f in instrumentos.values()), (
        "el campo que sí coincide se propaga igual"
    )
    assert all(f["revisar"] is True for f in instrumentos.values())
    assert any(a.codigo == CODIGO_HERENCIA_CONTRADICTORIA for a in resultado.alertas)


# --- Cronograma --------------------------------------------------------------------------------


def test_el_cronograma_viaja_con_las_nueve_columnas_del_contrato() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
        filas_cashflow=[cashflow("PLC7O", "ON")],
    )

    (fila,) = resultado.filas_cashflow
    assert set(fila) == {
        "ticker",
        "type",
        "issue_date",
        "payment_date",
        "capital",
        "interest_rate",
        "interest_amount",
        "residual_value",
        "cash_flow",
    }
    assert "days_convention" not in fila, "las passthrough no tienen semántica declarada"


def test_un_cronograma_no_usable_se_propaga_como_none_y_no_como_lista_vacia() -> None:
    """El contrato de F-006: `None` significa conservar lo persistido, no borrarlo."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
        filas_cashflow=None,
    )

    assert resultado.filas_cashflow is None
    assert resultado.filas_instrumentos[0]["tipo_tasa"] is None, (
        "sin cronograma no hay tipo de tasa"
    )


# --- Ceros y vacíos ----------------------------------------------------------------------------


def test_un_precio_en_cero_es_una_especie_que_no_opero_y_no_un_precio() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [
                especie("PLC7O", ultimo=0.0, monto=0.0, bidPrice=0.0, offerPrice=0.0)
            ]
        },
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    assert resultado.filas_precios[0]["last_price"] is None
    assert resultado.filas_puntas[0]["px_bid"] is None
    # El volumen sí conserva el cero: "no operó" es información sobre el instrumento.
    assert resultado.filas_precios[0]["effective_volume"] == 0.0


def test_un_vencimiento_ilegible_queda_vacio_y_se_alerta() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [especie("PLC7O", maturityDate="30/07/2030")]
        },
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    assert resultado.filas_instrumentos[0]["maturity"] is None
    assert any("vencimientos" in a.mensaje for a in resultado.alertas)


def test_una_especie_sin_ticker_se_descarta_y_se_cuenta() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"cedears": [especie("AAPL"), normalizar_fila_rueda({})]},
    )

    assert len(resultado.filas_instrumentos) == 1
    assert any("sin symbol" in a.mensaje for a in resultado.alertas)


def test_el_vencimiento_de_byma_se_parsea_a_fecha() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("AL30", maturityDate="2030-07-09")]},
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    assert resultado.filas_instrumentos[0]["maturity"] == date(2030, 7, 9)


# --- Métricas de IAMC entre corridas ------------------------------------------------------------


def test_las_metricas_viajan_rotuladas_con_la_fecha_de_su_informe() -> None:
    """`capturado_en` fecha el precio de BYMA; `fecha_metricas`, el informe del que salió la TIR."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
        filas_iamc=[informe("PLC7O", tir=7.92)],
        filas_cashflow=[cashflow("PLC7", "ON")],
        fecha_informe=FECHA_INFORME,
    )

    assert resultado.filas_precios[0]["fecha_metricas"] == date(2026, 8, 5)


def test_sin_informe_se_conservan_las_metricas_conocidas_con_su_fecha() -> None:
    """Sin esto la vista publicaría un universo sin TIR en cuanto una corrida no traiga informe,
    que es exactamente lo que hace un refresco intra-rueda."""
    previas = {
        "PLC7O": {
            "tir": 0.0792,
            "duration": 6.7,
            "paridad": 0.985,
            "convexidad": 0.55,
            "residual_value": 100.0,
            "fecha_metricas": FECHA_INFORME,
        }
    }
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O", ultimo=157000.0)]},
        filas_iamc=None,
        filas_cashflow=[cashflow("PLC7", "ON")],
        metricas_previas=previas,
    )

    (precio,) = resultado.filas_precios
    assert precio["tir"] == 0.0792
    assert precio["fecha_metricas"] == date(2026, 8, 5), "la fila dice de qué informe salió"
    assert precio["last_price"] == 157000.0, "el precio sí es el de esta corrida"
    assert precio["fuente"] == "byma+iamc"


def test_el_informe_de_hoy_le_gana_a_lo_conservado() -> None:
    previas = {"PLC7O": {"tir": 0.05, "fecha_metricas": date(2026, 8, 4)}}
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
        filas_iamc=[informe("PLC7O", tir=7.92)],
        filas_cashflow=[cashflow("PLC7", "ON")],
        fecha_informe=date(2026, 8, 5),
        metricas_previas=previas,
    )

    (precio,) = resultado.filas_precios
    assert precio["tir"] == pytest.approx(0.0792)
    assert precio["fecha_metricas"] == date(2026, 8, 5)


def test_nunca_se_retrocede_a_una_metrica_mas_vieja_que_la_publicada() -> None:
    """Si alguien sube un informe atrasado, el universo no puede volver para atrás en silencio."""
    previas = {"PLC7O": {"tir": 0.0792, "fecha_metricas": date(2026, 8, 5)}}
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
        filas_iamc=[informe("PLC7O", tir=5.0)],
        filas_cashflow=[cashflow("PLC7", "ON")],
        fecha_informe=date(2026, 8, 1),
        metricas_previas=previas,
    )

    (precio,) = resultado.filas_precios
    assert precio["tir"] == 0.0792
    assert precio["fecha_metricas"] == date(2026, 8, 5)


def test_una_especie_sin_metricas_ni_previas_queda_vacia() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("YMCXO")]},
        filas_cashflow=[cashflow("YMCX", "ON")],
    )

    (precio,) = resultado.filas_precios
    assert precio["tir"] is None
    assert precio["fecha_metricas"] is None
    assert precio["fuente"] == "byma"


# --- Cierre anterior (F-052) -------------------------------------------------------------------


def test_el_cierre_anterior_de_byma_se_persiste_en_precios() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [especie("PLC7O", previousClosingPrice=100.0)]
        },
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    assert resultado.filas_precios[0]["cierre_anterior"] == 100.0


def test_un_cierre_anterior_en_cero_no_es_un_precio_y_queda_vacio() -> None:
    """Misma semántica que `last_price`: un cero no es un cierre, es que no operó (`_precio`)."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [especie("PLC7O", previousClosingPrice=0.0)]
        },
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    assert resultado.filas_precios[0]["cierre_anterior"] is None
