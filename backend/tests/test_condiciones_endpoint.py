"""La siembra de punta a punta y sus tres endpoints, sin base y sin tocar el artefacto del repo.

El CSV se escribe en el test y `settings.condiciones_csv` se apunta ahí: la corrida completa se
ejercita igual y el artefacto curado —que es irrecuperable— no se toca ni por accidente.
"""

from pathlib import Path

import pytest

from app.condiciones.corrida import ruta_semilla, sembrar
from app.condiciones.persistencia import HERENCIA_ENTRE_ESPECIES
from app.condiciones.semilla import CAMPOS, CODIGO_SEMILLA_AUSENTE
from app.core.config import get_settings
from tests.conftest import cliente
from tests.test_condiciones_persistencia import FakeConexionCurada

ENCABEZADO = "ticker,ley,moneda_pago,lamina,calificacion,sector,underlying\n"

# Una emisión que hereda (AL30) y otra en conflicto (MR46), que es todo lo que la corrida decide.
SEMILLA = (
    "AL30,Ley Argentina,MEP,1,,Soberano,Gobierno Argentino\n"
    "AL30D,,,,,,\n"
    "AL30C,,,,,,\n"
    "MR46O,Ley N.Y.,CCL,100,,O&G,Emisor S.A.\n"
    "MR46D,Ley N.Y.,CCL,1000,,O&G,Emisor S.A.\n"
)


@pytest.fixture
def settings_con_semilla(tmp_path: Path, monkeypatch):
    ruta = tmp_path / "condiciones_emision.csv"
    ruta.write_text(ENCABEZADO + SEMILLA, encoding="utf-8")
    monkeypatch.setenv("CONDICIONES_CSV", str(ruta))
    get_settings.cache_clear()
    return get_settings()


def _conexion() -> FakeConexionCurada:
    return FakeConexionCurada(
        presentes={"total": 8, **dict.fromkeys(CAMPOS, 0), "lamina": 3, "ley": 5},
        filas_fetch=[
            {"campo": "lamina", "origen": "condiciones_emision.csv (curado)", "filas": 1},
            {"campo": "lamina", "origen": "herencia de AL30", "filas": 2},
        ],
        fuera_del_universo=2,
    )


# --- La corrida ---------------------------------------------------------------------------------


async def test_la_siembra_hereda_vacia_por_conflicto_y_reporta_las_dos_cosas(
    settings_con_semilla,
) -> None:
    conexion = _conexion()

    resultado = await sembrar(conexion, settings_con_semilla)

    assert resultado.escritura.filas == 5
    # AL30D y AL30C heredan los cinco campos que AL30 declara.
    assert resultado.resolucion.heredados_por_campo["lamina"] == 2
    # MR46O y MR46D declaran láminas distintas: las dos quedan vacías.
    assert resultado.resolucion.vaciados_por_campo["lamina"] == 2
    (conflicto,) = resultado.resolucion.conflictos
    assert conflicto.como_dict() == {
        "campo": "lamina",
        "emision": "MR46",
        "valores": {"MR46D": 1000.0, "MR46O": 100.0},
    }


async def test_ningun_campo_de_la_emision_en_conflicto_llega_a_la_base(
    settings_con_semilla,
) -> None:
    """Lo que se escribe tiene que ser lo que la resolución decidió, no lo que el CSV decía."""
    conexion = _conexion()

    await sembrar(conexion, settings_con_semilla)

    escritas = {
        fila[0]: fila for fila in conexion.filas_de("condiciones_emision")
    }  # ticker es la primera columna
    indice_lamina = 1 + 3 * CAMPOS.index("lamina")
    assert escritas["MR46O"][indice_lamina] is None
    assert escritas["MR46D"][indice_lamina] is None
    assert escritas["AL30C"][indice_lamina] == 1.0
    assert escritas["AL30C"][indice_lamina + 1] == "herencia de AL30"


async def test_un_artefacto_ausente_no_escribe_nada_y_lo_declara(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CONDICIONES_CSV", str(tmp_path / "no-existe.csv"))
    get_settings.cache_clear()
    conexion = FakeConexionCurada(presentes={"total": 0, **dict.fromkeys(CAMPOS, 0)})

    resultado = await sembrar(conexion, get_settings())

    assert not conexion.escribio_en("condiciones_emision")
    assert [a.codigo for a in resultado.semilla.alertas] == [CODIGO_SEMILLA_AUSENTE]


async def test_sembrar_dos_veces_deja_lo_mismo(settings_con_semilla) -> None:
    """No hay reloj ni fuente externa en el medio: la siembra es idempotente."""
    primera = await sembrar(_conexion(), settings_con_semilla)
    segunda = await sembrar(_conexion(), settings_con_semilla)

    assert primera.como_dict() == segunda.como_dict()


def test_una_ruta_relativa_se_resuelve_contra_la_raiz_del_repo() -> None:
    """El cwd cambia según se arranque con uvicorn, pytest o Docker; la raíz del repo no."""
    ruta = ruta_semilla(get_settings().model_copy(update={"condiciones_csv": "data/x.csv"}))

    assert ruta.is_absolute()
    assert ruta.parts[-2:] == ("data", "x.csv")


def test_una_ruta_absoluta_se_usa_tal_cual(tmp_path: Path) -> None:
    absoluta = tmp_path / "otra.csv"

    ruta = ruta_semilla(get_settings().model_copy(update={"condiciones_csv": str(absoluta)}))

    assert ruta == absoluta


# --- Los endpoints -----------------------------------------------------------------------------


async def test_post_semilla_devuelve_cobertura_conflictos_y_alertas(
    crear_app, settings_con_semilla
) -> None:
    async with cliente(crear_app(_conexion())) as http:
        respuesta = await http.post("/api/v1/condiciones/semilla")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["escrito"] == {"condiciones_emision": 5}
    assert cuerpo["fecha_artefacto"] == "2026-08-05"
    assert cuerpo["conflictos"][0]["campo"] == "lamina"
    assert cuerpo["curados_fuera_del_universo"] == 2
    assert {c["campo"] for c in cuerpo["cobertura_universo"]} == set(CAMPOS)


async def test_post_semilla_responde_200_aunque_el_artefacto_no_este(
    crear_app, tmp_path, monkeypatch
) -> None:
    """La corrida corrió: su estado lo declaran las alertas, no el status HTTP."""
    monkeypatch.setenv("CONDICIONES_CSV", str(tmp_path / "no-existe.csv"))
    get_settings.cache_clear()
    conexion = FakeConexionCurada(presentes={"total": 0, **dict.fromkeys(CAMPOS, 0)})

    async with cliente(crear_app(conexion)) as http:
        respuesta = await http.post("/api/v1/condiciones/semilla")

    assert respuesta.status_code == 200
    assert respuesta.json()["alertas"][0]["codigo"] == CODIGO_SEMILLA_AUSENTE


async def test_get_cobertura_abre_cada_campo_por_origen(crear_app) -> None:
    async with cliente(crear_app(_conexion())) as http:
        respuesta = await http.get("/api/v1/condiciones/cobertura")

    campos = {c["campo"]: c for c in respuesta.json()["campos"]}
    assert campos["lamina"]["presentes"] == 3
    assert campos["lamina"]["por_origen"][HERENCIA_ENTRE_ESPECIES] == 2


async def test_el_listado_devuelve_el_triplete_completo_de_cada_campo(crear_app) -> None:
    conexion = _conexion()
    conexion.filas_fetch = [
        {
            "ticker": "AL30",
            **{parte: None for campo in CAMPOS for parte in (campo, f"{campo}_origen")},
            **{f"{campo}_fecha": None for campo in CAMPOS},
        }
    ]

    async with cliente(crear_app(conexion)) as http:
        respuesta = await http.get("/api/v1/condiciones?limit=1")

    (item,) = respuesta.json()["items"]
    assert item["ticker"] == "AL30"
    for campo in CAMPOS:
        assert f"{campo}_origen" in item and f"{campo}_fecha" in item


async def test_los_endpoints_devuelven_503_sin_base(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        for metodo, ruta in (
            ("post", "/api/v1/condiciones/semilla"),
            ("get", "/api/v1/condiciones/cobertura"),
            ("get", "/api/v1/condiciones"),
        ):
            respuesta = await getattr(http, metodo)(ruta)
            assert respuesta.status_code == 503, ruta
