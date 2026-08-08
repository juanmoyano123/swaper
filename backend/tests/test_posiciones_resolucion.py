"""Los cuatro GWT de F-029 y la decisión sobre el porcentaje cuando falta el monto.

Todo acá es puro: sin Postgres, sin red y sin reloj. Lo que se prueba es la regla que da origen a
la feature —**un ticker que no está no se aproxima al más parecido**— y la aritmética de la
cobertura, que es donde un faltante tratado como cero mentiría sin que nadie lo note.
"""

from app.posiciones.resolucion import (
    Cobertura,
    FilaInstrumento,
    MotivoNoResuelta,
    PosicionDeclarada,
    clave_de_busqueda,
    indexar_instrumentos,
    resolver,
)
from app.universo.segmentacion import EspecieUniverso


def especie(ticker: str, *, segmento: str = "usd_hard", moneda: str = "USD") -> EspecieUniverso:
    raiz = ticker[:-1] if len(ticker) >= 4 and ticker[-1] in ("O", "D", "C") else ticker
    return EspecieUniverso(
        ticker=ticker,
        raiz=raiz,
        clase_activo="on_corporativo",
        segmento=segmento,
        rendimiento=0.0727,
        precio=98.4,
        moneda_cotizacion=moneda,
    )


# Las tres especies de liquidación de la misma emisión, más un soberano. La vista viva: sin
# colapsar, que es la que la cartera de un cliente necesita para tener la especie que compró.
UNIVERSO = [
    especie("MR46O", moneda="ARS"),
    especie("MR46D"),
    especie("MR46C"),
    especie("AL30"),
    especie("RUCEO"),
]

# Lo que la base conoce, sea comparable o no. GGAL es una acción y RUCEX una ON sin tipo de tasa:
# los dos existen y ninguno de los dos llega al universo comparable. Verificados contra la base
# real el 07/08/2026.
INSTRUMENTOS = {
    "MR46O": FilaInstrumento("MR46O", "on_corporativo", "2"),
    "MR46D": FilaInstrumento("MR46D", "on_corporativo", "2"),
    "MR46C": FilaInstrumento("MR46C", "on_corporativo", "1"),
    "AL30": FilaInstrumento("AL30", "bono_soberano", "2"),
    "RUCEO": FilaInstrumento("RUCEO", "on_corporativo", "2"),
    "RUCEX": FilaInstrumento("RUCEX", "on_corporativo", "1"),
    "GGAL": FilaInstrumento("GGAL", "accion", "2"),
}


def posicion(
    ticker: str,
    *,
    monto: float | None = 1000.0,
    nominal: float | None = None,
    fila: int = 1,
) -> PosicionDeclarada:
    return PosicionDeclarada(
        id=f"p-{ticker}-{fila}",
        fila=fila,
        ticker_declarado=ticker,
        nominal=nominal,
        monto=monto,
    )


def resolver_estas(*posiciones: PosicionDeclarada, descartados: set[str] | None = None):
    return resolver(posiciones, UNIVERSO, INSTRUMENTOS, descartados or set())


# --- GWT-1: un ticker que está en el universo queda vinculado a su especie -----------------------


def test_una_posicion_conocida_queda_vinculada_a_su_emision_y_a_su_especie() -> None:
    (resuelta,) = resolver_estas(posicion("MR46D")).posiciones

    assert resuelta.resuelta
    assert resuelta.especie is not None
    assert resuelta.especie.ticker == "MR46D"
    assert resuelta.especie.raiz == "MR46"
    assert resuelta.motivo is None


def test_la_especie_resuelta_declara_su_plazo_de_liquidacion() -> None:
    """El plazo sale de `instrumentos.plazo_liquidacion` y no del sufijo del ticker.

    MR46C y MR46D comparten emisión y difieren en el sufijo, que es la **moneda** de liquidación;
    sus plazos son distintos porque la base dice que lo son, no porque la letra lo diga.
    """
    cartera = resolver_estas(posicion("MR46D", fila=1), posicion("MR46C", fila=2))

    plazos = {p.declarada.ticker_declarado: p.plazo_liquidacion for p in cartera.posiciones}
    assert plazos == {"MR46D": "2", "MR46C": "1"}


def test_el_plazo_viaja_sin_traducir() -> None:
    """`"2"` y no `"48hs"`: ninguna fuente del proyecto publica qué plazo es cada código.

    Traducir un código de la fuente a una categoría "equivalente" es exactamente el error que una
    vez inventó una ley que no existe.
    """
    (resuelta,) = resolver_estas(posicion("AL30")).posiciones

    assert resuelta.plazo_liquidacion == "2"


def test_una_especie_resuelta_sin_plazo_en_la_base_lo_deja_vacio_y_lo_alerta() -> None:
    cartera = resolver(
        [posicion("AL30")],
        UNIVERSO,
        {"AL30": FilaInstrumento("AL30", "bono_soberano", None)},
    )

    (resuelta,) = cartera.posiciones
    assert resuelta.resuelta
    assert resuelta.plazo_liquidacion is None
    assert "plazo_de_liquidacion_no_disponible" in {a.codigo for a in cartera.alertas}


def test_las_tres_especies_del_mismo_bono_resuelven_cada_una_a_la_suya() -> None:
    """La vista viva y no la colapsada: el cliente tiene la especie que compró.

    Si se resolviera contra la vista colapsada, las tres posiciones apuntarían al representante de
    MR46 y la cartera diría que tiene un instrumento que no tiene.
    """
    cartera = resolver_estas(
        posicion("MR46O", fila=1), posicion("MR46D", fila=2), posicion("MR46C", fila=3)
    )

    tickers = [p.especie.ticker for p in cartera.posiciones if p.especie]
    assert tickers == ["MR46O", "MR46D", "MR46C"]
    assert {p.especie.raiz for p in cartera.posiciones if p.especie} == {"MR46"}


# --- GWT-2: un ticker que no existe no se reemplaza por el más parecido --------------------------


def test_un_ticker_que_no_esta_queda_no_reconocido_con_su_monto() -> None:
    (resuelta,) = resolver_estas(posicion("NOEXISTE", monto=5000.0)).posiciones

    assert not resuelta.resuelta
    assert resuelta.especie is None
    assert resuelta.motivo is MotivoNoResuelta.NO_ESTA_EN_EL_UNIVERSO
    # Sigue en la cartera y con el monto intacto: no se descarta en silencio.
    assert resuelta.declarada.monto == 5000.0
    assert resuelta.declarada.ticker_declarado == "NOEXISTE"


def test_un_ticker_parecido_a_uno_del_universo_no_se_aproxima() -> None:
    """`RUCE0` (con cero) contra `RUCEO` (con o). Una letra de diferencia y ninguna aproximación."""
    (resuelta,) = resolver_estas(posicion("RUCE0")).posiciones

    assert not resuelta.resuelta
    assert resuelta.especie is None


def test_la_alerta_de_no_resueltas_no_propone_ningun_reemplazo() -> None:
    cartera = resolver_estas(posicion("RUCE0"))

    (alerta,) = [a for a in cartera.alertas if a.codigo == "posiciones_no_resueltas"]
    assert "RUCE0" in alerta.mensaje
    assert "RUCEO" not in alerta.mensaje
    assert "RUCEO" not in str(alerta.detalle)


# --- GWT-4: no se deriva una especie por manipulación de sufijos ---------------------------------


def test_pedir_rucex_no_devuelve_rucex_derivado_de_ruceo() -> None:
    """El caso testigo de la feature: existe `RUCEO`, se pidió `RUCEX`, y `RUCEX` queda afuera.

    Contra la base real `RUCEX` además existe como ON sin tipo de tasa reconocido, así que ni
    siquiera hace falta inventarlo para que no resuelva — y si no existiera, tampoco se inventaría.
    """
    (resuelta,) = resolver_estas(posicion("RUCEX")).posiciones

    assert not resuelta.resuelta
    assert resuelta.especie is None
    assert resuelta.motivo is MotivoNoResuelta.SIN_TIPO_DE_TASA


def test_pedir_una_especie_de_liquidacion_inexistente_no_la_genera() -> None:
    """`AL30` está en el universo; `AL30D` no. No se genera pegándole la D a la raíz."""
    (resuelta,) = resolver_estas(posicion("AL30D")).posiciones

    assert not resuelta.resuelta
    assert resuelta.motivo is MotivoNoResuelta.NO_ESTA_EN_EL_UNIVERSO


def test_una_accion_no_es_un_ticker_inexistente() -> None:
    """GGAL existe: lo que pasa es que no es renta fija comparable, y eso es lo que se contesta."""
    (resuelta,) = resolver_estas(posicion("GGAL")).posiciones

    assert not resuelta.resuelta
    assert resuelta.motivo is MotivoNoResuelta.RENTA_VARIABLE
    assert resuelta.clase_activo == "accion"


# --- La única normalización que se le hace al ticker declarado -----------------------------------


def test_el_ticker_escrito_a_mano_se_busca_sin_espacios_y_en_mayusculas() -> None:
    (resuelta,) = resolver_estas(posicion("  al30 ")).posiciones

    assert resuelta.resuelta
    assert resuelta.especie is not None
    assert resuelta.especie.ticker == "AL30"
    # Y lo declarado viaja entero, para que la diferencia se pueda ver.
    assert resuelta.declarada.ticker_declarado == "  al30 "


def test_la_clave_de_busqueda_no_toca_el_cuerpo_del_ticker() -> None:
    assert clave_de_busqueda(" al30 ") == "AL30"
    assert clave_de_busqueda("RUCEX") == "RUCEX"


# --- GWT-3: el diagnóstico de cobertura ----------------------------------------------------------


def test_dos_de_once_sin_resolver_declaran_cantidad_y_porcentaje() -> None:
    """El GWT literal: 9 posiciones de 1.000 que resuelven y 2 de 1.000 que no. 2.000 / 11.000."""
    conocidas = [posicion("AL30", fila=i) for i in range(1, 10)]
    desconocidas = [posicion("NOEXISTE1", fila=10), posicion("NOEXISTE2", fila=11)]
    cobertura = resolver_estas(*conocidas, *desconocidas).cobertura

    assert cobertura.posiciones == 11
    assert cobertura.no_resueltas == 2
    assert cobertura.monto_declarado == 11_000.0
    assert cobertura.monto_no_resuelto == 2_000.0
    assert cobertura.porcentaje_no_resuelto is not None
    assert round(cobertura.porcentaje_no_resuelto, 2) == 18.18


def test_una_cartera_entera_resuelta_declara_cero_por_ciento_sin_resolver() -> None:
    cartera = resolver_estas(posicion("AL30", fila=1), posicion("MR46D", fila=2))

    assert cartera.cobertura.porcentaje_no_resuelto == 0.0
    assert cartera.cobertura.no_resueltas == 0
    assert not [a for a in cartera.alertas if a.codigo == "posiciones_no_resueltas"]


# --- La decisión sobre las posiciones sin monto --------------------------------------------------


def test_una_posicion_sin_monto_queda_fuera_de_la_base_y_no_cuenta_como_cero() -> None:
    """Sólo tiene nominales: no hay monto declarado, y valorizarla necesita un precio.

    Si entrara como cero, la base sería la misma pero el mensaje cambiaría: diría que se la tuvo en
    cuenta. Queda afuera y se cuenta aparte.
    """
    cartera = resolver_estas(
        posicion("AL30", monto=1000.0, fila=1),
        posicion("MR46D", monto=None, nominal=50_000.0, fila=2),
    )

    cobertura = cartera.cobertura
    assert cobertura.posiciones == 2
    assert cobertura.posiciones_con_monto == 1
    assert cobertura.posiciones_sin_monto == 1
    assert cobertura.monto_declarado == 1000.0


def test_la_no_resuelta_sin_monto_no_baja_el_porcentaje() -> None:
    """El caso peligroso: si la sin monto entrara como cero, el porcentaje diría 0 % en vez de la
    verdad, que es que hay una posición no resuelta que ni siquiera se puede valorizar."""
    cartera = resolver_estas(
        posicion("AL30", monto=1000.0, fila=1),
        posicion("NOEXISTE", monto=None, nominal=50_000.0, fila=2),
    )

    cobertura = cartera.cobertura
    assert cobertura.no_resueltas == 1
    assert cobertura.porcentaje_no_resuelto == 0.0
    assert cobertura.posiciones_sin_monto_no_resueltas == 1
    # Y el 0 % nunca se muestra solo: la alerta dice sobre qué base se calculó.
    assert "posiciones_sin_monto" in {a.codigo for a in cartera.alertas}


def test_la_alerta_de_base_dice_sobre_cuantas_posiciones_se_calculo() -> None:
    cartera = resolver_estas(
        posicion("AL30", monto=1000.0, fila=1),
        posicion("MR46D", monto=None, nominal=1.0, fila=2),
        posicion("NOEXISTE", monto=None, nominal=1.0, fila=3),
    )

    (alerta,) = [a for a in cartera.alertas if a.codigo == "posiciones_sin_monto"]
    assert "1 de 3" in alerta.mensaje
    assert alerta.detalle["posiciones_sin_monto_no_resueltas"] == 1


def test_sin_ninguna_posicion_con_monto_el_porcentaje_es_nulo_y_no_cero() -> None:
    cartera = resolver_estas(
        posicion("AL30", monto=None, nominal=10.0, fila=1),
        posicion("NOEXISTE", monto=None, nominal=10.0, fila=2),
    )

    assert cartera.cobertura.porcentaje_no_resuelto is None
    # Lo que sí es exacto es la cantidad: no depende del monto.
    assert cartera.cobertura.no_resueltas == 1
    assert "sin_base_para_el_porcentaje" in {a.codigo for a in cartera.alertas}


def test_sin_base_la_alerta_de_no_resueltas_no_inventa_un_porcentaje() -> None:
    cartera = resolver_estas(posicion("NOEXISTE", monto=None, nominal=10.0))

    (alerta,) = [a for a in cartera.alertas if a.codigo == "posiciones_no_resueltas"]
    assert "%" not in alerta.mensaje
    assert alerta.detalle["porcentaje_no_resuelto"] is None


def test_una_cartera_vacia_no_rompe_ni_alerta() -> None:
    cartera = resolver([], UNIVERSO, INSTRUMENTOS)

    assert cartera.posiciones == []
    assert cartera.cobertura == Cobertura()
    assert cartera.alertas == []


# --- El dato de mercado descartado por la sanidad de F-010 ---------------------------------------


def test_una_posicion_resuelve_aunque_su_especie_este_descartada_y_lo_declara() -> None:
    """El cliente tiene ese bono: no desaparece porque su precio esté mal escalado en la fuente."""
    cartera = resolver_estas(posicion("MR46D"), descartados={"MR46D"})

    (resuelta,) = cartera.posiciones
    assert resuelta.resuelta
    assert resuelta.dato_sano is False
    assert "posicion_con_dato_no_sano" in {a.codigo for a in cartera.alertas}


def test_una_posicion_no_resuelta_no_opina_sobre_la_sanidad_de_su_dato() -> None:
    (resuelta,) = resolver_estas(posicion("NOEXISTE")).posiciones

    assert resuelta.dato_sano is None


# --- El índice de instrumentos -------------------------------------------------------------------


def test_el_indice_se_arma_por_clave_de_busqueda_y_conserva_el_ticker_de_la_base() -> None:
    indice = indexar_instrumentos(
        [{"ticker": "AL30", "clase_activo": "bono_soberano", "plazo_liquidacion": "2"}]
    )

    assert indice["AL30"].ticker == "AL30"
    assert indice["AL30"].plazo_liquidacion == "2"


def test_una_columna_vacia_de_la_base_llega_como_faltante() -> None:
    indice = indexar_instrumentos(
        [{"ticker": "AL30", "clase_activo": None, "plazo_liquidacion": "  "}]
    )

    assert indice["AL30"].clase_activo is None
    assert indice["AL30"].plazo_liquidacion is None


def test_sin_indice_de_instrumentos_se_resuelve_igual_pero_sin_plazo() -> None:
    """El índice es opcional: la resolución no depende de él para encontrar la especie."""
    cartera = resolver([posicion("AL30")], UNIVERSO)

    (resuelta,) = cartera.posiciones
    assert resuelta.resuelta
    assert resuelta.plazo_liquidacion is None


def test_sin_indice_todo_lo_no_resuelto_dice_que_no_esta_en_el_universo() -> None:
    (resuelta,) = resolver([posicion("GGAL")], UNIVERSO).posiciones

    assert resuelta.motivo is MotivoNoResuelta.NO_ESTA_EN_EL_UNIVERSO


# --- La serialización que viaja por el API -------------------------------------------------------


def test_el_ticker_declarado_y_el_resuelto_viajan_los_dos_lado_a_lado() -> None:
    (resuelta,) = resolver_estas(posicion("  mr46d ")).posiciones

    fila = resuelta.como_dict()
    assert fila["ticker_declarado"] == "  mr46d "
    assert fila["ticker"] == "MR46D"
    assert fila["emision"] == "MR46"
    assert fila["sufijo_liquidacion"] == "D"
    assert fila["plazo_liquidacion"] == "2"
    assert fila["resuelta"] is True
    assert fila["motivo"] is None


def test_la_no_resuelta_viaja_con_su_motivo_descripto_y_sin_ticker_resuelto() -> None:
    fila = resolver_estas(posicion("GGAL")).posiciones[0].como_dict()

    assert fila["resuelta"] is False
    assert fila["ticker"] is None
    assert fila["emision"] is None
    assert fila["motivo"] == "renta_variable"
    assert fila["motivo_descripcion"] is not None
