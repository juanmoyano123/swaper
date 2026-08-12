"""El endpoint que alimenta la barra — F-013.

Verifica el contrato que el frontend valida con zod: que los campos estén, que se llamen así y que
la barra pueda dibujarse con lo que llega. Lo que decide cada número se prueba en
`test_estado_servicio.py`; acá lo que importa es la forma.
"""

from typing import Any

from fastapi import FastAPI

from app.ingesta.alertas import credencial_vencida, fuente_caida
from tests.conftest import cliente
from tests.test_estado_servicio import FakeConexionEstado, fila_corrida, fila_universo

RUTA = "/api/v1/estado-del-dato"


async def _pedir(app: FastAPI) -> Any:
    async with cliente(app) as http:
        return await http.get(RUTA)


class TestContrato:
    async def test_devuelve_las_secciones_que_la_barra_dibuja(self, crear_app: Any) -> None:
        respuesta = await _pedir(crear_app(FakeConexionEstado(corrida=fila_corrida())))

        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert set(cuerpo) == {
            "consultado_en",
            "dato",
            "corrida",
            "fuentes",
            "universo",
            "descartes",
            "cobertura",
            "tipo_de_cambio",
            "calendario",
            "alertas",
            "resumen",
            "costo",
        }

    async def test_la_hora_del_dato_viene_con_su_demora(self, crear_app: Any) -> None:
        """GWT-2 en el contrato: las tres horas viajan con nombres distintos."""
        respuesta = await _pedir(crear_app(FakeConexionEstado(corrida=fila_corrida())))

        dato = respuesta.json()["dato"]
        assert set(dato) == {
            "capturado_en",
            "dato_valido_hasta",
            "antiguedad_minutos",
            "demora",
        }
        assert dato["demora"]["minutos"] == 20

    async def test_cada_campo_de_cobertura_llega_con_su_rotulo_y_su_porque(
        self, crear_app: Any
    ) -> None:
        """El porcentaje sin el porqué es la métrica decorativa que esto no tiene que ser."""
        respuesta = await _pedir(crear_app(FakeConexionEstado()))

        cobertura = respuesta.json()["cobertura"]
        assert cobertura
        assert all({"campo", "rotulo", "por_que", "porcentaje"} <= set(c) for c in cobertura)

    async def test_las_alertas_llegan_con_todos_sus_campos(self, crear_app: Any) -> None:
        """El frontend valida la forma con zod: un campo ausente rompe la barra entera."""
        conn = FakeConexionEstado(
            corrida=fila_corrida(alertas=[credencial_vencida("Docta", "Regenerar el link.")])
        )

        respuesta = await _pedir(crear_app(conn))

        alertas = respuesta.json()["alertas"]
        assert alertas
        for alerta in alertas:
            assert set(alerta) == {
                "codigo",
                "mensaje",
                "severidad",
                "accion_requerida",
                "detalle",
                "origen",
            }

    async def test_el_detalle_de_los_descartes_trae_lo_que_el_desplegable_muestra(
        self, crear_app: Any
    ) -> None:
        """GWT-3: ticker, motivo y el valor que lo disparó."""
        conn = FakeConexionEstado(
            universo=[
                fila_universo(ticker="VSCQO", tir=0.0675),
                fila_universo(ticker="VSCQD", tir=346_279.17),
            ]
        )

        respuesta = await _pedir(crear_app(conn))

        descartes = respuesta.json()["descartes"]
        assert descartes["total"] == 1
        assert {"ticker", "motivo", "rendimiento", "umbral"} <= set(descartes["items"][0])


class TestSituaciones:
    async def test_distingue_credencial_vencida_de_fuente_caida(self, crear_app: Any) -> None:
        """GWT-4 en la respuesta: los dos montones llegan separados a la pantalla."""
        conn = FakeConexionEstado(
            corrida=fila_corrida(
                alertas=[
                    credencial_vencida("Docta", "Regenerar el link firmado."),
                    fuente_caida("BYMA", "timeout"),
                ]
            )
        )

        cuerpo = (await _pedir(crear_app(conn))).json()

        assert cuerpo["fuentes"]["hay_credencial_vencida"] is True
        assert cuerpo["fuentes"]["hay_fuente_caida"] is True
        assert cuerpo["resumen"]["requiere_intervencion"] is True

    async def test_sin_base_de_datos_contesta_503(self, crear_app: Any) -> None:
        """La barra no puede inventar un estado del dato cuando no puede leer el dato."""
        respuesta = await _pedir(crear_app(None))

        assert respuesta.status_code == 503

    async def test_la_segunda_consulta_sale_del_cache_de_la_aplicacion(
        self, crear_app: Any
    ) -> None:
        """El caché vive en `app.state`: dos requests a la misma app lo comparten."""
        conn = FakeConexionEstado(corrida=fila_corrida())
        app = crear_app(conn)

        primera = (await _pedir(app)).json()
        segunda = (await _pedir(app)).json()

        assert primera["costo"]["desde_cache"] is False
        assert segunda["costo"]["desde_cache"] is True
        assert conn.veces("universo") == 1

    async def test_dos_aplicaciones_no_comparten_el_cache(self, crear_app: Any) -> None:
        """Sin esto, un test decidiría el resultado del siguiente."""
        conn = FakeConexionEstado(corrida=fila_corrida())

        await _pedir(crear_app(conn))
        segunda = (await _pedir(crear_app(conn))).json()

        assert segunda["costo"]["desde_cache"] is False
