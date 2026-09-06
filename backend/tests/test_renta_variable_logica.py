"""Los GWT de F-052 sobre la lógica pura de renta variable, sin Postgres.

`variacion_diaria` y `volumen_en_dolares` viven en `app/renta_variable/especies.py` y no importan
nada del universo ni de la base — se prueban con valores a mano, igual que `cambio.py` prueba su
propia matemática.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.renta_variable.especies import armar_renta_variable, variacion_diaria, volumen_en_dolares
from app.renta_variable.geografia_etf import FilaGeografiaEtf
from app.renta_variable.paises import FilaPais
from app.universo.cambio import TipoDeCambio

# --- variacion_diaria: GWT-3, nunca se estima ----------------------------------------------------


def test_variacion_con_los_dos_datos_es_el_cociente() -> None:
    assert variacion_diaria(103.1, 100.0) == pytest.approx(0.031)


def test_variacion_sin_cierre_anterior_es_none() -> None:
    assert variacion_diaria(103.1, None) is None


def test_variacion_sin_precio_es_none() -> None:
    assert variacion_diaria(None, 100.0) is None


def test_variacion_con_cierre_anterior_no_positivo_es_none() -> None:
    """Un cierre en cero no es un cierre válido, y dividir por él no produciría una variación real
    (sería una variación inventada, no calculada)."""
    assert variacion_diaria(103.1, 0.0) is None


# --- volumen_en_dolares: GWT-2, nunca cae a la regla del sufijo ----------------------------------


def test_volumen_ars_se_divide_por_el_tipo_de_cambio() -> None:
    cambio = TipoDeCambio(valor=1000.0, pares=25)
    assert volumen_en_dolares(cambio, 1_500_000.0, "ARS") == pytest.approx(1_500.0)


def test_volumen_usd_se_conserva_tal_cual() -> None:
    cambio = TipoDeCambio(valor=1000.0, pares=25)
    assert volumen_en_dolares(cambio, 2_000.0, "USD") == 2_000.0


def test_volumen_sin_moneda_declarada_es_none_y_no_cae_al_sufijo_del_ticker() -> None:
    """Es la diferencia con la renta fija: acá no hay regla de sufijo D/C que completar por
    analogía."""
    cambio = TipoDeCambio(valor=1000.0, pares=25)
    assert volumen_en_dolares(cambio, 1_500_000.0, None) is None


def test_volumen_ars_sin_tipo_de_cambio_del_dia_es_none_y_no_el_crudo() -> None:
    cambio = TipoDeCambio()  # sin valor: menos de MIN_PARES_FX pares, FX no disponible
    assert volumen_en_dolares(cambio, 1_500_000.0, "ARS") is None


# --- armar_renta_variable: GWT-1, sin rendimiento, sin naturaleza, sin segmento -------------------


def test_como_dict_no_tiene_rendimiento_ni_naturaleza_ni_segmento() -> None:
    filas = [
        {
            "ticker": "GGAL",
            "clase_activo": "accion",
            "lastPrice": 5000.0,
            "effectiveVolume": 1_500_000_000.0,
            "cierre_anterior": 4850.0,
            "moneda_cotizacion": "ARS",
            "px_bid": 4995.0,
            "px_ask": 5005.0,
            "operaciones": 120,
        }
    ]
    (especie,) = armar_renta_variable(filas, TipoDeCambio())
    cuerpo = especie.como_dict()
    assert "rendimiento" not in cuerpo
    assert "naturaleza" not in cuerpo
    assert "segmento" not in cuerpo
    assert cuerpo["ticker"] == "GGAL"
    assert cuerpo["variacion"] == pytest.approx((5000.0 - 4850.0) / 4850.0)


# --- Perfil de empresa: Etapa 4 del rediseño del armador ------------------------------------------


def test_sin_fila_de_perfil_todos_los_campos_nuevos_quedan_none() -> None:
    """Una especie recién agregada al universo, antes de que el job de enriquecimiento la toque."""
    filas = [
        {
            "ticker": "GGAL",
            "clase_activo": "accion",
            "lastPrice": 5000.0,
            "effectiveVolume": 1_500_000_000.0,
            "cierre_anterior": 4850.0,
            "moneda_cotizacion": "ARS",
            "px_bid": 4995.0,
            "px_ask": 5005.0,
            "operaciones": 120,
        }
    ]
    (especie,) = armar_renta_variable(filas, TipoDeCambio())
    assert especie.nombre_largo is None
    assert especie.perfil_fuente is None
    assert especie.perfil_capturado_en is None


def test_con_fila_de_perfil_los_campos_llegan_tal_como_la_fuente_los_declaro() -> None:
    capturado = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    filas = [
        {
            "ticker": "GGAL",
            "clase_activo": "accion",
            "lastPrice": 5000.0,
            "effectiveVolume": 1_500_000_000.0,
            "cierre_anterior": 4850.0,
            "moneda_cotizacion": "ARS",
            "px_bid": 4995.0,
            "px_ask": 5005.0,
            "operaciones": 120,
            "nombre_largo": "Grupo Financiero Galicia S.A.",
            "perfil_fuente": "SEC EDGAR",
            "perfil_capturado_en": capturado,
        }
    ]
    (especie,) = armar_renta_variable(filas, TipoDeCambio())
    assert especie.nombre_largo == "Grupo Financiero Galicia S.A."
    assert especie.perfil_fuente == "SEC EDGAR"
    assert especie.perfil_capturado_en == capturado.isoformat()


# --- El OHLC de BYMA (13/08/2026) ------------------------------------------------------------------


def test_una_fila_sin_ohlc_los_declara_none() -> None:
    """Una fila anterior a la migración de OHLC (o una que sólo trajo lo mínimo) no rompe: los
    cuatro campos quedan `None`, igual que un perfil que todavía no cargó."""
    filas = [
        {
            "ticker": "GGAL",
            "clase_activo": "accion",
            "lastPrice": 5000.0,
            "effectiveVolume": 1_500_000_000.0,
        }
    ]
    (especie,) = armar_renta_variable(filas, TipoDeCambio())
    assert especie.precio_apertura is None
    assert especie.precio_maximo is None
    assert especie.precio_minimo is None
    assert especie.vwap is None


def test_el_ohlc_llega_tal_como_lo_declaro_byma() -> None:
    filas = [
        {
            "ticker": "GGAL",
            "clase_activo": "accion",
            "lastPrice": 5000.0,
            "effectiveVolume": 1_500_000_000.0,
            "precio_apertura": 4900.0,
            "precio_maximo": 5100.0,
            "precio_minimo": 4880.0,
            "vwap": 4990.5,
        }
    ]
    (especie,) = armar_renta_variable(filas, TipoDeCambio())
    assert especie.precio_apertura == 4900.0
    assert especie.precio_maximo == 5100.0
    assert especie.precio_minimo == 4880.0
    assert especie.vwap == 4990.5


# --- El país curado, junto por papel — F-078 -----------------------------------------------------


def _fila_cedear(ticker: str, precio: float, moneda: str) -> dict:
    return {
        "ticker": ticker,
        "clase_activo": "cedear",
        "lastPrice": precio,
        "effectiveVolume": 1_000_000.0,
        "cierre_anterior": precio,
        "moneda_cotizacion": moneda,
        "px_bid": None,
        "px_ask": None,
        "operaciones": 1,
    }


def _curado(papel: str, pais: str | None) -> dict[str, FilaPais]:
    return {
        papel: FilaPais(
            ticker_papel=papel,
            pais=pais,
            fuente=f"Curado de prueba para {papel}",
            verificado=date(2026, 8, 28),
        )
    }


def test_las_hermanas_comparten_el_pais_del_papel() -> None:
    """No es completar por analogía: `AAPL`, `AAPLC` y `AAPLD` son el mismo CEDEAR de Apple en
    pesos, cable y MEP, y el país de la empresa es literalmente el mismo dato. El curado tiene una
    fila por papel justamente por eso.

    El cociente entre el precio en pesos y el de la variante da el tipo de cambio, que es lo que le
    permite al agrupamiento confirmar el grupo (ver `agrupamiento.py`).
    """
    filas = [
        _fila_cedear("AAPL", 43_000.0, "ARS"),
        _fila_cedear("AAPLD", 43.0, "USD"),
        _fila_cedear("AAPLC", 41.5, "USD"),
    ]

    especies = armar_renta_variable(
        filas, TipoDeCambio(valor=1000.0, pares=25), _curado("AAPL", "US")
    )

    assert {e.ticker: e.pais for e in especies} == {"AAPL": "US", "AAPLD": "US", "AAPLC": "US"}
    assert {e.region for e in especies} == {"América del Norte"}


def test_el_pais_nunca_viaja_sin_su_fuente_ni_su_fecha() -> None:
    """Regla 11: un dato externo no se muestra sin decir de dónde salió."""
    filas = [_fila_cedear("MELI", 10_000.0, "ARS")]

    (especie,) = armar_renta_variable(filas, TipoDeCambio(), _curado("MELI", "AR"))

    cuerpo = especie.como_dict()
    assert cuerpo["pais"] == "AR"
    assert cuerpo["region"] == "América Latina y el Caribe"
    assert cuerpo["pais_fuente"] == "Curado de prueba para MELI"
    assert cuerpo["pais_verificado"] == "2026-08-28"


def test_un_papel_sin_curado_queda_con_el_pais_declarado_faltante() -> None:
    """Es el estado normal mientras el curado avanza por tandas, y el contrato del sistema: no se
    completa el país por parecido con otra empresa ni por el mercado donde cotiza."""
    filas = [_fila_cedear("XPEV", 5_000.0, "ARS")]

    (especie,) = armar_renta_variable(filas, TipoDeCambio(), _curado("AAPL", "US"))

    assert (especie.pais, especie.region, especie.pais_fuente) == (None, None, None)


def test_un_pais_curado_vacio_no_inventa_region() -> None:
    """"Se investigó y no se resolvió" carga la fila con su fuente, y la región queda vacía: no se
    deriva de nada."""
    filas = [_fila_cedear("GLD", 5_000.0, "ARS")]

    (especie,) = armar_renta_variable(filas, TipoDeCambio(), _curado("GLD", None))

    assert (especie.pais, especie.region) == (None, None)
    assert especie.pais_fuente == "Curado de prueba para GLD"


def test_sin_curado_el_listado_sigue_funcionando() -> None:
    """El curado es trabajo humano por tandas y nada del código lo espera para andar."""
    filas = [_fila_cedear("AAPL", 43_000.0, "ARS")]

    (especie,) = armar_renta_variable(filas, TipoDeCambio())

    assert especie.pais is None
    assert especie.ticker == "AAPL"


def test_lo_no_identificado_no_hereda_el_pais_de_nadie() -> None:
    """Las que terminan en `B` caen en `NO_IDENTIFICADO`: su `emision` es el centinela `n/n`, no un
    ticker. Buscarles el país sería inventarle identidad a una especie que la fuente no explica."""
    filas = [_fila_cedear("AAPL", 43_000.0, "ARS"), _fila_cedear("AAPLB", 43_000.0, "ARS")]

    armadas = armar_renta_variable(filas, TipoDeCambio(), _curado("AAPL", "US"))
    especies = {e.ticker: e for e in armadas}

    assert especies["AAPL"].pais == "US"
    assert especies["AAPLB"].pais is None


def test_el_region_etf_viaja_tal_cual_y_no_se_mezcla_con_la_region_curada() -> None:
    """Los dos vocabularios geográficos conviven sin unificarse: `Latin America` es lo que dice el
    nombre del fondo y "América Latina y el Caribe" es lo que dice el estándar M49 sobre un país.
    Traducir uno al otro sería exactamente lo que la regla 11 prohíbe."""
    fila = _fila_cedear("ILF", 5_000.0, "ARS") | {
        "region_etf": "Latin America",
        "estrategia_etf": "geografico",
    }

    (especie,) = armar_renta_variable([fila], TipoDeCambio())

    assert especie.region_etf == "Latin America"
    assert especie.region is None, "sin país curado no hay región M49, y no se copia de la del ETF"


# --- Sector y rubro específico, derivados del SIC — F-079 ----------------------------------------


def _apuntar_sic(
    monkeypatch: pytest.MonkeyPatch, *, sectores: Path | None, rubros: Path | None
) -> None:
    """Mismo patrón que `test_sic_es.py`: apunta las settings a un CSV de `tmp_path` (o a uno que
    no existe) y limpia la caché de `get_settings`/`_leer_etiquetas`."""
    if sectores is not None:
        monkeypatch.setenv("SIC_SECTORES_CSV", str(sectores))
    if rubros is not None:
        monkeypatch.setenv("SIC_RUBROS_CSV", str(rubros))
    get_settings.cache_clear()


def _fila_con_sic(sic_codigo: str | None) -> dict:
    fila = _fila_cedear("AAPL", 5000.0, "USD")
    if sic_codigo is not None:
        fila["sic_codigo"] = sic_codigo
    return fila


def test_sector_codigo_se_deriva_de_sic_codigo_sin_ningun_curado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`sector_codigo` es aritmética sobre `sic_codigo` (`major_group_de`): está aunque no exista
    ningún CSV curado todavía."""
    _apuntar_sic(
        monkeypatch, sectores=tmp_path / "no_existe.csv", rubros=tmp_path / "no_existe.csv"
    )
    (especie,) = armar_renta_variable([_fila_con_sic("7372")], TipoDeCambio())
    assert especie.sector_codigo == "73"
    assert especie.sector is None
    assert especie.rubro_especifico is None


def test_sector_titulo_esta_siempre_que_haya_sector_codigo_sin_ningun_curado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`sector_titulo` (30/08/2026) es el nombre oficial del SIC Manual de OSHA — igual que
    `sector_codigo`, aritmética pura, presente aunque no exista ningún CSV curado todavía."""
    _apuntar_sic(
        monkeypatch, sectores=tmp_path / "no_existe.csv", rubros=tmp_path / "no_existe.csv"
    )
    (especie,) = armar_renta_variable([_fila_con_sic("7372")], TipoDeCambio())
    assert especie.sector_titulo == "Business Services"


def test_sin_sic_codigo_sector_codigo_es_none() -> None:
    (especie,) = armar_renta_variable([_fila_con_sic(None)], TipoDeCambio())
    assert especie.sector_codigo is None
    assert especie.sector_titulo is None


def test_con_el_curado_cargado_sector_y_rubro_traen_la_etiqueta_es(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta_sectores = tmp_path / "sic_sectores.csv"
    ruta_sectores.write_text(
        "major_group,nombre_en,etiqueta_es\n73,Computer And Data Processing Services,Software y "
        "datos\n",
        encoding="utf-8",
    )
    ruta_rubros = tmp_path / "sic_rubros.csv"
    ruta_rubros.write_text(
        "sic_codigo,titulo_en,etiqueta_es\n7372,Prepackaged Software,Software empaquetado\n",
        encoding="utf-8",
    )
    _apuntar_sic(monkeypatch, sectores=ruta_sectores, rubros=ruta_rubros)

    (especie,) = armar_renta_variable([_fila_con_sic("7372")], TipoDeCambio())

    assert especie.sector_codigo == "73"
    assert especie.sector == "Software y datos"
    assert especie.sector_titulo == "Business Services", "el título OSHA convive con la etiqueta ES"
    assert especie.rubro_especifico == "Software empaquetado"
    cuerpo = especie.como_dict()
    assert cuerpo["sector_codigo"] == "73"
    assert cuerpo["sector"] == "Software y datos"
    assert cuerpo["sector_titulo"] == "Business Services"
    assert cuerpo["rubro_especifico"] == "Software empaquetado"


def test_sin_fila_en_el_curado_sector_y_rubro_quedan_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El curado existe pero no tiene fila para este código: mismo estado que sin CSV, el
    fallback lo decide quien consume la especie."""
    ruta_sectores = tmp_path / "sic_sectores.csv"
    ruta_sectores.write_text(
        "major_group,nombre_en,etiqueta_es\n28,Chemicals,Química\n", encoding="utf-8"
    )
    ruta_rubros = tmp_path / "sic_rubros.csv"
    ruta_rubros.write_text(
        "sic_codigo,titulo_en,etiqueta_es\n2834,Pharmaceutical Preparations,Preparados\n",
        encoding="utf-8",
    )
    _apuntar_sic(monkeypatch, sectores=ruta_sectores, rubros=ruta_rubros)

    (especie,) = armar_renta_variable([_fila_con_sic("7372")], TipoDeCambio())

    assert especie.sector_codigo == "73"
    assert especie.sector is None
    assert especie.sector_titulo == "Business Services", (
        "sin fila en el curado, el título OSHA sigue"
    )
    assert especie.rubro_especifico is None


# --- Geografía curada de ETFs — F-079, D3 ---------------------------------------------------------


def _geografia(papel: str, *, pais: str | None) -> dict[str, FilaGeografiaEtf]:
    return {
        papel: FilaGeografiaEtf(
            ticker_papel=papel,
            indice="MSCI EAFE",
            alcance="Mercados desarrollados fuera de EE.UU. y Canadá",
            pais=pais,
            fuente=f"Curado de prueba para {papel}",
            verificado=date(2026, 8, 29),
        )
    }


def test_la_geografia_del_etf_viaja_completa_cuando_esta_en_el_curado() -> None:
    filas = [_fila_cedear("EFA", 5_000.0, "USD")]

    (especie,) = armar_renta_variable(
        filas, TipoDeCambio(), geografia_etfs=_geografia("EFA", pais=None)
    )

    assert especie.etf_indice == "MSCI EAFE"
    assert especie.etf_alcance == "Mercados desarrollados fuera de EE.UU. y Canadá"
    assert especie.etf_pais is None, "fondo multi-país: no se cura la composición completa"
    assert especie.etf_region is None
    assert especie.etf_geo_fuente == "Curado de prueba para EFA"
    assert especie.etf_geo_verificado == date(2026, 8, 29)


def test_la_region_del_etf_se_deriva_del_pais_mono_pais() -> None:
    filas = [_fila_cedear("EWJ", 5_000.0, "USD")]

    (especie,) = armar_renta_variable(
        filas, TipoDeCambio(), geografia_etfs=_geografia("EWJ", pais="JP")
    )

    assert especie.etf_pais == "JP"
    assert especie.etf_region == "Asia oriental"


def test_un_papel_sin_fila_en_la_geografia_de_etfs_queda_con_todo_none() -> None:
    """Es el caso normal para todo lo que no es un ETF geográfico curado -- no hay fallback textual
    porque no hay ninguna fuente cruda equivalente que mostrar."""
    filas = [_fila_cedear("AAPL", 5_000.0, "USD")]

    (especie,) = armar_renta_variable(
        filas, TipoDeCambio(), geografia_etfs=_geografia("EFA", pais=None)
    )

    assert (
        especie.etf_indice,
        especie.etf_alcance,
        especie.etf_pais,
        especie.etf_region,
        especie.etf_geo_fuente,
        especie.etf_geo_verificado,
    ) == (None, None, None, None, None, None)


def test_sin_geografia_etfs_el_listado_sigue_funcionando() -> None:
    """`geografia_etfs=None` es el default: nada del código lo espera para andar, igual que
    `paises`."""
    filas = [_fila_cedear("AAPL", 5_000.0, "USD")]
    (especie,) = armar_renta_variable(filas, TipoDeCambio())
    assert especie.etf_indice is None


def test_las_hermanas_comparten_la_geografia_del_etf_del_papel() -> None:
    """Mismo criterio que el país curado (F-078): la geografía es del papel, no de la especie de
    liquidación, así que las hermanas la comparten."""
    filas = [
        _fila_cedear("EWZ", 5_000.0, "ARS"),
        _fila_cedear("EWZD", 5.0, "USD"),
    ]

    armadas = armar_renta_variable(
        filas, TipoDeCambio(valor=1000.0, pares=25), geografia_etfs=_geografia("EWZ", pais="BR")
    )
    especies = {e.ticker: e for e in armadas}

    assert especies["EWZ"].etf_pais == "BR"
    assert especies["EWZD"].etf_pais == "BR"
