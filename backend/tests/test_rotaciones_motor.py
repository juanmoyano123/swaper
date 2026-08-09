"""El núcleo puro del motor de rotaciones — F-032, GWT de la ficha (`plan.md:1546-1583`).

Todo con fixtures sintéticas de `EspecieUniverso`: no toca la base ni el consolidado versionado.
La paridad contra `tools/detectar_swaps.py` sobre datos reales, con el caso TLCWO→TLCMO como
criterio de aceptación (GWT-2), vive en `test_rotaciones_paridad_motor.py`.
"""

from datetime import date

from app.calendario.cupones import Flujos
from app.concentracion.riesgo import derivar_riesgo
from app.rotaciones.constantes import MAX_MAS_DURACION, MIN_DTIR, TOP_N, ParametrosRotacion
from app.rotaciones.emisores import clave_emisor_swap, nombre_emisor
from app.rotaciones.motor import detectar, evaluar_par
from app.universo.segmentacion import EspecieUniverso

HOY = date(2026, 8, 7)
FLUJOS_VACIOS = Flujos()

# El perfil moderado: `percentil_liquidez=25`, `usd_hard=0.15`, exactamente lo que reproduce
# `ParametrosRotacion.de_perfil("moderado")` (ver `test_rotaciones_paridad_motor.py`).
PARAMS_DEFAULT = ParametrosRotacion(percentil_liquidez=25.0, tope_distress={"usd_hard": 0.15})


def _especie(
    ticker: str,
    *,
    raiz: str | None = None,
    clase_activo: str = "on_corporativo",
    segmento: str = "usd_hard",
    tipo_tasa: str | None = "hard-dollar",
    rendimiento: float | None = 0.10,
    duracion: float | None = 3.0,
    ley: str | None = None,
    moneda_cupon: str | None = None,
    emisor: str | None = None,
    volumen_usd: float | None = 1_000_000.0,
    calificacion: str | None = None,
) -> EspecieUniverso:
    return EspecieUniverso(
        ticker=ticker,
        raiz=raiz or ticker,
        clase_activo=clase_activo,
        segmento=segmento,
        rendimiento=rendimiento,
        duracion=duracion,
        ley=ley,
        moneda_cupon=moneda_cupon,
        emisor=emisor,
        volumen_usd=volumen_usd,
        tipo_tasa=tipo_tasa,
        calificacion=calificacion,
    )


def _contexto(especies: list[EspecieUniverso]) -> tuple[dict[str, str], dict[str, str]]:
    riesgos = derivar_riesgo(especies)
    claves = {e.ticker: clave_emisor_swap(e, riesgos) for e in especies}
    nombres = {e.ticker: nombre_emisor(e, claves[e.ticker]) for e in especies}
    return claves, nombres


def _detectar(
    origenes: list[EspecieUniverso],
    universo_operable: list[EspecieUniverso],
    *,
    params: ParametrosRotacion = PARAMS_DEFAULT,
    medianas_ley: dict[str, int] | None = None,
    flujos: Flujos = FLUJOS_VACIOS,
    frecuencias: dict[str, tuple[str, int]] | None = None,
):
    claves, nombres = _contexto([*origenes, *universo_operable])
    return detectar(
        origenes,
        universo_operable,
        claves_emisor=claves,
        nombres_emisor=nombres,
        frecuencias=frecuencias or {},
        flujos=flujos,
        hoy=HOY,
        medianas_ley=medianas_ley or {},
        params=params,
    )


def _evaluar(origen: EspecieUniverso, destino: EspecieUniverso, **kwargs: object):
    claves, nombres = _contexto([origen, destino])
    return evaluar_par(
        origen,
        destino,
        claves_emisor=claves,
        nombres_emisor=nombres,
        frecuencias=kwargs.get("frecuencias") or {},
        flujos=kwargs.get("flujos") or FLUJOS_VACIOS,
        hoy=HOY,
        medianas_ley=kwargs.get("medianas_ley") or {},
        params=kwargs.get("params") or PARAMS_DEFAULT,
    )


# --- GWT-1: sólo dentro del mismo segmento ---------------------------------------------------


def test_gwt1_origen_en_cer_solo_propone_destinos_cer() -> None:
    origen = _especie("CERX01", segmento="cer", tipo_tasa="cer", rendimiento=0.02, duracion=2.0)
    destino_cer = _especie(
        "CERY01", segmento="cer", tipo_tasa="cer", rendimiento=0.05, duracion=2.2
    )
    destino_usd = _especie(
        "USDZ01", segmento="usd_hard", tipo_tasa="hard-dollar", rendimiento=0.20, duracion=2.0
    )
    destino_dl = _especie(
        "DLXX01",
        segmento="dollar_linked",
        tipo_tasa="dollar-linked",
        rendimiento=0.15,
        duracion=2.0,
    )

    candidatas, _alertas = _detectar([origen], [destino_cer, destino_usd, destino_dl])

    assert candidatas
    assert {c.destino.segmento for c in candidatas} == {"cer"}
    assert {c.destino.ticker for c in candidatas} == {"CERY01"}


# --- GWT-3: hermanas de la misma emisión (mismo raíz, distinta moneda de pago) ---------------


def test_gwt3_hermanas_de_la_misma_emision_pasan_a_cable() -> None:
    origen = _especie(
        "MR46O",
        raiz="MR46",
        segmento="usd_hard",
        tipo_tasa="hard-dollar",
        rendimiento=0.10,
        duracion=3.0,
        moneda_cupon="ARS",
        ley="Ley Argentina",
    )
    destino = _especie(
        "MR46D",
        raiz="MR46",
        segmento="usd_hard",
        tipo_tasa="hard-dollar",
        rendimiento=0.099,
        duracion=3.0,
        moneda_cupon="CCL",
        ley="Ley Argentina",
    )

    candidatas, _alertas = _detectar([origen], [destino])

    assert len(candidatas) == 1
    candidata = candidatas[0]
    assert candidata.destino.ticker == "MR46D"
    assert candidata.tipo == "mejora_perfil"
    assert candidata.pasa_a_cable is True
    assert candidata.mismo_emisor is True


# --- GWT-4: filtro de liquidez y de rendimiento mínimo ----------------------------------------


def test_gwt4_liquidez_y_rendimiento_minimo_excluyen_destinos() -> None:
    origen = _especie("CERX01", segmento="cer", tipo_tasa="cer", rendimiento=0.01, duracion=1.0)
    buenos = [
        _especie(
            f"CERD{i:02d}",
            segmento="cer",
            tipo_tasa="cer",
            rendimiento=0.02 + i * 0.001,
            duracion=1.0,
            volumen_usd=1_000_000.0,
        )
        for i in range(9)
    ]
    # Con 10 candidatos en el segmento (9 buenos + éste) el percentil sí aplica: queda muy por
    # debajo del piso de liquidez del percentil 25.
    iliquido = _especie(
        "CERZ99", segmento="cer", tipo_tasa="cer", rendimiento=0.05, duracion=1.0, volumen_usd=1.0
    )
    bajo_rend = _especie(
        "CERZ00",
        segmento="cer",
        tipo_tasa="cer",
        rendimiento=-0.5,
        duracion=1.0,
        volumen_usd=1_000_000.0,
    )

    candidatas, _alertas = _detectar([origen], [*buenos, iliquido, bajo_rend])

    destinos = {c.destino.ticker for c in candidatas}
    assert "CERZ99" not in destinos, "el destino ilíquido tiene que quedar excluido del ranking"
    assert "CERZ00" not in destinos, "el destino bajo el rendimiento mínimo queda excluido"
    assert destinos, "algún destino bueno tiene que sobrevivir a los dos filtros"
    assert destinos <= {b.ticker for b in buenos}


# --- El caso validado por la mesa: TLCWO → TLCMO ----------------------------------------------


def test_tlcwo_a_tlcmo_reproduce_el_swap_que_la_mesa_ejecuto() -> None:
    """Mismo emisor (prefijo `TLC`), mejora de rendimiento marginal (no alcanza `MIN_DTIR`),
    cambio a CCL y ~3x volumen: exactamente el patrón de `mejora_perfil`, ley N.Y. en las dos
    puntas. Datos calcados de `docs/historial/2026-07-diseno-wat/05-spec-motor-swaps.md`."""
    origen = _especie(
        "TLCWO",
        segmento="usd_hard",
        tipo_tasa="hard-dollar",
        rendimiento=0.095,
        duracion=2.5,
        moneda_cupon="MEP",
        ley="Ley N.Y.",
        volumen_usd=500_000.0,
    )
    destino = _especie(
        "TLCMO",
        segmento="usd_hard",
        tipo_tasa="hard-dollar",
        rendimiento=0.097,
        duracion=2.5,
        moneda_cupon="CCL",
        ley="Ley N.Y.",
        volumen_usd=1_600_000.0,
    )

    candidatas, _alertas = _detectar([origen], [destino])

    assert len(candidatas) == 1
    candidata = candidatas[0]
    assert candidata.destino.ticker == "TLCMO"
    assert candidata.tipo == "mejora_perfil"
    assert candidata.mismo_emisor is True
    assert candidata.pasa_a_cable is True
    assert candidata.mejora_volumen is True


# --- `riesgo_nota`: regla 8 y regla 11 del dominio --------------------------------------------


def test_riesgo_nota_mismo_emisor() -> None:
    origen = _especie("AAA1O", rendimiento=0.05, duracion=2.0)
    destino = _especie("AAA2O", rendimiento=0.08, duracion=2.0)

    candidata = _evaluar(origen, destino)

    assert candidata is not None
    assert candidata.riesgo_nota == "mismo emisor — mismo riesgo crediticio"


def test_riesgo_nota_cambia_categoria_de_credito() -> None:
    origen = _especie("GD30", clase_activo="bono_soberano", rendimiento=0.05, duracion=2.0)
    destino = _especie("BBB1O", rendimiento=0.09, duracion=2.0)

    candidata = _evaluar(origen, destino)

    assert candidata is not None
    assert candidata.mismo_emisor is False
    assert candidata.riesgo_nota == "cambia riesgo soberano → corporativo — verificar"


def test_riesgo_nota_distinto_emisor_misma_categoria() -> None:
    origen = _especie("AAA1O", rendimiento=0.05, duracion=2.0)
    destino = _especie("BBB1O", rendimiento=0.09, duracion=2.0)

    candidata = _evaluar(origen, destino)

    assert candidata is not None
    assert candidata.mismo_emisor is False
    assert candidata.riesgo_nota == "distinto emisor (corporativo) — verificar calidad crediticia"


def test_riesgo_nota_muestra_el_salto_de_calificacion_sin_ordenarlo() -> None:
    origen = _especie("AAA1O", rendimiento=0.05, duracion=2.0, calificacion="AA(arg)")
    destino = _especie("BBB1O", rendimiento=0.09, duracion=2.0, calificacion="BBB(arg)")

    candidata = _evaluar(origen, destino)

    assert candidata is not None
    assert candidata.riesgo_nota.endswith(" [AA(arg) → BBB(arg)]")


def test_riesgo_nota_avisa_cuando_empeora_la_ley() -> None:
    origen = _especie("AAA1O", rendimiento=0.05, duracion=2.0, ley="Ley N.Y.")
    destino = _especie("AAA2O", rendimiento=0.08, duracion=2.0, ley="Ley Argentina")

    candidata = _evaluar(origen, destino)

    assert candidata is not None
    assert candidata.empeora_ley is True
    assert "ATENCION: pasa de Ley N.Y. a Ley Argentina" in candidata.riesgo_nota


# --- Tesoro vs. Bopreal: `clave_emisor_swap` los separa -----------------------------------------


def test_tesoro_a_bopreal_no_es_mismo_emisor() -> None:
    origen = _especie(
        "GD30",
        clase_activo="bono_soberano",
        tipo_tasa="hard-dollar",
        rendimiento=0.05,
        duracion=2.0,
    )
    destino = _especie(
        "BPY26", clase_activo="bono_soberano", tipo_tasa="bopreal", rendimiento=0.08, duracion=2.0
    )
    claves, _nombres = _contexto([origen, destino])

    assert claves["GD30"] == "SOBERANO_AR"
    assert claves["BPY26"] == "BCRA"

    candidata = _evaluar(origen, destino)
    assert candidata is not None
    assert candidata.mismo_emisor is False


# --- Segmento chico: sin filtro de percentil, con alerta ----------------------------------------


def test_segmento_chico_no_aplica_percentil_de_liquidez() -> None:
    origen = _especie("CERX01", segmento="cer", tipo_tasa="cer", rendimiento=0.01, duracion=1.0)
    destinos = [
        _especie(
            f"CERD0{i}",
            segmento="cer",
            tipo_tasa="cer",
            rendimiento=0.02 + i * 0.001,
            duracion=1.0,
            volumen_usd=1.0 if i == 0 else 1_000_000.0,
        )
        for i in range(3)  # menos que MIN_OPERABLES_PERCENTIL: el percentil no aplica
    ]

    candidatas, alertas = _detectar([origen], destinos)

    assert any(c.destino.ticker == "CERD00" for c in candidatas), (
        "con el segmento chico, el destino ilíquido no se filtra"
    )
    assert any(a.codigo == "percentil_liquidez_no_aplica" for a in alertas)


# --- Corte de duración -------------------------------------------------------------------------


def test_corte_de_duracion_excluye_al_destino_que_estira_demasiado() -> None:
    origen = _especie("AAA1O", rendimiento=0.05, duracion=2.0)
    dentro_del_corte = _especie("AAA2O", rendimiento=0.08, duracion=2.0 + MAX_MAS_DURACION)
    fuera_del_corte = _especie("AAA3O", rendimiento=0.08, duracion=2.0 + MAX_MAS_DURACION + 0.5)

    candidatas, _alertas = _detectar([origen], [dentro_del_corte, fuera_del_corte])

    destinos = {c.destino.ticker for c in candidatas}
    assert "AAA2O" in destinos
    assert "AAA3O" not in destinos


# --- top_n por tipo: no compiten entre sí -------------------------------------------------------


def test_top_n_corta_por_tipo_no_en_conjunto() -> None:
    origen = _especie("AAA1O", rendimiento=0.05, duracion=2.0, moneda_cupon="MEP")
    mejoras_rendimiento = [
        _especie(f"ZZZ{i}O", rendimiento=0.05 + MIN_DTIR + i * 0.01, duracion=2.0)
        for i in range(TOP_N + 2)
    ]
    mejoras_perfil = [
        _especie(f"AAA{i + 2}O", rendimiento=0.049, duracion=2.0, moneda_cupon="CCL")
        for i in range(TOP_N + 2)
    ]

    candidatas, _alertas = _detectar([origen], [*mejoras_rendimiento, *mejoras_perfil])

    por_tipo: dict[str, int] = {}
    for c in candidatas:
        por_tipo[c.tipo] = por_tipo.get(c.tipo, 0) + 1

    assert por_tipo["mejora_rendimiento"] == TOP_N
    assert por_tipo["mejora_perfil"] == TOP_N


# --- Origen sin rendimiento: se salta, con alerta, sin frenar el resto -------------------------


def test_origen_sin_rendimiento_se_saltea_sin_frenar_el_resto() -> None:
    sin_rendimiento = _especie("AAA1O", rendimiento=None, duracion=2.0)
    con_rendimiento = _especie("BBB1O", rendimiento=0.05, duracion=2.0)
    destino = _especie("BBB2O", rendimiento=0.09, duracion=2.0)

    candidatas, alertas = _detectar([sin_rendimiento, con_rendimiento], [destino])

    assert any(c.origen.ticker == "BBB1O" for c in candidatas)
    assert not any(c.origen.ticker == "AAA1O" for c in candidatas)
    assert any(a.codigo == "origen_sin_rendimiento" and "AAA1O" in a.mensaje for a in alertas)
