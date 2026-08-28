"""Las guardas de candidatos del armador — Fase 4 (28/08/2026).

Hasta acá el único corte de liquidez del armado era el percentil de `candidatos_del_segmento`, que
no es un piso absoluto: se calcula sobre los volúmenes de los candidatos que ya pasaron los filtros
previos, así que con un conjunto candidato de poco volumen el corte baja con él. Con los 1.339
instrumentos que entraron el 27/08/2026 —casi todos sin rueda, porque se empezó a pedir el panel
completo de BYMA— el armador podía proponer un papel que no operó.

`aplicar_guardas_de_candidatos` agrega dos cortes que no dependen de con quién compitió cada
especie: sin precio del día no se propone, y sin emisor identificado tampoco. Lo que se prueba acá
es que descartan lo que tienen que descartar, que **lo declaran** (regla 1: conteo, motivo y
muestra de tickers) y que no tocan una corrida donde no falta nada.

Sin base de datos: `armar()` es pura sobre `EspecieUniverso`/`RiesgoDeEspecie` construidos a mano,
mismo criterio que `test_armado_min_sectores.py`.
"""

from datetime import datetime

from app.armado.motor import (
    CODIGO_CANDIDATOS_SIN_EMISOR,
    CODIGO_CANDIDATOS_SIN_PRECIO_DEL_DIA,
    MUESTRA_ALERTA,
    aplicar_guardas_de_candidatos,
    armar,
)
from app.armado.parametros import ParametrosArmado
from app.armado.renta_variable import CODIGO_RV_SIN_PRECIO, armar_renta_variable
from app.concentracion.perfiles import PERFILES
from app.concentracion.riesgo import RiesgoDeEspecie
from app.ingesta.alertas import Severidad
from app.renta_variable.especies import EspecieRentaVariable
from app.universo.segmentacion import EspecieUniverso

MONTO = 100_000.0

# Dos corridas del mismo día: el refresh corre cada 15 minutos, así que la antigüedad se mide con
# precisión de instante y no de fecha (ver `_fechahora` en `app/universo/segmentacion.py`).
HOY = datetime(2026, 8, 28, 17, 30)
AYER = datetime(2026, 8, 27, 17, 30)


def _especie(
    ticker: str,
    *,
    rendimiento: float = 0.08,
    emisor: str | None = "Emisor S.A.",
    precio: float | None = 100.0,
    capturado_en: datetime | None = HOY,
    clase_activo: str = "on_corporativo",
    sector: str | None = "O&G",
) -> EspecieUniverso:
    return EspecieUniverso(
        ticker=ticker,
        raiz=ticker,
        clase_activo=clase_activo,
        segmento="usd_hard",
        rendimiento=rendimiento,
        duracion=3.0,
        precio=precio,
        emisor=emisor,
        sector=sector,
        capturado_en=capturado_en,
    )


def _riesgo(especie: EspecieUniverso) -> RiesgoDeEspecie:
    es_soberano = especie.clase_activo == "bono_soberano"
    grupo = especie.ticker[:3]
    return RiesgoDeEspecie(
        ticker=especie.ticker,
        grupo_emisor=grupo,
        es_soberano=es_soberano,
        clave_riesgo="SOBERANO_AR" if es_soberano else grupo,
        nombre="Riesgo soberano argentino" if es_soberano else f"Emisor {grupo}",
    )


def _armar(especies: list[EspecieUniverso], *, n_total: int = 15):
    riesgos = {e.ticker: _riesgo(e) for e in especies}
    params = ParametrosArmado(monto=MONTO, mix={"usd_hard": 100}, n_total=n_total)
    return armar(
        especies, {"usd_hard": 100}, PERFILES["conservador"], "conservador", params, riesgos
    )


def _alerta(resultado, codigo: str):
    return next((a for a in resultado.alertas if a.codigo == codigo), None)


def test_no_se_propone_una_especie_sin_emisor_y_se_declara_cuantas_quedaron_afuera() -> None:
    especies = [
        _especie("T1CO", emisor="Pampa Energía"),
        _especie("T2CO", emisor=None),
        _especie("T3CO", emisor=None),
    ]

    resultado = _armar(especies)

    assert [p.ticker for p in resultado.posiciones] == ["T1CO"]
    alerta = _alerta(resultado, CODIGO_CANDIDATOS_SIN_EMISOR)
    assert alerta is not None
    assert alerta.severidad is Severidad.ADVERTENCIA
    assert alerta.accion_requerida is None  # informa, no bloquea
    assert alerta.detalle["cantidad"] == 2
    assert "2 instrumento(s)" in alerta.mensaje


def test_la_alerta_nombra_una_muestra_de_tickers_y_resume_el_resto() -> None:
    """Regla 1: el faltante se declara con nombre y apellido. Con más de `MUESTRA_ALERTA` casos se
    nombran los primeros en orden alfabético y se dice cuántos más hay — una alerta que lista mil
    tickers no la lee nadie, pero una que no nombra ninguno no se puede verificar."""
    sin_emisor = [_especie(f"S{i}CO", emisor=None) for i in range(MUESTRA_ALERTA + 3)]

    resultado = _armar([_especie("T1CO"), *sin_emisor])

    alerta = _alerta(resultado, CODIGO_CANDIDATOS_SIN_EMISOR)
    assert alerta is not None
    assert "S0CO" in alerta.mensaje
    assert "y 3 más" in alerta.mensaje
    # El detalle lleva la lista entera, aunque el mensaje resuma: quien audita no depende del texto.
    assert alerta.detalle["tickers"] == sorted(e.ticker for e in sin_emisor)


def test_los_soberanos_no_caen_por_la_guarda_de_emisor() -> None:
    """La corrida de consolidación le escribe siempre su emisor al soberano (asigna `underlying`
    para `bono_soberano`), así que la guarda alcanza a ONs y subsoberanos sin emisor escrito y
    nunca al Tesoro. Sin esto, un armado hard-dollar se quedaría sin su segmento más líquido."""
    especies = [
        _especie("AL30", clase_activo="bono_soberano", emisor="Tesoro Nacional", sector="Soberano"),
        _especie("GD30", clase_activo="bono_soberano", emisor="Tesoro Nacional", sector="Soberano"),
    ]

    resultado = _armar(especies)

    assert sorted(p.ticker for p in resultado.posiciones) == ["AL30", "GD30"]
    assert _alerta(resultado, CODIGO_CANDIDATOS_SIN_EMISOR) is None


def test_no_se_propone_una_huerfana_aunque_tenga_precio_publicado() -> None:
    """Una especie que dejó de cotizar conserva su última fila para siempre —la poda de precios es
    por-ticker— y la vista la sirve sin marca de antigüedad. Su precio existe pero es de otra rueda,
    así que valuar una posición con él sería mostrar un dato viejo como si fuera de hoy."""
    especies = [
        _especie("T1CO", capturado_en=HOY),
        _especie("T2CO", capturado_en=AYER),
        _especie("T3CO", precio=None),
    ]

    resultado = _armar(especies)

    assert [p.ticker for p in resultado.posiciones] == ["T1CO"]
    alerta = _alerta(resultado, CODIGO_CANDIDATOS_SIN_PRECIO_DEL_DIA)
    assert alerta is not None
    assert alerta.detalle["tickers"] == ["T2CO", "T3CO"]


def test_una_corrida_donde_no_falta_nada_no_se_altera() -> None:
    """La guarda no puede ser un impuesto sobre el caso sano: con todo el universo de la última
    corrida y con emisor, no descarta a nadie ni agrega ninguna alerta."""
    especies = [_especie(f"T{i}CO", rendimiento=0.07 + i * 0.001) for i in range(3)]

    candidatos, alertas = aplicar_guardas_de_candidatos(especies)

    assert candidatos == especies
    assert alertas == []


def test_una_especie_sin_precio_y_sin_emisor_se_cuenta_una_sola_vez() -> None:
    """Las guardas van en cascada: la alerta dice por qué no entró, no todas las razones por las que
    podría no haber entrado."""
    especies = [_especie("T1CO"), _especie("T2CO", precio=None, emisor=None)]

    candidatos, alertas = aplicar_guardas_de_candidatos(especies)

    assert [e.ticker for e in candidatos] == ["T1CO"]
    assert [a.codigo for a in alertas] == [CODIGO_CANDIDATOS_SIN_PRECIO_DEL_DIA]


def test_sin_capturado_en_no_se_declara_huerfana_a_nadie() -> None:
    """Misma definición que `Segmentacion.huerfanas`: sin instante de captura no hay contra qué
    comparar, y suponer que una fila sin fecha es vieja sería inventar el dato (regla 1). Es el caso
    de cualquier corrida anterior a la migración que expuso `capturado_en` en la vista."""
    especies = [_especie("T1CO", capturado_en=None), _especie("T2CO", capturado_en=None)]

    candidatos, alertas = aplicar_guardas_de_candidatos(especies)

    assert len(candidatos) == 2
    assert alertas == []


def _accion(ticker: str, *, precio: float | None) -> EspecieRentaVariable:
    return EspecieRentaVariable(
        ticker=ticker,
        clase_activo="cedear",
        precio=precio,
        moneda_cotizacion="ARS",
        cierre_anterior=None,
        variacion=None,
        volumen=1_000_000.0,
        volumen_usd=1_000.0,
        px_bid=None,
        px_ask=None,
        operaciones=10,
    )


def test_renta_variable_tampoco_propone_lo_que_no_tiene_precio() -> None:
    """La contraparte de la guarda de precio para el otro universo. La de emisor **no** aplica acá y
    no es un olvido: una acción o un CEDEAR es su propio emisor."""
    especies = [_accion("AAPL", precio=25_000.0), _accion("MSFT", precio=None)]

    posiciones, alertas = armar_renta_variable(
        especies, pct_rv=20.0, n_rv=2, monto_total=MONTO, rubro_rv=None
    )

    assert [p.ticker for p in posiciones] == ["AAPL"]
    alerta = next(a for a in alertas if a.codigo == CODIGO_RV_SIN_PRECIO)
    assert alerta.detalle["cantidad"] == 1
    assert alerta.accion_requerida is None
