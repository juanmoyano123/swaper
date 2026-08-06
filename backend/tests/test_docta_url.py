"""URL efectiva del feed de cashflow: ventana móvil (GWT-4) y expansión del token.

`fromDate` tiene que calcularse relativo a la fecha de corrida, nunca hardcodeado — es el
criterio de aceptación de la ficha. Y la expansión del placeholder `${DOCTA_API_TOKEN}` es la
decisión más importante del paquete a nivel mecánico: sin ella, todo el resto de F-006 fallaría
con "token inválido" mientras el token real está perfectamente vigente.
"""

from datetime import date, timedelta

import pytest

from app.ingesta.docta.url import (
    ConfiguracionFaltante,
    url_con_ventana_movil,
    url_efectiva,
)

# --- GWT-4: ventana móvil, sin fecha hardcodeada ------------------------------------------------


def test_from_date_se_reescribe_a_quince_dias_antes_de_hoy() -> None:
    url = "https://docta.test/api/cash-flow?token=x&fromDate=2020-01-01&toDate=2020-12-31"

    resultado = url_con_ventana_movil(url)

    esperado = (date.today() - timedelta(days=15)).strftime("%Y-%m-%d")
    assert f"fromDate={esperado}" in resultado
    assert "toDate=2020-12-31" in resultado, "el resto de la query no se toca"


def test_una_url_sin_from_date_queda_intacta() -> None:
    url = "https://docta.test/api/cash-flow?token=x"

    assert url_con_ventana_movil(url) == url


def test_la_ventana_acepta_una_cantidad_de_dias_distinta() -> None:
    url = "https://docta.test/api/cash-flow?fromDate=2020-01-01"

    resultado = url_con_ventana_movil(url, dias=30)

    esperado = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    assert f"fromDate={esperado}" in resultado


# --- Expansión del placeholder -------------------------------------------------------------------


def test_el_placeholder_del_token_se_expande_con_el_token_de_settings() -> None:
    url = url_efectiva("https://docta.test/api/cash-flow?token=${DOCTA_API_TOKEN}", "abc123")

    assert "${DOCTA_API_TOKEN}" not in url
    assert "token=abc123" in url


def test_una_url_sin_placeholder_no_necesita_token() -> None:
    url = url_efectiva("https://docta.test/api/cash-flow?token=ya-embebido", None)

    assert url == "https://docta.test/api/cash-flow?token=ya-embebido"


def test_una_url_ausente_pide_configurar_docta_cashflow_url() -> None:
    with pytest.raises(ConfiguracionFaltante) as exc:
        url_efectiva(None, "abc123")

    assert exc.value.variable == "DOCTA_CASHFLOW_URL"


def test_una_url_vacia_tambien_pide_configurar_docta_cashflow_url() -> None:
    with pytest.raises(ConfiguracionFaltante) as exc:
        url_efectiva("", "abc123")

    assert exc.value.variable == "DOCTA_CASHFLOW_URL"


def test_un_placeholder_sin_token_pide_configurar_docta_api_token() -> None:
    with pytest.raises(ConfiguracionFaltante) as exc:
        url_efectiva("https://docta.test/api/cash-flow?token=${DOCTA_API_TOKEN}", None)

    assert exc.value.variable == "DOCTA_API_TOKEN"


def test_la_url_efectiva_combina_expansion_y_ventana_movil() -> None:
    url = url_efectiva(
        "https://docta.test/api/cash-flow?token=${DOCTA_API_TOKEN}&fromDate=2020-01-01",
        "abc123",
    )

    esperado = (date.today() - timedelta(days=15)).strftime("%Y-%m-%d")
    assert "token=abc123" in url
    assert f"fromDate={esperado}" in url
