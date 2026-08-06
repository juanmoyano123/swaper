"""Los tres GWT de la spec de F-005 (`claude-docs/planning/plan.md:303-340`), verificados tanto
contra páginas sintéticas como contra el informe real del 05/08/2026, versionado en
`fuentes/iamc-deuda-corporativa-2026-08-05.pdf`. Como el archivo está en el repo, estos tests
corren sin red y sin marker `integration` en cualquier worktree.
"""

from datetime import date
from pathlib import Path

import pytest

import app.ingesta.iamc.parser as modulo_parser
from app.ingesta.cobertura import medir_cobertura
from app.ingesta.iamc.parser import (
    CAMPOS_COBERTURA,
    InformeInvalido,
    _headers_compatibles,
    _procesar_paginas,
    _validar_headers,
    parsear_informe,
)
from app.ingesta.iamc.secciones import SECCIONES
from app.ingesta.iamc.tablas import FilaCruda, FilaNoReconocida, TablaPagina
from app.ingesta.snapshot import Snapshot

RUTA_PDF_REAL = (
    Path(__file__).resolve().parents[2] / "fuentes" / "iamc-deuda-corporativa-2026-08-05.pdf"
)

_SECCION_LEY_NY = SECCIONES["DEUDA CORPORATIVA EN USD - LEY NY"]


@pytest.fixture(scope="module")
def resultado_real() -> modulo_parser.ResultadoInforme:
    """Un solo parseo del PDF real (~2-4s) compartido entre los tests que sólo lo leen. Cada uno
    igual corre contra el resultado completo: nada de esto muta `resultado.filas`."""
    return parsear_informe(RUTA_PDF_REAL.read_bytes())


def _snapshot() -> Snapshot:
    return Snapshot(fuente="IAMC")


def _fila_valida(seccion, **overrides: str | None) -> FilaCruda:
    """Una fila sintética con un valor de relleno en cada columna de la sección, para poder
    testear headers/cobertura sin escribir a mano 20+ valores por test."""
    valores: list[str | None] = []
    for campo in seccion.campos:
        if campo.campo in overrides:
            valores.append(overrides[campo.campo])
        elif campo.campo == "ticker":
            valores.append("AL30O")
        elif "fecha" in campo.campo or campo.campo.startswith("proximo"):
            valores.append("01-Jan-26")
        else:
            valores.append("100.0")
    return FilaCruda(valores=valores, pagina=1)


# --- GWT-1: ley y moneda de pago salen del título de la sección, y se registra de dónde --------


def test_cada_on_hereda_ley_y_moneda_del_titulo_de_su_seccion(resultado_real) -> None:
    por_ticker = {fila["ticker"]: fila for fila in resultado_real.filas}

    ley_ny = por_ticker["PLC7O"]
    assert ley_ny["ley"] == "Ley N.Y."
    assert ley_ny["moneda_pago"] == "USD"
    assert ley_ny["seccion"] == "DEUDA CORPORATIVA EN USD - LEY NY"

    ley_arg = por_ticker["MCC3O"]
    assert ley_arg["ley"] == "Ley Argentina"
    assert ley_arg["moneda_pago"] == "USD"
    # de paso, confirma que la continuación del emisor a dos líneas se concatenó bien.
    assert ley_arg["emisor"] == "PECOM SERVICIOS ENERGIA S.A.U"

    tasa_fija = por_ticker["PNRCO"]
    assert tasa_fija["ley"] == "Ley Argentina"
    assert tasa_fija["moneda_pago"] == "ARS"
    assert tasa_fija["estructura_cupon"] == "Tasa Fija"

    cupon_cero = por_ticker["LMS6O"]
    assert cupon_cero["ley"] == "Ley Argentina"  # viene de la columna, no del título
    assert cupon_cero["moneda_pago"] == "ARS"
    assert cupon_cero["moneda_emision"] == "USD"

    pesos = por_ticker["RVS1O"]
    assert pesos["ley"] is None
    assert pesos["moneda_pago"] == "ARS"


def test_la_seccion_de_pesos_no_declara_ley_y_el_hueco_se_cuenta(resultado_real) -> None:
    cobertura_ley = next(c for c in resultado_real.snapshot.cobertura if c.campo == "ley")
    filas_pesos = [
        f
        for f in resultado_real.filas
        if f["seccion"] == "DEUDA CORPORATIVA - EMITIDA Y PAGADERA EN PESOS"
    ]

    assert all(f["ley"] is None for f in filas_pesos)
    assert cobertura_ley.faltantes == len(filas_pesos)
    assert cobertura_ley.faltantes > 0


# --- GWT-2: layout cambiado / sección no reconocida → aborta sin filas parciales ---------------


def test_una_seccion_desconocida_aborta_el_informe_entero_sin_filas_parciales() -> None:
    fila_ok = _fila_valida(_SECCION_LEY_NY)
    tabla_ok = TablaPagina(header_names=[c.header for c in _SECCION_LEY_NY.campos], filas=[fila_ok])

    paginas = [
        (1, _SECCION_LEY_NY.titulo, None, tabla_ok),
        (2, "DEUDA CORPORATIVA EN EUR - LEY FRANCESA", None, None),
    ]

    with pytest.raises(InformeInvalido) as exc:
        _procesar_paginas(paginas, snapshot=_snapshot())

    assert exc.value.detalle["pagina"] == 2
    assert exc.value.detalle["titulo"] == "DEUDA CORPORATIVA EN EUR - LEY FRANCESA"


def test_una_seccion_reconocida_pero_sin_tabla_de_datos_tambien_aborta() -> None:
    """Si el título matchea pero la página no trajo ninguna fila de headers reconocible (por
    ejemplo, porque `find_tables()` dejó de ver la grilla), es la misma familia de problema que
    una sección desconocida: no hay con qué construir filas confiables."""
    paginas = [(1, _SECCION_LEY_NY.titulo, None, None)]

    with pytest.raises(InformeInvalido) as exc:
        _procesar_paginas(paginas, snapshot=_snapshot())

    assert exc.value.detalle["pagina"] == 1


def test_una_fila_con_forma_desconocida_tambien_aborta() -> None:
    """La detección de la forma vive en `tablas.py` (`FilaNoReconocida`, ya cubierto en
    `test_iamc_tablas.py`); esto verifica que `parsear_informe` la propaga como el mismo
    `InformeInvalido` que cualquier otro cambio de layout, forzando el error contra el PDF real
    con un monkeypatch de la extracción por página."""

    original = modulo_parser.extraer_tabla_pagina
    modulo_parser.extraer_tabla_pagina = lambda p, n: (
        (_ for _ in ()).throw(FilaNoReconocida(pagina=1, indice_fila=59, celdas=[(0, "x")]))
        if n == 1
        else original(p, n)
    )
    try:
        with pytest.raises(InformeInvalido) as exc:
            parsear_informe(RUTA_PDF_REAL.read_bytes())
    finally:
        modulo_parser.extraer_tabla_pagina = original

    assert exc.value.detalle["pagina"] == 1
    assert exc.value.detalle["indice_fila"] == 59


def test_las_paginas_de_sensibilidad_y_curva_se_saltean_sin_abortar(resultado_real) -> None:
    """Contra el PDF real: las 7 páginas de gráficos (SENSIBILIDAD/CURVA) no aportan filas ni
    alertas — saltear no es lo mismo que abortar."""
    assert resultado_real.snapshot.completo
    assert sum(resultado_real.snapshot.filas_por_tramo.values()) == len(resultado_real.filas)


# --- GWT-3: un campo numérico ausente queda vacío y se contabiliza en la cobertura -------------


def test_un_faltante_se_cuenta_en_la_cobertura_del_campo() -> None:
    fila_completa = _fila_valida(_SECCION_LEY_NY)
    fila_sin_tir = _fila_valida(_SECCION_LEY_NY, tir=None)
    tabla = TablaPagina(
        header_names=[c.header for c in _SECCION_LEY_NY.campos],
        filas=[fila_completa, fila_sin_tir],
    )
    snapshot = _snapshot()

    filas, _ = _procesar_paginas(
        [(1, _SECCION_LEY_NY.titulo, date(2026, 8, 5), tabla)], snapshot=snapshot
    )

    assert len(filas) == 2
    assert filas[0]["tir"] == 100.0
    assert filas[1]["tir"] is None

    (cobertura_tir,) = [c for c in medir_cobertura(filas, CAMPOS_COBERTURA) if c.campo == "tir"]
    assert cobertura_tir.presentes == 1
    assert cobertura_tir.total == 2
    assert snapshot.alertas == []  # ausente desde el vamos, no "ilegible": no hay nada que avisar


def test_un_valor_ilegible_se_alerta_con_el_valor_crudo_y_queda_vacio() -> None:
    fila_con_tir_rota = _fila_valida(_SECCION_LEY_NY, tir="no-es-un-numero")
    tabla = TablaPagina(
        header_names=[c.header for c in _SECCION_LEY_NY.campos], filas=[fila_con_tir_rota]
    )
    snapshot = _snapshot()

    filas, _ = _procesar_paginas(
        [(1, _SECCION_LEY_NY.titulo, date(2026, 8, 5), tabla)], snapshot=snapshot
    )

    assert filas[0]["tir"] is None
    (alerta,) = snapshot.alertas
    assert alerta.detalle["valor_crudo"] == "no-es-un-numero"
    assert alerta.detalle["campo"] == "tir"


# --- validación de headers: tolerante a truncamiento, estricta en cantidad y orden -------------


def test_headers_compatibles_tolera_el_truncamiento_por_ancho_de_celda() -> None:
    """Verificado contra la muestra real: la página 7 trae "Fecha\\nVencimient\\no" en vez de
    "Fecha\\nVencimiento"."""
    assert _headers_compatibles("Fecha\nVencimient\no", "Fecha\nVencimiento")
    assert _headers_compatibles("Estructura\nCup", "Estructura\nCupon")


def test_headers_compatibles_no_acepta_un_header_totalmente_distinto() -> None:
    assert not _headers_compatibles("Calificacion", "Estructura\nCupon")


def test_una_seccion_con_menos_columnas_de_las_esperadas_aborta() -> None:
    header_names = [c.header for c in _SECCION_LEY_NY.campos][:-1]  # falta una columna

    with pytest.raises(InformeInvalido):
        _validar_headers(_SECCION_LEY_NY, header_names, pagina=1)


# --- smoke test: el informe real completo -------------------------------------------------------


def test_el_informe_real_del_5_de_agosto_produce_filas_en_las_cinco_secciones_sin_duplicados(
    resultado_real,
) -> None:
    """El test de humo más valioso del paquete. Los conteos por sección son los que salen de
    contar tickers de verdad en el PDF (`Ticker <= índice 3` en cada página), no los que
    estimaba el plan antes de la implementación: el plan preveía 234 filas, pero rechazaba sin
    contar 8 filas reales (la última de cada una de 8 páginas, donde pdfplumber pega el bloque de
    notas metodológicas a la fila de datos) — ver el reporte de cierre de la feature."""
    assert resultado_real.fecha_informe == date(2026, 8, 5)
    assert resultado_real.snapshot.filas_por_tramo == {
        "DEUDA CORPORATIVA EN USD - LEY NY": 41,
        "DEUDA CORPORATIVA EN USD - LEY ARG": 151,
        "BONOS EN USD - PAGADEROS EN PESOS - TASA FIJA - LEY ARG": 21,
        "BONOS EN USD - PAGADEROS EN PESOS - CUPÓN CERO": 17,
        "DEUDA CORPORATIVA - EMITIDA Y PAGADERA EN PESOS": 12,
    }
    assert len(resultado_real.filas) == 242
    assert resultado_real.snapshot.completo

    tickers = [fila["ticker"] for fila in resultado_real.filas]
    assert len(set(tickers)) == len(tickers)

    emisor_multilinea = next(f for f in resultado_real.filas if f["ticker"] == "MCC3O")
    assert emisor_multilinea["emisor"] == "PECOM SERVICIOS ENERGIA S.A.U"
