"""Endpoint de subida del informe de IAMC (`POST /iamc/informe`) — F-005.

httpx contra la app en memoria (`ASGITransport`), como el resto de la suite (`conftest.py`). El
directorio donde se guarda el PDF se redirige a `tmp_path` en cada test: no se escribe de verdad
en `fuentes/`.
"""

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.ingesta.iamc.parser import InformeInvalido
from tests.conftest import cliente

RUTA_PDF_REAL = (
    Path(__file__).resolve().parents[2] / "fuentes" / "iamc-deuda-corporativa-2026-08-05.pdf"
)

RUTA_ENDPOINT = "/api/v1/iamc/informe"


@pytest.fixture(autouse=True)
def _directorio_iamc_en_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IAMC_DIRECTORIO", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_un_content_type_que_no_es_pdf_devuelve_400(crear_app) -> None:
    app = crear_app()
    async with cliente(app) as http:
        respuesta = await http.post(
            RUTA_ENDPOINT,
            files={"archivo": ("informe.txt", b"hola", "text/plain")},
        )

    assert respuesta.status_code == 400
    assert "application/pdf" in respuesta.json()["error"]["message"]


async def test_un_archivo_vacio_devuelve_400(crear_app) -> None:
    app = crear_app()
    async with cliente(app) as http:
        respuesta = await http.post(
            RUTA_ENDPOINT,
            files={"archivo": ("informe.pdf", b"", "application/pdf")},
        )

    assert respuesta.status_code == 400
    assert "vacío" in respuesta.json()["error"]["message"]


async def test_un_archivo_de_mas_de_25mb_devuelve_413(crear_app) -> None:
    contenido_enorme = b"0" * (26 * 1024 * 1024)
    app = crear_app()
    async with cliente(app) as http:
        respuesta = await http.post(
            RUTA_ENDPOINT,
            files={"archivo": ("informe.pdf", contenido_enorme, "application/pdf")},
        )

    assert respuesta.status_code == 413


async def test_un_contenido_que_no_empieza_con_la_firma_pdf_devuelve_400(crear_app) -> None:
    app = crear_app()
    async with cliente(app) as http:
        contenido_falso = b"esto dice ser un pdf pero no lo es"
        respuesta = await http.post(
            RUTA_ENDPOINT,
            files={"archivo": ("informe.pdf", contenido_falso, "application/pdf")},
        )

    assert respuesta.status_code == 400
    assert "%PDF-" in respuesta.json()["error"]["message"]


async def test_el_pdf_real_se_sube_se_parsea_y_se_guarda_con_el_nombre_esperado(
    crear_app, tmp_path: Path
) -> None:
    contenido = RUTA_PDF_REAL.read_bytes()
    nombre_subido = "iamc-deuda-corporativa-2026-08-05.pdf"
    app = crear_app()
    async with cliente(app) as http:
        respuesta = await http.post(
            RUTA_ENDPOINT,
            files={"archivo": (nombre_subido, contenido, "application/pdf")},
        )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["fecha_informe"] == "2026-08-05"
    assert cuerpo["archivo"] == "iamc-deuda-corporativa-2026-08-05.pdf"
    assert cuerpo["snapshot"]["filas_por_tramo"]["DEUDA CORPORATIVA EN USD - LEY NY"] == 41
    assert cuerpo["snapshot"]["total_filas"] == 242
    assert cuerpo["snapshot"]["completo"] is True

    guardado = tmp_path / "iamc-deuda-corporativa-2026-08-05.pdf"
    assert guardado.exists()
    assert guardado.read_bytes() == contenido


async def test_subir_el_mismo_informe_dos_veces_sobreescribe_no_duplica(
    crear_app, tmp_path: Path
) -> None:
    contenido = RUTA_PDF_REAL.read_bytes()
    app = crear_app()
    async with cliente(app) as http:
        for _ in range(2):
            respuesta = await http.post(
                RUTA_ENDPOINT,
                files={"archivo": ("informe.pdf", contenido, "application/pdf")},
            )
            assert respuesta.status_code == 200

    assert list(tmp_path.glob("iamc-deuda-corporativa-*.pdf")) == [
        tmp_path / "iamc-deuda-corporativa-2026-08-05.pdf"
    ]


async def test_un_informe_que_no_se_puede_parsear_devuelve_422_y_guarda_el_pdf_como_rechazado(
    crear_app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _parsear_falso(contenido: bytes):
        raise InformeInvalido(
            "sección no reconocida: 'DEUDA CORPORATIVA EN EUR - LEY FRANCESA'",
            pagina=20,
            titulo="DEUDA CORPORATIVA EN EUR - LEY FRANCESA",
        )

    monkeypatch.setattr("app.api.v1.iamc.parsear_informe", _parsear_falso)

    app = crear_app()
    async with cliente(app) as http:
        respuesta = await http.post(
            RUTA_ENDPOINT,
            files={"archivo": ("informe.pdf", b"%PDF-1.4\nno importa el resto", "application/pdf")},
        )

    assert respuesta.status_code == 422
    cuerpo = respuesta.json()
    assert cuerpo["error"]["code"] == "validation_error"
    assert "no se pudo parsear" in cuerpo["error"]["message"]

    rechazados = list(tmp_path.glob("iamc-rechazado-*.pdf"))
    assert len(rechazados) == 1
    # nada de lo aceptado se guardó: no hay filas parciales ni archivo con nombre de "aceptado".
    assert not list(tmp_path.glob("iamc-deuda-corporativa-*.pdf"))
