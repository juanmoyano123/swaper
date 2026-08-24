"""El puente `codigo_cnv` -> id interno de la CNV — el enlace de la ficha de un FCI a su
"COMPOSICIÓN DE CARTERA" pública."""

from pathlib import Path

from app.fci import enlaces


def _escribir_csv(tmp_path: Path) -> Path:
    ruta = tmp_path / "fci_cnv_ids.csv"
    ruta.write_text(
        "codigo_cnv,id_detalle_cnv,denominacion_cnv,verificado_por,curado_en\n"
        "500,63918,1810 MAS AHORRO,nombre,2026-08-23\n",
        encoding="utf-8",
    )
    return ruta


class _SettingsFalsa:
    def __init__(self, ruta: Path) -> None:
        self.fci_cnv_csv = str(ruta)


def test_enlace_url_exacta_para_codigo_mapeado(tmp_path, monkeypatch) -> None:
    ruta = _escribir_csv(tmp_path)
    monkeypatch.setattr(enlaces, "get_settings", lambda: _SettingsFalsa(ruta))

    assert (
        enlaces.enlace_composicion_cnv("500")
        == "https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/DetallesFCI/63918"
    )


def test_enlace_none_si_codigo_cnv_no_esta_mapeado(tmp_path, monkeypatch) -> None:
    ruta = _escribir_csv(tmp_path)
    monkeypatch.setattr(enlaces, "get_settings", lambda: _SettingsFalsa(ruta))

    assert enlaces.enlace_composicion_cnv("999999") is None


def test_enlace_none_si_no_hay_codigo_cnv(tmp_path, monkeypatch) -> None:
    ruta = _escribir_csv(tmp_path)
    monkeypatch.setattr(enlaces, "get_settings", lambda: _SettingsFalsa(ruta))

    assert enlaces.enlace_composicion_cnv(None) is None


def test_enlace_none_si_el_csv_no_existe(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(enlaces, "get_settings", lambda: _SettingsFalsa(tmp_path / "no_existe.csv"))

    assert enlaces.enlace_composicion_cnv("500") is None
