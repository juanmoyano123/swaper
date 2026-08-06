"""Lectura del artefacto curado: qué se carga, qué se descarta y con qué trazabilidad.

Se prueba sobre CSV escritos en el test y, al final, sobre el artefacto real del repo: ese último
es el que verifica que el contrato que la feature asume siga siendo el que el archivo tiene.
"""

from datetime import date
from pathlib import Path

from app.condiciones.semilla import (
    CAMPOS,
    CODIGO_FUERA_DE_VOCABULARIO,
    CODIGO_SEMILLA_AUSENTE,
    CODIGO_TICKER_REPETIDO,
    CODIGO_VALOR_ILEGIBLE,
    FECHA_ARTEFACTO,
    ORIGEN_SEMILLA,
    leer_semilla,
)
from app.ingesta.alertas import CODIGO_FORMATO_INESPERADO, Severidad

RAIZ_REPO = Path(__file__).resolve().parents[2]
CSV_REAL = RAIZ_REPO / "data" / "condiciones_emision.csv"

ENCABEZADO = "ticker,ley,moneda_pago,lamina,calificacion,sector,underlying\n"
FECHA_DE_PRUEBA = date(2026, 1, 15)


def _escribir(tmp_path: Path, cuerpo: str, encabezado: str = ENCABEZADO) -> Path:
    ruta = tmp_path / "condiciones.csv"
    ruta.write_text(encabezado + cuerpo, encoding="utf-8")
    return ruta


def test_cada_valor_cargado_trae_el_origen_del_artefacto_y_su_fecha(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, "AL30,Ley Argentina,MEP,1,,Soberano,Gobierno Argentino\n")

    semilla = leer_semilla(ruta, FECHA_DE_PRUEBA)

    (fila,) = semilla.filas
    assert fila.ticker == "AL30"
    assert fila.valores["ley"].valor == "Ley Argentina"
    assert all(valor.origen == ORIGEN_SEMILLA for valor in fila.valores.values())
    assert all(valor.fecha == FECHA_DE_PRUEBA for valor in fila.valores.values())


def test_un_campo_vacio_no_queda_como_valor_vacio_sino_ausente(tmp_path: Path) -> None:
    """La distinción es la que impide escribir un valor sin origen ni fecha."""
    ruta = _escribir(tmp_path, "AL30,Ley Argentina,MEP,, ,,\n")

    (fila,) = leer_semilla(ruta, FECHA_DE_PRUEBA).filas

    assert set(fila.valores) == {"ley", "moneda_pago"}


def test_la_lamina_se_carga_como_numero(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, "AL30,,,1000,,,\n")

    (fila,) = leer_semilla(ruta, FECHA_DE_PRUEBA).filas

    assert fila.valores["lamina"].valor == 1000.0


def test_una_lamina_que_no_es_numero_no_se_carga_y_se_reporta(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, "AL30,,,mil,,,\n")

    semilla = leer_semilla(ruta, FECHA_DE_PRUEBA)

    (fila,) = semilla.filas
    assert "lamina" not in fila.valores
    (alerta,) = semilla.alertas
    assert alerta.codigo == CODIGO_VALOR_ILEGIBLE
    assert alerta.detalle["valores"] == {"AL30": "mil"}


def test_una_ley_fuera_del_vocabulario_no_se_carga_y_se_reporta(tmp_path: Path) -> None:
    """El antecedente es "Ley Inglesa": una categoría que no existe, traducida de la fuente."""
    ruta = _escribir(tmp_path, "AL30,Ley Inglesa,MEP,,,,\n")

    semilla = leer_semilla(ruta, FECHA_DE_PRUEBA)

    (fila,) = semilla.filas
    assert "ley" not in fila.valores
    assert fila.valores["moneda_pago"].valor == "MEP"
    (alerta,) = semilla.alertas
    assert alerta.codigo == CODIGO_FUERA_DE_VOCABULARIO
    assert "AL30" in alerta.detalle["valores"]


def test_una_moneda_de_pago_fuera_del_vocabulario_tampoco_se_carga(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, "AL30,,EUR,,,,\n")

    semilla = leer_semilla(ruta, FECHA_DE_PRUEBA)

    assert semilla.filas[0].valores == {}
    assert semilla.alertas[0].detalle["campo"] == "moneda_pago"


def test_un_ticker_repetido_conserva_la_primera_aparicion_y_se_reporta(tmp_path: Path) -> None:
    """No se fusionan: fusionar sería decidir cuál de las dos versiones vale."""
    ruta = _escribir(
        tmp_path,
        "AL30,Ley Argentina,MEP,,,,\nAL30,Ley N.Y.,CCL,,,,\n",
    )

    semilla = leer_semilla(ruta, FECHA_DE_PRUEBA)

    (fila,) = semilla.filas
    assert fila.valores["ley"].valor == "Ley Argentina"
    (alerta,) = semilla.alertas
    assert alerta.codigo == CODIGO_TICKER_REPETIDO


def test_una_fila_sin_ticker_se_ignora(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, " ,Ley Argentina,MEP,,,,\nAL30,Ley Argentina,MEP,,,,\n")

    assert [f.ticker for f in leer_semilla(ruta, FECHA_DE_PRUEBA).filas] == ["AL30"]


def test_un_archivo_ausente_devuelve_cero_filas_y_una_alerta_de_error(tmp_path: Path) -> None:
    """Sin filas no se escribe: es lo que evita vaciar la tabla por una ruta mal puesta."""
    semilla = leer_semilla(tmp_path / "no-existe.csv", FECHA_DE_PRUEBA)

    assert semilla.filas == []
    (alerta,) = semilla.alertas
    assert alerta.codigo == CODIGO_SEMILLA_AUSENTE
    assert alerta.severidad is Severidad.ERROR
    assert alerta.accion_requerida


def test_un_csv_al_que_le_falta_una_columna_no_carga_nada_y_dice_cual(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, "AL30,Ley Argentina\n", encabezado="ticker,ley\n")

    semilla = leer_semilla(ruta, FECHA_DE_PRUEBA)

    assert semilla.filas == []
    (alerta,) = semilla.alertas
    assert alerta.codigo == CODIGO_FORMATO_INESPERADO
    assert "lamina" in alerta.detalle["faltantes"]


def test_el_bom_de_las_planillas_no_rompe_la_primera_columna(tmp_path: Path) -> None:
    ruta = tmp_path / "con-bom.csv"
    ruta.write_text(ENCABEZADO + "AL30,Ley Argentina,MEP,,,,\n", encoding="utf-8-sig")

    assert leer_semilla(ruta, FECHA_DE_PRUEBA).filas[0].ticker == "AL30"


# --- El artefacto real del repo -----------------------------------------------------------------


def test_el_csv_curado_del_repo_se_lee_entero_y_sin_alertas() -> None:
    """823 especies, las seis columnas trazables y ningún valor que haya que descartar.

    Si esto falla, alguien editó el artefacto: es dato irrecuperable y el cambio hay que mirarlo.
    """
    semilla = leer_semilla(CSV_REAL)

    assert len(semilla.filas) == 823
    assert semilla.alertas == []
    assert semilla.fecha == FECHA_ARTEFACTO


def test_la_fecha_declarada_del_artefacto_no_es_del_futuro() -> None:
    """La constante se actualiza a mano cuando se reemplaza el CSV; una fecha futura es un error."""
    assert date.today() >= FECHA_ARTEFACTO


def test_la_cobertura_del_artefacto_es_la_que_la_feature_declara() -> None:
    """Los números que justifican la feature, fijados para que un cambio silencioso se note."""
    filas = leer_semilla(CSV_REAL).filas
    presentes = {campo: sum(1 for f in filas if campo in f.valores) for campo in CAMPOS}

    assert presentes == {
        "ley": 693,
        "moneda_pago": 688,
        "lamina": 568,
        "calificacion": 359,
        "sector": 423,
        "underlying": 376,
    }
