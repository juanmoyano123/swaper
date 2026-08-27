"""Qué especie entra al cálculo propio y cuál no — F-051, la parte que decide el dominio.

`test_calendario_metricas.py` prueba que el número esté bien calculado. Acá se prueba lo otro: que
se calcule **sólo donde corresponde**. La tabla por naturaleza de tasa, la regla de que el precio y
el flujo compartan moneda, y que todo lo que queda afuera salga nombrado en una alerta en vez de
desaparecer.

El caso que más importa vuelve a ser el que no calcula nada: un bono CER tiene precio, cronograma y
todo lo que hace falta para que el solver devuelva un número — y ese número sería una tasa nominal
presentada donde va una real.
"""

from datetime import date

import pytest

from app.calendario.metricas import MetricasEspecie
from app.ingesta.byma.normalizacion import normalizar_fila_rueda
from app.ingesta.consolidacion.armado import armar_consolidacion
from app.ingesta.consolidacion.metricas import (
    CODIGO_METRICAS_FUERA_DE_NATURALEZA,
    CODIGO_METRICAS_SIN_INSUMO,
    FUENTE_CALCULO,
    FUENTE_FUERA,
    MOTIVO_MONEDA_CRUZADA,
    MOTIVO_NATURALEZA_DESCONOCIDA,
    MOTIVO_SIN_TIPO_TASA,
    ResultadoMetricas,
    fuente_de_metricas,
)

HOY = date(2026, 8, 7)


def especie(ticker: str, *, moneda="USD", ultimo=56.7, **extra):
    crudo = {
        "symbol": ticker,
        "denominationCcy": moneda,
        "settlementType": "2",
        "trade": ultimo,
        "volumeAmount": 1000.0,
        "bidPrice": 99.0,
        "offerPrice": 101.0,
        "numberOfOrders": 5,
        "maturityDate": "2030-07-09",
        **extra,
    }
    return normalizar_fila_rueda(crudo)


def cronograma(ticker: str, tipo: str) -> list[dict[str, object]]:
    """Tres pagos futuros con amortización al final: alcanza para que el solver resuelva."""
    return [
        {
            "ticker": ticker,
            "type": tipo,
            "payment_date": fecha,
            "issue_date": date(2020, 1, 1),
            "capital": capital,
            "interest_rate": 5.0,
            "interest_amount": 2.5,
            "residual_value": 100.0 - capital,
            "cash_flow": 2.5 + capital,
        }
        for fecha, capital in (
            (date(2027, 1, 9), 0.0),
            (date(2028, 1, 9), 0.0),
            (date(2029, 1, 9), 100.0),
        )
    ]


def armar(**kwargs):
    kwargs.setdefault("hoy", HOY)
    return armar_consolidacion(**kwargs)


def alerta_con(resultado, codigo):
    return next((a for a in resultado.alertas if a.codigo == codigo), None)


class TestQuienSeCalcula:
    """La tabla de decisión, una fila por naturaleza de tasa."""

    @pytest.mark.parametrize(
        ("tipo_tasa", "moneda", "esperado"),
        [
            ("hard-dollar", "USD", FUENTE_CALCULO),
            # `EXT` pasó de `calculo` a `fuera` el 08/08/2026 con la regla 11: para dividir el
            # precio por el flujo hay que saber que están en la misma moneda, y BYMA no documenta
            # qué denota ese código. Cuesta 63 de las 276 hard-dollar calculables del universo real.
            ("hard-dollar", "EXT", FUENTE_FUERA),
            ("hard-dollar", "ARS", FUENTE_FUERA),
            ("bopreal", "USD", FUENTE_CALCULO),
            ("bopreal", "EXT", FUENTE_FUERA),
            ("tasa-fija", "ARS", FUENTE_CALCULO),
            ("tasa-fija", "USD", FUENTE_FUERA),
            ("cer", "ARS", FUENTE_FUERA),
            ("dollar-linked", "ARS", FUENTE_FUERA),
            ("badlar", "ARS", FUENTE_FUERA),
            ("tamar", "ARS", FUENTE_FUERA),
            # Sin tipo de tasa no hay unidad en la que reportar. Hasta el 26/08/2026 esto era
            # `iamc` —había una fuente publicando por estas especies— y con la ingesta eliminada
            # pasa a `fuera`, que es lo que las hace aparecer nombradas en la alerta.
            (None, "ARS", FUENTE_FUERA),
        ],
    )
    def test_la_tabla_por_naturaleza(self, tipo_tasa, moneda, esperado) -> None:
        assert fuente_de_metricas(tipo_tasa, moneda) == esperado

    def test_una_naturaleza_desconocida_queda_fuera_en_vez_de_improvisar(self) -> None:
        assert fuente_de_metricas("uva-plus-plus", "ARS") == FUENTE_FUERA

    def test_sin_moneda_declarada_no_se_calcula(self) -> None:
        """La moneda se lee, no se deduce del sufijo: hay especies con D declaradas en pesos."""
        assert fuente_de_metricas("hard-dollar", None) == FUENTE_FUERA


class TestUnBonoCerNoSeCalcula:
    """GWT-5, el caso que la regla 2 protege."""

    def test_queda_fuera_y_la_alerta_dice_por_que(self) -> None:
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("TX26", moneda="ARS", ultimo=1500.0)]},
            filas_cashflow=cronograma("TX26", "CER"),
        )

        (precio,) = resultado.filas_precios
        assert precio["tir"] is None, "descontar el flujo sin ajuste daría una tasa nominal"
        assert precio["paridad"] is None

        alerta = alerta_con(resultado, CODIGO_METRICAS_FUERA_DE_NATURALEZA)
        assert alerta is not None
        detalle = alerta.detalle["por_motivo"]["cer"]
        assert detalle["tickers"] == ["TX26"]
        assert "coeficiente CER" in detalle["porque"]

    def test_no_se_le_reporta_la_tasa_de_otra_naturaleza(self) -> None:
        """Ni siquiera cuando el solver tendría todo para devolver un número.

        Precio, cronograma y monedas coincidentes: al solver no le falta nada para resolver. Lo
        que falta es el coeficiente CER, y sin él el número que saldría sería una tasa nominal
        puesta donde va una real. La fila lo declara sin atribuirse un cálculo que no hizo.
        """
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("TX26", moneda="ARS", ultimo=1500.0)]},
            filas_cashflow=cronograma("TX26", "CER"),
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is None
        assert "calculo" not in precio["fuente"]


class TestFaltaDeInsumo:
    """GWT-3: el campo queda vacío y la especie sale nombrada."""

    def test_sin_cronograma_la_especie_queda_nombrada(self) -> None:
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=cronograma("GD30", "HARD_DOLLAR"),
        )
        # Sin cronograma propio no se clasifica y no llega a precios: lo declara la alerta de clase.
        assert resultado.filas_precios == []

    def test_sin_precio_del_dia_queda_vacia_y_nombrada(self) -> None:
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D", ultimo=0.0)]},
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
        )

        (precio,) = resultado.filas_precios
        assert precio["last_price"] is None, "un precio de cero es que no operó"
        assert precio["tir"] is None
        alerta = alerta_con(resultado, CODIGO_METRICAS_SIN_INSUMO)
        assert alerta is not None
        assert alerta.detalle["por_motivo"]["sin_precio"] == ["AL30D"]

    def test_un_bono_vencido_se_declara_vencido(self) -> None:
        pagos = [
            {
                "ticker": "AL30",
                "type": "HARD_DOLLAR",
                "payment_date": date(2025, 1, 9),
                "issue_date": date(2020, 1, 1),
                "capital": 100.0,
                "interest_rate": 5.0,
                "interest_amount": 2.5,
                "residual_value": 0.0,
                "cash_flow": 102.5,
            }
        ]
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=pagos,
        )
        alerta = alerta_con(resultado, CODIGO_METRICAS_SIN_INSUMO)
        assert alerta is not None
        assert alerta.detalle["por_motivo"]["vencida"] == ["AL30D"]


class TestPrecedencia:
    def test_lo_que_no_se_calcula_queda_vacio_y_declarado(self) -> None:
        """AL30 cotiza en pesos y paga en dólares: no se descuenta una punta contra la otra.

        Hasta el 26/08/2026 esta fila mostraba la TIR que publicaba IAMC y se rotulaba
        `byma+iamc`. Sin esa fuente la celda queda vacía y la especie sale nombrada en la alerta:
        no se le copia la métrica de AL30D, que es la misma emisión pero otro precio.
        """
        resultado = armar(
            especies_por_endpoint={
                "public-bonds": [especie("AL30", moneda="ARS", ultimo=86_320.0)]
            },
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is None
        assert precio["fuente"] == "byma"

        alerta = alerta_con(resultado, CODIGO_METRICAS_FUERA_DE_NATURALEZA)
        assert alerta is not None
        assert alerta.detalle["por_motivo"][MOTIVO_MONEDA_CRUZADA]["tickers"] == ["AL30"]

    def test_la_convexidad_quedo_sin_fuente(self) -> None:
        """La publicaba IAMC y nadie más: el cálculo propio no la produce (26/08/2026).

        La columna sigue existiendo y la fila la escribe explícitamente en `None`. Si la omitiera,
        el upsert la dejaría con lo que hubiera de antes y una convexidad de agosto seguiría
        publicándose al lado de un precio de hoy.
        """
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is not None, "la TIR sí se calcula: es la convexidad la que no tiene"
        assert precio["convexidad"] is None
        assert precio["fecha_metricas"] is None

    def test_la_tna_sigue_sin_fuente(self) -> None:
        """El solver devuelve efectiva anual; pasarla a nominal exige una convención inventada."""
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=cronograma("AL30", "HARD_DOLLAR"),
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is not None
        assert precio["tna"] is None


class TestCronogramaPersistido:
    def test_una_corrida_sin_docta_calcula_igual_con_el_cronograma_guardado(self) -> None:
        """El cronograma es contractual y no envejece; el precio sigue siendo el del día."""
        resultado = armar(
            especies_por_endpoint={"public-bonds": [especie("AL30D")]},
            filas_cashflow=None,
            cronograma_persistido=cronograma("AL30", "HARD_DOLLAR"),
        )
        (precio,) = resultado.filas_precios
        assert precio["tir"] is not None
        assert resultado.filas_cashflow is None, "no se re-persiste lo que no vino de la fuente"


class TestNadaDesapareceSinMotivo:
    """El fix del 26/08/2026: las especies que caían en `FUENTE_IAMC` volvían `None` sin anotar.

    Mientras IAMC publicaba por ellas era una atribución, no un faltante. Eliminada la ingesta
    quedaban como un agujero silencioso —~535 especies según la medición SQL de `docs/ESTADO.md`—
    y un faltante sin nombre es un faltante que nadie va a buscar (regla 1).
    """

    def test_una_especie_sin_tipo_de_tasa_sale_nombrada_en_la_alerta(self) -> None:
        """Una ON sin cronograma: el endpoint declara la clase, pero nadie declara la naturaleza.

        Es el caso mayoritario del agujero — el `type` del cronograma es la única fuente de
        `tipo_tasa`, y sin cronograma la ON entra al universo clasificada y sin naturaleza.
        """
        resultado = armar(
            especies_por_endpoint={"negociable-obligations": [especie("YCA6O")]},
            filas_cashflow=cronograma("OTRA", "ON"),
        )

        (precio,) = resultado.filas_precios
        assert precio["tir"] is None
        alerta = alerta_con(resultado, CODIGO_METRICAS_FUERA_DE_NATURALEZA)
        assert alerta is not None
        motivo = alerta.detalle["por_motivo"][MOTIVO_SIN_TIPO_TASA]
        assert motivo["tickers"] == ["YCA6O"]
        assert motivo["porque"], "el motivo viaja con su porqué, no sólo con la etiqueta"

    def test_una_naturaleza_desconocida_sale_nombrada_con_su_motivo(self) -> None:
        """Si mañana aparece una naturaleza sin regla de cálculo, se declara en vez de callarse."""
        resultado = ResultadoMetricas()
        resultado.anotar(MOTIVO_NATURALEZA_DESCONOCIDA, "XYZ9")

        alerta = alerta_con(resultado, CODIGO_METRICAS_FUERA_DE_NATURALEZA)
        assert alerta is not None
        motivo = alerta.detalle["por_motivo"][MOTIVO_NATURALEZA_DESCONOCIDA]
        assert motivo["tickers"] == ["XYZ9"]
        assert "no se sabe en qué unidad" in motivo["porque"]


class TestResumen:
    def test_cuenta_lo_calculado_y_lo_que_falto_por_motivo(self) -> None:
        resultado = ResultadoMetricas()
        resultado.registrar("AL30D", MetricasEspecie(0.12, 2.1, 2.3, 0.88, None))
        resultado.anotar("cer", "TX26")
        resultado.anotar("cer", "TZX28")
        resultado.anotar("sin_precio", "GD35D")

        assert resultado.resumen() == {
            "calculadas": 1,
            "intentadas": 1,
            "sin_metrica": {"cer": 2, "sin_precio": 1},
        }

    def test_una_especie_que_entro_al_solver_y_no_resolvio_no_cuenta_como_calculada(self) -> None:
        """El fix del 26/08/2026: `calculadas` se incrementaba en cada `registrar()`, así que el
        número que la corrida publicaba como "cuántas se calcularon" incluía a las que volvieron
        con `tir=None`. Un contador de éxitos que sube con los fracasos no informa nada."""
        resultado = ResultadoMetricas()
        resultado.registrar("AL30D", MetricasEspecie(0.12, 2.1, 2.3, 0.88, None))
        resultado.registrar("GD30D", MetricasEspecie(None, None, None, 1.4, "tir_bajo_piso"))
        resultado.registrar("AE38D", MetricasEspecie(None, None, None, None, "vencida"))

        assert resultado.resumen() == {
            "calculadas": 1,
            "intentadas": 3,
            "sin_metrica": {"tir_bajo_piso": 1, "vencida": 1},
        }

    def test_las_que_ni_entraron_al_solver_no_suman_a_intentadas(self) -> None:
        """`anotar` es el camino de las que quedaron fuera antes del cálculo —sin precio, sin
        cronograma, moneda cruzada—. No pasaron por el solver, así que no son un intento."""
        resultado = ResultadoMetricas()
        resultado.anotar(MOTIVO_MONEDA_CRUZADA, "AL30")

        assert resultado.resumen()["intentadas"] == 0
