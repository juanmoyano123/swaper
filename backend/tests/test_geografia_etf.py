"""El curado de geografía de ETFs: qué se carga, qué se descarta y qué se declara — F-079, D3.

El parser es puro (sin base, sin red, sin reloj), así que se ejercita escribiendo el CSV en el
test y apuntando `settings.etfs_geografia_csv` ahí — mismo andamiaje que
`test_renta_variable_paises.py`, del que este módulo es calco.

Lo que se fija acá no es que un CSV se lea: es que `indice` y `alcance` sean obligatorios (son la
razón de ser de la fila), que `pais` vacío sea el caso normal (fondo multi-país, sin composición
curada) y que un país fuera de vocabulario se descarte igual que en `paises.py`.
"""

from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.renta_variable.geografia_etf import (
    CODIGO_CURADO_AUSENTE,
    CODIGO_FILA_SIN_TRAZA,
    CODIGO_PAIS_FUERA_DE_VOCABULARIO,
    CODIGO_PAPEL_REPETIDO,
    FilaGeografiaEtf,
    leer_curado,
    leer_geografia_etfs,
    persistir,
    ruta_geografia_etfs,
    sembrar_geografia_etfs,
)

CABECERA = "ticker_papel,indice,alcance,pais,fuente,verificado\n"


def _csv(tmp_path: Path, cuerpo: str) -> Path:
    ruta = tmp_path / "etfs_geografia.csv"
    ruta.write_text(CABECERA + cuerpo, encoding="utf-8")
    return ruta


def _ajustes(ruta: Path) -> Any:
    return get_settings().model_copy(update={"etfs_geografia_csv": str(ruta)})


class FakeConexion:
    """Guarda lo que se escribió y sirve lo que el test decida que hay en la tabla."""

    def __init__(self, filas: list[dict[str, Any]] | None = None) -> None:
        self.filas = filas or []
        self.escrituras: list[tuple[Any, ...]] = []
        self.consultas: list[str] = []

    def transaction(self) -> "FakeConexion":
        return self

    async def __aenter__(self) -> "FakeConexion":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def executemany(self, query: str, args: list[tuple[Any, ...]]) -> None:
        self.consultas.append(query)
        self.escrituras.extend(args)

    async def fetch(self, query: str, *_args: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        return self.filas

    @property
    def papeles_escritos(self) -> list[str]:
        return [a[0] for a in self.escrituras]


# --- El parser -----------------------------------------------------------------------------------


def test_una_fila_mono_pais_se_lee_con_su_trazabilidad(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path,
        "EWJ,MSCI Japan Index,Acciones de gran y mediana capitalización de Japón,JP,"
        "MSCI Index Factsheet,2026-08-29\n",
    )

    curado = leer_curado(ruta)

    assert curado.alertas == []
    (fila,) = curado.filas
    assert fila == FilaGeografiaEtf(
        ticker_papel="EWJ",
        indice="MSCI Japan Index",
        alcance="Acciones de gran y mediana capitalización de Japón",
        pais="JP",
        fuente="MSCI Index Factsheet",
        verificado=date(2026, 8, 29),
    )


def test_la_region_se_deriva_del_pais_y_no_se_guarda(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path,
        "EWY,MSCI Korea Index,Acciones de gran y mediana capitalización de Corea del Sur,KR,"
        "MSCI Index Factsheet,2026-08-29\n",
    )

    (fila,) = leer_curado(ruta).filas

    assert fila.region == "Asia oriental"


def test_un_pais_vacio_es_el_caso_normal_de_un_fondo_multi_pais(tmp_path: Path) -> None:
    """Un ETF multi-país no cura su composición completa: envejece con cada rebalanceo (D3)."""
    ruta = _csv(
        tmp_path,
        "EFA,MSCI EAFE Index,"
        "Acciones de gran y mediana capitalización de mercados desarrollados ex EE.UU./Canadá,,"
        "MSCI Index Factsheet,2026-08-29\n",
    )

    curado = leer_curado(ruta)

    assert curado.alertas == []
    (fila,) = curado.filas
    assert fila.pais is None
    assert fila.region is None


def test_un_pais_fuera_del_vocabulario_no_se_carga_y_se_dice_cual(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path,
        "EWJ,MSCI Japan Index,Acciones de Japón,JPN,MSCI Index Factsheet,2026-08-29\n"
        "EWY,MSCI Korea Index,Acciones de Corea del Sur,KR,MSCI Index Factsheet,2026-08-29\n",
    )

    curado = leer_curado(ruta)

    assert [f.ticker_papel for f in curado.filas] == ["EWY"]
    assert curado.descartados[CODIGO_PAIS_FUERA_DE_VOCABULARIO] == {"EWJ": "JPN"}
    (alerta,) = curado.alertas
    assert alerta.codigo == CODIGO_PAIS_FUERA_DE_VOCABULARIO
    assert "EWJ" in alerta.mensaje


def test_una_fila_sin_indice_alcance_fuente_o_fecha_no_se_carga(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path,
        "ACWI,,Acciones globales de mercados desarrollados y emergentes,,MSCI,2026-08-29\n"
        "EFA,MSCI EAFE Index,,,MSCI,2026-08-29\n"
        "IEMG,MSCI EM Index,Acciones de mercados emergentes,,,2026-08-29\n"
        "VEA,FTSE Developed All Cap ex US,Acciones de mercados desarrollados ex EE.UU.,,FTSE,\n",
    )

    curado = leer_curado(ruta)

    assert curado.filas == []
    assert sorted(curado.descartados[CODIGO_FILA_SIN_TRAZA]) == ["ACWI", "EFA", "IEMG", "VEA"]


def test_una_fecha_ambigua_no_se_adivina(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path,
        "EWJ,MSCI Japan Index,Acciones de Japón,JP,MSCI Index Factsheet,08/09/2026\n",
    )

    assert leer_curado(ruta).filas == []


def test_un_papel_repetido_conserva_el_primero_y_no_fusiona(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path,
        "EWJ,MSCI Japan Index,Acciones de Japón,JP,MSCI Index Factsheet,2026-08-29\n"
        "EWJ,FTSE Japan Index,Otro alcance,JP,FTSE Index Factsheet,2026-08-29\n",
    )

    curado = leer_curado(ruta)

    (fila,) = curado.filas
    assert fila.indice == "MSCI Japan Index"
    assert curado.descartados[CODIGO_PAPEL_REPETIDO] == {"EWJ": "FTSE Japan Index"}


def test_el_curado_se_normaliza_como_lo_escribe_una_planilla(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path, " ewj , MSCI Japan Index , Acciones de Japón , jp ,MSCI,2026-08-29\n"
    )

    (fila,) = leer_curado(ruta).filas

    assert (fila.ticker_papel, fila.pais) == ("EWJ", "JP")


def test_un_archivo_que_no_esta_alerta_y_no_devuelve_filas(tmp_path: Path) -> None:
    curado = leer_curado(tmp_path / "no-existe.csv")

    assert curado.filas == []
    (alerta,) = curado.alertas
    assert alerta.codigo == CODIGO_CURADO_AUSENTE
    assert alerta.severidad == "error"


def test_un_csv_sin_las_columnas_esperadas_no_se_interpreta(tmp_path: Path) -> None:
    ruta = tmp_path / "etfs_geografia.csv"
    ruta.write_text("ticker,indice\nEWJ,MSCI Japan Index\n", encoding="utf-8")

    curado = leer_curado(ruta)

    assert curado.filas == []
    assert curado.alertas[0].codigo == "formato_inesperado"


def test_la_ruta_relativa_se_resuelve_contra_la_raiz_del_repo_y_no_contra_el_cwd() -> None:
    relativa = ruta_geografia_etfs(
        get_settings().model_copy(update={"etfs_geografia_csv": "data/x.csv"})
    )
    assert relativa.is_absolute()
    assert relativa.parts[-2:] == ("data", "x.csv")

    absoluta = Path("/tmp/otro/etfs.csv")
    assert ruta_geografia_etfs(_ajustes(absoluta)) == absoluta


# --- La siembra ----------------------------------------------------------------------------------


async def test_la_siembra_carga_el_curado_y_devuelve_la_cantidad(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path,
        "EWJ,MSCI Japan Index,Acciones de Japón,JP,MSCI,2026-08-29\n"
        "EFA,MSCI EAFE Index,Acciones de mercados desarrollados ex EE.UU./Canadá,,MSCI,"
        "2026-08-29\n"
        "XXXX,Indice cualquiera,Alcance cualquiera,USA,Fuente cualquiera,2026-08-29\n",
    )
    conn = FakeConexion()

    cargados = await sembrar_geografia_etfs(conn, _ajustes(ruta))

    assert cargados == 2
    assert conn.papeles_escritos == ["EWJ", "EFA"]


async def test_sembrar_dos_veces_deja_lo_mismo(tmp_path: Path) -> None:
    """Idempotente porque no hay reloj ni fuente externa en el medio."""
    ruta = _csv(tmp_path, "EWJ,MSCI Japan Index,Acciones de Japón,JP,MSCI,2026-08-29\n")
    ajustes = _ajustes(ruta)

    primera = await sembrar_geografia_etfs(FakeConexion(), ajustes)
    segunda = await sembrar_geografia_etfs(FakeConexion(), ajustes)

    assert primera == segunda == 1


async def test_sin_artefacto_no_se_escribe_nada_y_devuelve_cero(tmp_path: Path) -> None:
    conn = FakeConexion()

    cargados = await sembrar_geografia_etfs(conn, _ajustes(tmp_path / "no-existe.csv"))

    assert conn.escrituras == []
    assert cargados == 0


async def test_persistir_sin_filas_no_escribe_nada() -> None:
    conn = FakeConexion()

    cargados = await persistir(conn, [])

    assert cargados == 0
    assert conn.escrituras == []


async def test_el_upsert_no_protege_ninguna_columna_con_coalesce(tmp_path: Path) -> None:
    """El CSV es la fuente de verdad completa por fila: un re-run pisa todo con el valor nuevo."""
    ruta = _csv(tmp_path, "EFA,MSCI EAFE Index,Acciones desarrolladas ex EE.UU.,,MSCI,2026-08-29\n")
    conn = FakeConexion()

    await sembrar_geografia_etfs(conn, _ajustes(ruta))

    (consulta,) = conn.consultas
    assert "COALESCE" not in consulta.upper()
    assert "pais = EXCLUDED.pais" in consulta
    assert "indice = EXCLUDED.indice" in consulta


# --- La lectura ----------------------------------------------------------------------------------


async def test_leer_geografia_etfs_indexa_por_papel() -> None:
    conn = FakeConexion(
        [
            {
                "ticker_papel": "EWJ",
                "indice": "MSCI Japan Index",
                "alcance": "Acciones de Japón",
                "pais": "JP",
                "fuente": "MSCI Index Factsheet",
                "verificado": date(2026, 8, 29),
            }
        ]
    )

    geografia = await leer_geografia_etfs(conn)

    assert geografia["EWJ"].pais == "JP"
    assert geografia["EWJ"].region == "Asia oriental"
