"""GWT-4: el token vencido se distingue de la API caída — F-013.

Las dos dejan al producto sin ese dato y las dos son `error`. Lo que las separa es que una se
arregla regenerando un link a mano y la otra se arregla esperando, y presentarlas iguales haría que
alguien espere sentado algo que no se destraba solo.
"""

from app.estado.fuentes import diagnosticar
from app.ingesta.alertas import credencial_vencida, fuente_caida, respuesta_vacia


def _serializar(*alertas: object) -> list[dict[str, object]]:
    """Las alertas como salen de `corridas_ingesta`, que las guarda en `jsonb`."""
    return [a.como_dict() for a in alertas]  # type: ignore[attr-defined]


class TestDiagnostico:
    def test_separa_credencial_vencida_de_fuente_caida(self) -> None:
        alertas = _serializar(
            credencial_vencida("Docta", "Regenerar el link firmado desde el panel."),
            fuente_caida("BYMA", "timeout tras 5 intentos"),
        )

        diagnostico = diagnosticar(alertas)

        assert diagnostico["hay_credencial_vencida"] is True
        assert diagnostico["hay_fuente_caida"] is True
        assert len(diagnostico["credenciales_vencidas"]) == 1
        assert len(diagnostico["caidas"]) == 1

    def test_una_fuente_caida_no_se_cuenta_como_credencial_vencida(self) -> None:
        """El caso que hace daño: mandar a renovar una credencial que está perfecta."""
        diagnostico = diagnosticar(_serializar(fuente_caida("BYMA", "502 del gateway")))

        assert diagnostico["hay_credencial_vencida"] is False
        assert diagnostico["credenciales_vencidas"] == []

    def test_una_credencial_vencida_no_se_cuenta_como_caida(self) -> None:
        """El caso simétrico: esperar a que se destrabe algo que nadie va a destrabar."""
        diagnostico = diagnosticar(
            _serializar(credencial_vencida("Docta", "Regenerar el link firmado."))
        )

        assert diagnostico["hay_fuente_caida"] is False
        assert diagnostico["caidas"] == []

    def test_la_alerta_de_credencial_conserva_su_accion(self) -> None:
        """El mensaje y la acción viajan tal cual: no se reescriben acá."""
        diagnostico = diagnosticar(
            _serializar(credencial_vencida("Docta", "Regenerar el link firmado desde el panel."))
        )

        [alerta] = diagnostico["credenciales_vencidas"]
        assert alerta["accion_requerida"] == "Regenerar el link firmado desde el panel."

    def test_una_fuente_caida_no_pide_intervencion_por_si_sola(self) -> None:
        """`fuente_caida` no lleva acción: se resuelve sola cuando la fuente vuelva."""
        diagnostico = diagnosticar(_serializar(fuente_caida("BYMA", "timeout")))

        assert diagnostico["requiere_intervencion"] is False

    def test_requiere_intervencion_mira_todas_las_alertas_y_no_solo_las_dos_categorias(
        self,
    ) -> None:
        """Una alerta con acción que no es ninguna de las dos también cuenta.

        Es la pregunta de la barra —"¿hay algo que alguien tenga que hacer hoy?"— y contestarla
        mirando sólo las credenciales dejaría afuera, por ejemplo, un formato de fuente que cambió.
        """
        from app.ingesta.alertas import formato_inesperado

        diagnostico = diagnosticar(_serializar(formato_inesperado("IAMC", "falta la columna TIR")))

        assert diagnostico["requiere_intervencion"] is True
        assert diagnostico["hay_credencial_vencida"] is False
        assert diagnostico["hay_fuente_caida"] is False

    def test_sin_alertas_no_hay_nada_que_diagnosticar(self) -> None:
        diagnostico = diagnosticar([])

        assert diagnostico == {
            "credenciales_vencidas": [],
            "caidas": [],
            "hay_credencial_vencida": False,
            "hay_fuente_caida": False,
            "requiere_intervencion": False,
        }

    def test_las_alertas_que_no_clasifican_no_se_pierden_ni_se_inventan(self) -> None:
        """`respuesta_vacia` es error y no es ninguna de las dos: no entra a ningún montón."""
        diagnostico = diagnosticar(_serializar(respuesta_vacia("Docta", 3)))

        assert diagnostico["credenciales_vencidas"] == []
        assert diagnostico["caidas"] == []
