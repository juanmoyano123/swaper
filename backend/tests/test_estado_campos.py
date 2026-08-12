"""Cobertura de los campos críticos — F-013.

Lo que se prueba acá es el denominador, que es donde está el error fácil: medir `tipo_tasa` sobre
las especies que ya tienen segmento daría 100 % siempre y taparía exactamente el hueco que la barra
existe para mostrar.
"""

from app.estado.campos import (
    CAMPOS_CRITICOS,
    alertas_de_cobertura,
    como_dict,
    medir_campos_criticos,
)
from app.ingesta.alertas import CODIGO_CAMPO_SIN_COBERTURA, Severidad


def _fila(**campos: object) -> dict[str, object]:
    """Una fila de `resumen` con todos los campos críticos vacíos salvo los que se pidan."""
    base: dict[str, object] = {c.campo: None for c in CAMPOS_CRITICOS}
    base["ticker"] = "TEST"
    base.update(campos)
    return base


def _paridad(ticker: str, valor: object) -> dict[str, object]:
    return {"ticker": ticker, "paridad": valor}


class TestMedicion:
    def test_mide_sobre_el_universo_entero_y_no_sobre_lo_segmentado(self) -> None:
        """El denominador son todas las filas leídas, tengan tipo de tasa o no.

        Es el punto del módulo: dos de estas tres filas no van a llegar nunca al universo
        comparable, y son justamente las que hacen que la cobertura de `tipo_tasa` sea 33 % y no
        100 %.
        """
        filas = [
            _fila(tipo_tasa="hard-dollar"),
            _fila(tipo_tasa=None),
            _fila(tipo_tasa=""),
        ]
        paridades = [_paridad("A", None), _paridad("B", None), _paridad("C", None)]

        medidas = {c.campo: c for c in medir_campos_criticos(filas, paridades)}

        assert medidas["tipo_tasa"].presentes == 1
        assert medidas["tipo_tasa"].total == 3

    def test_la_paridad_se_mide_sobre_sus_propias_filas(self) -> None:
        """`paridad` no viaja en las columnas del universo: la lee F-015 con su propia consulta."""
        filas = [_fila(), _fila(), _fila()]
        paridades = [_paridad("A", 78.5), _paridad("B", None), _paridad("C", 101.2)]

        medidas = {c.campo: c for c in medir_campos_criticos(filas, paridades)}

        assert medidas["paridad"].presentes == 2
        assert medidas["paridad"].total == 3

    def test_devuelve_los_campos_en_el_orden_declarado(self) -> None:
        """El orden es el de la barra y va de lo que rompe más a lo que rompe menos."""
        medidas = medir_campos_criticos([_fila()], [_paridad("A", None)])

        assert [c.campo for c in medidas] == [c.campo for c in CAMPOS_CRITICOS]

    def test_cero_por_ciento_cuando_no_hay_ni_una_fila(self) -> None:
        """Sin universo la cobertura es 0 %, no 100 %: no hay nada que esté completo."""
        medidas = medir_campos_criticos([], [])

        assert all(c.total == 0 and c.porcentaje == 0.0 for c in medidas)


class TestAlertas:
    def test_alerta_el_campo_que_ninguna_fila_trae(self) -> None:
        """Es el caso real de `tna` contra la base: 0 de 2.894, ninguna fuente lo publica."""
        filas = [_fila(tir=0.0725), _fila(tir=0.0810)]

        alertas = alertas_de_cobertura(
            medir_campos_criticos(filas, [_paridad("A", 1), _paridad("B", 1)])
        )

        codigos = {a.codigo for a in alertas}
        assert codigos == {CODIGO_CAMPO_SIN_COBERTURA}
        assert any("tna" in a.mensaje for a in alertas)
        assert all(a.severidad is Severidad.ADVERTENCIA for a in alertas)

    def test_no_alerta_un_campo_con_cobertura_baja_pero_no_nula(self) -> None:
        """Sólo el cero.

        Un campo al 8 % es un campo que alguna fuente publica para algunas especies. Decidir a
        partir de qué porcentaje eso es un problema sería fijar cuánta ceguera es aceptable, que es
        una decisión de dominio que nadie tomó.
        """
        filas = [_fila(law="NY")] + [_fila() for _ in range(99)]

        alertas = alertas_de_cobertura(medir_campos_criticos(filas, []))

        assert not any("ley" in a.mensaje for a in alertas)

    def test_la_alerta_nombra_la_columna_de_la_fuente_en_el_detalle(self) -> None:
        """El mensaje lleva el rótulo legible; el detalle, la columna que hay que ir a buscar."""
        alertas = alertas_de_cobertura(medir_campos_criticos([_fila()], []))

        de_tna = next(a for a in alertas if a.detalle.get("columna") == "tna")
        assert de_tna.detalle["campo"] == "tna"


class TestSerializacion:
    def test_cada_campo_viaja_con_su_porque(self) -> None:
        """El porcentaje solo no dice nada: lo accionable es qué se rompe sin el campo."""
        medida = next(c for c in medir_campos_criticos([_fila()], []) if c.campo == "paridad")

        serializada = como_dict(medida)

        assert serializada["rotulo"] == "Paridad"
        assert "calendario" in str(serializada["por_que"])
        assert serializada["porcentaje"] == 0.0
