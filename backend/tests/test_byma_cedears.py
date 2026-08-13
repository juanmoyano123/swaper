"""El parseo de la tabla oficial de CEDEARs de BYMA.

Los renglones son transcripciones literales del PDF del 12/06/2026 — incluido el que está mal, que
es el que da origen a la mitad de este archivo.
"""

from app.ingesta.byma.cedears import CODIGO_CEDEAR_EN_CONFLICTO, link_del_pdf, parsear_lista

# Tal cual salen del PDF, con su espaciado.
RENGLONES = [
    "CEDEARs Negociables en BYMA",
    "Código Mercado donde",
    "Apple Inc. AAPL NASDAQ 20:1",
    "Ambev S.A. ABEV NASDAQ 1:3",
    "Ambev S.A. ABEV3 B3 1:1",
    "Barrick Gold Corp B NYSE 2:1",
    "iShares MSCI ACWI ETF ACWI NASDAQ 26:1",
    "Adidas AG ADS XETRA 22:1",
]


def test_lee_los_cuatro_datos_de_cada_renglon() -> None:
    r = parsear_lista(["\n".join(RENGLONES)])

    assert r.cedears["AAPL"].nombre == "Apple Inc."
    assert r.cedears["AAPL"].mercado == "NASDAQ"
    assert r.cedears["AAPL"].ratio == "20:1"


def test_los_titulos_y_encabezados_no_entran_como_papeles() -> None:
    """Sin el ancla del mercado, el parseo levanta títulos y notas al pie del documento."""
    r = parsear_lista(["\n".join(RENGLONES)])
    assert len(r.cedears) == 6
    assert "CEDEARs" not in r.cedears


def test_el_mismo_papel_con_dos_subyacentes_son_dos_cedears() -> None:
    """`ABEV` cotiza sobre el ADR de NASDAQ con ratio 1:3 y `ABEV3` sobre la acción de B3 con 1:1:
    misma empresa, distinto instrumento y distinto ratio."""
    r = parsear_lista(["\n".join(RENGLONES)])

    assert r.cedears["ABEV"].mercado == "NASDAQ"
    assert r.cedears["ABEV"].ratio == "1:3"
    assert r.cedears["ABEV3"].mercado == "B3"
    assert r.cedears["ABEV3"].ratio == "1:1"


def test_un_ticker_de_una_letra_se_lee_igual() -> None:
    """`B` es Barrick y es un código legítimo de la tabla oficial."""
    assert parsear_lista(["\n".join(RENGLONES)]).cedears["B"].nombre == "Barrick Gold Corp"


# --- El error de la fuente ------------------------------------------------------------------------


def test_un_codigo_con_dos_nombres_se_descarta_entero_y_se_declara() -> None:
    """Caso real del PDF del 12/06/2026: BYMA publica `XLU` dos veces, una para el ETF de
    ciberseguridad y otra para el de Utilities. **No se elige uno** — no hay forma de saber cuál es
    el correcto, y quedarse con el primero sería decidir por la fuente."""
    r = parsear_lista(
        [
            "First Trust NASDAQ Cybersecurity XLU NASDAQ 10:1\n"
            "Utilities Select Sector SPDR Fund XLU NYSE Arca 15:1\n"
            "Apple Inc. AAPL NASDAQ 20:1"
        ]
    )

    assert "XLU" not in r.cedears, "el código en conflicto no se resuelve, se descarta"
    assert "AAPL" in r.cedears, "el conflicto de uno no arrastra al resto de la tabla"

    (alerta,) = r.alertas
    assert alerta.codigo == CODIGO_CEDEAR_EN_CONFLICTO
    assert "XLU" in alerta.mensaje
    assert alerta.detalle["codigos"] == ["XLU"]


def test_el_mismo_codigo_repetido_con_el_mismo_nombre_no_es_conflicto() -> None:
    """El PDF repite renglones entre páginas. Dos filas idénticas son una sola fila, no una
    contradicción."""
    r = parsear_lista(["Apple Inc. AAPL NASDAQ 20:1", "Apple Inc. AAPL NASDAQ 20:1"])

    assert r.cedears["AAPL"].nombre == "Apple Inc."
    assert r.alertas == []


def test_sin_conflictos_no_hay_alertas() -> None:
    assert parsear_lista(["\n".join(RENGLONES)]).alertas == []


# --- El link al PDF, que cambia en cada actualización ---------------------------------------------


def test_encuentra_el_pdf_de_cedears_entre_otros_pdf_de_la_pagina() -> None:
    """La página de BYMA tiene reglamentos y comunicados en PDF: agarrar el primero traería
    cualquier cosa."""
    html = (
        '<a href="/reglamento-de-listado.pdf">Reglamento</a>'
        '<a href="https://cdn.example.com/abc_2026-06-12-BYMA-CEDEARs.pdf">Lista</a>'
    )
    assert link_del_pdf(html) == "https://cdn.example.com/abc_2026-06-12-BYMA-CEDEARs.pdf"


def test_si_la_pagina_cambio_de_forma_no_se_adivina_un_link() -> None:
    assert link_del_pdf('<a href="/otra-cosa.pdf">Algo</a>') is None
    assert link_del_pdf("<p>sin links</p>") is None
