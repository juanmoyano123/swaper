"""La matemática de TIR, duración y paridad, sin base y sin red — F-051.

Acá se prueba el número contra su forma cerrada donde la hay (un cupón cero tiene TIR y duración
exactas, no aproximadas) y contra sí mismo donde no la hay: si `resolver_tir` devuelve una tasa,
descontar los flujos a esa tasa tiene que reproducir el precio del que se partió. Esa vuelta es lo
que ata el solver a la definición de TIR y no a lo que el solver crea que es.

**Los casos que más importan son los que no devuelven número**: un precio que ningún descuento
explica sale `None` con su motivo, no sale con la tasa del extremo del bracket.
"""

import csv
import math
from datetime import date
from pathlib import Path

import pytest

from app.calendario.cupones import Pago, indexar_cronograma
from app.calendario.metricas import (
    MAX_ITERACIONES,
    MOTIVO_RESIDUAL_CONTRADICTORIO,
    MOTIVO_SIN_PRECIO_POSITIVO,
    MOTIVO_SIN_RESIDUAL_VIGENTE,
    MOTIVO_TIR_BAJO_PISO,
    MOTIVO_TIR_SOBRE_TECHO,
    MOTIVO_VENCIDA,
    TASA_PISO,
    TASA_TECHO,
    TOLERANCIA_SOLVER,
    anios_entre,
    duracion_macaulay,
    duracion_modificada,
    metricas_de,
    paridad_de,
    resolver_tir,
    valor_presente,
)

HOY = date(2026, 8, 7)

RAIZ_REPO = Path(__file__).resolve().parents[2]
CASHFLOW = RAIZ_REPO / "data" / "output" / "cashflow_completo.csv"


def pago(
    fecha: str, *, capital: float = 0.0, interes: float = 0.0, residual: float = 100.0
) -> Pago:
    return Pago(
        fecha=date.fromisoformat(fecha),
        capital=capital,
        interes=interes,
        total=capital + interes,
        residual=residual,
        emision=date(2024, 1, 15),
    )


def anios_exactos(n: float) -> float:
    """Un plazo de `n` años en la convención del módulo, para armar casos de forma cerrada."""
    return n


class TestValorPresente:
    def test_descuenta_cada_flujo_a_su_plazo(self) -> None:
        assert valor_presente([1.0], [105.0], 0.05) == pytest.approx(100.0)
        assert valor_presente([1.0, 2.0], [10.0, 110.0], 0.10) == pytest.approx(100.0)

    def test_a_tasa_cero_es_la_suma_de_los_flujos(self) -> None:
        assert valor_presente([0.5, 3.2], [7.0, 107.0], 0.0) == pytest.approx(114.0)


class TestResolverTir:
    def test_cupon_cero_devuelve_la_tasa_de_su_forma_cerrada(self) -> None:
        # 100 a dos años, comprado a 100/(1,05)^2: la TIR es 5 % por definición.
        precio = 100.0 / 1.05**2
        assert resolver_tir([anios_exactos(2)], [100.0], precio) == pytest.approx(
            1e-9 + 0.05, abs=1e-8
        )

    def test_un_bono_a_la_par_rinde_su_cupon(self) -> None:
        t = [anios_exactos(1), anios_exactos(2), anios_exactos(3)]
        cf = [8.0, 8.0, 108.0]
        assert resolver_tir(t, cf, 100.0) == pytest.approx(0.08, abs=1e-8)

    def test_el_valor_presente_a_la_tir_reproduce_el_precio(self) -> None:
        """La vuelta que ata el solver a la definición: VP(flujos, TIR) == precio.

        La tolerancia es de un millonésimo de punto de precio, no del orden del solver: el corte
        del solver es sobre la *tasa*, y una tasa a 5e-11 mueve el precio de un bono largo unas
        décimas de milmillonésimo. Pedir 1e-8 acá sería pedirle al solver una precisión que su
        propio criterio de corte no promete.
        """
        t = [0.4, 1.1, 2.6, 4.9]
        cf = [3.5, 3.5, 3.5, 103.5]
        for precio in (65.0, 88.0, 100.0, 131.5):
            tir = resolver_tir(t, cf, precio)
            assert tir is not None
            assert valor_presente(t, cf, tir) == pytest.approx(precio, abs=1e-6)

    def test_un_precio_mas_alto_rinde_menos(self) -> None:
        t, cf = [1.0, 2.0], [6.0, 106.0]
        caro = resolver_tir(t, cf, 110.0)
        barato = resolver_tir(t, cf, 90.0)
        assert caro is not None and barato is not None
        assert caro < barato

    def test_es_deterministico_bit_a_bit(self) -> None:
        """Regla 6: dos corridas sobre el mismo insumo dan el mismo número, no uno parecido."""
        t, cf = [0.7, 1.9, 3.4], [5.0, 5.0, 105.0]
        assert resolver_tir(t, cf, 92.3) == resolver_tir(t, cf, 92.3)

    def test_sin_flujos_futuros_no_hay_tir(self) -> None:
        assert resolver_tir([], [], 100.0) is None

    def test_un_precio_que_ningun_descuento_explica_no_devuelve_tasa(self) -> None:
        """El bracket es ancho a propósito: pagar 500 por un flujo de 100 a dos años **sí** tiene
        TIR —muy negativa, pero real— y se reporta. Lo que no tiene solución es un precio que ni
        siquiera el piso del descuento alcanza: a medio año, el valor presente al piso es ~1017."""
        assert resolver_tir([anios_exactos(2)], [100.0], 500.0) is not None
        assert resolver_tir([0.5037], [100.0], 5_000.0) is None


class TestDuracion:
    def test_la_macaulay_de_un_cupon_cero_es_su_plazo(self) -> None:
        assert duracion_macaulay([anios_exactos(3)], [100.0], 0.07) == pytest.approx(3.0)

    def test_la_modificada_es_la_macaulay_sobre_uno_mas_la_tasa(self) -> None:
        t, cf, tasa = [1.0, 2.0, 3.0], [9.0, 9.0, 109.0], 0.09
        macaulay = duracion_macaulay(t, cf, tasa)
        assert macaulay is not None
        assert duracion_modificada(t, cf, tasa) == pytest.approx(macaulay / 1.09)

    def test_un_bono_que_amortiza_antes_dura_menos(self) -> None:
        t = [1.0, 2.0, 3.0]
        bullet = duracion_macaulay(t, [5.0, 5.0, 105.0], 0.05)
        amortizing = duracion_macaulay(t, [38.3, 36.6, 35.0], 0.05)
        assert bullet is not None and amortizing is not None
        assert amortizing < bullet


class TestParidad:
    def test_es_el_precio_sobre_el_valor_tecnico(self) -> None:
        assert paridad_de(88.07, 100.0) == pytest.approx(0.8807)

    def test_sin_valor_tecnico_no_hay_paridad(self) -> None:
        assert paridad_de(88.07, None) is None
        assert paridad_de(88.07, 0.0) is None


class TestMetricasDe:
    def test_calcula_las_tres_sobre_un_cronograma_completo(self) -> None:
        pagos = [
            pago("2025-07-09", interes=0.5, residual=100.0),
            pago("2027-01-09", interes=1.5, residual=100.0),
            pago("2028-01-09", capital=100.0, interes=1.5, residual=0.0),
        ]
        m = metricas_de(pagos, precio_sucio=85.0, hoy=HOY)
        assert m.motivo is None
        assert m.tir is not None and m.duration is not None and m.paridad is not None
        assert m.duration < 2.0  # el último pago está a menos de dos años

    def test_un_bono_vencido_no_reporta_nada_y_dice_por_que(self) -> None:
        pagos = [pago("2025-01-09", capital=100.0, interes=2.0, residual=0.0)]
        m = metricas_de(pagos, precio_sucio=99.0, hoy=HOY)
        assert (m.tir, m.duration, m.paridad) == (None, None, None)
        assert m.motivo == MOTIVO_VENCIDA

    def test_sin_cronograma_no_reporta_nada(self) -> None:
        m = metricas_de([], precio_sucio=99.0, hoy=HOY)
        assert m.motivo == MOTIVO_VENCIDA and m.tir is None

    def test_la_paridad_se_reporta_aunque_la_tir_no_resuelva(self) -> None:
        """Son magnitudes independientes: vaciar la que sí se pudo calcular sería perder dato."""
        pagos = [pago("2027-02-07", capital=100.0, interes=1.0, residual=0.0)]
        m = metricas_de(pagos, precio_sucio=5_000.0, hoy=HOY)
        assert m.tir is None
        assert m.motivo == MOTIVO_TIR_BAJO_PISO
        assert m.paridad is not None and m.paridad > 1

    def test_un_precio_irrisorio_cae_del_otro_lado_del_bracket(self) -> None:
        pagos = [pago("2027-02-07", capital=100.0, interes=1.0, residual=0.0)]
        m = metricas_de(pagos, precio_sucio=1.0, hoy=HOY)
        assert m.tir is None and m.motivo == MOTIVO_TIR_SOBRE_TECHO

    def test_un_precio_de_cero_no_es_un_precio(self) -> None:
        pagos = [pago("2028-01-09", capital=100.0, interes=1.0, residual=0.0)]
        assert metricas_de(pagos, precio_sucio=0.0, hoy=HOY).tir is None


class TestCadaMotivoNombraLoQuePaso:
    """Hasta el 26/08/2026 tres situaciones distintas salían las tres como `vencida`.

    Sólo una es un vencimiento. Las otras dos mandaban a buscar el problema al lugar equivocado:
    quien lee "vencida" va a mirar la fecha de la emisión, no el precio del día ni el residual del
    cronograma, que es donde estaba.
    """

    def test_un_bono_vivo_sin_precio_no_esta_vencido(self) -> None:
        pagos = [pago("2028-01-09", capital=100.0, interes=1.0, residual=0.0)]
        m = metricas_de(pagos, precio_sucio=0.0, hoy=HOY)
        assert m.motivo == MOTIVO_SIN_PRECIO_POSITIVO

    def test_un_precio_negativo_cae_en_el_mismo_motivo(self) -> None:
        pagos = [pago("2028-01-09", capital=100.0, interes=1.0, residual=0.0)]
        assert metricas_de(pagos, -1.0, HOY).motivo == MOTIVO_SIN_PRECIO_POSITIVO

    def test_un_residual_que_no_cierra_contra_lo_amortizado_se_nombra_aparte(self) -> None:
        """La fuente dejó el residual clavado en 100 mientras el bono amortizaba: el pago pasado
        se llevó 50 de capital y el residual que declara sigue diciendo 100."""
        pagos = [
            pago("2026-01-09", capital=50.0, interes=2.0, residual=100.0),
            pago("2028-01-09", capital=50.0, interes=1.0, residual=0.0),
        ]
        m = metricas_de(pagos, precio_sucio=60.0, hoy=HOY)
        assert m.motivo == MOTIVO_RESIDUAL_CONTRADICTORIO
        assert m.tir is None

    def test_un_residual_ya_agotado_con_pagos_futuros_tampoco_es_un_vencimiento(self) -> None:
        """El cronograma sigue proyectando un pago, pero el residual que declara está en cero.
        No hay valor técnico contra el cual medir, y el bono no venció: le falta el dato."""
        pagos = [
            pago("2026-01-09", capital=100.0, interes=2.0, residual=0.0),
            pago("2028-01-09", capital=0.0, interes=1.0, residual=0.0),
        ]
        assert metricas_de(pagos, 60.0, HOY).motivo == MOTIVO_SIN_RESIDUAL_VIGENTE


class TestElTechoNoDecideQueRendimientoEsCreible:
    """El bracket superior era 10.0 (1000 % EA) y cortaba aritmética válida (26/08/2026).

    El antecedente medido está en `docs/ESTADO.md:194`: SNSBO rindiendo 245 % es dato correcto.
    Esa misma cuenta con plazos más cortos se pasa del 1000 % sin dejar de ser exacta, y el solver
    la devolvía vacía. Quien filtra por plausibilidad es la capa de sanidad por segmento
    (`app/universo/sanidad.py`), que **rotula** en vez de vaciar.
    """

    @staticmethod
    def bono_corto_muy_barato() -> list[Pago]:
        """Cupón cero a 60 días al 61 % de su valor técnico: TIR ≈ 1900 % EA.

        Cae justo entre el techo viejo (1000 %) y el nuevo (10.000 %), que es el rango que el
        cambio recupera.
        """
        return [pago("2026-10-06", capital=100.0, interes=0.0, residual=100.0)]

    def test_un_bono_corto_y_barato_ahora_resuelve(self) -> None:
        m = metricas_de(self.bono_corto_muy_barato(), precio_sucio=61.0, hoy=HOY)
        assert m.motivo is None
        assert m.tir is not None and m.tir > 10.0, "por encima del techo viejo"

    def test_y_el_numero_reproduce_el_precio_del_que_se_partio(self) -> None:
        """La vuelta que ata el solver a la definición de TIR: descontar a la tasa devuelta tiene
        que dar el precio, no algo parecido."""
        pagos = self.bono_corto_muy_barato()
        m = metricas_de(pagos, precio_sucio=61.0, hoy=HOY)
        assert m.tir is not None
        t = [anios_entre(HOY, p.fecha) for p in pagos]
        assert valor_presente(t, [p.total for p in pagos], m.tir) == pytest.approx(61.0)

    def test_por_encima_del_techo_nuevo_se_sigue_declarando_sin_numero(self) -> None:
        """El techo se movió, no se sacó: un precio que ningún descuento razonable explica sigue
        saliendo con su motivo en vez de con la tasa del extremo."""
        pagos = [pago("2026-08-27", capital=100.0, interes=0.0, residual=100.0)]
        assert metricas_de(pagos, 1.0, HOY).motivo == MOTIVO_TIR_SOBRE_TECHO

    def test_las_iteraciones_alcanzan_para_el_bracket_mas_ancho(self) -> None:
        """La bisección parte el intervalo al medio, así que necesita n con
        `(techo - piso) / 2**n < TOLERANCIA_SOLVER`. Con el bracket nuevo son 40; con el viejo
        eran 37. El tope de 200 sobra, y este test es lo que avisa si alguien lo baja."""
        ancho = TASA_TECHO - TASA_PISO
        necesarias = math.ceil(math.log2(ancho / TOLERANCIA_SOLVER))
        assert necesarias == 40
        assert necesarias < MAX_ITERACIONES


class TestContraElCronogramaReal:
    """La vuelta completa sobre un bono de verdad, con el cronograma versionado del repo.

    Los casos de arriba usan flujos armados a mano, que son limpios por construcción. Éste corre
    sobre AL30 —amortizing, con residual decreciente y cupones crecientes— que es la forma que
    rompe los atajos: si alguien reemplazara el residual vivo por 100 fijo, acá se nota.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def pagos_al30() -> list[Pago]:
        """AL30 del CSV versionado, con los tipos que tendría viniendo de la base.

        La conversión de fechas la hace el test y no `indexar_cronograma`, que rechaza cadenas a
        propósito: interpretar texto abriría la puerta a confundir `10/03/2030` entre marzo y
        octubre. Acá el formato es ISO y la conversión es explícita.
        """
        if not CASHFLOW.exists():
            pytest.skip("falta data/output/cashflow_completo.csv")
        with CASHFLOW.open(encoding="utf-8") as fuente:
            filas = [
                {
                    **f,
                    "payment_date": date.fromisoformat(f["payment_date"]),
                    "issue_date": date.fromisoformat(f["issue_date"]),
                    "capital": float(f["capital"]),
                    "interest_amount": float(f["interest_amount"]),
                    "residual_value": float(f["residual_value"]),
                    "cash_flow": float(f["cash_flow"]),
                }
                for f in csv.DictReader(fuente)
                if f["ticker"] == "AL30"
            ]
        if not filas:
            pytest.skip("el cronograma versionado no tiene AL30")
        return indexar_cronograma(filas).pagos_de("AL30")

    # Precio compatible con la paridad 0,8807 que `test_calendario_paridad_motor.py` verifica para
    # AL30 contra el motor: al 07/08/2026 su valor técnico es 64,04, así que ~56,4 es el precio
    # sucio que corresponde. Un número por encima del valor técnico daría paridad mayor a 1, que
    # para AL30 no es un escenario de mercado sino un error de convención.
    PRECIO_AL30 = 56.35

    def test_el_valor_presente_a_la_tir_reproduce_el_precio(self, pagos_al30: list[Pago]) -> None:
        m = metricas_de(pagos_al30, precio_sucio=self.PRECIO_AL30, hoy=HOY)
        assert m.tir is not None, "AL30 tiene cronograma y precio: tiene que resolver"
        futuros = [p for p in pagos_al30 if p.fecha > HOY]
        t = [anios_entre(HOY, p.fecha) for p in futuros]
        cf = [p.total for p in futuros]
        assert valor_presente(t, cf, m.tir) == pytest.approx(self.PRECIO_AL30, abs=1e-6)

    def test_la_tir_sale_en_fraccion_y_en_un_orden_de_magnitud_creible(
        self, pagos_al30: list[Pago]
    ) -> None:
        """Atrapa el error de unidades: una TIR de 7,69 en vez de 0,0769 pasa el round-trip
        —es consistente consigo misma— pero es cien veces la tasa y llegaría así a la pantalla."""
        m = metricas_de(pagos_al30, precio_sucio=self.PRECIO_AL30, hoy=HOY)
        assert m.tir is not None
        assert 0.0 < m.tir < 0.5
        assert m.paridad is not None and 0.5 < m.paridad < 1.0

    def test_la_duracion_no_supera_el_plazo_al_ultimo_pago(self, pagos_al30: list[Pago]) -> None:
        m = metricas_de(pagos_al30, precio_sucio=self.PRECIO_AL30, hoy=HOY)
        assert m.duration_macaulay is not None
        ultimo = max(p.fecha for p in pagos_al30 if p.fecha > HOY)
        assert 0 < m.duration_macaulay <= anios_entre(HOY, ultimo)

    def test_comprar_mas_barato_rinde_mas(self, pagos_al30: list[Pago]) -> None:
        caro = metricas_de(pagos_al30, precio_sucio=56.0, hoy=HOY)
        barato = metricas_de(pagos_al30, precio_sucio=45.0, hoy=HOY)
        assert caro.tir is not None and barato.tir is not None
        assert barato.tir > caro.tir


class TestConvencionDeAnios:
    def test_usa_la_base_del_motor(self) -> None:
        assert anios_entre(date(2026, 1, 1), date(2027, 1, 1)) == pytest.approx(365 / 365.25)

    def test_una_fecha_pasada_da_plazo_negativo(self) -> None:
        assert anios_entre(date(2026, 8, 7), date(2026, 2, 7)) < 0
