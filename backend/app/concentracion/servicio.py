"""Los topes y la distribución de una cartera, medidos sobre el universo del día — F-020.

`evaluar_concentracion` es **pura**: no toca la base, no sale a la red y no depende del reloj. Lo
que le entra son las posiciones con su peso y las especies del universo ya saneado; lo que sale es
el estado de cada tope, la distribución en los tres cortes y las advertencias. La conexión la
resuelve el endpoint, igual que en `app/calendario/servicio.py`.

## Los pesos se miden como vienen, sin normalizar a 100

Es la regla que F-018 ya sostiene en la tabla de la cartera: la ponderación pedida y la real no se
hacen coincidir en pantalla. Si la cartera suma 94 %, el emisor que pesa 16 % pesa 16 % y no 17 % —
normalizar mostraría un exceso que no existe, o taparía uno que sí. Lo que sí se declara es el
total: `peso_declarado` es lo que suman las posiciones y `peso_medido` lo que suman las que están
en el universo, y verlos separados es lo que evita leer "los topes están bien" sobre media cartera.

## Qué se acota y qué no

- **El soberano tiene tope propio** (regla 4 del dominio). Todo el Tesoro entra bajo `SOBERANO_AR`
  y se mide contra `max_soberano`; los corporativos, cada uno contra `max_emisor`.
- **Soberano y Subsoberano están exentos del tope sectorial** porque ya los acota el tope soberano
  — pero **cuentan como sector presente** para `min_sectores`. La exención es del tope, no de la
  existencia: una cartera de soberanos y provinciales tiene dos sectores, no cero.
- **"Sector no informado" nunca cuenta para el mínimo ni se reparte entre los conocidos.** No se
  acredita diversificación con un dato que no está (reglas 1 y 11 del dominio), y por eso aparece
  como su propio tramo en la distribución, con su peso a la vista.

## Las tres distribuciones no comparten criterio de completitud

Sector, ley y naturaleza de tasa se cortan sobre las mismas posiciones pero fallan distinto: el
sector falta en la mayor parte del universo, la ley falta poco y además puede quedar vacía por
conflicto entre fuentes (F-009), y la naturaleza de tasa **está siempre** porque se deriva del
segmento, que es lo que define si una especie entra al universo comparable. Cada corte lleva igual
su tramo de "no informado": el de naturaleza hoy nunca aparece, y que exista es lo que hace que el
día que aparezca se vea, en vez de que la distribución sume 100 % sobre un subconjunto.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

from app.concentracion.alertas import (
    concentracion_emisor,
    concentracion_sector,
    concentracion_soberana,
    diversificacion_insuficiente,
    fuera_del_universo,
)
from app.concentracion.perfiles import (
    PERFILES,
    TOLERANCIA_TOPE,
    Perfil,
    sector_computable,
)
from app.concentracion.riesgo import RiesgoDeEspecie, derivar_riesgo
from app.ingesta.alertas import Alerta
from app.universo.segmentacion import NOMBRE_NATURALEZA, EspecieUniverso

SIN_SECTOR = "sector no informado"
SIN_LEY = "ley no informada"
SIN_NATURALEZA = "naturaleza de tasa no informada"


class TipoDeTope(StrEnum):
    """Contra qué se mide un acumulado. Los tres topes del motor, sin componer ninguno.

    Es la regla 7 del dominio llevada a este panel: el riesgo no se resume en un número. Un mismo
    peso puede estar bien por emisor y mal por sector, y las dos cosas se muestran por separado
    porque se arreglan distinto.
    """

    SOBERANO = "soberano"
    EMISOR = "emisor"
    SECTOR = "sector"


@dataclass(frozen=True, slots=True)
class Posicion:
    """Una posición de la cartera: qué especie y cuánto pesa.

    `peso` va **en puntos porcentuales** (16.5 = 16,5 %), tal como los declara el armador. Un
    ticker repetido suma su peso: son dos compras de la misma especie y concentran el mismo crédito.
    """

    ticker: str
    peso: float


@dataclass(frozen=True, slots=True)
class EstadoDeTope:
    """Cuánto pesa un crédito o un sector y contra qué tope se lo compara.

    Se devuelven **todos**, no sólo los excedidos: el panel muestra el estado de cada tope, y una
    lista que sólo trajera los rotos haría imposible distinguir "está holgado" de "no se midió".
    """

    tipo: TipoDeTope
    clave: str
    nombre: str
    peso: float
    tope: float

    @property
    def excedido(self) -> bool:
        """Con la misma holgura que el motor: un exceso de una centésima de punto es redondeo."""
        return self.peso > self.tope + TOLERANCIA_TOPE

    @property
    def exceso(self) -> float:
        """Cuánto sobra, en puntos porcentuales. Cero cuando no está excedido."""
        return max(0.0, self.peso - self.tope)

    def como_dict(self) -> dict[str, object]:
        return {
            "tipo": self.tipo.value,
            "clave": self.clave,
            "nombre": self.nombre,
            "peso": self.peso,
            "tope": self.tope,
            "excedido": self.excedido,
            "exceso": self.exceso,
        }


@dataclass(frozen=True, slots=True)
class Tramo:
    """Un pedazo de la cartera en un corte de la distribución."""

    nombre: str
    peso: float
    sin_dato: bool = False
    """`True` en el tramo que agrupa lo que no tiene el dato. Se muestra, nunca se reparte."""

    def como_dict(self) -> dict[str, object]:
        return {"nombre": self.nombre, "peso": self.peso, "sin_dato": self.sin_dato}


@dataclass(frozen=True, slots=True)
class Concentracion:
    """El veredicto completo: topes, distribución y advertencias."""

    perfil: str
    limites: Perfil
    topes: list[EstadoDeTope]
    por_sector: list[Tramo]
    por_ley: list[Tramo]
    por_naturaleza: list[Tramo]
    sectores_presentes: list[str]
    """Sectores informados de la cartera, exentos incluidos. Es lo que se compara con el mínimo."""

    peso_sin_sector: float
    peso_declarado: float
    """Lo que suman todas las posiciones, esté o no cada una en el universo. No se normaliza."""

    peso_medido: float
    """Lo que suman las que sí están. Los topes se miden sobre esto."""

    fuera_del_universo: list[str] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)

    @property
    def excedidos(self) -> list[EstadoDeTope]:
        return [t for t in self.topes if t.excedido]

    @property
    def diversificacion_suficiente(self) -> bool:
        return len(self.sectores_presentes) >= self.limites["min_sectores"]

    def como_dict(self) -> dict[str, object]:
        return {
            "perfil": self.perfil,
            "limites": dict(self.limites),
            "topes": [t.como_dict() for t in self.topes],
            "excedidos": len(self.excedidos),
            "distribucion": {
                "sector": [t.como_dict() for t in self.por_sector],
                "ley": [t.como_dict() for t in self.por_ley],
                "naturaleza": [t.como_dict() for t in self.por_naturaleza],
            },
            "sectores": {
                "presentes": list(self.sectores_presentes),
                "cantidad": len(self.sectores_presentes),
                "minimo": self.limites["min_sectores"],
                "suficiente": self.diversificacion_suficiente,
                "peso_sin_sector": self.peso_sin_sector,
            },
            "peso": {
                "declarado": self.peso_declarado,
                "medido": self.peso_medido,
            },
            "fuera_del_universo": list(self.fuera_del_universo),
            "alertas": [a.como_dict() for a in self.alertas],
        }


def evaluar_concentracion(
    posiciones: Sequence[Posicion],
    especies: Sequence[EspecieUniverso],
    perfil: str,
) -> Concentracion:
    """Mide una cartera contra los topes de un perfil. Función pura: sin base, sin red, sin reloj.

    `posiciones` son pares ticker/peso en puntos porcentuales; `especies` es el universo saneado
    (`saneado.especies`), del que sale la clave de riesgo, el sector, la ley y la naturaleza de tasa
    de cada posición. Se trabaja sobre la vista **viva** y no sobre la colapsada: el asesor tiene
    RUCED o RUCEO, y buscar la emisión en vez de la especie haría desaparecer la posición que sí
    tiene.
    """
    if perfil not in PERFILES:
        raise ValueError(f"perfil desconocido: {perfil!r}")
    limites = PERFILES[perfil]

    pesos = _sumar_por_ticker(posiciones)
    por_ticker = {e.ticker: e for e in especies}
    riesgos = derivar_riesgo(especies)

    presentes = {t: p for t, p in pesos.items() if t in por_ticker}
    ausentes = sorted(t for t in pesos if t not in por_ticker)
    peso_ausente = sum(pesos[t] for t in ausentes)

    topes = _medir_topes(presentes, por_ticker, riesgos, limites)
    por_sector, sectores, peso_sin_sector = _repartir_por_sector(presentes, por_ticker)
    por_ley = _repartir(presentes, por_ticker, lambda e: e.ley, SIN_LEY)
    por_naturaleza = _repartir(
        presentes, por_ticker, lambda e: NOMBRE_NATURALEZA.get(e.naturaleza), SIN_NATURALEZA
    )

    # Se arma sin alertas y se completa con `replace`: las advertencias se deducen del veredicto ya
    # calculado —qué topes quedaron excedidos, cuántos sectores hay— y no de los datos crudos, así
    # que no puede pasar que el panel muestre un tope en verde y la alerta diga lo contrario.
    concentracion = Concentracion(
        perfil=perfil,
        limites=limites,
        topes=topes,
        por_sector=por_sector,
        por_ley=por_ley,
        por_naturaleza=por_naturaleza,
        sectores_presentes=sectores,
        peso_sin_sector=peso_sin_sector,
        peso_declarado=sum(pesos.values()),
        peso_medido=sum(presentes.values()),
        fuera_del_universo=ausentes,
    )
    return replace(concentracion, alertas=_advertir(concentracion, ausentes, peso_ausente))


def _sumar_por_ticker(posiciones: Sequence[Posicion]) -> dict[str, float]:
    """Un ticker repetido es una sola posición: dos compras de la misma especie concentran igual."""
    pesos: dict[str, float] = {}
    for posicion in posiciones:
        pesos[posicion.ticker] = pesos.get(posicion.ticker, 0.0) + posicion.peso
    return pesos


def _medir_topes(
    pesos: Mapping[str, float],
    por_ticker: Mapping[str, EspecieUniverso],
    riesgos: Mapping[str, RiesgoDeEspecie],
    limites: Perfil,
) -> list[EstadoDeTope]:
    """Los tres topes sobre los mismos pesos: soberano, por emisor y por sector.

    Los dos primeros parten de `clave_riesgo` y por eso son excluyentes —una especie es del Tesoro o
    de un corporativo, nunca las dos—; el tercero es un corte transversal, así que una misma
    posición puede estar en un tope de emisor y en uno de sector a la vez. Eso no es doble conteo:
    son dos ejes distintos del riesgo (regla 7 del dominio), y por eso no se combinan en un número.
    """
    por_credito: dict[str, float] = {}
    riesgo_de_la_clave: dict[str, RiesgoDeEspecie] = {}
    for ticker, peso in pesos.items():
        riesgo = riesgos[ticker]
        por_credito[riesgo.clave_riesgo] = por_credito.get(riesgo.clave_riesgo, 0.0) + peso
        riesgo_de_la_clave.setdefault(riesgo.clave_riesgo, riesgo)

    topes: list[EstadoDeTope] = []
    for clave, peso in por_credito.items():
        soberano = riesgo_de_la_clave[clave].es_soberano
        topes.append(
            EstadoDeTope(
                tipo=TipoDeTope.SOBERANO if soberano else TipoDeTope.EMISOR,
                clave=clave,
                nombre=riesgo_de_la_clave[clave].nombre,
                peso=peso,
                tope=limites["max_soberano"] if soberano else limites["max_emisor"],
            )
        )

    por_sector: dict[str, float] = {}
    for ticker, peso in pesos.items():
        sector = sector_computable(por_ticker[ticker].sector)
        if sector is not None:
            por_sector[sector] = por_sector.get(sector, 0.0) + peso
    topes.extend(
        EstadoDeTope(
            tipo=TipoDeTope.SECTOR,
            clave=sector,
            nombre=sector,
            peso=peso,
            tope=limites["max_sector"],
        )
        for sector, peso in por_sector.items()
    )

    orden = {TipoDeTope.SOBERANO: 0, TipoDeTope.EMISOR: 1, TipoDeTope.SECTOR: 2}
    return sorted(topes, key=lambda t: (orden[t.tipo], -t.peso, t.clave))


def _repartir(
    pesos: Mapping[str, float],
    por_ticker: Mapping[str, EspecieUniverso],
    de: Callable[[EspecieUniverso], str | None],
    etiqueta_faltante: str,
) -> list[Tramo]:
    """Un corte de la distribución: acumula el peso por el valor que devuelve `de(especie)`.

    Lo que devuelve `None` va a un tramo propio con `sin_dato`, **nunca repartido** entre los
    conocidos ni omitido. Repartirlo haría que la distribución sumara 100 % mintiendo sobre la
    cobertura; omitirlo, peor: la haría sumar menos sin decir por qué.
    """
    acumulado: dict[str, float] = {}
    faltante = 0.0
    for ticker, peso in pesos.items():
        valor = de(por_ticker[ticker])
        if valor is None:
            faltante += peso
        else:
            acumulado[valor] = acumulado.get(valor, 0.0) + peso

    tramos = [
        Tramo(nombre=nombre, peso=peso)
        for nombre, peso in sorted(acumulado.items(), key=lambda par: (-par[1], par[0]))
    ]
    if faltante > 0:
        # Siempre último: es el tramo que no compite con los otros, y ponerlo en el medio del orden
        # por peso lo haría parecer una categoría más.
        tramos.append(Tramo(nombre=etiqueta_faltante, peso=faltante, sin_dato=True))
    return tramos


def _repartir_por_sector(
    pesos: Mapping[str, float], por_ticker: Mapping[str, EspecieUniverso]
) -> tuple[list[Tramo], list[str], float]:
    """La distribución sectorial, más los dos números que el mínimo del perfil necesita.

    Los sectores presentes incluyen a **Soberano y Subsoberano**: están exentos del tope sectorial
    porque ya los acota el tope soberano, pero eso no los borra del mapa — una cartera de bonos del
    Tesoro y bonos provinciales está expuesta a dos cosas distintas y el mínimo tiene que verlas.
    Lo que nunca cuenta es el peso sin sector informado, que sale por separado.
    """
    tramos = _repartir(pesos, por_ticker, lambda e: e.sector, SIN_SECTOR)
    presentes = sorted(t.nombre for t in tramos if not t.sin_dato)
    sin_sector = next((t.peso for t in tramos if t.sin_dato), 0.0)
    return tramos, presentes, sin_sector


def _advertir(
    concentracion: Concentracion, ausentes: Sequence[str], peso_ausente: float
) -> list[Alerta]:
    """Las advertencias, en el orden en que importan: primero los topes rotos, después el mínimo.

    Una por tope excedido y no una que los resuma, porque cada una se arregla moviendo una posición
    distinta. Ninguna bloquea.
    """
    alertas: list[Alerta] = []
    for tope in concentracion.excedidos:
        if tope.tipo is TipoDeTope.SOBERANO:
            alertas.append(concentracion_soberana(tope.peso, tope.tope))
        elif tope.tipo is TipoDeTope.EMISOR:
            alertas.append(concentracion_emisor(tope.clave, tope.nombre, tope.peso, tope.tope))
        else:
            alertas.append(concentracion_sector(tope.clave, tope.peso, tope.tope))

    # El mínimo sectorial sólo se evalúa cuando hay algo que evaluar: sobre una cartera sin ninguna
    # posición en el universo, "0 sectores de 3" no habla de la cartera sino de que no se midió
    # nada, y la alerta que lo dice es la de posiciones fuera del universo.
    if concentracion.peso_medido > 0 and not concentracion.diversificacion_suficiente:
        pesos_por_sector = {t.nombre: t.peso for t in concentracion.por_sector if not t.sin_dato}
        alertas.append(
            diversificacion_insuficiente(
                presentes=sorted(pesos_por_sector.items(), key=lambda par: (-par[1], par[0])),
                minimo=concentracion.limites["min_sectores"],
                sin_sector=concentracion.peso_sin_sector,
            )
        )

    if ausentes:
        alertas.append(fuera_del_universo(ausentes, peso_ausente))
    return alertas
