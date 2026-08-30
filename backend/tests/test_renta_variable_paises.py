"""El curado de países de CEDEARs: qué se carga, qué se descarta y qué se declara — F-078.

El parser es puro (sin base, sin red, sin reloj), así que se ejercita escribiendo el CSV en el test
y apuntando `settings.paises_cedears_csv` ahí — mismo andamiaje que `test_condiciones_endpoint.py`.

Lo que se fija acá no es que un CSV se lea: es **hasta dónde se puede afirmar un país y dónde hay
que declarar que no se sabe**. Los casos que más importan son los tres descartes, porque cada uno
deja un papel sin país y el sistema tiene que decir cuál y por qué en vez de cargarlo a medias.
"""

from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.renta_variable.paises import (
    CODIGO_CURADO_AUSENTE,
    CODIGO_FILA_SIN_TRAZA,
    CODIGO_PAIS_FUERA_DE_VOCABULARIO,
    CODIGO_PAPEL_REPETIDO,
    FilaPais,
    leer_curado,
    leer_paises,
    ruta_paises,
    sembrar_paises,
)

CABECERA = "ticker_papel,pais,fuente,verificado\n"


def _csv(tmp_path: Path, cuerpo: str) -> Path:
    ruta = tmp_path / "paises_cedears.csv"
    ruta.write_text(CABECERA + cuerpo, encoding="utf-8")
    return ruta


def _ajustes(ruta: Path) -> Any:
    return get_settings().model_copy(update={"paises_cedears_csv": str(ruta)})


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


def test_una_fila_completa_se_lee_con_su_trazabilidad(tmp_path: Path) -> None:
    """El país nunca viaja solo: la fuente y la fecha van al lado, como todo dato externo del
    proyecto (regla 11)."""
    ruta = _csv(tmp_path, "AAPL,US,Apple Inc. 10-K FY2025 (SEC EDGAR),2026-08-28\n")

    curado = leer_curado(ruta)

    assert curado.alertas == []
    (fila,) = curado.filas
    assert fila == FilaPais(
        ticker_papel="AAPL",
        pais="US",
        fuente="Apple Inc. 10-K FY2025 (SEC EDGAR)",
        verificado=date(2026, 8, 28),
    )


def test_la_region_se_deriva_del_pais_y_no_se_guarda(tmp_path: Path) -> None:
    """La región no está en el CSV ni en la tabla: sale del país con la subregión M49 al leer,
    igual que `division_cadena` sale del código SIC."""
    ruta = _csv(tmp_path, "VALE,BR,Vale S.A. Form 20-F 2025,2026-08-28\n")

    (fila,) = leer_curado(ruta).filas

    assert fila.region == "América Latina y el Caribe"


def test_un_pais_vacio_es_un_valor_declarado_y_no_un_descarte(tmp_path: Path) -> None:
    """"Se investigó y no se resolvió" es un resultado, y su fuente es donde queda escrita la duda.
    Es también el caso de los ETFs, cuyo eje geográfico es `region_etf` y no un país."""
    ruta = _csv(tmp_path, "GLD,,ETF sobre oro físico: sin país de exposición,2026-08-28\n")

    curado = leer_curado(ruta)

    assert curado.alertas == []
    (fila,) = curado.filas
    assert fila.pais is None
    assert fila.region is None
    assert fila.fuente.startswith("ETF sobre oro")


def test_un_pais_fuera_del_vocabulario_no_se_carga_y_se_dice_cual(tmp_path: Path) -> None:
    """El vocabulario cerrado es `REGION_M49`. Un país del que no podemos decir la región entraría a
    la base para aparecer en pantalla sin poder agruparse por ningún eje, y no se distinguiría de un
    typo de la planilla."""
    ruta = _csv(
        tmp_path,
        "AAPL,USA,Apple Inc. 10-K,2026-08-28\nMELI,AR,MercadoLibre 10-K,2026-08-28\n",
    )

    curado = leer_curado(ruta)

    assert [f.ticker_papel for f in curado.filas] == ["MELI"]
    assert curado.descartados[CODIGO_PAIS_FUERA_DE_VOCABULARIO] == {"AAPL": "USA"}
    (alerta,) = curado.alertas
    assert alerta.codigo == CODIGO_PAIS_FUERA_DE_VOCABULARIO
    assert "AAPL" in alerta.mensaje


def test_una_fila_sin_fuente_o_sin_fecha_no_se_carga(tmp_path: Path) -> None:
    """La tabla las exige `NOT NULL` y el producto no muestra un país sin decir de dónde salió. La
    fila se cae entera aunque el país sea impecable, y el detalle dice cuál de las dos faltaba."""
    ruta = _csv(
        tmp_path,
        "AAPL,US,,2026-08-28\nMSFT,US,Microsoft 10-K,\nKO,US,Coca-Cola 10-K,28/08/2026\n",
    )

    curado = leer_curado(ruta)

    assert curado.filas == []
    assert sorted(curado.descartados[CODIGO_FILA_SIN_TRAZA]) == ["AAPL", "KO", "MSFT"]


def test_una_fecha_ambigua_no_se_adivina(tmp_path: Path) -> None:
    """`08/09/2026` es 8 de septiembre o 9 de agosto según quién lo escriba. Sólo ISO."""
    ruta = _csv(tmp_path, "AAPL,US,Apple Inc. 10-K,08/09/2026\n")

    assert leer_curado(ruta).filas == []


def test_un_papel_repetido_conserva_el_primero_y_no_fusiona(tmp_path: Path) -> None:
    """Fusionar sería decidir cuál de los dos países vale, y eso es exactamente lo que el sistema no
    hace por cuenta propia."""
    ruta = _csv(
        tmp_path,
        "AAPL,US,Apple Inc. 10-K,2026-08-28\nAAPL,IE,Apple Operations Intl.,2026-08-28\n",
    )

    curado = leer_curado(ruta)

    (fila,) = curado.filas
    assert fila.pais == "US"
    assert curado.descartados[CODIGO_PAPEL_REPETIDO] == {"AAPL": "IE"}


def test_el_curado_se_normaliza_como_lo_escribe_una_planilla(tmp_path: Path) -> None:
    """Minúsculas y espacios: normalizar la caja de un código ISO no es interpretarlo."""
    ruta = _csv(tmp_path, " aapl , us ,Apple Inc. 10-K,2026-08-28\n")

    (fila,) = leer_curado(ruta).filas

    assert (fila.ticker_papel, fila.pais) == ("AAPL", "US")


def test_un_archivo_que_no_esta_alerta_y_no_devuelve_filas(tmp_path: Path) -> None:
    """**Es el caso normal hasta la primera tanda validada.** Sin artefacto no hay nada que sembrar,
    y una corrida que cantara éxito sobre cero filas sería indistinguible de un curado completo."""
    curado = leer_curado(tmp_path / "no-existe.csv")

    assert curado.filas == []
    (alerta,) = curado.alertas
    assert alerta.codigo == CODIGO_CURADO_AUSENTE
    assert alerta.severidad == "error"


def test_un_csv_sin_las_columnas_esperadas_no_se_interpreta(tmp_path: Path) -> None:
    ruta = tmp_path / "paises_cedears.csv"
    ruta.write_text("ticker,pais\nAAPL,US\n", encoding="utf-8")

    curado = leer_curado(ruta)

    assert curado.filas == []
    assert curado.alertas[0].codigo == "formato_inesperado"


def test_la_ruta_relativa_se_resuelve_contra_la_raiz_del_repo_y_no_contra_el_cwd() -> None:
    """El cwd cambia según se arranque con uvicorn, pytest o Docker; el repo, no."""
    relativa = ruta_paises(get_settings().model_copy(update={"paises_cedears_csv": "data/x.csv"}))
    assert relativa.is_absolute()
    assert relativa.parts[-2:] == ("data", "x.csv")

    absoluta = Path("/tmp/otro/paises.csv")
    assert ruta_paises(_ajustes(absoluta)) == absoluta


# --- La siembra ----------------------------------------------------------------------------------


async def test_la_siembra_carga_el_curado_y_reporta_los_tres_conteos(tmp_path: Path) -> None:
    ruta = _csv(
        tmp_path,
        "AAPL,US,Apple Inc. 10-K,2026-08-28\n"
        "VALE,BR,Vale S.A. 20-F,2026-08-28\n"
        "GLD,,ETF sobre oro físico,2026-08-28\n"
        "XXXX,USA,Fuente cualquiera,2026-08-28\n",
    )
    conn = FakeConexion()

    resumen = await sembrar_paises(conn, _ajustes(ruta))

    assert (resumen.cargados, resumen.descartados, resumen.sin_pais) == (3, 1, 1)
    assert conn.papeles_escritos == ["AAPL", "VALE", "GLD"]
    assert resumen.detalle_descartes[CODIGO_PAIS_FUERA_DE_VOCABULARIO] == {"XXXX": "USA"}
    assert resumen.como_dict()["cargados"] == 3


async def test_sembrar_dos_veces_deja_lo_mismo(tmp_path: Path) -> None:
    """Idempotente porque no hay reloj ni fuente externa en el medio: es lo que la hace segura de
    reejecutar."""
    ruta = _csv(tmp_path, "AAPL,US,Apple Inc. 10-K,2026-08-28\n")
    ajustes = _ajustes(ruta)

    primera = await sembrar_paises(FakeConexion(), ajustes)
    segunda = await sembrar_paises(FakeConexion(), ajustes)

    assert primera.como_dict() == segunda.como_dict()


async def test_sin_artefacto_no_se_escribe_nada(tmp_path: Path) -> None:
    """El guardia que separa "el curado no sabe nada" de "el curado no se pudo leer". Sin él, una
    corrida sobre un archivo ausente no tocaría la tabla pero cantaría éxito."""
    conn = FakeConexion()

    resumen = await sembrar_paises(conn, _ajustes(tmp_path / "no-existe.csv"))

    assert conn.escrituras == []
    assert resumen.cargados == 0
    assert [a.codigo for a in resumen.alertas] == [CODIGO_CURADO_AUSENTE]


async def test_el_upsert_no_protege_el_pais_con_coalesce(tmp_path: Path) -> None:
    """Vaciar un país **es una decisión** del curado, no una ausencia: un COALESCE resucitaría desde
    la carga anterior un valor que el curado acaba de retirar."""
    ruta = _csv(tmp_path, "GLD,,ETF sobre oro físico,2026-08-28\n")
    conn = FakeConexion()

    await sembrar_paises(conn, _ajustes(ruta))

    (consulta,) = conn.consultas
    assert "COALESCE" not in consulta.upper()
    assert "pais = EXCLUDED.pais" in consulta


# --- La lectura ----------------------------------------------------------------------------------


async def test_leer_paises_indexa_por_papel() -> None:
    conn = FakeConexion(
        [
            {
                "ticker_papel": "AAPL",
                "pais": "US",
                "fuente": "Apple Inc. 10-K",
                "verificado": date(2026, 8, 28),
            }
        ]
    )

    paises = await leer_paises(conn)

    assert paises["AAPL"].pais == "US"
    assert paises["AAPL"].region == "América del Norte"
