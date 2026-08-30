"""Los GWT de F-007 (`claude-docs/planning/plan.md:406-423`), sobre la función pura que decide todo.

No hay base ni red en este archivo: `armar_consolidacion` recibe filas y devuelve filas, así que
las cuatro reglas que la spec pide verificar se pueden mirar de frente. Lo que se prueba no es que
los datos viajen, es que **no** viajen cuando no corresponde: que la TIR de una especie no aparezca
en su hermana, y que lo que ninguna fuente declara quede vacío en vez de estimado.

Los GWT que verificaban la herencia por raíz desde el informe de IAMC se fueron con esa ingesta el
26/08/2026. Lo que queda de ellos es la mitad que sigue viva: los atributos de emisión viajan
`None` y el COALESCE del upsert conserva lo persistido, que se prueba en
`test_consolidacion_persistencia.py`.
"""

from datetime import date

import pytest

from app.ingesta.alertas import CODIGO_CAMPO_SIN_COBERTURA, Severidad
from app.ingesta.byma.cliente import ENDPOINTS_ESPECIES
from app.ingesta.byma.normalizacion import normalizar_fila_rueda
from app.ingesta.consolidacion.armado import (
    CODIGO_ESPECIE_REPETIDA,
    ORDEN_DESEMPATE_ENDPOINTS,
    armar_consolidacion,
)
from app.ingesta.consolidacion.clasificacion import (
    CODIGO_CLASE_DISCREPANTE,
    CODIGO_CLASE_SIN_MAPEO,
)
from app.ingesta.consolidacion.metricas import (
    CODIGO_METRICAS_FUERA_DE_NATURALEZA,
    CODIGO_METRICAS_SIN_INSUMO,
)

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


def cashflow(
    ticker: str,
    tipo: str,
    payment_date=date(2027, 1, 1),
    *,
    capital: float = 0.0,
    residual_value: float | None = None,
) -> dict[str, object]:
    """`residual_value=None` (default) lo deriva de `capital`, coherente. Pasarlo explícito es
    para simular el caso real de fuente: 29 emisiones lo declaran clavado en 100 mientras
    amortizan (ver `test_calendario_cupones.py`)."""
    return {
        "ticker": ticker,
        "type": tipo,
        "payment_date": payment_date,
        "issue_date": date(2020, 1, 1),
        "capital": capital,
        "interest_rate": 5.0,
        "interest_amount": 2.5,
        "residual_value": (100.0 - capital) if residual_value is None else residual_value,
        "cash_flow": 2.5 + capital,
        "days_convention": "30/360",
    }


def por_ticker(filas):
    return {f["ticker"]: f for f in filas}


# --- GWT-1: las tres especies se clasifican por la raíz, cada una conserva lo suyo --------------


def test_las_tres_especies_se_clasifican_por_el_cronograma_de_su_raiz() -> None:
    """Clase y tipo de tasa siguen siendo de la emisión: salen del `type` del cronograma.

    Los atributos que traía IAMC —ley, moneda de pago, estructura de cupón— viajan `None` desde
    que se eliminó esa ingesta (26/08/2026). No es que se hayan perdido: la fila no los escribe y
    el COALESCE del upsert conserva lo que ya esté persistido.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie("AL30", moneda="ARS", ultimo=86320.0),
                especie("AL30D", moneda="USD", ultimo=56.7),
                especie("AL30C", moneda="EXT", ultimo=54.05),
            ]
        },
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    assert set(instrumentos) == {"AL30", "AL30D", "AL30C"}
    for ticker in ("AL30", "AL30D", "AL30C"):
        fila = instrumentos[ticker]
        assert fila["clase_activo"] == "bono_soberano"
        assert fila["tipo_tasa"] == "hard-dollar"
        assert fila["law"] is None
        assert fila["coupon_currency"] is None
        assert fila["estructura_cupon"] is None
        assert fila["revisar"] is False, "sin herencia no hay dos especies que se contradigan"


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
        filas_cashflow=[cashflow("AAL", "HARD_DOLLAR")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    assert instrumentos["AAL"]["clase_activo"] == "bono_soberano"
    assert instrumentos["AAL"]["tipo_tasa"] == "hard-dollar"
    assert instrumentos["AALD"]["clase_activo"] == "cedear"
    assert instrumentos["AALD"]["tipo_tasa"] is None, "un CEDEAR no tiene tasa"


# --- GWT-2: lo que BYMA trae y ninguna otra fuente declara --------------------------------------


def test_un_instrumento_entra_con_precio_y_sin_atributos_de_emision() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("YMCXO", ultimo=168500.0)]},
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


def test_un_campo_que_nadie_llena_se_declara_en_la_cobertura() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("YMCXO"), especie("PLC7O")]},
        filas_cashflow=[cashflow("YMCX", "ON"), cashflow("PLC7", "ON_TAMAR")],
    )

    assert len(resultado.filas_instrumentos) == 2
    assert all(f["law"] is None for f in resultado.filas_instrumentos)
    codigos = {a.codigo for a in resultado.alertas}
    assert CODIGO_CAMPO_SIN_COBERTURA in codigos, "un campo que nadie llenó tiene que declararse"


# --- GWT-3: la TIR es de la especie y de ninguna otra -------------------------------------------


def test_la_tir_de_una_especie_no_se_copia_a_sus_hermanas() -> None:
    """AL30 y AL30D son el mismo bono con precios en monedas distintas. Copiarla sería inventar.

    AL30D cotiza en dólares como paga su flujo, así que calcula su propia TIR. AL30 cotiza en
    pesos: **queda vacía**. Llenarla con la de su hermana pediría el tipo de cambio que se deriva
    de dividir una por la otra, o sea del propio bono — es el caso que esta invariante cuida desde
    F-007 y el que se volvió más filoso cuando se eliminó IAMC, porque antes había un número
    publicado ahí y ahora la celda vacía es la única alternativa a copiarla.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie("AL30", moneda="ARS", ultimo=86_320.0),
                especie("AL30D", moneda="USD", ultimo=56.7),
            ]
        },
        filas_cashflow=[
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2027, 1, 9)),
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2028, 1, 9)),
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2029, 1, 9), capital=100.0),
        ],
    )

    precios = por_ticker(resultado.filas_precios)
    assert precios["AL30"]["tir"] is None, "no se le copia la de AL30D ni con otro nombre"
    assert precios["AL30"]["fuente"] == "byma"
    assert precios["AL30D"]["tir"] is not None
    assert precios["AL30D"]["fuente"] == "byma+calculo"


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
    """Ninguna fuente la publica. Que quede nula en silencio sería el peor resultado."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
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


def test_el_subtipo_queda_vacio_porque_la_corrida_no_trae_la_ley() -> None:
    """Global o bonar se deriva de la ley, y la ley la traía IAMC — eliminado el 26/08/2026.

    No se lee la que ya está persistida para desempatar acá: quien re-deriva esta columna es F-009,
    que tiene el CSV curado. Derivarla de otra cosa sería completar por analogía (regla 1).
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("GD30"), especie("AL30")]},
        filas_cashflow=[cashflow("GD30", "HARD_DOLLAR"), cashflow("AL30", "HARD_DOLLAR")],
    )

    instrumentos = por_ticker(resultado.filas_instrumentos)
    assert instrumentos["GD30"]["subtipo"] is None
    assert instrumentos["AL30"]["subtipo"] is None


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


def test_un_plazo_sin_cotizacion_no_le_gana_al_plazo_que_si_cotizo() -> None:
    """El plazo 2 gana entre dos cotizaciones, no entre una cotización y un hueco.

    Es la fila que aparece desde que el cliente pide el panel completo (`EXCLUIR_SIN_COTIZACION` en
    `byma/cliente.py`): BYMA declara la especie en los dos plazos y sólo uno operó. Caso real
    medido el 27/08/2026 — BYZ1X trae 160.200 en plazo 1 y todo en cero en plazo 2, y con el
    criterio anterior ganaba la de plazo 2 y la especie salía publicada sin precio. Eran 52 tickers.
    La metadata no depende de cuál gane: verificado que ninguno de los 4.018 tickers repetidos del
    panel completo difiere en moneda ni en vencimiento entre sus filas.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie("BYZ1X", plazo="1", ultimo=160200.0, monto=1602000000.0),
                especie("BYZ1X", plazo="2", ultimo=0.0, monto=0.0),
            ]
        },
        filas_cashflow=[cashflow("BYZ1X", "HARD_DOLLAR")],
    )

    (instrumento,) = resultado.filas_instrumentos
    (precio,) = resultado.filas_precios
    assert precio["last_price"] == 160200.0
    assert instrumento["plazo_liquidacion"] == "1", "se guarda el plazo de la cotización elegida"
    assert instrumento["moneda_cotizacion"] == "ARS"
    assert instrumento["maturity"] == date(2030, 7, 9)


def test_sin_cotizacion_en_ningun_plazo_sigue_ganando_el_plazo_estandar() -> None:
    """Una especie que no operó en ninguno de los dos plazos entra igual, con su metadata.

    Es el caso que el panel completo agrega de a miles: la moneda y el vencimiento los publica
    BYMA y se guardan igual. La fila de precios, en cambio, no se inserta (ver
    `test_un_ticker_declarado_sin_ningun_precio_no_genera_fila_de_precios`): sin ningún campo de
    precio no hay nada que persistir, y no persistir es lo que deja sobrevivir el último precio
    bueno de una corrida anterior en vez de pisarlo con una fila vacía (30/08/2026).
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [
                especie("PS38C", moneda="EXT", plazo="1", ultimo=0.0, monto=0.0),
                especie("PS38C", moneda="EXT", plazo="2", ultimo=0.0, monto=0.0),
            ]
        },
        filas_cashflow=[],
    )

    (instrumento,) = resultado.filas_instrumentos
    assert instrumento["plazo_liquidacion"] == "2"
    assert instrumento["moneda_cotizacion"] == "EXT", "código propietario, se guarda sin traducir"
    assert instrumento["maturity"] == date(2030, 7, 9)
    assert resultado.filas_precios == [], "sin ningún precio no hay fila que insertar"


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


def test_el_desempate_entre_endpoints_sigue_el_orden_declarado_y_no_el_alfabetico() -> None:
    """BUN26 estaba en `negociable-obligations` el 17/08 y en `lebacs` el 28/08.

    Por abecedario ganaría `lebacs` —que no declara clase— y la ON pasaría a clasificarse por
    cronograma o a quedar afuera. `ORDEN_DESEMPATE_ENDPOINTS` lo pone último justamente para eso.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "lebacs": [especie("BUN26")],
            "negociable-obligations": [especie("BUN26")],
        },
        filas_cashflow=[],
    )

    (instrumento,) = resultado.filas_instrumentos
    assert instrumento["clase_activo"] == "on_corporativo", "gana el panel con clase propia"
    assert any(a.codigo == CODIGO_ESPECIE_REPETIDA for a in resultado.alertas)


def test_el_orden_de_desempate_cubre_los_endpoints_de_especies() -> None:
    """Un endpoint fuera de la tupla haría estallar `.index()` en `_colapsar` a mitad de corrida."""
    assert set(ENDPOINTS_ESPECIES) == set(ORDEN_DESEMPATE_ENDPOINTS)
    assert ORDEN_DESEMPATE_ENDPOINTS[-1] == "lebacs", "el panel sin clase propia va último"


# --- Panel de letras (`lebacs`, 28/08/2026) ----------------------------------------------------


def test_una_letra_del_tesoro_del_panel_entra_con_subtipo_letra() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"lebacs": [especie("S31G6")]},
        filas_cashflow=[cashflow("S31G6", "FIXED_RATE")],
    )

    (instrumento,) = resultado.filas_instrumentos
    assert instrumento["clase_activo"] == "bono_soberano"
    assert instrumento["subtipo"] == "letra"


def test_una_letra_subsoberana_del_mismo_panel_no_lleva_subtipo() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"lebacs": [especie("BA26T")]},
        filas_cashflow=[cashflow("BA26T", "SUB_SOBERANO_TAMAR")],
    )

    (instrumento,) = resultado.filas_instrumentos
    assert instrumento["clase_activo"] == "bono_subsoberano"
    assert instrumento["subtipo"] is None, "una letra provincial no es una letra del Tesoro"


def test_un_bopreal_lleva_subtipo_bopreal() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("BPOA7")]},
        filas_cashflow=[cashflow("BPOA7", "BOPREAL")],
    )

    (instrumento,) = resultado.filas_instrumentos
    assert instrumento["subtipo"] == "bopreal"


def test_una_especie_sb_del_panel_queda_fuera_del_universo_con_su_punta_guardada() -> None:
    """SENEBI: su ticker no cruza el cronograma por raíz, así que no hay clase que declararle.

    Es el mismo destino que ya tenían las variantes C/D/X/Y/Z, y no un filtro nuevo: nadie mira el
    sufijo `.SB`. Lo que se prueba es que no se pierda la punta ni el faltante.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"lebacs": [especie("S31G6.SB")]},
        filas_cashflow=[cashflow("S31G6", "FIXED_RATE")],
    )

    assert resultado.filas_instrumentos == []
    (punta,) = resultado.filas_puntas
    assert punta["ticker"] == "S31G6.SB"
    assert punta["px_bid"] == 99.0
    assert any(a.codigo == CODIGO_CLASE_SIN_MAPEO for a in resultado.alertas)


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
    """Un cero no es un precio — pero acá SÍ hay algo que persistir: el cierre de ayer.

    `previousClosingPrice=100.0` es la única señal de precio de esta fila; con eso alcanza para
    que la fila de precios se inserte, y adentro `last_price` queda vacío por el cero, no por la
    ausencia total de datos (ese otro caso, con bid/ask también en cero, es
    `test_un_ticker_declarado_sin_ningun_precio_no_genera_fila_de_precios`, donde ni precios ni
    puntas se insertan).
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [
                especie(
                    "PLC7O",
                    ultimo=0.0,
                    monto=0.0,
                    bidPrice=0.0,
                    offerPrice=0.0,
                    previousClosingPrice=100.0,
                )
            ]
        },
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    assert resultado.filas_precios[0]["last_price"] is None
    # El volumen sí conserva el cero: "no operó" es información sobre el instrumento.
    assert resultado.filas_precios[0]["effective_volume"] == 0.0


def test_un_ticker_declarado_sin_ningun_precio_no_genera_fila_de_precios() -> None:
    """El hallazgo del 30/08/2026: BYMA declaró MGCOC/MGCRC/YM34C en la rueda pre-apertura sin un
    solo campo de precio, y como la fila SÍ se insertaba (vacía, con `capturado_en` de ahora),
    `sql_poda` la tomaba como la más nueva del ticker y borraba la corrida anterior que sí tenía
    precio bueno — perdiendo un dato real por uno vacío.

    Sin ningún campo de precio (ni hoy, ni cierre de ayer, ni OHLC) no se inserta fila: el ticker
    queda "ausente" a ojos de la poda, que es el mismo mecanismo que ya protege a una especie que
    el panel dejó de declarar del todo. `effective_volume` no participa de esta condición — ver
    `test_un_precio_en_cero_es_una_especie_que_no_opero_y_no_un_precio` para el caso con volumen
    en cero pero con una señal de precio real.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [
                especie("PLC7O", ultimo=0.0, monto=0.0, bidPrice=0.0, offerPrice=0.0)
            ]
        },
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    assert resultado.filas_precios == []
    assert resultado.filas_puntas == []
    # El instrumento se sigue clasificando igual: lo que no se persiste es sólo el precio del día.
    assert resultado.filas_instrumentos[0]["ticker"] == "PLC7O"


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


# --- Las métricas que se fueron con IAMC (26/08/2026) -------------------------------------------


def test_una_especie_sin_calculo_propio_queda_vacia_y_no_arrastra_nada() -> None:
    """YMCXO no declara moneda de flujo comparable: no se calcula, y ya no hay de dónde arrastrar.

    Hasta el 26/08/2026 esta fila conservaba lo del último informe de IAMC rotulado con su
    `fecha_metricas`. El arrastre se fue con la ingesta: la fila declara el faltante en vez de
    publicar la TIR de un día al lado del precio de otro.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("YMCXO", ultimo=157000.0)]},
        filas_cashflow=[cashflow("YMCX", "ON")],
    )

    (precio,) = resultado.filas_precios
    assert precio["tir"] is None
    assert precio["fecha_metricas"] is None
    assert precio["last_price"] == 157000.0, "el precio sí es el de esta corrida"
    assert precio["fuente"] == "byma"


def test_la_convexidad_se_escribe_vacia_y_no_se_omite() -> None:
    """Era la única columna que sólo IAMC publicaba y el cálculo propio no produce.

    Omitirla del dict la dejaría con lo que hubiera de antes, porque el upsert usa COALESCE: una
    convexidad de agosto seguiría publicándose al lado de un precio de hoy.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [especie("PLC7O", moneda="USD", ultimo=60.0)]
        },
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    (precio,) = resultado.filas_precios
    assert "convexidad" in precio
    assert precio["convexidad"] is None


# --- Residual y valor técnico, calculados (relevamiento de confiabilidad de datos, 16/08/2026) --


def test_el_residual_sale_del_cronograma_y_no_del_ultimo_valor_declarado() -> None:
    """PLC7O ya amortizó 40 antes de hoy, así que su residual vigente es 60 y no el 100 inicial.

    Es cálculo propio sobre el cronograma contractual, igual que tir/duration/paridad desde F-051:
    no depende de que alguna fuente lo publique, que es lo que lo dejó en pie cuando se eliminó
    IAMC.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [especie("PLC7O", moneda="USD", ultimo=60.0)]
        },
        filas_cashflow=[
            cashflow("PLC7", "ON", payment_date=date(2026, 1, 1), capital=40.0),
            cashflow("PLC7", "ON", payment_date=date(2027, 1, 1), capital=0.0),
        ],
    )

    (precio,) = resultado.filas_precios
    assert precio["residual_value"] == pytest.approx(60.0)
    assert precio["valor_tecnico"] is not None


def test_el_residual_se_calcula_aunque_quede_fuera_del_calculo_por_moneda_cruzada() -> None:
    """AL30 en pesos con flujo en dólares no calcula tir ni paridad (moneda cruzada), pero el
    residual es contractual —no depende de en qué moneda cotiza la especie— y se calcula igual."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [especie("AL30", moneda="ARS", ultimo=86_320.0)]},
        filas_cashflow=[
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2026, 1, 1), capital=25.0),
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2029, 1, 9)),
        ],
    )

    (precio,) = resultado.filas_precios
    assert precio["tir"] is None and precio["paridad"] is None, "sigue sin tir ni paridad"
    assert precio["residual_value"] == pytest.approx(75.0), "pero el residual sí se calcula"
    assert precio["valor_tecnico"] is not None


def test_un_residual_incoherente_queda_vacio_y_se_alerta() -> None:
    """El caso real (29 de 816 tickers): la fuente declara el residual clavado en 100 después de
    un pago que sí amortizó. Regla 1 — se prefiere vacío antes que un valor técnico sobreestimado.
    """
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "negociable-obligations": [especie("BDC33", moneda="USD", ultimo=60.0)]
        },
        filas_cashflow=[
            cashflow(
                "BDC33", "ON", payment_date=date(2026, 1, 1), capital=33.33, residual_value=100.0
            ),
            cashflow(
                "BDC33", "ON", payment_date=date(2027, 1, 1), capital=0.0, residual_value=100.0
            ),
        ],
    )

    (precio,) = resultado.filas_precios
    assert precio["residual_value"] is None
    assert precio["valor_tecnico"] is None
    alerta = next(a for a in resultado.alertas if a.codigo == CODIGO_METRICAS_SIN_INSUMO)
    assert "BDC33" in alerta.detalle["por_motivo"]["residual_contradictorio"]


def test_sin_cronograma_el_residual_no_se_inventa() -> None:
    """Una especie sin cronograma no tiene de dónde derivar el residual: queda vacío, no en 100."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("SINCRO")]},
        filas_cashflow=[],
    )

    (precio,) = resultado.filas_precios
    assert precio["residual_value"] is None
    assert precio["valor_tecnico"] is None


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


# --- Experimento data912: `origen_precio` viaja hasta `fuente`, en precios y en puntas -----------


def test_un_arrastre_de_data912_con_calculo_se_rotula_data912_arrastre_mas_calculo() -> None:
    """El overlay pisa `precio_ultimo` y setea `origen_precio` antes de que esto corra — acá se
    simula directamente sobre la `FilaRueda`, que es el contrato entre los dos módulos."""
    fila_pisada = {
        **especie("AL30D", moneda="USD", ultimo=56.7),
        "origen_precio": "data912-arrastre",
    }

    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [fila_pisada]},
        filas_cashflow=[
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2027, 1, 9)),
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2028, 1, 9)),
            cashflow("AL30", "HARD_DOLLAR", payment_date=date(2029, 1, 9), capital=100.0),
        ],
    )

    (precio,) = resultado.filas_precios
    assert precio["tir"] is not None, "el arrastre se calcula igual: sábado con cierre del viernes"
    assert precio["fuente"] == "data912-arrastre+calculo"


def test_una_fila_sin_origen_precio_sigue_dando_byma() -> None:
    """El default de `_fuente_de` no cambió: una fila que el overlay no tocó sigue siendo byma."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
        filas_cashflow=[cashflow("PLC7", "ON")],
    )

    assert resultado.filas_precios[0]["fuente"] == "byma"


def test_la_punta_conserva_el_origen_precio_incluido_el_sufijo_arrastre() -> None:
    fila_pisada = {**especie("AFCHD", moneda="USD"), "origen_precio": "data912-arrastre"}

    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [fila_pisada]},
    )

    (punta,) = resultado.filas_puntas
    assert punta["fuente"] == "data912-arrastre", (
        "si no operó, la fecha del libro es tan desconocida como la del precio"
    )


def test_la_punta_de_un_ticker_no_pisado_sigue_siendo_byma() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"negociable-obligations": [especie("PLC7O")]},
    )

    assert resultado.filas_puntas[0]["fuente"] == "byma"


# --- El OHLC de BYMA que se descartaba ----------------------------------------------------------


def test_los_ohlc_de_byma_llegan_a_la_fila_de_precios() -> None:
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie(
                    "AL30",
                    ultimo=86320.0,
                    openingPrice=86000.0,
                    tradingHighPrice=86500.0,
                    tradingLowPrice=85800.0,
                    vwap=86210.5,
                )
            ]
        },
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    (precio,) = resultado.filas_precios
    assert precio["precio_apertura"] == 86000.0
    assert precio["precio_maximo"] == 86500.0
    assert precio["precio_minimo"] == 85800.0
    assert precio["vwap"] == 86210.5


def test_un_ohlc_en_cero_se_guarda_como_ausente() -> None:
    """Mismo criterio que `last_price`: un 0 no es un precio, es que la especie no operó."""
    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={
            "public-bonds": [
                especie(
                    "AL30",
                    openingPrice=0.0,
                    tradingHighPrice=0.0,
                    tradingLowPrice=0.0,
                    vwap=0.0,
                )
            ]
        },
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    (precio,) = resultado.filas_precios
    assert precio["precio_apertura"] is None
    assert precio["precio_maximo"] is None
    assert precio["precio_minimo"] is None
    assert precio["vwap"] is None


def test_un_precio_de_data912_no_inventa_ohlc() -> None:
    """El overlay pisa precio/puntas/operaciones, nunca el OHLC (no está en `CAMPOS_PISADOS`): una
    fila cuyo precio vino de data912 tiene que quedar sin apertura/máximo/mínimo/VWAP, no heredar
    el de BYMA de otra sesión ni inventarlos."""
    fila_pisada = {**especie("AL30", ultimo=86320.0), "origen_precio": "data912"}

    resultado = armar_consolidacion(
        hoy=HOY,
        especies_por_endpoint={"public-bonds": [fila_pisada]},
        filas_cashflow=[cashflow("AL30", "HARD_DOLLAR")],
    )

    (precio,) = resultado.filas_precios
    assert precio["fuente"].startswith("data912")
    assert precio["precio_apertura"] is None
    assert precio["precio_maximo"] is None
    assert precio["precio_minimo"] is None
    assert precio["vwap"] is None
