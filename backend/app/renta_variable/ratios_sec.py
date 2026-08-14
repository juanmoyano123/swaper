"""Los ratios de la ficha SEC, calculados sobre `DatosEjercicio` — lógica de dominio, no de I/O.

Separado de `app/externos/sec_ficha_parser.py` a propósito: aquél extrae hechos crudos con su
período y su unidad; acá se decide qué cuenta contra qué. Mismo criterio que separa
`app/renta_variable/especies.py` de `app/renta_variable/clasificacion.py`.

**Regla de misma unidad (regla 3 del dominio).** Un ratio sólo se computa si numerador y
denominador declaran la MISMA unidad. YPF tiene `Assets` en ARS y en USD conviviendo en el mismo
companyfacts —cambió de moneda funcional en 2020, y las dos series siguen ahí—: dividir una serie
contra la otra daría un número con total confianza y totalmente inventado. Unidades distintas es
ausente, no un error: cada ratio que no se puede calcular así se declara vacío.

**El período de cada ratio es el de `DatosEjercicio.periodo`**, siempre — nunca se recalcula un
período propio por ratio.
"""

from dataclasses import dataclass

from app.externos.sec_ficha_parser import DatosEjercicio, HechoXbrl


@dataclass(frozen=True, slots=True)
class RatioSec:
    """Un ratio o un monto de la ficha SEC. `unidad` es `None` para los adimensionales (ROE,
    márgenes, liquidez, deuda/patrimonio, crecimiento); el EPS es el único que lleva moneda."""

    valor: float
    unidad: str | None
    periodo: str
    """ISO. El `fin` del hecho que originó el ratio — para un cociente, el del numerador."""


@dataclass(frozen=True, slots=True)
class RatiosSec:
    roe: RatioSec | None
    margen_operativo: RatioSec | None
    crecimiento_ingresos: RatioSec | None
    eps: RatioSec | None
    deuda_patrimonio: RatioSec | None
    liquidez_corriente: RatioSec | None


def _dividir(numerador: HechoXbrl | None, denominador: HechoXbrl | None) -> RatioSec | None:
    """El cociente, sólo si los dos existen, tienen la misma unidad y el denominador no es cero.
    Cualquier otra cosa es ausente — nunca una excepción, nunca un número aproximado."""
    if numerador is None or denominador is None:
        return None
    if numerador.unidad != denominador.unidad:
        return None
    if denominador.valor == 0:
        return None
    return RatioSec(valor=numerador.valor / denominador.valor, unidad=None, periodo=numerador.fin)


def calcular_ratios(datos: DatosEjercicio) -> RatiosSec:
    """Los seis ratios del paquete SEC, cada uno independiente: que uno falte no afecta a los
    demás."""
    roe = _dividir(datos.net_income, datos.equity)

    margen_operativo = _dividir(datos.operating_income, datos.revenue)

    crecimiento_ingresos: RatioSec | None = None
    if (
        datos.revenue is not None
        and datos.revenue_anio_anterior is not None
        and datos.revenue.unidad == datos.revenue_anio_anterior.unidad
        and datos.revenue_anio_anterior.valor != 0
    ):
        variacion = (datos.revenue.valor - datos.revenue_anio_anterior.valor) / abs(
            datos.revenue_anio_anterior.valor
        )
        crecimiento_ingresos = RatioSec(valor=variacion, unidad=None, periodo=datos.revenue.fin)

    eps: RatioSec | None = None
    if datos.eps_diluted is not None:
        eps = RatioSec(
            valor=datos.eps_diluted.valor,
            unidad=datos.eps_diluted.unidad,
            periodo=datos.eps_diluted.fin,
        )

    # Deuda de largo plazo (única cuenta de deuda disponible: no hay un "deuda total" uniforme
    # entre empresas, ver el mapa de conceptos del parser) contra el patrimonio.
    deuda_patrimonio = _dividir(datos.long_term_debt, datos.equity)

    liquidez_corriente = _dividir(datos.current_assets, datos.current_liabilities)

    return RatiosSec(
        roe=roe,
        margen_operativo=margen_operativo,
        crecimiento_ingresos=crecimiento_ingresos,
        eps=eps,
        deuda_patrimonio=deuda_patrimonio,
        liquidez_corriente=liquidez_corriente,
    )
