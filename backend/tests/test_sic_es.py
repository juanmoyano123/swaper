"""La traducción curada al español del SIC (sector + rubro específico) — F-079, fase 1.

Los dos CSV son opcionales por diseño: mientras el dueño del producto no valide el curado, el
archivo no existe y el módulo tiene que seguir funcionando devolviendo `None`, igual que
`pais_cedear` con cero filas. Lo que se fija acá es esa gracia — no sólo el camino feliz.
"""

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.renta_variable.sic_es import rubro_de, sector_de

CABECERA_SECTORES = "major_group,nombre_en,etiqueta_es\n"
CABECERA_RUBROS = "sic_codigo,titulo_en,etiqueta_es\n"


def _csv_sectores(tmp_path: Path, cuerpo: str, nombre: str = "sic_sectores.csv") -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(CABECERA_SECTORES + cuerpo, encoding="utf-8")
    return ruta


def _csv_rubros(tmp_path: Path, cuerpo: str, nombre: str = "sic_rubros.csv") -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(CABECERA_RUBROS + cuerpo, encoding="utf-8")
    return ruta


def _apuntar(
    monkeypatch: pytest.MonkeyPatch, *, sectores: Path | None, rubros: Path | None
) -> None:
    if sectores is not None:
        monkeypatch.setenv("SIC_SECTORES_CSV", str(sectores))
    if rubros is not None:
        monkeypatch.setenv("SIC_RUBROS_CSV", str(rubros))
    get_settings.cache_clear()


# --- CSV ausente: el estado esperado hasta que el dueño valida el curado --------------------------


def test_sin_csv_de_sectores_sector_de_es_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _apuntar(monkeypatch, sectores=tmp_path / "no_existe.csv", rubros=None)
    assert sector_de("2834") is None


def test_sin_csv_de_rubros_rubro_de_es_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _apuntar(monkeypatch, sectores=None, rubros=tmp_path / "no_existe.csv")
    assert rubro_de("2834") is None


# --- CSV presente con filas válidas -----------------------------------------------------------


def test_sector_de_devuelve_la_etiqueta_es_del_major_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _csv_sectores(tmp_path, "28,Chemicals And Allied Products,Química\n")
    _apuntar(monkeypatch, sectores=ruta, rubros=None)
    assert sector_de("2834") == "Química"


def test_rubro_de_devuelve_la_etiqueta_es_del_sic_codigo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _csv_rubros(tmp_path, "2834,Pharmaceutical Preparations,Preparados farmacéuticos\n")
    _apuntar(monkeypatch, sectores=None, rubros=ruta)
    assert rubro_de("2834") == "Preparados farmacéuticos"


def test_sector_de_matchea_con_y_sin_ceros_a_la_izquierda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El CSV trae `01` (cero a la izquierda, como lo escribiría una planilla) y el `sic_codigo`
    persistido puede llegar como `"100"` (sin ceros, como ya documenta `sic.py`)."""
    ruta = _csv_sectores(tmp_path, "01,Agricultural Production Crops,Producción agrícola\n")
    _apuntar(monkeypatch, sectores=ruta, rubros=None)
    assert sector_de("100") == "Producción agrícola"
    assert sector_de(100) == "Producción agrícola"


def test_rubro_de_matchea_con_y_sin_ceros_a_la_izquierda(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _csv_rubros(tmp_path, "0100,Agricultural Production Crops,Producción agrícola\n")
    _apuntar(monkeypatch, sectores=None, rubros=ruta)
    assert rubro_de("100") == "Producción agrícola"


# --- Fila malformada: se descarta sin romper el resto ------------------------------------------


def test_fila_con_codigo_no_numerico_se_descarta_sin_romper_las_demas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _csv_sectores(
        tmp_path,
        "XX,Broken Row,Fila Rota\n28,Chemicals And Allied Products,Química\n",
    )
    _apuntar(monkeypatch, sectores=ruta, rubros=None)
    assert sector_de("2834") == "Química"


def test_fila_con_etiqueta_vacia_se_descarta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _csv_sectores(tmp_path, "28,Chemicals And Allied Products,\n")
    _apuntar(monkeypatch, sectores=ruta, rubros=None)
    assert sector_de("2834") is None


def test_csv_sin_la_columna_de_etiqueta_no_rompe_y_devuelve_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falta `etiqueta_es`, la columna que el módulo necesita devolver: sin ella no hay nada que
    leer, y el archivo entero se descarta en vez de romper."""
    ruta = tmp_path / "sic_sectores_incompleto.csv"
    ruta.write_text("major_group,nombre_en\n28,Chemicals And Allied Products\n", encoding="utf-8")
    _apuntar(monkeypatch, sectores=ruta, rubros=None)
    assert sector_de("2834") is None


# --- Código no encontrado en el CSV --------------------------------------------------------------


def test_major_group_ausente_del_csv_es_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _csv_sectores(tmp_path, "28,Chemicals And Allied Products,Química\n")
    _apuntar(monkeypatch, sectores=ruta, rubros=None)
    assert sector_de("7372") is None  # Prepackaged Software, major group 73, no está en el CSV


def test_sic_codigo_ausente_del_csv_de_rubros_es_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta = _csv_rubros(tmp_path, "2834,Pharmaceutical Preparations,Preparados farmacéuticos\n")
    _apuntar(monkeypatch, sectores=None, rubros=ruta)
    assert rubro_de("7372") is None


# --- Sin sic_codigo no hay nada que buscar --------------------------------------------------------


def test_sin_sic_codigo_no_se_busca_nada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ruta_sectores = _csv_sectores(tmp_path, "28,Chemicals And Allied Products,Química\n")
    ruta_rubros = _csv_rubros(tmp_path, "2834,Pharmaceutical Preparations,Preparados\n")
    _apuntar(monkeypatch, sectores=ruta_sectores, rubros=ruta_rubros)
    assert sector_de(None) is None
    assert rubro_de(None) is None
    assert sector_de("no es un numero") is None
    assert rubro_de("no es un numero") is None
