"""El reparto sectorial del armado asistido — F-019, alcance ampliado 08/2026 (GWT-4 y GWT-5).

Sin base de datos: `armar()` es una función pura sobre `EspecieUniverso`/`RiesgoDeEspecie`
construidos a mano, mismo criterio que `test_concentracion_servicio.py` para la evaluación de
concentración.
"""

from typing import Any

from app.armado.motor import armar
from app.armado.parametros import ParametrosArmado
from app.concentracion.alertas import CODIGO_DIVERSIFICACION_INSUFICIENTE
from app.concentracion.perfiles import PERFILES
from app.concentracion.riesgo import RiesgoDeEspecie
from app.universo.segmentacion import EspecieUniverso

MONTO = 100_000.0


def _especie(
    ticker: str, *, rendimiento: float, sector: str | None, duracion: float = 3.0
) -> EspecieUniverso:
    return EspecieUniverso(
        ticker=ticker,
        raiz=ticker,
        clase_activo="on_corporativo",
        segmento="usd_hard",
        rendimiento=rendimiento,
        duracion=duracion,
        precio=100.0,
        sector=sector,
    )


def _riesgo(especie: EspecieUniverso, *, es_soberano: bool = False) -> RiesgoDeEspecie:
    grupo = especie.ticker[:3]
    return RiesgoDeEspecie(
        ticker=especie.ticker,
        grupo_emisor=grupo,
        es_soberano=es_soberano,
        clave_riesgo="SOBERANO_AR" if es_soberano else grupo,
        nombre=f"Emisor {grupo}",
    )


def _armar(especies: list[EspecieUniverso], *, perfil_nombre: str, n_total: int = 15) -> Any:
    riesgos = {e.ticker: _riesgo(e) for e in especies}
    params = ParametrosArmado(monto=MONTO, mix={"usd_hard": 100}, n_total=n_total)
    return armar(
        especies, {"usd_hard": 100}, PERFILES[perfil_nombre], perfil_nombre, params, riesgos
    )


def test_seis_sectores_comparables_dan_al_menos_el_minimo_del_conservador() -> None:
    """GWT-4: perfil con `min_sectores = 4` y un universo con candidatos comparables de 6 sectores
    -> la cartera resultante contiene posiciones de al menos 4 sectores distintos, sin contar
    Soberano ni Subsoberano."""
    sectores = ["O&G", "Agro", "Financiera", "Infraestructura", "Servicios", "Minería"]
    # Emisores (prefijos de ticker) todos distintos, y todos dentro de la banda de rendimiento del
    # motor (0.5pp) para que el desempate sectorial tenga candidatos comparables entre los que
    # elegir -- si no estuvieran en banda, el orden por rendimiento solo ya alcanzaría.
    especies = [
        _especie(f"T{i}CO", rendimiento=0.070 + i * 0.001, sector=sectores[i]) for i in range(6)
    ]

    resultado = _armar(especies, perfil_nombre="conservador")

    assert resultado.sectores_presentes >= PERFILES["conservador"]["min_sectores"]
    assert len(resultado.posiciones) == 6


def test_un_solo_sector_corporativo_sale_con_alerta_y_no_bloquea() -> None:
    """GWT-5: universo elegible con un solo sector corporativo -> la cartera sale con ese sector y
    una advertencia que nombra el mínimo incumplido y la causa, sin bloquear ni rellenar."""
    especies = [_especie(f"T{i}CO", rendimiento=0.07 + i * 0.001, sector="O&G") for i in range(3)]

    resultado = _armar(especies, perfil_nombre="conservador")

    assert len(resultado.posiciones) == 3  # no se bloquea: la cartera sale igual
    assert resultado.sectores_presentes == 1
    assert resultado.sectores_presentes < resultado.min_sectores
    alerta = next(a for a in resultado.alertas if a.codigo == CODIGO_DIVERSIFICACION_INSUFICIENTE)
    assert str(resultado.min_sectores) in alerta.mensaje
    assert "O&G" in alerta.mensaje
    assert alerta.accion_requerida is None  # informa, no bloquea


def test_soberano_y_subsoberano_no_cuentan_para_el_minimo_de_f019() -> None:
    """GWT-4 dice literal 'sin contar Soberano ni Subsoberano' -- a diferencia del criterio de F-020
    (`app/concentracion/perfiles.py::sector_computable`'s docstring dice que un soberano sí cuenta
    como sector presente para el `min_sectores` de ESE panel). Es una divergencia de texto entre las
    dos fichas, declarada en el plan de F-019: acá se sigue el GWT literal de esta ficha."""
    especies = [
        EspecieUniverso(
            ticker="AL30",
            raiz="AL30",
            clase_activo="bono_soberano",
            segmento="usd_hard",
            rendimiento=0.07,
            duracion=3.0,
            precio=100.0,
            sector="Soberano",
        ),
        EspecieUniverso(
            ticker="PBA25",
            raiz="PBA25",
            clase_activo="bono_subsoberano",
            segmento="usd_hard",
            rendimiento=0.071,
            duracion=3.0,
            precio=100.0,
            sector="Subsoberano",
        ),
        _especie("T0CO", rendimiento=0.072, sector="O&G"),
    ]
    riesgos = {
        "AL30": RiesgoDeEspecie(
            ticker="AL30",
            grupo_emisor="AL3",
            es_soberano=True,
            clave_riesgo="SOBERANO_AR",
            nombre="Riesgo soberano argentino",
        ),
        "PBA25": RiesgoDeEspecie(
            ticker="PBA25",
            grupo_emisor="PBA",
            es_soberano=False,
            clave_riesgo="PBA",
            nombre="Provincia de Buenos Aires",
        ),
        "T0CO": _riesgo(especies[2]),
    }
    params = ParametrosArmado(monto=MONTO, mix={"usd_hard": 100}, n_total=15)
    resultado = armar(
        especies, {"usd_hard": 100}, PERFILES["conservador"], "conservador", params, riesgos
    )

    # Las tres posiciones entran (no hay tope que las excluya), pero sólo "O&G" es un sector
    # computable: Soberano y Subsoberano están exentos y no suman al conteo de esta ficha.
    assert len(resultado.posiciones) == 3
    assert resultado.sectores_presentes == 1
