"""El armado en sí: port de `resolver_mix`, `candidatos_del_segmento`, `elegir_siguiente` y `armar`
de `tools/armar_cartera.py`, más el criterio de reparto sectorial que agrega F-019 (alcance
ampliado 08/2026).

## Qué asume `universo` en estas funciones

Las cuatro reciben `universo` ya **colapsado por emisión** (una fila por emisión, no una por
especie de liquidación) y **operable** (rendimiento y precio publicados, sin descarte de sanidad).
Es responsabilidad del llamador (`app/api/v1/armado.py`) armarlo así — ver el docstring de ese
módulo para el porqué: el motor arma con `dedup=True` porque comprar dos especies de la misma
emisión es comprar el mismo bono creyendo que se diversifica, y `UniversoDeduplicado.colapsado()`
es, en palabras de su propio docstring, "la vista del armador".

## El desempate por calendario no se portó

`tools/armar_cartera.py::elegir_siguiente` prefiere, dentro de la banda de rendimiento, al
candidato que suma un mes de cobro todavía sin cubrir. Acá no se implementa: ningún GWT de F-019 lo
prueba, y traerlo exige dos lecturas más de la base por request (cronograma y paridades, vía
`app.calendario.grilla.armar_calendario`) que no se justifican sin un criterio de aceptación que
las pida. El plan de la feature declara esto como aceptable ("es la parte con más margen para
simplificar si hace falta") a condición de declararlo, y así queda declarado acá y en el reporte de
la feature. El desempate que sí queda es sector nuevo → mejor rendimiento.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.armado.constantes import BANDA_RENDIMIENTO, HORIZONTES, MIX_COBERTURA
from app.armado.parametros import ParametrosArmado
from app.concentracion.alertas import (
    concentracion_emisor,
    concentracion_sector,
    concentracion_soberana,
    diversificacion_insuficiente,
)
from app.concentracion.perfiles import TOLERANCIA_TOPE, Perfil, sector_computable
from app.concentracion.riesgo import RiesgoDeEspecie
from app.ingesta.alertas import Alerta, Severidad
from app.universo.segmentacion import MONEDA_SEGMENTO, EspecieUniverso

CODIGO_MIX_NORMALIZADO = "mix_normalizado"
CODIGO_MIX_SIN_MONEDA = "mix_sin_segmentos_en_moneda"
CODIGO_SEGMENTO_SIN_CANDIDATOS = "segmento_sin_candidatos"
CODIGO_SEGMENTO_SIN_CUPO = "segmento_sin_cupo_por_concentracion"
CODIGO_SEGMENTO_INCOMPLETO = "segmento_incompleto"
CODIGO_CARTERA_RESCALADA = "cartera_rescalada_a_100"
CODIGO_CANDIDATOS_SIN_PRECIO_DEL_DIA = "candidatos_sin_precio_del_dia"
CODIGO_CANDIDATOS_SIN_EMISOR = "candidatos_sin_emisor"

# Cuántos tickers se nombran en el mensaje de una alerta antes de resumir el resto. Mismo criterio y
# mismo número que `ingesta/consolidacion/metricas.py`, `calendario/alertas.py` y `universo/
# cambio.py`: cada módulo se lo declara, porque una alerta que lista 1.300 tickers no se lee.
MUESTRA_ALERTA = 6


def _alerta(codigo: str, mensaje: str, **detalle: object) -> Alerta:
    """Toda alerta de este módulo informa y no bloquea, igual que las de F-020: `accion_requerida`
    siempre `None` porque no hay nada que una persona tenga que hacer a mano para destrabar esto."""
    return Alerta(
        codigo=codigo,
        mensaje=mensaje,
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle=detalle,
    )


def _muestra(tickers: Sequence[str]) -> str:
    """Los primeros tickers en orden alfabético y cuántos quedaron sin nombrar — mismo criterio que
    `app.ingesta.consolidacion.metricas._muestra`, para que todas las alertas del proyecto declaren
    un faltante grande de la misma forma."""
    visibles = ", ".join(sorted(tickers)[:MUESTRA_ALERTA])
    resto = len(tickers) - MUESTRA_ALERTA
    return f"{visibles} y {resto} más" if resto > 0 else visibles


def aplicar_guardas_de_candidatos(
    universo: Sequence[EspecieUniverso],
) -> tuple[list[EspecieUniverso], list[Alerta]]:
    """Lo que el armador puede proponer, y la declaración de lo que dejó afuera por no poder
    analizarlo. Función pura: no lee nada y no muta lo que recibe.

    Descarta dos cosas, cada una con su alerta. **Nunca en silencio**: el conteo, el motivo y una
    muestra de tickers viajan en el mensaje (regla 1 del dominio, el faltante se declara con nombre
    y apellido).

    ## Por qué hace falta, si ya hay un filtro de liquidez

    `candidatos_del_segmento` corta por un **percentil** de los volúmenes de los candidatos que ya
    pasaron los filtros previos, y un percentil no es un piso absoluto: si el conjunto candidato
    opera poco, el corte baja con él y sigue dejando pasar al que no operó. El 27/08/2026 entraron
    1.339 instrumentos nuevos —casi todos sin rueda, porque se empezó a pedir el panel completo de
    BYMA— y eso dejó de ser un caso de borde. Estas dos guardas son absolutas y no dependen de con
    quién le tocó competir a cada especie.

    ## Sin precio del día

    `precio is None`, o especie **huérfana**: su `capturado_en` no es el de la corrida más reciente
    del universo recibido. Es la misma definición que `Segmentacion.huerfanas` en
    `app/universo/segmentacion.py` —comparación exacta contra el máximo, y una especie sin
    `capturado_en` no se declara huérfana porque no hay contra qué compararla— y se sostiene en el
    mismo hecho: la poda de precios es por-ticker, así que una especie que dejó de cotizar conserva
    su última fila para siempre y la vista la sigue sirviendo sin ninguna marca de antigüedad.

    El máximo se toma sobre el universo que llega acá, que ya viene recortado por el llamador. Es
    el mismo instante que el de la corrida completa mientras al menos un candidato sea de la última
    —el caso normal—; si ninguno lo fuera, esta guarda no descartaría nada y el faltante lo
    seguirían declarando las alertas de sanidad, que miran todas las filas leídas.

    ## Sin emisor identificado

    `emisor is None`. Proponerle a un cliente un riesgo de crédito que no se puede nombrar no es una
    propuesta, es una apuesta. **Los soberanos nunca caen acá**: la corrida de consolidación les
    escribe siempre su emisor (asigna `underlying` para `bono_soberano`), así que la guarda sólo
    alcanza a ONs y subsoberanos sin emisor escrito, que es exactamente su intención.

    **No es la whitelist de bróker que la regla 9 prohíbe.** Ahí lo vedado es recortar el universo
    por dónde se puede comprar; acá se exige el dato sin el cual el instrumento no se puede
    analizar. Por eso la especie sigue existiendo y mostrándose en el monitor: lo único que no puede
    es entrar sola a una cartera que el asesor va a firmar.

    Las dos guardas se aplican en cascada, así que una especie sin precio **y** sin emisor se cuenta
    una sola vez, en la primera: la alerta dice por qué no entró, no todas las razones por las que
    podría no haber entrado.
    """
    alertas: list[Alerta] = []

    capturas = [e.capturado_en for e in universo if e.capturado_en is not None]
    ultima_corrida: datetime | None = max(capturas) if capturas else None

    con_precio: list[EspecieUniverso] = []
    sin_precio: list[str] = []
    for especie in universo:
        huerfana = (
            ultima_corrida is not None
            and especie.capturado_en is not None
            and especie.capturado_en != ultima_corrida
        )
        if especie.precio is None or huerfana:
            sin_precio.append(especie.ticker)
        else:
            con_precio.append(especie)

    if sin_precio:
        alertas.append(
            _alerta(
                CODIGO_CANDIDATOS_SIN_PRECIO_DEL_DIA,
                f"{len(sin_precio)} instrumento(s) no se proponen porque no tienen precio de la "
                f"corrida más reciente —sin precio publicado, o con la última cotización de una "
                f"rueda anterior—: {_muestra(sin_precio)}.",
                cantidad=len(sin_precio),
                tickers=sorted(sin_precio),
            )
        )

    candidatos = [e for e in con_precio if e.emisor is not None]
    sin_emisor = sorted(e.ticker for e in con_precio if e.emisor is None)
    if sin_emisor:
        alertas.append(
            _alerta(
                CODIGO_CANDIDATOS_SIN_EMISOR,
                f"{len(sin_emisor)} instrumento(s) no se proponen porque la fuente no declara su "
                f"emisor, y sin emisor no se puede nombrar el riesgo de crédito que se asume: "
                f"{_muestra(sin_emisor)}. Se siguen mostrando en el monitor.",
                cantidad=len(sin_emisor),
                tickers=sin_emisor,
            )
        )

    return candidatos, alertas


def percentil_lineal(valores: Sequence[float], q: float) -> float:
    """El percentil `q` (0-1) con interpolación lineal — el método por defecto de
    `pandas.Series.quantile`, que es el que usa `tools/armar_cartera.py` para el piso de liquidez.

    No se usa `statistics.quantiles` de la stdlib: por default interpola con el método
    exclusive/N+1, que da un corte distinto y rompería la paridad. Verificado contra
    `pandas.Series.quantile()` en `tests/test_armado_paridad_motor.py::test_percentil_lineal_...`.
    """
    if not valores:
        raise ValueError("percentil_lineal necesita al menos un valor")
    ordenados = sorted(valores)
    n = len(ordenados)
    if n == 1:
        return ordenados[0]
    pos = q * (n - 1)
    lo, hi = int(pos), min(int(pos) + 1, n - 1)
    frac = pos - lo
    return ordenados[lo] + (ordenados[hi] - ordenados[lo]) * frac


def resolver_mix(params: ParametrosArmado) -> tuple[dict[str, float], str, list[Alerta]]:
    """Precedencia: `mix` explícito > `cobertura` > mix por defecto (balanceado)."""
    alertas: list[Alerta] = []
    if params.mix:
        mix = dict(params.mix)
        total = sum(mix.values())
        if abs(total - 100) > 0.01:
            alertas.append(
                _alerta(
                    CODIGO_MIX_NORMALIZADO,
                    f"El mix indicado suma {total:g}%, se normaliza a 100%.",
                    total=total,
                )
            )
            mix = {k: v / total * 100 for k, v in mix.items()}
        return mix, "mix manual", alertas

    if params.cobertura:
        return dict(MIX_COBERTURA[params.cobertura]), f"cobertura {params.cobertura}", alertas

    return dict(MIX_COBERTURA["mixta"]), "mix balanceado (por defecto)", alertas


def filtrar_por_moneda(mix: dict[str, float], moneda: str) -> tuple[dict[str, float], list[Alerta]]:
    """Restringe el mix a los segmentos que cobran en `moneda` y reescala el resto a 100%.

    Levanta `ValueError` cuando ningún segmento del mix cobra en esa moneda — equivalente al
    `sys.exit(1)` del CLI. El endpoint lo convierte en 422: es un pedido mal formado, no un hecho de
    la cartera.
    """
    alertas: list[Alerta] = []
    if moneda == "todas":
        return mix, alertas
    filtrado = {s: p for s, p in mix.items() if MONEDA_SEGMENTO[s] == moneda}
    if not filtrado:
        raise ValueError(f"el mix pedido no tiene ningún segmento en moneda {moneda!r}")
    descartados = sorted(set(mix) - set(filtrado))
    if descartados:
        alertas.append(
            _alerta(
                CODIGO_MIX_SIN_MONEDA,
                f"Por moneda {moneda} se descartaron segmentos: {', '.join(descartados)}. "
                "El resto se reescala a 100%.",
                descartados=descartados,
            )
        )
    total = sum(filtrado.values())
    return {k: v / total * 100 for k, v in filtrado.items()}, alertas


def candidatos_del_segmento(
    universo: Sequence[EspecieUniverso],
    segmento: str,
    perfil: Perfil,
    params: ParametrosArmado,
) -> list[EspecieUniverso]:
    """Los candidatos de un segmento que cumplen los filtros de calidad del perfil, ordenados por
    rendimiento descendente. Espera `universo` ya colapsado y operable — ver el docstring del
    módulo."""
    dur_min, dur_max = HORIZONTES[params.horizonte]
    candidatos = [
        e
        for e in universo
        if e.segmento == segmento and e.duracion is not None and dur_min <= e.duracion <= dur_max
    ]

    # Tope de rendimiento: sólo tiene sentido en USD. En pesos, rendimientos de 25-30% son normales
    # (inflación), no señal de distress.
    if MONEDA_SEGMENTO[segmento] == "usd":
        tope = perfil["tope_rend_usd"]
        candidatos = [e for e in candidatos if e.rendimiento is not None and e.rendimiento <= tope]

    # Piso de rendimiento: no tiene sentido comprar rendimiento negativo (ni por debajo del mínimo
    # pedido). De paso deja `rendimiento` garantizado no-`None` para el sort de más abajo.
    piso_rend = params.min_rend / 100.0
    candidatos = [e for e in candidatos if e.rendimiento is not None and e.rendimiento > piso_rend]

    volumenes = [e.volumen_usd for e in candidatos if e.volumen_usd is not None]
    if volumenes:
        piso = percentil_lineal(volumenes, perfil["percentil_liquidez"] / 100.0)
        candidatos = [e for e in candidatos if (e.volumen_usd or 0.0) >= piso]

    return sorted(candidatos, key=lambda e: e.rendimiento or 0.0, reverse=True)


def elegir_siguiente(
    candidatos: list[EspecieUniverso],
    ya_elegidos: list[EspecieUniverso],
    riesgos: dict[str, RiesgoDeEspecie],
    peso_acumulado: dict[str, float],
    peso_posicion: float,
    perfil: Perfil,
    peso_sector: dict[str, float],
    sectores_presentes: set[str],
) -> EspecieUniverso | None:
    """El próximo instrumento del segmento.

    Recorre los candidatos (ya ordenados por rendimiento) y descarta los que romperían
    concentración por crédito o por sector. Entre los que quedan, si hay más de uno dentro de
    `BANDA_RENDIMIENTO` del mejor, se prefiere el de un sector todavía no representado en
    `sectores_presentes` (alcance ampliado 08/2026) — y si ninguno aporta sector nuevo, gana el de
    mejor rendimiento, que ya es el primero de la lista por venir pre-ordenada.
    """
    elegidos_tk = {e.ticker for e in ya_elegidos}
    viables: list[EspecieUniverso] = []
    for especie in candidatos:
        if especie.ticker in elegidos_tk:
            continue
        riesgo = riesgos[especie.ticker]
        tope = perfil["max_soberano"] if riesgo.es_soberano else perfil["max_emisor"]
        if peso_acumulado.get(riesgo.clave_riesgo, 0.0) + peso_posicion > tope + 1e-9:
            continue
        sector = sector_computable(especie.sector)
        peso_sector_previo = peso_sector.get(sector, 0.0) if sector is not None else 0.0
        if sector is not None and peso_sector_previo + peso_posicion > perfil["max_sector"] + 1e-9:
            continue
        viables.append(especie)
    if not viables:
        return None

    mejor_rendimiento = viables[0].rendimiento or 0.0
    banda = [e for e in viables if (e.rendimiento or 0.0) >= mejor_rendimiento - BANDA_RENDIMIENTO]
    de_sector_nuevo = [
        e
        for e in banda
        if (sector := sector_computable(e.sector)) is not None and sector not in sectores_presentes
    ]
    if de_sector_nuevo:
        return max(de_sector_nuevo, key=lambda e: e.rendimiento or 0.0)
    return viables[0]


@dataclass(frozen=True, slots=True)
class PosicionArmada:
    """Una posición de la cartera que salió del armado. `pct_cartera` ya está post-reponderación."""

    ticker: str
    pct_cartera: float
    monto: float
    clase: str = "renta_fija"
    """`renta_fija` para todo lo que arma este módulo; `renta_variable` para lo que compone el
    endpoint desde `app.armado.renta_variable`. Default `renta_fija` para que el motor -- que no
    sabe nada de renta variable y no tiene por qué saberlo -- siga construyendo posiciones sin
    tener que nombrar la clase en cada uno de sus `PosicionArmada(...)`."""


@dataclass(frozen=True, slots=True)
class ResultadoArmado:
    """El veredicto completo del armado, listo para precargar en el panel editable."""

    posiciones: list[PosicionArmada]
    alertas: list[Alerta]
    mix_aplicado: dict[str, float]
    origen_mix: str
    """`armar()` no lo conoce -- lo produce `resolver_mix`, un paso antes. Queda vacío acá y el
    endpoint lo completa con `dataclasses.replace`, mismo patrón que usa `evaluar_concentracion`
    para juntar el veredicto con sus alertas."""

    perfil: str
    sectores_presentes: int
    min_sectores: int

    pct_rv_aplicado: float = 0.0
    """El % de la cartera que terminó en renta variable. `armar()` no lo conoce -- igual que
    `origen_mix`, lo completa `app/api/v1/armado.py` con `dataclasses.replace` una vez que compone
    el bloque de renta variable (`app.armado.renta_variable`). `0.0` es el valor de un armado
    solo-renta-fija, que es lo que produce este módulo por su cuenta."""

    def como_dict(self) -> dict[str, object]:
        return {
            "posiciones": [
                {
                    "ticker": p.ticker,
                    "pct_cartera": p.pct_cartera,
                    "monto": p.monto,
                    "clase": p.clase,
                }
                for p in self.posiciones
            ],
            "mix_aplicado": self.mix_aplicado,
            "origen_mix": self.origen_mix,
            "perfil": self.perfil,
            "sectores": {
                "presentes": self.sectores_presentes,
                "minimo": self.min_sectores,
                "suficiente": self.sectores_presentes >= self.min_sectores,
            },
            "pct_rv_aplicado": self.pct_rv_aplicado,
            "alertas": [a.como_dict() for a in self.alertas],
        }


def _pesos_por_sector(
    posiciones: Sequence[PosicionArmada], por_ticker: Mapping[str, EspecieUniverso]
) -> dict[str, float]:
    pesos: dict[str, float] = {}
    for posicion in posiciones:
        sector = sector_computable(por_ticker[posicion.ticker].sector)
        if sector is not None:
            pesos[sector] = pesos.get(sector, 0.0) + posicion.pct_cartera
    return pesos


def _verificar_concentracion(
    posiciones: Sequence[PosicionArmada],
    riesgos: Mapping[str, RiesgoDeEspecie],
    por_ticker: Mapping[str, EspecieUniverso],
    perfil: Perfil,
) -> list[Alerta]:
    """Chequeo post-hoc: la reponderación final puede empujar un crédito o un sector por encima de
    su tope aunque cada elección individual haya respetado el límite en el momento de elegirse.
    Reusa los constructores de alerta de F-020 (`app.concentracion.alertas`) — mismo texto, mismo
    criterio, sin reimplementar un tercero."""
    por_credito: dict[str, float] = {}
    riesgo_de_la_clave: dict[str, RiesgoDeEspecie] = {}
    for posicion in posiciones:
        riesgo = riesgos[posicion.ticker]
        acumulado = por_credito.get(riesgo.clave_riesgo, 0.0)
        por_credito[riesgo.clave_riesgo] = acumulado + posicion.pct_cartera
        riesgo_de_la_clave.setdefault(riesgo.clave_riesgo, riesgo)

    alertas: list[Alerta] = []
    for clave, peso in por_credito.items():
        riesgo = riesgo_de_la_clave[clave]
        tope = perfil["max_soberano"] if riesgo.es_soberano else perfil["max_emisor"]
        if peso > tope + TOLERANCIA_TOPE:
            if riesgo.es_soberano:
                alertas.append(concentracion_soberana(peso, tope))
            else:
                alertas.append(concentracion_emisor(clave, riesgo.nombre, peso, tope))

    for sector, peso in _pesos_por_sector(posiciones, por_ticker).items():
        if peso > perfil["max_sector"] + TOLERANCIA_TOPE:
            alertas.append(concentracion_sector(sector, peso, perfil["max_sector"]))

    return alertas


def armar(
    universo: Sequence[EspecieUniverso],
    mix: dict[str, float],
    perfil: Perfil,
    perfil_nombre: str,
    params: ParametrosArmado,
    riesgos: dict[str, RiesgoDeEspecie],
) -> ResultadoArmado:
    """Selecciona instrumentos segmento por segmento, controlando la concentración por crédito y
    por sector de forma GLOBAL sobre la cartera (un emisor puede aparecer en varios segmentos a la
    vez: el soberano cotiza en hard-dollar, CER y tasa fija).

    Cartera parcial cuando el universo no alcanza para completar el mix o el mínimo sectorial del
    perfil: nunca se rellena con otra naturaleza (regla 1 del dominio) — se alerta y se sigue.

    Lo primero que corre es `aplicar_guardas_de_candidatos`, así cualquier llamador las hereda sin
    tener que acordarse: nada sin precio del día ni sin emisor identificado llega a
    `elegir_siguiente`. Sus alertas siembran la lista, de modo que el descarte se declara aunque
    después la cartera salga completa.
    """
    universo, alertas = aplicar_guardas_de_candidatos(universo)
    peso_acumulado: dict[str, float] = {}
    peso_sector: dict[str, float] = {}
    sectores_presentes: set[str] = set()
    partes: list[tuple[list[EspecieUniverso], float]] = []

    # Los segmentos más chicos se resuelven primero: son los que tienen menos candidatos
    # disponibles, así no se quedan sin lugar por el límite global de concentración.
    for segmento, pct in sorted(mix.items(), key=lambda kv: kv[1]):
        n_objetivo = max(1, round(params.n_total * pct / 100))
        candidatos = candidatos_del_segmento(universo, segmento, perfil, params)
        if not candidatos:
            alertas.append(
                _alerta(
                    CODIGO_SEGMENTO_SIN_CANDIDATOS,
                    f"Segmento {segmento} ({pct:g}%): sin candidatos que cumplan los filtros del "
                    "perfil y el horizonte. Su peso se redistribuye en el resto.",
                    segmento=segmento,
                    pct=pct,
                )
            )
            continue

        peso_posicion = pct / n_objetivo
        elegidos: list[EspecieUniverso] = []
        for _ in range(n_objetivo):
            especie = elegir_siguiente(
                candidatos,
                elegidos,
                riesgos,
                peso_acumulado,
                peso_posicion,
                perfil,
                peso_sector,
                sectores_presentes,
            )
            if especie is None:
                break
            elegidos.append(especie)
            riesgo = riesgos[especie.ticker]
            peso_acumulado[riesgo.clave_riesgo] = (
                peso_acumulado.get(riesgo.clave_riesgo, 0.0) + peso_posicion
            )
            sector = sector_computable(especie.sector)
            if sector is not None:
                peso_sector[sector] = peso_sector.get(sector, 0.0) + peso_posicion
                sectores_presentes.add(sector)

        if not elegidos:
            alertas.append(
                _alerta(
                    CODIGO_SEGMENTO_SIN_CUPO,
                    f"Segmento {segmento} ({pct:g}%): había candidatos pero ninguno entra sin "
                    "romper los límites de concentración. Su peso se redistribuye en el resto.",
                    segmento=segmento,
                    pct=pct,
                )
            )
            continue
        if len(elegidos) < n_objetivo:
            alertas.append(
                _alerta(
                    CODIGO_SEGMENTO_INCOMPLETO,
                    f"Segmento {segmento}: se buscaban {n_objetivo} posiciones y entraron "
                    f"{len(elegidos)} sin romper los límites de concentración. El segmento queda "
                    f"en {peso_posicion * len(elegidos):.1f}% en vez de {pct:g}%; el resto se "
                    "redistribuye proporcionalmente.",
                    segmento=segmento,
                    n_objetivo=n_objetivo,
                    entraron=len(elegidos),
                )
            )
        partes.append((elegidos, peso_posicion))

    if not partes:
        return ResultadoArmado(
            posiciones=[],
            alertas=alertas,
            mix_aplicado=mix,
            origen_mix="",
            perfil=perfil_nombre,
            sectores_presentes=0,
            min_sectores=perfil["min_sectores"],
        )

    posiciones_crudas = [
        (especie, peso_posicion) for elegidos, peso_posicion in partes for especie in elegidos
    ]
    total_pct = sum(peso for _, peso in posiciones_crudas)
    factor = 1.0
    if abs(total_pct - 100) > 0.01:
        alertas.append(
            _alerta(
                CODIGO_CARTERA_RESCALADA,
                f"Los segmentos cubiertos suman {total_pct:.1f}%: se reescala la cartera a 100% "
                "con lo disponible.",
                total_pct=total_pct,
            )
        )
        factor = 100 / total_pct

    posiciones = [
        PosicionArmada(
            ticker=especie.ticker,
            pct_cartera=peso * factor,
            monto=peso * factor / 100 * params.monto,
        )
        for especie, peso in posiciones_crudas
    ]

    por_ticker = {e.ticker: e for e in universo}
    alertas.extend(_verificar_concentracion(posiciones, riesgos, por_ticker, perfil))

    # Mínimo de diversificación sectorial del perfil (GWT-4/GWT-5). El reescalado no cambia QUÉ
    # sectores están presentes, sólo su peso, así que `sectores_presentes` (construido durante la
    # selección) sigue siendo el conjunto final -- se recalculan los pesos nomás, para que la
    # alerta muestre el número post-reponderación y no el peso con el que se validó cada elección.
    pesos_sector_final = _pesos_por_sector(posiciones, por_ticker)
    if len(sectores_presentes) < perfil["min_sectores"]:
        sin_sector = sum(p.pct_cartera for p in posiciones if por_ticker[p.ticker].sector is None)
        alertas.append(
            diversificacion_insuficiente(
                presentes=sorted(pesos_sector_final.items(), key=lambda par: (-par[1], par[0])),
                minimo=perfil["min_sectores"],
                sin_sector=sin_sector,
            )
        )

    return ResultadoArmado(
        posiciones=posiciones,
        alertas=alertas,
        mix_aplicado=mix,
        origen_mix="",
        perfil=perfil_nombre,
        sectores_presentes=len(sectores_presentes),
        min_sectores=perfil["min_sectores"],
    )
