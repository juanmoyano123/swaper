"""Herencia entre especies y detección de conflictos: los dos criterios que definen F-009.

El segundo es el que importa y el más fácil de arruinar: ante dos valores en pugna el sistema no
elige ninguno. Por eso hay un test por cada forma de elegir que podría colarse —precedencia por
orden del archivo, por orden alfabético, por "el que declara primero"— y todos exigen lo mismo:
las dos especies vacías y el conflicto reportado con los dos valores.
"""

from datetime import date

from app.condiciones.resolucion import Conflicto, resolver
from app.condiciones.semilla import Condiciones, Valor
from app.ingesta.alertas import CODIGO_CONDICIONES_EN_CONFLICTO

FECHA = date(2026, 8, 5)
ORIGEN = "condiciones_emision.csv (curado)"


def _especie(ticker: str, **campos: object) -> Condiciones:
    return Condiciones(
        ticker=ticker,
        valores={
            campo: Valor(valor=valor, origen=ORIGEN, fecha=FECHA) for campo, valor in campos.items()
        },
    )


def _por_ticker(resolucion) -> dict[str, Condiciones]:
    return {fila.ticker: fila for fila in resolucion.filas}


# --- GWT-1: herencia entre especies -------------------------------------------------------------


def test_las_especies_sin_lamina_la_heredan_de_la_que_si_la_declara() -> None:
    """GIVEN AL30 con lámina y AL30D y AL30C sin ella WHEN corre la herencia THEN la heredan."""
    resolucion = resolver([_especie("AL30", lamina=1.0), _especie("AL30D"), _especie("AL30C")])

    filas = _por_ticker(resolucion)
    for heredera in ("AL30D", "AL30C"):
        assert filas[heredera].valores["lamina"].valor == 1.0
        assert filas[heredera].valores["lamina"].origen == "herencia de AL30"
    assert resolucion.heredados_por_campo["lamina"] == 2


def test_el_valor_heredado_conserva_la_fecha_del_donante() -> None:
    """El heredero no sabe más de lo que sabía quien se lo prestó."""
    otra_fecha = date(2025, 3, 1)
    donante = Condiciones("AL30", {"ley": Valor("Ley Argentina", ORIGEN, otra_fecha)})

    filas = _por_ticker(resolver([donante, _especie("AL30D")]))

    assert filas["AL30D"].valores["ley"].fecha == otra_fecha


def test_la_especie_que_ya_declaraba_el_valor_conserva_su_propio_origen() -> None:
    """Heredar no reescribe lo que ya estaba: el origen del que lo declaró sigue siendo el suyo."""
    filas = _por_ticker(resolver([_especie("AL30", sector="Soberano"), _especie("AL30D")]))

    assert filas["AL30"].valores["sector"].origen == ORIGEN
    assert filas["AL30D"].valores["sector"].origen == "herencia de AL30"


def test_la_herencia_no_cruza_emisiones_distintas() -> None:
    """AL30 y AL35 son bonos distintos: nada de uno vale para el otro."""
    filas = _por_ticker(resolver([_especie("AL30", lamina=1.0), _especie("AL35D")]))

    assert "lamina" not in filas["AL35D"].valores


def test_hereda_de_cualquier_especie_no_solo_de_la_raiz() -> None:
    """El curado tiene emisiones donde el dato está en la especie D y no en la raíz."""
    filas = _por_ticker(resolver([_especie("AEC2O", sector="Servicios"), _especie("AEC2C")]))

    assert filas["AEC2C"].valores["sector"].origen == "herencia de AEC2O"


def test_el_donante_es_la_raiz_cuando_varias_especies_declaran_lo_mismo() -> None:
    """Todas declaran igual, así que el rótulo no cambia el valor: sólo tiene que nombrar a una."""
    filas = _por_ticker(
        resolver([_especie("AL30D", lamina=1.0), _especie("AL30", lamina=1.0), _especie("AL30C")])
    )

    assert filas["AL30C"].valores["lamina"].origen == "herencia de AL30"


def test_el_donante_es_estable_aunque_cambie_el_orden_del_archivo() -> None:
    especies = [_especie("AL30D", lamina=1.0), _especie("AL30C", lamina=1.0), _especie("AL30")]

    directo = _por_ticker(resolver(especies))["AL30"].valores["lamina"].origen
    invertido = _por_ticker(resolver(list(reversed(especies))))["AL30"].valores["lamina"].origen

    assert directo == invertido == "herencia de AL30C"


def test_los_seis_campos_se_heredan() -> None:
    """Los seis son atributos de la emisión o del emisor, no de la especie."""
    completa = _especie(
        "MR46O",
        ley="Ley N.Y.",
        moneda_pago="CCL",
        lamina=100.0,
        calificacion="AAA(arg)",
        sector="O&G",
        underlying="Emisor S.A.",
    )

    filas = _por_ticker(resolver([completa, _especie("MR46D")]))

    assert set(filas["MR46D"].valores) == set(completa.valores)


def test_resolver_no_modifica_las_filas_que_recibe() -> None:
    """La resolución tiene que ser reejecutable sobre la misma semilla."""
    entrada = [_especie("AL30", lamina=1.0), _especie("AL30D")]

    resolver(entrada)

    assert entrada[1].valores == {}


# --- GWT-2: conflicto entre especies ------------------------------------------------------------


def test_dos_laminas_distintas_vacian_las_dos_especies_y_se_reporta() -> None:
    """GIVEN dos especies con láminas distintas THEN quedan vacías y el sistema no elige ninguna."""
    resolucion = resolver([_especie("AL30", lamina=1.0), _especie("AL30D", lamina=100.0)])

    filas = _por_ticker(resolucion)
    assert "lamina" not in filas["AL30"].valores
    assert "lamina" not in filas["AL30D"].valores
    assert resolucion.conflictos == [
        Conflicto(campo="lamina", raiz="AL30", valores={"AL30": 1.0, "AL30D": 100.0})
    ]
    assert resolucion.vaciados_por_campo["lamina"] == 2


def test_el_conflicto_reporta_los_dos_valores_en_pugna_con_su_ticker() -> None:
    resolucion = resolver([_especie("AL30", lamina=1.0), _especie("AL30D", lamina=100.0)])

    (alerta,) = resolucion.alertas
    assert alerta.codigo == CODIGO_CONDICIONES_EN_CONFLICTO
    assert alerta.detalle["valores"] == {"AL30": 1.0, "AL30D": 100.0}
    assert "AL30=1.0" in alerta.mensaje and "AL30D=100.0" in alerta.mensaje
    assert alerta.accion_requerida


def test_el_conflicto_no_se_resuelve_por_el_orden_del_archivo() -> None:
    directo = resolver([_especie("AL30", lamina=1.0), _especie("AL30D", lamina=100.0)])
    invertido = resolver([_especie("AL30D", lamina=100.0), _especie("AL30", lamina=1.0)])

    for resolucion in (directo, invertido):
        assert all("lamina" not in fila.valores for fila in resolucion.filas)


def test_el_conflicto_no_se_resuelve_a_favor_de_la_raiz() -> None:
    """Ser la especie que da nombre a la emisión no es un criterio de precedencia."""
    filas = _por_ticker(
        resolver([_especie("AL30", ley="Ley Argentina"), _especie("AL30D", ley="Ley N.Y.")])
    )

    assert "ley" not in filas["AL30"].valores


def test_una_tercera_especie_sin_valor_tampoco_hereda_del_conflicto() -> None:
    """Una emisión que no sabe cuál es su lámina no tiene ninguna para prestarle a nadie."""
    resolucion = resolver(
        [_especie("AL30", lamina=1.0), _especie("AL30D", lamina=100.0), _especie("AL30C")]
    )

    assert all("lamina" not in fila.valores for fila in resolucion.filas)
    assert resolucion.heredados_por_campo["lamina"] == 0


def test_el_conflicto_de_un_campo_no_arrastra_a_los_demas() -> None:
    """Se vacía el campo en pugna, no la especie entera."""
    resolucion = resolver(
        [
            _especie("AL30", lamina=1.0, sector="Soberano"),
            _especie("AL30D", lamina=100.0),
        ]
    )

    filas = _por_ticker(resolucion)
    assert filas["AL30"].valores["sector"].valor == "Soberano"
    assert filas["AL30D"].valores["sector"].origen == "herencia de AL30"
    assert "lamina" not in filas["AL30"].valores


def test_tres_valores_distintos_vacian_las_tres_especies() -> None:
    resolucion = resolver(
        [
            _especie("AL30", calificacion="AAA(arg)"),
            _especie("AL30D", calificacion="AA(arg)"),
            _especie("AL30C", calificacion="A(arg)"),
        ]
    )

    assert all("calificacion" not in fila.valores for fila in resolucion.filas)
    assert len(resolucion.conflictos[0].valores) == 3


def test_dos_grafias_del_mismo_texto_son_un_conflicto() -> None:
    """Unificarlas obligaría a elegir cuál grafía se guarda, que es la decisión prohibida."""
    resolucion = resolver(
        [_especie("AL30", sector="Soberano"), _especie("AL30D", sector="soberano")]
    )

    assert len(resolucion.conflictos) == 1


def test_un_valor_heredado_nunca_entra_en_conflicto_con_su_donante() -> None:
    """El conflicto se evalúa sólo sobre lo declarado, así que la pregunta no llega a existir."""
    resolucion = resolver([_especie("AL30", lamina=1.0), _especie("AL30D"), _especie("AL30C")])

    assert resolucion.conflictos == []
    assert resolucion.vaciados_por_campo["lamina"] == 0


# --- Casos de borde ------------------------------------------------------------------------------


def test_una_semilla_vacia_resuelve_a_nada() -> None:
    resolucion = resolver([])

    assert resolucion.filas == []
    assert resolucion.conflictos == []
    assert set(resolucion.heredados_por_campo.values()) == {0}


def test_una_especie_sola_se_devuelve_igual() -> None:
    filas = _por_ticker(resolver([_especie("TX26", lamina=1.0)]))

    assert filas["TX26"].valores["lamina"].origen == ORIGEN


def test_un_ticker_corto_terminado_en_o_no_se_corta_para_buscar_hermanas() -> None:
    """El guardia de longitud de `raiz_emision`: cortar strings ya costó 121 tickers inventados."""
    resolucion = resolver([_especie("PBO", lamina=1.0), _especie("PB", lamina=100.0)])

    assert resolucion.conflictos == []
