"""De qué crédito es cada especie — F-020, `app/concentracion/riesgo.py`.

Se prueba sobre filas de la vista `resumen` pasadas por `segmentar`, y no construyendo
`EspecieUniverso` a mano: así el test también cubre que los campos que la derivación mira —
`clase_activo`, `underlying`— sean los que efectivamente llegan del universo.
"""

from typing import Any

from app.concentracion.perfiles import NOMBRE_SOBERANO, SOBERANO_AR
from app.concentracion.riesgo import clave_riesgo, derivar_riesgo, es_soberano, grupo_emisor
from app.universo.segmentacion import segmentar


def fila(ticker: str, **campos: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ticker": ticker,
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.08,
        "tna": None,
    }
    return {**base, **campos}


def especies(*filas: dict[str, Any]):
    return segmentar(filas).especies


def test_el_grupo_de_emisor_son_las_tres_primeras_letras_del_ticker() -> None:
    assert grupo_emisor("YMCHO") == "YMC"
    assert grupo_emisor("YMCIO") == "YMC"
    assert grupo_emisor("GD") == "GD"


def test_dos_emisiones_del_mismo_emisor_comparten_grupo() -> None:
    """YMCHO e YMCIO son dos ONs de YPF. Agrupar por raíz de emisión las contaría como dos
    créditos distintos y subestimaría la concentración: ése es el motivo del prefijo."""
    riesgos = derivar_riesgo(especies(fila("YMCHO"), fila("YMCIO")))

    assert riesgos["YMCHO"].clave_riesgo == riesgos["YMCIO"].clave_riesgo == "YMC"


def test_todo_el_tesoro_cae_bajo_una_sola_clave() -> None:
    """GWT-1 de la ficha: GD30, AE38 y TZX26 son el mismo crédito. Regla 4 del dominio."""
    riesgos = derivar_riesgo(
        especies(
            fila("GD30", clase_activo="bono_soberano"),
            fila("AE38", clase_activo="bono_soberano"),
            fila("TZX26", clase_activo="bono_soberano", tipo_tasa="cer", tir=0.1),
        )
    )

    assert {r.clave_riesgo for r in riesgos.values()} == {SOBERANO_AR}
    assert all(r.es_soberano for r in riesgos.values())
    assert all(r.nombre == NOMBRE_SOBERANO for r in riesgos.values())


def test_el_soberano_no_se_agrupa_por_prefijo() -> None:
    """El prefijo de GD30 y el de AE38 son distintos y aun así son el mismo riesgo: si la clave
    saliera del prefijo, una cartera íntegramente soberana pasaría como diversificada."""
    riesgos = derivar_riesgo(
        especies(
            fila("GD30", clase_activo="bono_soberano"),
            fila("AE38", clase_activo="bono_soberano"),
        )
    )

    assert riesgos["GD30"].grupo_emisor != riesgos["AE38"].grupo_emisor
    assert riesgos["GD30"].clave_riesgo == riesgos["AE38"].clave_riesgo


def test_un_subsoberano_no_es_soberano() -> None:
    """Una provincia emite su propio crédito: entra al tope corporativo, no al del Tesoro."""
    riesgos = derivar_riesgo(especies(fila("BA37D", clase_activo="bono_subsoberano")))

    assert riesgos["BA37D"].es_soberano is False
    assert riesgos["BA37D"].clave_riesgo == "BA3"


def test_el_nombre_del_emisor_se_muestra_pero_no_agrupa() -> None:
    riesgos = derivar_riesgo(especies(fila("YMCHO", underlying="YPF S.A."), fila("YMCIO")))

    assert riesgos["YMCHO"].nombre == "YPF S.A."
    # La hermana sin nombre hereda el del grupo: es el mismo crédito y mostrarlo "(sin identificar)"
    # al lado del que sí tiene nombre haría creer que son dos.
    assert riesgos["YMCIO"].nombre == "YPF S.A."


def test_un_grupo_sin_nombre_conserva_el_prefijo_a_la_vista() -> None:
    """El tope se aplica igual —el crédito existe aunque no sepamos cómo se llama— y quien lea la
    advertencia puede ir a averiguar de quién es ese prefijo."""
    riesgos = derivar_riesgo(especies(fila("XYZ1O")))

    assert riesgos["XYZ1O"].nombre == "(sin identificar: XYZ)"


def test_entre_varias_grafias_se_elige_siempre_la_misma() -> None:
    """No hay forma de saber cuál grafía es la correcta; lo que importa es que no cambie sola."""
    dos_grafias = especies(fila("YMCHO", underlying="YPF SA"), fila("YMCIO", underlying="YPF S.A."))

    assert derivar_riesgo(dos_grafias)["YMCIO"].nombre == "YPF SA"
    assert derivar_riesgo(list(reversed(dos_grafias)))["YMCIO"].nombre == "YPF SA"


def test_las_funciones_sueltas_coinciden_con_la_derivacion_completa() -> None:
    assert es_soberano("bono_soberano") is True
    assert es_soberano("on_corporativo") is False
    assert clave_riesgo("GD30", "bono_soberano") == SOBERANO_AR
    assert clave_riesgo("YMCHO", "on_corporativo") == "YMC"
