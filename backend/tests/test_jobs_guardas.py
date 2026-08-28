"""La guarda de panel colapsado: el caso del 28/08/2026, en el que BYMA devolvió 5 filas en
`public-bonds` contra 1.116 del día anterior sin que nada lo declarara.

Son tests de lógica pura —no tocan la base ni la red—: `paneles_colapsados` recibe los dos conteos
ya leídos y decide. Que la corrida los enchufe de verdad se prueba en `test_jobs_corridas.py`.
"""

from app.ingesta.alertas import Severidad
from app.jobs.guardas import (
    CODIGO_PANEL_COLAPSADO,
    claves_de_tramos,
    paneles_colapsados,
)


def test_alerta_cuando_un_panel_trae_menos_de_la_mitad() -> None:
    """El caso medido: 5 filas contra 1.116, con `total_elements_count` de la fuente diciendo 5 —
    o sea, sin nada que `paginacion_incompleta` pueda ver."""
    alertas = paneles_colapsados({"public-bonds": 1116}, {"public-bonds": 5})

    assert len(alertas) == 1
    assert alertas[0].codigo == CODIGO_PANEL_COLAPSADO
    assert alertas[0].severidad is Severidad.ERROR
    assert alertas[0].accion_requerida is None


def test_el_mensaje_nombra_el_endpoint_los_dos_conteos_y_el_porcentaje() -> None:
    """La alerta se lee en la barra de estado sin acceso al detalle: tiene que alcanzar para saber
    qué panel se cayó y cuánto, sin ir a buscar el número a otro lado."""
    (alerta,) = paneles_colapsados({"public-bonds": 1116}, {"public-bonds": 5})

    assert "public-bonds" in alerta.mensaje
    assert "5" in alerta.mensaje
    assert "1116" in alerta.mensaje
    assert "0,4 %" in alerta.mensaje
    assert alerta.detalle == {
        "endpoint": "public-bonds",
        "previas": 1116,
        "obtenidas": 5,
        "umbral": 0.5,
    }


def test_no_alerta_cuando_el_panel_encogio_poco() -> None:
    """Un panel que pierde un tercio de sus filas no es un colapso: la renta variable mueve esa
    magnitud de un día para el otro, y avisar ahí volvería la alerta ruido de fondo."""
    assert paneles_colapsados({"leading-equity": 300}, {"leading-equity": 200}) == []


def test_el_umbral_es_estricto_en_el_borde() -> None:
    """Exactamente la mitad no alerta: el umbral es "menos de", así que un panel que cae justo al
    50 % pasa. Se elige el lado que no avisa para que el borde no genere una alerta por redondeo."""
    assert paneles_colapsados({"cedears": 400}, {"cedears": 200}) == []
    assert len(paneles_colapsados({"cedears": 400}, {"cedears": 199})) == 1


def test_un_panel_en_cero_no_se_alerta_dos_veces() -> None:
    """`ingerir_rueda` ya emite `respuesta_vacia` o `fuente_caida` con el endpoint en el detalle
    cuando un tramo no trae una sola fila. Contarlo también acá duplicaría el mismo hecho."""
    assert paneles_colapsados({"public-bonds": 1116}, {"public-bonds": 0}) == []


def test_un_endpoint_sin_historia_no_alerta() -> None:
    """La primera corrida después del deploy, y cualquier endpoint recién agregado, se estrenan sin
    línea de base. No se inventa una: la comparación empieza a valer en la corrida siguiente."""
    assert paneles_colapsados({}, {"public-bonds": 5}) == []
    assert paneles_colapsados({"public-bonds": 1116}, {"lebacs": 3}) == []


def test_no_alerta_sin_corrida_anterior_que_declare_tramos() -> None:
    """El `{}` que devuelve `tramos_byma_previos` cuando ninguna corrida registró conteos por
    endpoint todavía: la corrida entera pasa sin una sola alerta."""
    actuales = {"public-bonds": 5, "negociable-obligations": 900, "cedears": 3000}

    assert paneles_colapsados({}, actuales) == []


def test_cada_panel_se_compara_contra_si_mismo() -> None:
    """La comparación es panel contra panel y no contra el total de la fuente: el 28/08 las 1.111
    filas que faltaron eran ~10 % de las 5.771 que BYMA trajo en total, y un umbral sobre el
    agregado no las habría visto."""
    previas = {"public-bonds": 1116, "negociable-obligations": 900, "cedears": 3000}
    actuales = {"public-bonds": 5, "negociable-obligations": 890, "cedears": 2900}

    alertas = paneles_colapsados(previas, actuales)

    assert [a.detalle["endpoint"] for a in alertas] == ["public-bonds"]


def test_varios_paneles_caidos_salen_ordenados_por_endpoint() -> None:
    """Orden estable: las alertas se serializan a `corridas_ingesta.alertas` y se comparan entre
    corridas, así que no pueden depender del orden en que la fuente devolvió los tramos."""
    previas = {"public-bonds": 1000, "cedears": 1000, "leading-equity": 1000}
    actuales = {"public-bonds": 1, "cedears": 1, "leading-equity": 1}

    alertas = paneles_colapsados(previas, actuales)

    assert [a.detalle["endpoint"] for a in alertas] == [
        "cedears",
        "leading-equity",
        "public-bonds",
    ]


def test_el_umbral_se_puede_apretar() -> None:
    previas = {"public-bonds": 1000}
    actuales = {"public-bonds": 600}

    assert paneles_colapsados(previas, actuales) == []
    assert len(paneles_colapsados(previas, actuales, umbral=0.9)) == 1


def test_claves_de_tramos_prefija_para_convivir_con_los_agregados() -> None:
    """`filas_por_fuente` es un jsonb plano donde ya viven `byma`, `data912` y `cafci`. El prefijo
    es lo único que separa un panel de una fuente entera, y `byma` a secas no lo lleva."""
    prefijadas = claves_de_tramos({"public-bonds": 1116, "cedears": 3000})

    assert prefijadas == {"byma:public-bonds": 1116, "byma:cedears": 3000}
    assert "byma" not in prefijadas


def test_claves_de_tramos_sin_tramos_no_agrega_nada() -> None:
    assert claves_de_tramos({}) == {}
