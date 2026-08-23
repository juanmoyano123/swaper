"""Los topes y la distribución de una cartera — F-020, `app/concentracion/servicio.py`.

**Los seis GWT de la ficha son el contrato de este archivo** y están marcados como tal. Lo demás
—tolerancia, pesos sin normalizar, tickers repetidos, posiciones fuera del universo— es el
comportamiento que la ficha da por sentado y que ningún GWT nombra, que es exactamente donde una
implementación se puede equivocar sin que nadie lo note.

El universo se arma con `segmentar` sobre filas de la vista `resumen`, igual que
`test_concentracion_riesgo`: lo que se prueba tiene que entrar por donde entra el dato real.
"""

from typing import Any

import pytest

from app.concentracion.alertas import (
    CODIGO_CONCENTRACION_EMISOR,
    CODIGO_CONCENTRACION_SECTOR,
    CODIGO_CONCENTRACION_SOBERANA,
    CODIGO_DIVERSIFICACION_INSUFICIENTE,
    CODIGO_EXPOSICION_FCI_NO_ATRIBUIBLE,
    CODIGO_FUERA_DEL_UNIVERSO,
)
from app.concentracion.perfiles import PERFILES, SOBERANO_AR, TOLERANCIA_TOPE
from app.concentracion.servicio import (
    SIN_LEY,
    SIN_SECTOR,
    Posicion,
    TipoDeTope,
    evaluar_concentracion,
)
from app.ingesta.alertas import Severidad
from app.universo.segmentacion import segmentar

# --- El universo de prueba ------------------------------------------------------------------------

# Tres emisiones del Tesoro bajo prefijos distintos, dos ONs del mismo emisor, tres corporativos de
# sectores distintos, un provincial y una ON sin sector curado. Es el mínimo que permite disparar
# los seis GWT sin que ninguno dependa de un caso inventado para la ocasión.
FILAS: list[dict[str, Any]] = [
    {"ticker": "GD30", "clase_activo": "bono_soberano", "tipo_tasa": "hard-dollar", "tir": 0.10,
     "sector": "Soberano", "law": "Ley N.Y."},
    {"ticker": "AE38", "clase_activo": "bono_soberano", "tipo_tasa": "hard-dollar", "tir": 0.11,
     "sector": "Soberano", "law": "Ley Argentina"},
    {"ticker": "TZX26", "clase_activo": "bono_soberano", "tipo_tasa": "cer", "tir": 0.05,
     "sector": "Soberano", "law": "Ley Argentina"},
    {"ticker": "YMCHO", "clase_activo": "on_corporativo", "tipo_tasa": "hard-dollar", "tir": 0.08,
     "sector": "O&G", "underlying": "YPF S.A.", "law": "Ley N.Y."},
    {"ticker": "YMCIO", "clase_activo": "on_corporativo", "tipo_tasa": "hard-dollar", "tir": 0.08,
     "sector": "O&G", "underlying": "YPF S.A.", "law": "Ley N.Y."},
    {"ticker": "PTSTO", "clase_activo": "on_corporativo", "tipo_tasa": "hard-dollar", "tir": 0.09,
     "sector": "O&G", "underlying": "Pampa Energia", "law": "Ley Argentina"},
    {"ticker": "MRCOO", "clase_activo": "on_corporativo", "tipo_tasa": "hard-dollar", "tir": 0.09,
     "sector": "O&G", "underlying": "Petrolera Marco", "law": "Ley Argentina"},
    {"ticker": "BNCAO", "clase_activo": "on_corporativo", "tipo_tasa": "badlar", "tna": 0.40,
     "sector": "Financiera", "underlying": "Banco Ejemplo"},
    {"ticker": "AGRCO", "clase_activo": "on_corporativo", "tipo_tasa": "hard-dollar", "tir": 0.07,
     "sector": "Agro", "underlying": "Agro Ejemplo", "law": "Ley N.Y."},
    {"ticker": "BA37D", "clase_activo": "bono_subsoberano", "tipo_tasa": "hard-dollar", "tir": 0.12,
     "sector": "Subsoberano", "underlying": "Provincia de Buenos Aires", "law": "Ley N.Y."},
    # Sin sector en el dato curado. No se le asigna uno por parecido con otro emisor (F-017).
    {"ticker": "XYZ1O", "clase_activo": "on_corporativo", "tipo_tasa": "hard-dollar", "tir": 0.09},
]

ESPECIES = segmentar(FILAS).especies


def evaluar(pesos: dict[str, float], perfil: str = "moderado"):
    return evaluar_concentracion(
        [Posicion(ticker=t, peso=p) for t, p in pesos.items()], ESPECIES, perfil
    )


def codigos(resultado) -> list[str]:
    return [a.codigo for a in resultado.alertas]


def tope_de(resultado, clave: str, tipo: TipoDeTope):
    return next(t for t in resultado.topes if t.clave == clave and t.tipo is tipo)


# --- Los seis GWT de la ficha ---------------------------------------------------------------------


def test_gwt1_los_tres_soberanos_se_miden_contra_el_tope_soberano() -> None:
    """GIVEN una cartera con GD30, AE38 y TZX26 → los tres bajo `SOBERANO_AR`, contra su tope."""
    resultado = evaluar({"GD30": 20, "AE38": 15, "TZX26": 10})

    soberano = tope_de(resultado, SOBERANO_AR, TipoDeTope.SOBERANO)
    assert soberano.peso == pytest.approx(45)
    assert soberano.tope == PERFILES["moderado"]["max_soberano"]
    # Y ninguno figura como emisor corporativo: si el prefijo mandara, serían tres créditos de 20,
    # 15 y 10 medidos contra un tope de 15, y el que se pasa sería AE38.
    assert [t.clave for t in resultado.topes if t.tipo is TipoDeTope.EMISOR] == []


def test_gwt2_una_cartera_cien_por_ciento_soberana_no_figura_como_diversificada() -> None:
    """GIVEN una cartera 100 % soberana → se advierte el exceso, y nunca pasa por diversificada."""
    resultado = evaluar({"GD30": 40, "AE38": 35, "TZX26": 25})

    assert tope_de(resultado, SOBERANO_AR, TipoDeTope.SOBERANO).excedido is True
    assert CODIGO_CONCENTRACION_SOBERANA in codigos(resultado)
    assert resultado.sectores_presentes == ["Soberano"]
    assert resultado.diversificacion_suficiente is False


def test_gwt3_un_emisor_corporativo_excedido_se_nombra_con_su_exceso() -> None:
    """GIVEN exceso de un emisor corporativo → se advierte nombrándolo, sin bloquear.

    Las dos ONs de YPF suman contra la misma clave: es un solo crédito con dos emisiones.
    """
    resultado = evaluar({"YMCHO": 20, "YMCIO": 10, "GD30": 40, "BNCAO": 20, "AGRCO": 10})

    ypf = tope_de(resultado, "YMC", TipoDeTope.EMISOR)
    assert ypf.peso == pytest.approx(30)
    assert ypf.excedido is True
    assert ypf.exceso == pytest.approx(15)

    alerta = next(a for a in resultado.alertas if a.codigo == CODIGO_CONCENTRACION_EMISOR)
    assert "YPF S.A." in alerta.mensaje
    # No bloquea: la posición se puede dejar igual.
    assert alerta.severidad is Severidad.ADVERTENCIA
    assert alerta.accion_requerida is None


def test_gwt4_soberano_y_subsoberano_quedan_exentos_del_tope_sectorial() -> None:
    """GIVEN posiciones de clase Soberano y Subsoberano → no participan del tope por sector.

    Ya los acota el tope soberano; acotarlos dos veces sería contar el mismo riesgo dos veces.
    """
    resultado = evaluar({"GD30": 60, "BA37D": 40})

    assert [t.clave for t in resultado.topes if t.tipo is TipoDeTope.SECTOR] == []
    assert CODIGO_CONCENTRACION_SECTOR not in codigos(resultado)
    # Pero siguen existiendo como sectores: la exención es del tope, no de la existencia.
    assert resultado.sectores_presentes == ["Soberano", "Subsoberano"]


def test_gwt5_dos_sectores_en_perfil_moderado_se_advierten_con_su_peso() -> None:
    """GIVEN una cartera dentro de todos los topes pero con sólo 2 sectores en moderado."""
    resultado = evaluar({"GD30": 60, "YMCHO": 15, "PTSTO": 15, "MRCOO": 10})

    assert resultado.excedidos == []
    assert resultado.sectores_presentes == ["O&G", "Soberano"]
    assert resultado.limites["min_sectores"] == 3

    alerta = next(a for a in resultado.alertas if a.codigo == CODIGO_DIVERSIFICACION_INSUFICIENTE)
    assert "O&G 40.0 %" in alerta.mensaje
    assert "Soberano 60.0 %" in alerta.mensaje
    assert alerta.accion_requerida is None


def test_gwt6_lo_que_no_tiene_sector_aparece_como_tal_y_no_se_reparte() -> None:
    """GIVEN posiciones sin sector informado → agrupadas como 'sector no informado', con su %."""
    resultado = evaluar({"GD30": 50, "YMCHO": 20, "XYZ1O": 30})

    sin_sector = next(t for t in resultado.por_sector if t.sin_dato)
    assert sin_sector.nombre == SIN_SECTOR
    assert sin_sector.peso == pytest.approx(30)
    # No se reparte entre los conocidos: O&G sigue siendo 20 y no 20 + una parte de los 30.
    assert next(t.peso for t in resultado.por_sector if t.nombre == "O&G") == pytest.approx(20)
    # Ni acredita diversificación: no se cuenta un sector que nadie declaró.
    assert resultado.sectores_presentes == ["O&G", "Soberano"]
    assert resultado.peso_sin_sector == pytest.approx(30)


# --- Lo que la ficha da por sentado ---------------------------------------------------------------


def test_los_pesos_se_miden_como_vienen_y_no_se_normalizan_a_cien() -> None:
    """Regla de F-018: si la cartera no suma 100, eso se mide tal cual y se declara.

    Normalizar mostraría el 16 % de YPF como un 20 % excedido sobre una cartera que sólo está
    armada al 80 %: sería inventar un exceso que no existe.
    """
    resultado = evaluar({"YMCHO": 16, "GD30": 40, "BNCAO": 24})

    assert resultado.peso_declarado == pytest.approx(80)
    assert resultado.peso_medido == pytest.approx(80)
    assert tope_de(resultado, "YMC", TipoDeTope.EMISOR).peso == pytest.approx(16)
    assert tope_de(resultado, "YMC", TipoDeTope.EMISOR).excedido is True


def test_un_ticker_repetido_concentra_como_una_sola_posicion() -> None:
    """Dos compras de la misma especie son el mismo crédito, no dos."""
    resultado = evaluar_concentracion(
        [Posicion("YMCHO", 8), Posicion("YMCHO", 9)], ESPECIES, "moderado"
    )

    assert tope_de(resultado, "YMC", TipoDeTope.EMISOR).peso == pytest.approx(17)
    assert resultado.peso_declarado == pytest.approx(17)


def test_la_tolerancia_del_motor_distingue_redondeo_de_exceso() -> None:
    """`peso > tope + 0.01`, portado tal cual: una centésima de punto es la reponderación."""
    tope = PERFILES["moderado"]["max_emisor"]

    justo = evaluar({"YMCHO": tope + TOLERANCIA_TOPE})
    pasado = evaluar({"YMCHO": tope + TOLERANCIA_TOPE * 2})

    assert tope_de(justo, "YMC", TipoDeTope.EMISOR).excedido is False
    assert tope_de(pasado, "YMC", TipoDeTope.EMISOR).excedido is True


def test_se_devuelve_el_estado_de_todos_los_topes_y_no_solo_los_rotos() -> None:
    """Una lista que sólo trajera los excedidos haría indistinguible 'holgado' de 'no se midió'."""
    resultado = evaluar({"GD30": 30, "YMCHO": 10, "BNCAO": 10})

    assert {(t.tipo, t.clave) for t in resultado.topes} == {
        (TipoDeTope.SOBERANO, SOBERANO_AR),
        (TipoDeTope.EMISOR, "YMC"),
        (TipoDeTope.EMISOR, "BNC"),
        (TipoDeTope.SECTOR, "O&G"),
        (TipoDeTope.SECTOR, "Financiera"),
    }
    assert resultado.excedidos == []
    assert resultado.alertas == []


def test_el_tope_sectorial_se_advierte_nombrando_el_sector() -> None:
    """Tres emisores distintos, cada uno dentro de su tope, y el sector igual se pasa: es el caso
    que el tope por emisor no puede ver."""
    resultado = evaluar({"YMCHO": 15, "PTSTO": 15, "MRCOO": 15, "GD30": 40, "BNCAO": 15})

    og = tope_de(resultado, "O&G", TipoDeTope.SECTOR)
    assert og.peso == pytest.approx(45)
    assert og.excedido is True
    assert all(not t.excedido for t in resultado.topes if t.tipo is TipoDeTope.EMISOR)
    assert "O&G" in next(
        a.mensaje for a in resultado.alertas if a.codigo == CODIGO_CONCENTRACION_SECTOR
    )


def test_las_posiciones_fuera_del_universo_no_participan_de_ningun_tope() -> None:
    """Un FCI, una acción o un ticker mal escrito: no tienen emisor derivable ni sector."""
    resultado = evaluar({"GD30": 50, "YMCHO": 15, "FCIALGO": 35})

    assert resultado.fuera_del_universo == ["FCIALGO"]
    assert resultado.peso_declarado == pytest.approx(100)
    assert resultado.peso_medido == pytest.approx(65)
    assert all(t.clave != "FCI" for t in resultado.topes)

    alerta = next(a for a in resultado.alertas if a.codigo == CODIGO_FUERA_DEL_UNIVERSO)
    assert alerta.severidad is Severidad.INFO
    assert "FCIALGO" in alerta.mensaje
    assert alerta.detalle["peso"] == pytest.approx(35)


def test_una_cartera_entera_fuera_del_universo_no_inventa_un_veredicto() -> None:
    """Cero sectores sobre cero posiciones medidas no es falta de diversificación: es que no se
    midió nada, y lo que lo dice es la alerta de posiciones fuera del universo."""
    resultado = evaluar({"FCIALGO": 60, "AAPL": 40})

    assert resultado.peso_medido == 0
    assert codigos(resultado) == [CODIGO_FUERA_DEL_UNIVERSO]


def test_la_distribucion_por_ley_declara_lo_que_no_esta() -> None:
    """La ley falta poco, pero además puede quedar vacía por conflicto entre fuentes (F-009)."""
    resultado = evaluar({"GD30": 40, "AE38": 30, "BNCAO": 30})

    por_ley = {t.nombre: t.peso for t in resultado.por_ley}
    assert por_ley["Ley N.Y."] == pytest.approx(40)
    assert por_ley["Ley Argentina"] == pytest.approx(30)
    assert por_ley[SIN_LEY] == pytest.approx(30)
    assert resultado.por_ley[-1].sin_dato is True


def test_la_distribucion_por_naturaleza_no_mezcla_unidades() -> None:
    """Regla 2 del dominio: una TIR en dólares, una tasa real sobre CER y una TNA en pesos son
    tres magnitudes distintas. La distribución las muestra abiertas, nunca sumadas."""
    resultado = evaluar({"GD30": 40, "TZX26": 30, "BNCAO": 30})

    por_naturaleza = {t.nombre: t.peso for t in resultado.por_naturaleza}
    assert por_naturaleza == {
        "TIR en dólares (hard dollar)": pytest.approx(40),
        "Tasa real sobre CER (por encima de inflación)": pytest.approx(30),
        "TNA nominal en pesos": pytest.approx(30),
    }
    # Hoy nunca falta: la naturaleza sale del segmento, que es lo que define si una especie entra
    # al universo comparable. El tramo existe igual, para el día que eso cambie.
    assert all(not t.sin_dato for t in resultado.por_naturaleza)


def test_ninguna_alerta_de_esta_feature_bloquea() -> None:
    """La ficha: 'la advertencia no bloquea: informa'."""
    resultado = evaluar({"GD30": 90, "YMCHO": 30, "FCIALGO": 10})

    assert len(resultado.alertas) > 0
    assert all(a.accion_requerida is None for a in resultado.alertas)
    assert all(a.severidad is not Severidad.ERROR for a in resultado.alertas)


def test_el_perfil_cambia_el_veredicto_sobre_la_misma_cartera() -> None:
    """Un 60 % soberano es exceso en conservador (50 %) y no lo es en moderado (65 %)."""
    pesos = {"GD30": 60, "YMCHO": 10, "BNCAO": 10, "AGRCO": 10, "PTSTO": 10}

    assert tope_de(evaluar(pesos, "conservador"), SOBERANO_AR, TipoDeTope.SOBERANO).excedido is True
    assert tope_de(evaluar(pesos, "moderado"), SOBERANO_AR, TipoDeTope.SOBERANO).excedido is False


def test_un_perfil_que_no_existe_no_se_resuelve_por_parecido() -> None:
    with pytest.raises(ValueError, match="perfil desconocido"):
        evaluar({"GD30": 100}, "prudente")


def test_el_dict_que_viaja_por_el_api_lleva_todo_lo_que_el_panel_muestra() -> None:
    cuerpo = evaluar({"GD30": 70, "YMCHO": 20, "XYZ1O": 10}).como_dict()

    assert cuerpo["perfil"] == "moderado"
    assert cuerpo["limites"]["min_sectores"] == 3
    # El soberano al 70 % (tope 65) y YPF al 20 % (tope 15): dos ejes distintos del mismo peso.
    assert cuerpo["excedidos"] == 2
    assert set(cuerpo["distribucion"]) == {"sector", "ley", "naturaleza"}
    assert cuerpo["sectores"]["cantidad"] == 2
    assert cuerpo["sectores"]["suficiente"] is False
    assert cuerpo["peso"] == {"declarado": pytest.approx(100), "medido": pytest.approx(100)}
    assert all("excedido" in tope for tope in cuerpo["topes"])
    assert all("sin_dato" in tramo for tramo in cuerpo["distribucion"]["sector"])


# --- F-046: exposición no atribuible de un FCI valuado ---------------------------------------------


def test_un_fci_valuado_entra_al_peso_medido_pero_a_ningun_tope() -> None:
    resultado = evaluar_concentracion(
        [
            Posicion(ticker="GD30", peso=70),
            Posicion(ticker="Fondo Renta Fija Clase A", peso=30, es_fci=True),
        ],
        ESPECIES,
        "moderado",
    )

    assert resultado.peso_declarado == pytest.approx(100)
    assert resultado.peso_medido == pytest.approx(100)
    assert resultado.fci == ["Fondo Renta Fija Clase A"]
    # El FCI no aporta a ningún tope: sólo GD30 (soberano) figura.
    assert [t.clave for t in resultado.topes] == [SOBERANO_AR]
    soberano = tope_de(resultado, SOBERANO_AR, TipoDeTope.SOBERANO)
    assert soberano.peso == pytest.approx(70)


def test_un_fci_valuado_no_entra_a_la_distribucion_por_sector_ley_ni_naturaleza() -> None:
    resultado = evaluar_concentracion(
        [Posicion(ticker="YMCHO", peso=60), Posicion(ticker="Fondo X", peso=40, es_fci=True)],
        ESPECIES,
        "moderado",
    )

    assert sum(t.peso for t in resultado.por_sector) == pytest.approx(60)
    assert sum(t.peso for t in resultado.por_ley) == pytest.approx(60)
    assert sum(t.peso for t in resultado.por_naturaleza) == pytest.approx(60)


def test_un_fci_valuado_dispara_una_alerta_propia_distinta_de_fuera_del_universo() -> None:
    resultado = evaluar_concentracion(
        [Posicion(ticker="GD30", peso=70), Posicion(ticker="Fondo X", peso=30, es_fci=True)],
        ESPECIES,
        "moderado",
    )

    codigos_alerta = codigos(resultado)
    assert CODIGO_EXPOSICION_FCI_NO_ATRIBUIBLE in codigos_alerta
    assert CODIGO_FUERA_DEL_UNIVERSO not in codigos_alerta

    alerta = next(a for a in resultado.alertas if a.codigo == CODIGO_EXPOSICION_FCI_NO_ATRIBUIBLE)
    assert alerta.severidad is Severidad.INFO
    assert "Fondo X" in alerta.mensaje


def test_un_fci_y_un_ticker_fuera_del_universo_disparan_las_dos_alertas_por_separado() -> None:
    resultado = evaluar_concentracion(
        [
            Posicion(ticker="GD30", peso=50),
            Posicion(ticker="NOEXISTE", peso=20),
            Posicion(ticker="Fondo X", peso=30, es_fci=True),
        ],
        ESPECIES,
        "moderado",
    )

    assert resultado.fuera_del_universo == ["NOEXISTE"]
    assert resultado.fci == ["Fondo X"]
    codigos_alerta = codigos(resultado)
    assert CODIGO_FUERA_DEL_UNIVERSO in codigos_alerta
    assert CODIGO_EXPOSICION_FCI_NO_ATRIBUIBLE in codigos_alerta
