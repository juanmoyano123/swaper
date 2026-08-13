"""Criterio 2: si falta una variable obligatoria, el servicio no arranca y dice cuál."""

import pytest

from app.core.config import Settings, get_settings


@pytest.fixture
def sin_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla del .env real: acá se prueba qué pasa cuando la variable no está en ningún lado."""
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()


def test_carga_la_configuracion_cuando_esta_completa() -> None:
    settings = get_settings()

    assert settings.database_url.startswith("postgresql://")
    assert settings.log_level == "INFO"
    assert settings.environment == "development"


def test_no_arranca_sin_database_url(
    sin_env_file: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    with pytest.raises(SystemExit) as salida:
        get_settings()

    assert salida.value.code == 1
    assert "DATABASE_URL" in capsys.readouterr().err


def test_una_variable_presente_pero_vacia_falla_igual(
    sin_env_file: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(SystemExit):
        get_settings()

    assert "SUPABASE_SERVICE_ROLE_KEY" in capsys.readouterr().err


def test_el_mensaje_nombra_todas_las_variables_que_faltan(
    sin_env_file: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    get_settings.cache_clear()

    with pytest.raises(SystemExit):
        get_settings()

    error = capsys.readouterr().err
    assert "DATABASE_URL" in error
    assert "SUPABASE_URL" in error
