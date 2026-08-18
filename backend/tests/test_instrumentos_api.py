"""Los tres endpoints de la ficha de instrumento — F-039.

Lo que se prueba acá es el contrato HTTP de cada uno, por separado: la deduplicación de especies ya
está probada sin levantar nada en `test_universo_emisiones.py`, la matemática del cronograma en
`test_calendario_cupones.py`, y el triplete campo/origen/fecha en
`test_condiciones_persistencia.py`. Una conexión falsa que despacha por SQL, mismo patrón que
`FakeConexionCalendario` en
`test_calendario_api.py`: universo, condiciones y cashflow son tres consultas distintas, y un fake
que devolviera lo mismo a las tres no probaría que cada endpoint lee lo que dice leer.
"""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

import app.api.v1.instrumentos as modulo_instrumentos
from app.condiciones.semilla import CAMPOS
from app.externos.cnv import ArchivoAdjunto, DocumentoCnv, RespuestaInesperadaDeCnv
from app.externos.emisores_cuit import EmisorArca
from tests.conftest import cliente

FICHA = "/api/v1/instrumentos/{ticker}"
CONDICIONES = "/api/v1/instrumentos/{ticker}/condiciones"
CRONOGRAMA = "/api/v1/instrumentos/{ticker}/cronograma"
SENSIBILIDAD = "/api/v1/instrumentos/{ticker}/sensibilidad"
PROSPECTO = "/api/v1/instrumentos/{ticker}/prospecto"
PROSPECTO_ARCHIVO = "/api/v1/instrumentos/{ticker}/prospecto/{uuid}/archivo"

# AL30 / AL30D / AL30C: la misma emisión en pesos, MEP y cable — mismas duraciones, así que
# deduplica en una sola emisión con dos hermanas por especie. S30J6 no comparte raíz con nadie:
# es el caso "sin hermanas".
FILAS_UNIVERSO: list[dict[str, Any]] = [
    {
        "ticker": "AL30",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.12,
        "tna": None,
        "duration": 3.5,
        "maturity": date(2030, 7, 9),
        "law": "Ley Argentina",
        "couponCurrency": "USD",
        "underlying": "Gobierno Argentino",
        "lastPrice": 65_000.0,
        "effectiveVolume": 1_000.0,
        "moneda_cotizacion": "ARS",
        "paridad": 0.7,
    },
    {
        "ticker": "AL30D",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.121,
        "tna": None,
        "duration": 3.5,
        "maturity": date(2030, 7, 9),
        "law": "Ley Argentina",
        "couponCurrency": "USD",
        "underlying": "Gobierno Argentino",
        "lastPrice": 43.0,
        "effectiveVolume": 500.0,
        "moneda_cotizacion": "USD",
        "paridad": 0.7,
    },
    {
        "ticker": "AL30C",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.119,
        "tna": None,
        "duration": 3.5,
        "maturity": date(2030, 7, 9),
        "law": "Ley Argentina",
        "couponCurrency": "USD",
        "underlying": "Gobierno Argentino",
        "lastPrice": 43.2,
        "effectiveVolume": 300.0,
        "moneda_cotizacion": "USD",
        "paridad": 0.7,
    },
    {
        "ticker": "S30J6",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "tasa-fija",
        "tir": None,
        "tna": 0.35,
        "duration": 0.5,
        "maturity": date(2027, 6, 30),
        "law": "Ley Argentina",
        "couponCurrency": "ARS",
        "underlying": "Gobierno Argentino",
        "lastPrice": 130.0,
        "effectiveVolume": 9_000.0,
        "moneda_cotizacion": "ARS",
        "paridad": 0.98,
    },
    {
        "ticker": "TLCMO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.09,
        "tna": None,
        "duration": 4.0,
        "maturity": date(2031, 7, 18),
        "law": "Ley N.Y.",
        "couponCurrency": "USD",
        "underlying": "TELECOM ARGENTINA S.A.",
        "lastPrice": 171_740.0,
        "effectiveVolume": 0.0,
        "moneda_cotizacion": "ARS",
        "paridad": None,
    },
]

# Dos pagos futuros de AL30 (raíz de AL30/AL30D/AL30C): uno de renta pura y uno de capital+renta al
# vencimiento. Los dos son futuros respecto de `date.today()` en cualquier fecha en que corra este
# test, así que el residual vigente cae siempre en `RESIDUAL_ENTERO` (100.0): sin pagos pasados no
# hay nada que contradiga la fuente, y el `resumen` del cronograma sale coherente.
FILAS_CASHFLOW: list[dict[str, Any]] = [
    {
        "ticker": "AL30",
        "issue_date": date(2020, 1, 9),
        "payment_date": date(2028, 1, 9),
        "capital": 0.0,
        "interest_amount": 1.5,
        "residual_value": 100.0,
        "cash_flow": 1.5,
    },
    {
        "ticker": "AL30",
        "issue_date": date(2020, 1, 9),
        "payment_date": date(2030, 7, 9),
        "capital": 100.0,
        "interest_amount": 1.5,
        "residual_value": 0.0,
        "cash_flow": 101.5,
    },
]


def _fila_condiciones(ticker: str, **valores: Any) -> dict[str, Any]:
    """Una fila de `condiciones_emision` con el triplete completo de cada campo de `CAMPOS`."""
    fila: dict[str, Any] = {"ticker": ticker}
    for campo in CAMPOS:
        fila[campo] = valores.get(campo)
        fila[f"{campo}_origen"] = valores.get(f"{campo}_origen")
        fila[f"{campo}_fecha"] = valores.get(f"{campo}_fecha")
    return fila


CONDICIONES_AL30 = _fila_condiciones(
    "AL30",
    ley="Ley Argentina",
    ley_origen="condiciones_emision.csv (curado)",
    ley_fecha="2026-08-05",
    calificacion=None,
    calificacion_origen=None,
    calificacion_fecha=None,
)


class FakeConexionInstrumentos:
    """Conexión falsa que despacha por consulta: universo, condiciones o cashflow."""

    def __init__(
        self,
        universo: list[dict[str, Any]] | None = None,
        condiciones: dict[str, dict[str, Any]] | None = None,
        cashflow: list[dict[str, Any]] | None = None,
    ) -> None:
        self.universo = FILAS_UNIVERSO if universo is None else universo
        self.condiciones = {} if condiciones is None else condiciones
        self.cashflow = FILAS_CASHFLOW if cashflow is None else cashflow
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if "public.cashflow" in query:
            return self.cashflow
        return self.universo

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.consultas.append(query)
        (ticker,) = args
        return self.condiciones.get(ticker)


@pytest.fixture
def app_con_instrumentos(crear_app):
    def _crear(**kwargs: Any):
        return crear_app(FakeConexionInstrumentos(**kwargs))

    return _crear


# --- GET /instrumentos/{ticker} -------------------------------------------------------------------


async def test_un_ticker_vivo_trae_sus_dos_hermanas(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(FICHA.format(ticker="AL30D"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["ticker"] == "AL30D"
    assert cuerpo["especie"]["ticker"] == "AL30D"
    assert cuerpo["especie"]["emision"] == "AL30"
    assert cuerpo["especie"]["dato_sano"] is True
    assert {h["ticker"] for h in cuerpo["hermanas"]} == {"AL30", "AL30C"}


async def test_un_ticker_sin_hermanas_trae_la_lista_vacia(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(FICHA.format(ticker="S30J6"))

    cuerpo = respuesta.json()
    assert cuerpo["especie"]["ticker"] == "S30J6"
    assert cuerpo["hermanas"] == []


async def test_un_ticker_fuera_del_universo_da_404(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(FICHA.format(ticker="NOEXISTE"))

    assert respuesta.status_code == 404


async def test_ficha_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(FICHA.format(ticker="AL30D"))

    assert respuesta.status_code == 503


# --- GET /instrumentos/{ticker}/condiciones -------------------------------------------------------


async def test_condiciones_presentes_traen_origen_y_fecha(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos(condiciones={"AL30": CONDICIONES_AL30})) as http:
        respuesta = await http.get(CONDICIONES.format(ticker="AL30"))

    assert respuesta.status_code == 200
    condiciones_ = respuesta.json()["condiciones"]
    assert condiciones_["ley"] == "Ley Argentina"
    assert condiciones_["ley_origen"] == "condiciones_emision.csv (curado)"
    assert condiciones_["ley_fecha"] == "2026-08-05"
    assert condiciones_["calificacion"] is None


async def test_lamina_decimal_sale_como_numero_no_como_string(app_con_instrumentos) -> None:
    """`lamina` es `numeric` en Postgres y asyncpg la trae como `Decimal`; sin conversión el
    encoder JSON la serializa como `"1"` y el schema del frontend —que la declara numérica—
    rechaza la fila entera con `contract_mismatch`. Atrapado contra la base real con GYC4D: los
    tests offline no lo veían porque el fake devolvía valores Python nativos."""
    fila = _fila_condiciones(
        "GYC4D",
        lamina=Decimal("1"),
        lamina_origen="condiciones_emision.csv (curado)",
        lamina_fecha="2026-08-05",
    )
    async with cliente(app_con_instrumentos(condiciones={"GYC4D": fila})) as http:
        respuesta = await http.get(CONDICIONES.format(ticker="GYC4D"))

    assert respuesta.status_code == 200
    lamina = respuesta.json()["condiciones"]["lamina"]
    assert lamina == 1
    assert not isinstance(lamina, str)


async def test_condiciones_ausentes_no_es_404(app_con_instrumentos) -> None:
    """Que no haya condiciones curadas para un ticker es un estado normal (GWT-2), no un error."""
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(CONDICIONES.format(ticker="AL30"))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ticker": "AL30", "condiciones": None}


async def test_condiciones_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(CONDICIONES.format(ticker="AL30"))

    assert respuesta.status_code == 503


# --- GET /instrumentos/{ticker}/cronograma ----------------------------------------------------


async def test_cronograma_con_pagos_distingue_interes_de_amortizacion(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30D"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["ticker"] == "AL30D"
    assert len(cuerpo["pagos"]) == 2
    solo_renta, capital_y_renta = cuerpo["pagos"]
    assert solo_renta["interes"] == 1.5
    assert solo_renta["amortizacion"] == 0.0
    assert capital_y_renta["amortizacion"] == 100.0
    assert capital_y_renta["interes"] == 1.5
    # La moneda sale del universo (couponCurrency), no se infiere del sufijo del ticker.
    assert cuerpo["pagos"][0]["moneda"] == "USD"
    # El residual declarado por la fuente viaja por pago: coherente acá (sin pagos pasados).
    assert solo_renta["residual"] == 100.0
    assert capital_y_renta["residual"] == 0.0


async def test_cronograma_vacio_no_es_404(app_con_instrumentos) -> None:
    """Sin cronograma para la raíz puede ser legítimamente un instrumento sin cashflow cargado."""
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="S30J6"))

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "ticker": "S30J6",
        "pagos": [],
        "resumen": {
            "residual_vigente": None,
            "valor_tecnico": None,
            "cupon_corrido": None,
            "paridad": None,
            "coherente": True,
            "motivo_ausente": "sin cronograma de pagos en la fuente",
        },
    }


async def test_cronograma_sin_universo_declara_moneda_nula(app_con_instrumentos) -> None:
    """Sin fuente que declare la moneda de un ticker fuera del universo, se declara `null` y no se
    inventa a partir del sufijo del ticker (regla 1 del proyecto)."""
    async with cliente(app_con_instrumentos(universo=[], cashflow=FILAS_CASHFLOW)) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30D"))

    cuerpo = respuesta.json()
    assert len(cuerpo["pagos"]) == 2
    assert all(pago["moneda"] is None for pago in cuerpo["pagos"])
    # Sin especie no hay precio con qué comparar: el residual sigue siendo contractual y se
    # calcula igual, pero la paridad no.
    assert cuerpo["resumen"]["residual_vigente"] == 100.0
    assert cuerpo["resumen"]["paridad"] is None
    assert "no está en el universo" in cuerpo["resumen"]["motivo_ausente"]


async def test_cronograma_resumen_calcula_paridad_con_moneda_que_coincide(
    app_con_instrumentos,
) -> None:
    """AL30D cotiza en USD y su flujo (hard-dollar) paga en USD: el gate de F-051 deja pasar la
    paridad — mismo criterio que `fuente_de_metricas`, no uno nuevo para la ficha."""
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30D"))

    resumen = respuesta.json()["resumen"]
    assert resumen["coherente"] is True
    assert resumen["residual_vigente"] == 100.0
    assert resumen["valor_tecnico"] is not None
    # precio 43.0 / valor técnico (≈100 + corridos)
    assert resumen["paridad"] == pytest.approx(43.0 / resumen["valor_tecnico"])
    assert resumen["motivo_ausente"] is None


async def test_cronograma_resumen_declara_moneda_cruzada_sin_paridad(
    app_con_instrumentos,
) -> None:
    """AL30 cotiza en pesos pero su flujo paga en dólares: el residual es contractual y se calcula
    igual, pero la paridad mezclaría monedas y se declara sin calcular, no se inventa un TC."""
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30"))

    resumen = respuesta.json()["resumen"]
    assert resumen["residual_vigente"] == 100.0
    assert resumen["paridad"] is None
    assert "moneda distinta" in resumen["motivo_ausente"]


async def test_cronograma_resumen_vacio_con_residual_incoherente(
    app_con_instrumentos,
) -> None:
    """El caso real (29 de 816 tickers): la fuente declara el residual clavado en 100 después de un
    pago que sí amortizó. El resumen y el residual de cada pago quedan vacíos, con el motivo."""
    cashflow_incoherente = [
        {
            "ticker": "AL30",
            "issue_date": date(2020, 1, 9),
            "payment_date": date(2024, 1, 9),
            "capital": 40.0,
            "interest_amount": 1.5,
            "residual_value": 100.0,
            "cash_flow": 41.5,
        },
        {
            "ticker": "AL30",
            "issue_date": date(2020, 1, 9),
            "payment_date": date(2030, 7, 9),
            "capital": 60.0,
            "interest_amount": 1.5,
            "residual_value": 0.0,
            "cash_flow": 61.5,
        },
    ]
    async with cliente(app_con_instrumentos(cashflow=cashflow_incoherente)) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30D"))

    cuerpo = respuesta.json()
    assert all(pago["residual"] is None for pago in cuerpo["pagos"])
    resumen = cuerpo["resumen"]
    assert resumen["coherente"] is False
    assert resumen["residual_vigente"] is None
    assert resumen["valor_tecnico"] is None
    assert resumen["paridad"] is None
    assert "contradice" in resumen["motivo_ausente"]


async def test_cronograma_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30D"))

    assert respuesta.status_code == 503


# --- GET /instrumentos/{ticker}/sensibilidad --------------------------------------------------


async def test_sensibilidad_de_un_bono_usd_hard_repricea_los_ocho_escenarios(
    app_con_instrumentos,
) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(SENSIBILIDAD.format(ticker="AL30D"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["calculable"] is True
    assert cuerpo["naturaleza"] == "tir_usd"
    assert cuerpo["tir_actual"] == pytest.approx(0.121)
    assert cuerpo["omitidos_bps"] == []

    escenarios = cuerpo["escenarios"]
    assert [e["delta_bps"] for e in escenarios] == [-500, -400, -300, -200, -100, 0, 100, 200]

    nulo = next(e for e in escenarios if e["delta_bps"] == 0)
    assert nulo["retorno"] == pytest.approx(0.0)

    compresion = next(e for e in escenarios if e["delta_bps"] == -100)
    apertura = next(e for e in escenarios if e["delta_bps"] == 100)
    assert compresion["retorno"] > 0
    assert apertura["retorno"] < 0


async def test_sensibilidad_de_tasa_fija_declara_tna_nominal_y_no_calcula(
    app_con_instrumentos,
) -> None:
    """S30J6 es tasa_fija: su rendimiento es TNA nominal, no una tasa efectiva descontable."""
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(SENSIBILIDAD.format(ticker="S30J6"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["calculable"] is False
    assert "TNA nominal" in cuerpo["motivo"]
    assert cuerpo["escenarios"] == []
    # Nunca un número derivado de duración: ningún campo numérico de escenario en la respuesta.
    assert "tir_escenario" not in str(cuerpo["escenarios"])


async def test_sensibilidad_sin_cronograma_declara_y_no_estima_por_duracion(
    app_con_instrumentos,
) -> None:
    async with cliente(app_con_instrumentos(cashflow=[])) as http:
        respuesta = await http.get(SENSIBILIDAD.format(ticker="AL30D"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["calculable"] is False
    assert cuerpo["motivo"] == "sin cronograma de pagos en la fuente"
    assert cuerpo["escenarios"] == []


async def test_sensibilidad_de_un_ticker_fuera_del_universo_da_200_no_404(
    app_con_instrumentos,
) -> None:
    """GWT-3 en su forma de endpoint: éste es un recurso derivado, el 404 de existencia lo da la
    ficha (`GET /instrumentos/{t}`)."""
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(SENSIBILIDAD.format(ticker="NOEXISTE"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["calculable"] is False
    assert cuerpo["tir_actual"] is None
    assert cuerpo["naturaleza"] is None
    assert "no está en el universo de hoy" in cuerpo["motivo"]


async def test_sensibilidad_sin_tir_vigente_declara_el_motivo(app_con_instrumentos) -> None:
    universo_sin_tir = [
        {**fila, "tir": None} if fila["ticker"] == "AL30D" else fila for fila in FILAS_UNIVERSO
    ]
    async with cliente(app_con_instrumentos(universo=universo_sin_tir)) as http:
        respuesta = await http.get(SENSIBILIDAD.format(ticker="AL30D"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["calculable"] is False
    assert cuerpo["motivo"] == "sin TIR vigente publicada ni calculada hoy"


async def test_sensibilidad_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(SENSIBILIDAD.format(ticker="AL30D"))

    assert respuesta.status_code == 503


# --- GET /instrumentos/{ticker}/prospecto — F-072 -----------------------------------------------


class FakeClienteCnv:
    """Reemplaza `cliente_cnv()` en el módulo del endpoint — mismo patrón que
    `test_renta_variable_ficha_api.py` con `cliente_yahoo`/`cliente_sec_ficha`: la respuesta se
    inyecta en vez de pegarle a la red."""

    def __init__(
        self,
        documentos: list[DocumentoCnv]
        | dict[str, list[DocumentoCnv] | None]
        | Exception
        | None = None,
        archivo: ArchivoAdjunto | Exception | None = None,
        contenido: bytes | Exception = b"%PDF-1.7 contenido",
    ) -> None:
        self._documentos = documentos
        self._archivo = archivo
        self._contenido = contenido
        self.pedidos: list[str] = []

    async def documentos_de(self, cuit: str) -> list[DocumentoCnv] | None:
        self.pedidos.append(cuit)
        if isinstance(self._documentos, Exception):
            raise self._documentos
        if isinstance(self._documentos, dict):
            return self._documentos.get(cuit)
        return self._documentos

    async def archivo_de(self, uuid: str) -> ArchivoAdjunto | None:
        if isinstance(self._archivo, Exception):
            raise self._archivo
        return self._archivo

    async def descargar(self, guid: str) -> bytes:
        if isinstance(self._contenido, Exception):
            raise self._contenido
        return self._contenido


UN_DOCUMENTO = DocumentoCnv(
    grupo="Suplementos",
    fecha=date(2026, 8, 11),
    hora="15:34",
    descripcion="Un suplemento de prueba",
    documento_id="3557195",
    uuid="96bad10a-713b-46e1-a9ac-04fa19f3a8cd",
)


@pytest.fixture
def app_con_prospecto(crear_app, monkeypatch):
    """Los dos puentes al CUIT se reemplazan en memoria (mismo criterio que el resto del archivo: el
    contrato HTTP se prueba sin tocar disco), y `cliente_cnv()` se inyecta en el módulo del
    endpoint. `CNV_HABILITADO=true` por default acá: la pausa tiene sus propios tests.

    `emisores_arca` arranca vacío a propósito: así el default de la fixture ejerce el respaldo por
    nombre, y los tests que quieren el camino de ARCA lo piden explícito.
    """

    def _crear(
        *,
        universo: list[dict[str, Any]] | None = None,
        emisores_cuit: dict[str, str] | None = None,
        emisores_arca: dict[str, EmisorArca] | None = None,
        cnv_habilitado: bool = True,
        **kwargs: Any,
    ):
        monkeypatch.setenv("CNV_HABILITADO", "true" if cnv_habilitado else "false")
        from app.core.config import get_settings

        get_settings.cache_clear()

        emisores = (
            {"TELECOM ARGENTINA S.A.": "30639453738"} if emisores_cuit is None else emisores_cuit
        )
        monkeypatch.setattr(modulo_instrumentos, "leer_emisores_cuit", lambda _ruta: emisores)
        monkeypatch.setattr(
            modulo_instrumentos, "leer_emisores_arca", lambda _ruta: emisores_arca or {}
        )

        app = crear_app(FakeConexionInstrumentos(universo=universo, **kwargs))
        return app

    return _crear


def _inyectar_cliente(monkeypatch, fake: FakeClienteCnv) -> None:
    monkeypatch.setattr(modulo_instrumentos, "cliente_cnv", lambda: fake)


async def test_prospecto_de_una_on_agrupa_los_documentos(app_con_prospecto, monkeypatch) -> None:
    fake = FakeClienteCnv(documentos=[UN_DOCUMENTO])
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is True
    assert cuerpo["emisor"] == "TELECOM ARGENTINA S.A."
    assert cuerpo["cuit"] == "30639453738"
    assert cuerpo["url_emisor_cnv"] == (
        "https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30639453738"
        "?formType=EMISIO&fdesde=1/1/2015"
    )
    assert cuerpo["grupos"] == [
        {
            "grupo": "Suplementos",
            "documentos": [
                {
                    "fecha": "2026-08-11",
                    "hora": "15:34",
                    "descripcion": "Un suplemento de prueba",
                    "documento_id": "3557195",
                    "uuid": "96bad10a-713b-46e1-a9ac-04fa19f3a8cd",
                    "url_publicview": (
                        "https://aif2.cnv.gov.ar/presentations/publicview/"
                        "96bad10a-713b-46e1-a9ac-04fa19f3a8cd"
                    ),
                }
            ],
        }
    ]
    assert cuerpo["motivo_ausente"] is None
    assert fake.pedidos == ["30639453738"]


async def test_prospecto_pone_los_prospectos_primero(app_con_prospecto, monkeypatch) -> None:
    suplemento = UN_DOCUMENTO
    prospecto_doc = DocumentoCnv(
        grupo="Prospectos",
        fecha=date(2020, 1, 1),
        hora="10:00",
        descripcion="Prospecto original",
        documento_id="1",
        uuid="7024d6c5-9b2a-4a86-975d-7843a4cf9896",
    )
    fake = FakeClienteCnv(documentos=[suplemento, prospecto_doc])
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    grupos = [g["grupo"] for g in respuesta.json()["grupos"]]
    assert grupos == ["Prospectos", "Suplementos"]


async def test_prospecto_de_un_ticker_que_no_es_on_declara_aplica_false(
    app_con_prospecto, monkeypatch
) -> None:
    fake = FakeClienteCnv()
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="AL30D"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is False
    assert "no es una obligación negociable" in cuerpo["motivo_ausente"]
    assert cuerpo["cuit"] is None
    # Ni se intenta resolver el CUIT ni se pide nada a la CNV para algo que no aplica.
    assert fake.pedidos == []


async def test_prospecto_de_un_ticker_fuera_del_universo_da_200_no_404(
    app_con_prospecto, monkeypatch
) -> None:
    """Mismo criterio que `/sensibilidad`: es un recurso derivado, el 404 de existencia lo da la
    ficha."""
    fake = FakeClienteCnv()
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="NOEXISTE"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is False
    assert "no está en el universo de hoy" in cuerpo["motivo_ausente"]


async def test_prospecto_sin_cuit_curado_declara_el_motivo_y_no_pide_nada(
    app_con_prospecto, monkeypatch
) -> None:
    fake = FakeClienteCnv()
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto(emisores_cuit={})) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is False
    assert cuerpo["emisor"] == "TELECOM ARGENTINA S.A."
    assert cuerpo["cuit"] is None
    assert cuerpo["url_emisor_cnv"] is None
    assert "todavía no tiene CUIT curado" in cuerpo["motivo_ausente"]
    assert fake.pedidos == []


# --- la cascada al CUIT: ARCA por raíz de emisión, después el nombre contra la CNV ---------------

# Una ON sin emisor declarado: exactamente el hueco que el puente por nombre no puede cubrir y ARCA
# sí, porque su clave es el código de especie. 89 emisiones del universo real están así.
ON_SIN_EMISOR: dict[str, Any] = {
    "ticker": "MR35D",
    "clase_activo": "on_corporativo",
    "tipo_tasa": "hard-dollar",
    "tir": 0.11,
    "tna": None,
    "duration": 2.0,
    "maturity": date(2030, 3, 15),
    "law": None,
    "couponCurrency": "USD",
    "underlying": None,
    "lastPrice": 98.0,
    "effectiveVolume": 0.0,
    "moneda_cotizacion": "USD",
    "paridad": None,
}


async def test_prospecto_resuelve_el_cuit_por_raiz_de_emision_contra_arca(
    app_con_prospecto, monkeypatch
) -> None:
    """Sin nombre de emisor y sin entrada en el puente por nombre, ARCA igual resuelve: la clave es
    la raíz de la especie. La denominación de ARCA queda de etiqueta porque no hay otra."""
    fake = FakeClienteCnv(documentos=[UN_DOCUMENTO])
    _inyectar_cliente(monkeypatch, fake)

    app = app_con_prospecto(
        universo=[ON_SIN_EMISOR],
        emisores_cuit={},
        emisores_arca={"MR35": EmisorArca(cuit="30604731018", denominacion="MSU S.A.")},
    )
    async with cliente(app) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="MR35D"))

    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is True
    assert cuerpo["cuit"] == "30604731018"
    assert cuerpo["cuit_fuente"] == "ARCA"
    assert cuerpo["emisor"] == "MSU S.A."
    assert fake.pedidos == ["30604731018"]


async def test_prospecto_prefiere_el_cuit_de_arca_sobre_el_del_nombre(
    app_con_prospecto, monkeypatch
) -> None:
    """El caso PAN AMERICAN ENERGY: BYMA nombra a una sociedad del grupo y la emisión es de otra.
    Gana ARCA —identifica la especie, no el nombre— pero el emisor que se muestra sigue siendo el
    que el asesor ve en el resto de la app."""
    fake = FakeClienteCnv(documentos=[UN_DOCUMENTO])
    _inyectar_cliente(monkeypatch, fake)

    app = app_con_prospecto(
        emisores_cuit={"TELECOM ARGENTINA S.A.": "30695542476"},
        emisores_arca={
            "TLCM": EmisorArca(
                cuit="30639453738", denominacion="TELECOM ARGENTINA SOCIEDAD ANONIMA"
            )
        },
    )
    async with cliente(app) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    cuerpo = respuesta.json()
    assert cuerpo["cuit"] == "30639453738"
    assert cuerpo["cuit_fuente"] == "ARCA"
    assert cuerpo["emisor"] == "TELECOM ARGENTINA S.A."
    assert fake.pedidos == ["30639453738"]


async def test_prospecto_cae_al_puente_por_nombre_cuando_arca_no_trae_la_emision(
    app_con_prospecto, monkeypatch
) -> None:
    """Lo que ARCA no puede traer: la tabla valúa al 31/12 y una emisión posterior no figura."""
    fake = FakeClienteCnv(documentos=[UN_DOCUMENTO])
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto(emisores_arca={})) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    cuerpo = respuesta.json()
    assert cuerpo["cuit"] == "30639453738"
    assert cuerpo["cuit_fuente"] == "CNV listado"
    assert cuerpo["emisor"] == "TELECOM ARGENTINA S.A."


async def test_prospecto_prueba_el_cuit_por_nombre_si_la_cnv_no_reconoce_el_de_arca(
    app_con_prospecto, monkeypatch
) -> None:
    """El caso PAE Sucursal: ARCA identifica bien la sociedad emisora, pero esa sociedad no tiene
    ficha de emisora en la CNV y el buscador devuelve su página genérica. Se prueba el otro CUIT
    curado, que es dato de fuente igual, y la respuesta declara cuál terminó usando."""
    fake = FakeClienteCnv(documentos={"30695542476": [UN_DOCUMENTO], "30714813583": None})
    _inyectar_cliente(monkeypatch, fake)

    app = app_con_prospecto(
        emisores_cuit={"TELECOM ARGENTINA S.A.": "30695542476"},
        emisores_arca={"TLCM": EmisorArca(cuit="30714813583", denominacion="OTRA DEL GRUPO S.A.")},
    )
    async with cliente(app) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is True
    assert cuerpo["cuit"] == "30695542476"
    assert cuerpo["cuit_fuente"] == "CNV listado"
    assert fake.pedidos == ["30714813583", "30695542476"]


async def test_prospecto_no_reintenta_si_el_cuit_por_nombre_es_el_mismo(
    app_con_prospecto, monkeypatch
) -> None:
    """Sin CUIT alternativo distinto no hay nada que probar: se declara y no se pide dos veces."""
    fake = FakeClienteCnv(documentos=None)
    _inyectar_cliente(monkeypatch, fake)

    app = app_con_prospecto(
        emisores_cuit={"TELECOM ARGENTINA S.A.": "30639453738"},
        emisores_arca={"TLCM": EmisorArca(cuit="30639453738", denominacion="TELECOM ARG. S.A.")},
    )
    async with cliente(app) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is False
    assert cuerpo["cuit_fuente"] == "ARCA"
    assert "no confirmó los resultados" in cuerpo["motivo_ausente"]
    assert fake.pedidos == ["30639453738"]


async def test_prospecto_sin_emisor_ni_entrada_en_arca_declara_las_dos_ausencias(
    app_con_prospecto, monkeypatch
) -> None:
    fake = FakeClienteCnv()
    _inyectar_cliente(monkeypatch, fake)

    app = app_con_prospecto(universo=[ON_SIN_EMISOR], emisores_cuit={}, emisores_arca={})
    async with cliente(app) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="MR35D"))

    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is False
    assert cuerpo["cuit"] is None
    assert cuerpo["cuit_fuente"] is None
    assert "sin emisor declarado en el universo de hoy" in cuerpo["motivo_ausente"]
    assert "ARCA" in cuerpo["motivo_ausente"]
    assert fake.pedidos == []


async def test_prospecto_con_la_fuente_pausada_no_pide_nada_a_la_red(
    app_con_prospecto, monkeypatch
) -> None:
    fake = FakeClienteCnv()
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto(cnv_habilitado=False)) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is False
    # El CUIT sí se resuelve (es local) y la salida de emergencia sigue disponible aunque la
    # fuente esté pausada.
    assert cuerpo["cuit"] == "30639453738"
    assert cuerpo["url_emisor_cnv"] is not None
    assert "pausada" in cuerpo["motivo_ausente"]
    assert fake.pedidos == []


async def test_prospecto_declara_cuando_la_cnv_no_confirma_los_resultados(
    app_con_prospecto, monkeypatch
) -> None:
    """`documentos_de` devuelve `None` cuando la fuente respondió con la página genérica en vez de
    los resultados del emisor — un fallo silencioso que no se confunde con "sin documentos"."""
    fake = FakeClienteCnv(documentos=None)
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    # `aplica` es "hay una respuesta confirmada que mostrar", no "el ticker es una ON": mismo
    # criterio que `calculable` en /sensibilidad, que junta bajo un solo booleano "no corresponde"
    # y "no se pudo calcular".
    assert cuerpo["aplica"] is False
    assert cuerpo["grupos"] == []
    assert "no confirmó" in cuerpo["motivo_ausente"]
    # La salida de emergencia sigue viajando aunque el parseo no haya podido confirmar nada.
    assert cuerpo["url_emisor_cnv"] is not None


async def test_prospecto_declara_un_fallo_de_red_sin_romper_el_endpoint(
    app_con_prospecto, monkeypatch
) -> None:
    import httpx

    fake = FakeClienteCnv(documentos=httpx.ConnectError("sin red"))
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["aplica"] is False
    assert "no respondió" in cuerpo["motivo_ausente"]


async def test_prospecto_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(PROSPECTO.format(ticker="TLCMO"))

    assert respuesta.status_code == 503


# --- GET /instrumentos/{ticker}/prospecto/{uuid}/archivo — F-072 --------------------------------

UUID_VALIDO = "96bad10a-713b-46e1-a9ac-04fa19f3a8cd"
UN_ARCHIVO = ArchivoAdjunto(
    guid="4ce6fe56-f5f7-428b-f6ac-ef4ece785218",
    nombre_archivo="Suplemento de Prospecto.pdf",
    tamano_declarado="1.33 MB",
    total_en_la_presentacion=1,
)


async def test_archivo_descarga_el_pdf_con_el_nombre_real(app_con_prospecto, monkeypatch) -> None:
    fake = FakeClienteCnv(archivo=UN_ARCHIVO, contenido=b"%PDF-1.7 contenido real")
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO_ARCHIVO.format(ticker="TLCMO", uuid=UUID_VALIDO))

    assert respuesta.status_code == 200
    assert respuesta.content == b"%PDF-1.7 contenido real"
    assert respuesta.headers["content-type"] == "application/pdf"
    assert 'filename="Suplemento de Prospecto.pdf"' in respuesta.headers["content-disposition"]


async def test_archivo_sin_adjunto_da_404(app_con_prospecto, monkeypatch) -> None:
    fake = FakeClienteCnv(archivo=None)
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO_ARCHIVO.format(ticker="TLCMO", uuid=UUID_VALIDO))

    assert respuesta.status_code == 404


async def test_archivo_con_la_fuente_pausada_da_503(app_con_prospecto, monkeypatch) -> None:
    fake = FakeClienteCnv(archivo=UN_ARCHIVO)
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto(cnv_habilitado=False)) as http:
        respuesta = await http.get(PROSPECTO_ARCHIVO.format(ticker="TLCMO", uuid=UUID_VALIDO))

    assert respuesta.status_code == 503


async def test_archivo_cuando_la_cnv_no_devuelve_un_pdf_da_502(
    app_con_prospecto, monkeypatch
) -> None:
    fake = FakeClienteCnv(
        archivo=UN_ARCHIVO,
        contenido=RespuestaInesperadaDeCnv("no era un PDF"),
    )
    _inyectar_cliente(monkeypatch, fake)

    async with cliente(app_con_prospecto()) as http:
        respuesta = await http.get(PROSPECTO_ARCHIVO.format(ticker="TLCMO", uuid=UUID_VALIDO))

    assert respuesta.status_code == 502
