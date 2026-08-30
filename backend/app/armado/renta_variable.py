"""El bloque de renta variable del armado asistido — Tanda de composición RF+RV.

**Por qué es un módulo aparte y no vive dentro de `motor.py`.** El motor arma sobre
`EspecieUniverso`, que no puede representar una acción (`.naturaleza` busca el segmento en
`NATURALEZA_TASA` y una acción no tiene ninguno — ver `app/universo/segmentacion.py`). La renta
variable tiene su propio tipo, `EspecieRentaVariable`, sin rendimiento por diseño (regla 2 del
dominio: una acción no tiene TIR), así que arma con otro criterio: no hay banda de rendimiento que
ordenar, hay liquidez que rankear. `armar_renta_variable()` de acá es la contraparte de
`armar()` de `motor.py` para ese otro universo, y el endpoint (`app/api/v1/armado.py`) es quien
compone los dos resultados en una sola cartera — ver el docstring de ese módulo para el porqué de
que la composición viva ahí y no acá.

## De dónde salen los porcentajes por perfil

`PCT_RV_PERFIL` sale de `referencia/carteras-sugeridas-ifa.xlsx`, el Excel de referencia del IFA:
la cartera conservadora no lleva renta variable, la moderada lleva un cuarto del libro y la
agresiva es mayoritariamente renta variable. Son los mismos tres perfiles que ya usa
`app.concentracion.perfiles.PERFILES`, y `pct_rv` en `ParametrosArmado` puede pisarlos: el default
es una guía, no una regla del dominio.

## Cambio de comportamiento del 28/08/2026 (F-078, Fase 4)

Antes de esta fecha el bloque se armaba **sin ningún tope**: liquidez, un papel por rubro nuevo, y
relleno. Desde F-078 el armador aplica los topes de `TOPES_RV_DEFAULT[perfil]` cuando el llamador
no manda `topes_rv`, así que **las carteras que el endpoint propone cambian** — un pedido que
antes devolvía tres papeles del mismo rubro ahora devuelve tres rubros distintos, o menos papeles
y una alerta que dice por qué. No es un efecto colateral: es la feature. Los tests que asumían el
comportamiento sin topes se ajustaron declarando `topes_rv=None` explícito, que es el apagado.

## Qué acota un tope, y qué no

Un tope dice **cuánto del bloque de renta variable puede caer en una misma categoría de un eje**
—rubro, país, región, moneda, mercado—. Cinco ejes independientes, sin score compuesto: es la
regla 7 del dominio (el riesgo es un vector de ejes, no un número).

El porcentaje se mide sobre el bloque de renta variable y no sobre la cartera entera, porque es la
unidad en la que se reparten los cupos: con `pct_rv=25` y `n_rv=4`, un tope de rubro del 50 %
significa "dos de las cuatro posiciones", no "el 50 % de la cartera".

**Una categoría faltante no computa contra ningún tope.** Es el criterio de
`app.concentracion.perfiles.sector_computable()`, palabra por palabra: no se acota lo que no se
conoce, y **no se reparte entre los conocidos** (reglas 1 y 11). Un CEDEAR sin país curado no
consume cupo de país — pero se cuenta, y `rv_tope_sin_dato_en_eje` declara sobre cuántas de
cuántas posiciones se pudo medir ese tope. Un tope medido sobre 2 de 5 posiciones no es el mismo
tope, y callarlo lo haría pasar por uno cumplido.

## El algoritmo, en orden

1. `pct_rv <= 0` o `n_rv <= 0`: no hay bloque de renta variable que armar.
2. Se descartan las especies sin precio publicado —no se propone lo que no se puede valuar— y
   después las que quedan sin `volumen_usd` medible: sin liquidez comparable no hay con qué
   rankear, y no se le asume cero, que es la regla 1 del dominio. Cada motivo tiene su alerta y se
   evalúan en cascada, así que una especie a la que le faltan las dos cosas se cuenta una sola vez.
3. Filtro temático (`FiltroRv`): cada dimensión declarada se compara contra el valor **de la
   fuente, sin traducir** (regla 11). En `interseccion` toda dimensión declarada tiene que
   cumplirse; en `union` alcanza con una. Una especie sin el dato **nunca** cumple una dimensión
   activa: no se puede afirmar que pertenece a un recorte que no declara. `rubro_rv`, la temática
   de una sola dimensión que el frontend manda desde F-052, se pliega acá adentro con
   `normalizar_filtro_rv`.
4. Orden determinístico: `volumen_usd` descendente, empate por `ticker` ascendente.
5. Cupos: para cada eje con tope, `cupo = max(1, floor(max_pct / 100 * n_rv))`, el mismo para
   todas las categorías de ese eje. El `max(1, ...)` está para que un tope chico **acote** el eje
   en vez de **prohibirlo**: con `n_rv=4` y un tope del 20 %, `floor` da 0 y el eje entero se
   volvería incomprable — ninguna categoría podría tener ni un papel, y el bloque saldría vacío
   por aritmética y no por falta de candidatos. El precio de ese `max(1, ...)` es que una posición
   sola puede pesar más que el tope, y eso no se esconde: lo declara `rv_tope_excedido`.
6. Selección greedy en dos pasadas, las mismas de siempre: la primera reparte por rubro todavía no
   representado (un rubro `None` nunca cuenta como rubro nuevo), la segunda completa con lo que
   quede en el mismo orden. En las dos, un candidato cuya categoría ya llenó el cupo **se saltea**
   y se sigue con el siguiente. Si no alcanza para `n_rv`, se arma con lo que hay — no se rellena
   con otra naturaleza.
7. Equiponderación dentro del bloque: cada posición pesa `pct_rv / len(elegidas)` del total de la
   cartera, y su monto sale de aplicar ese peso a `monto_total` — mismo patrón que usa `armar()` en
   `motor.py` para las posiciones de renta fija.
8. Verificación **post-selección** de los topes, sobre los pesos que quedaron. Los cupos se
   repartieron contra `n_rv`, pero si se eligieron menos papeles cada uno pesa más: dos papeles de
   diez son el 20 %, dos de tres son el 67 %. Se recomputa el porcentaje real por categoría y todo
   exceso se declara con `rv_tope_excedido`. **Declara, no bloquea**, igual que
   `evaluar_concentracion`: reponderar para cumplirlo exigiría comprar un papel que el universo no
   ofreció, y devolver la cartera vacía sería peor información que devolverla con el exceso a la
   vista.

## Por qué las alertas de tope no son excepciones

Un tope incumplible es un hecho del universo, no un pedido mal formado: el mercado local no ofrece
CEDEARs de todos los países en todos los rubros. Es la misma decisión que ya toma el endpoint con
la cartera parcial (siempre 200) y que toma `armar()` cuando un segmento se queda sin candidatos.
"""

import math
import re
from collections import Counter
from collections.abc import Sequence

from app.armado.motor import PosicionArmada
from app.armado.parametros import FiltroRv, TopesRv, normalizar_filtro_rv
from app.concentracion.perfiles import TOLERANCIA_TOPE
from app.ingesta.alertas import Alerta, Severidad
from app.renta_variable.especies import EspecieRentaVariable

# Ver el punto "De dónde salen los porcentajes por perfil" en el docstring del módulo.
PCT_RV_PERFIL: dict[str, float] = {
    "conservador": 0.0,
    "moderado": 25.0,
    "agresivo": 60.0,
}

TOPES_RV_DEFAULT: dict[str, TopesRv] = {
    "conservador": TopesRv(
        max_pct_rubro=30,
        max_pct_pais=40,
        max_pct_region=60,
        max_pct_mercado=60,
        max_pct_moneda=None,
    ),
    "moderado": TopesRv(
        max_pct_rubro=40,
        max_pct_pais=50,
        max_pct_region=70,
        max_pct_mercado=70,
        max_pct_moneda=None,
    ),
    "agresivo": TopesRv(
        max_pct_rubro=55,
        max_pct_pais=60,
        max_pct_region=85,
        max_pct_mercado=85,
        max_pct_moneda=None,
    ),
}
"""Los topes de arranque de cada perfil. Todo lo medido acá salió de la base el 28/08/2026 sobre
las 1.209 especies de clase `cedear` con perfil, y cada número dice de dónde sale.

**Esta tabla está espejada en `frontend/src/features/armador/lib/schemaArmado.ts::TOPES_RV_PERFIL`**
—el asesor tiene que ver con qué topes se armó, no adivinarlos—, mismo arreglo que `PCT_RV_PERFIL`.
Las dos tienen que decir lo mismo: si acá se cambia un número, allá también.

- **Rubro 30 / 40 / 55.** Son los mismos números de `max_sector` en
  `app.concentracion.perfiles.PERFILES`, a propósito: "conservador" tiene que significar lo mismo
  del lado de la renta fija y del de la renta variable, o el perfil pasa a significar dos cosas
  según qué mitad de la cartera lo mire. **Desde F-079 (29/08/2026) el eje "rubro" mide
  `sector_codigo`** —el major group SIC de dos dígitos, 43 valores presentes— **y no `sic_oficina`**
  —la oficina de la SEC, 12 valores—: el nivel más fino elimina las 78 especies que caían en
  oficinas ambiguas ("X or Y", "Multiple Offices") sin perder cobertura, porque `sector_codigo` es
  aritmética sobre `sic_codigo` y no depende de ningún curado adicional. Los números no cambian con
  la migración: el tope no muerde sobre el universo entero sino sobre el ranking de liquidez, que
  sigue mucho más concentrado en ese puñado de sectores top que antes lo estaba en esas oficinas.
- **País 40 / 50 / 60, elegido para cuando el curado exista, no para hoy.** Hasta que aterrice
  `data/paises_cedears.csv` (Fase 3 de F-078) `pais` es `None` en todo el universo, así que este
  tope **no acota nada todavía**: cae por la regla de "categoría faltante no computa" y lo declara
  `rv_tope_sin_dato_en_eje` sobre cada armado. Cuando el curado esté, EE.UU. va a ser el que toque
  el tope: el 97,9 % de los CEDEARs con mercado declarado (969 de 990) cotiza en un mercado
  estadounidense, así que cualquier número por debajo de ~95 % se excede. La consecuencia buscada
  no es que el armado se cumpla, es que se declare — subir el default a un número que no muerda
  sería presentar como diversificada una cartera que no lo está, y bajarlo tampoco cambiaría nada
  (no hay ningún número entre 1 y 95 que evite la alerta). Los únicos no-estadounidenses medidos
  son 19 papeles de B3 y 2 de XETRA, todos lejos del tope del ranking de liquidez.
- **Región 60 / 70 / 85, siempre por encima del de país.** No es gusto, es aritmética: una región
  contiene países, así que su concentración nunca puede ser menor que la del país más grande que
  la integra. Un tope de región por debajo del de país lo volvería letra muerta —se activaría
  primero y siempre—, y entonces habría dos ejes configurables que en los hechos son uno.
- **Mercado 60 / 70 / 85.** La categoría más grande del eje es NYSE, 565 de 990 con mercado
  declarado (57 %), y NASDAQ le sigue con 223; sobre el ranking de liquidez la dominante se da
  vuelta y es NASDAQ (14 de los 25 más líquidos, 56 %). El 60 % del conservador es lo que acota esa
  concentración sin volverla incomprable. Ojo con una asimetría del eje: la fuente escribe
  `NYSE Arca` (81) y `NYSE ARCA` (12), y `NASDAQ` convive con `NASDAQ GS`/`GM`/`CM` — la diferencia
  de caja se pliega (ver `_clave`), la de sufijo **no**, porque son valores distintos de la fuente
  y unificarlos sería traducirla.
- **Moneda apagada por default, y es la única diferencia contra la propuesta coordinada
  (70 / 80 / 90).** El motivo que sostenía esa propuesta —"la moneda de cotización se elige al
  elegir la especie hermana, no al elegir el papel"— es exactamente el motivo para apagar el eje,
  no para ponerle un número: `moneda_cotizacion` dice en qué moneda **liquida la especie en BYMA**,
  no a qué moneda queda expuesta la plata (un CEDEAR de Apple es exposición al dólar se compre en
  pesos o en dólares). Medido el 28/08/2026 sobre los candidatos reales —los que pasan la guarda de
  `volumen_usd`—: 379 especies cotizan en ARS y 286 en USD, y **276 de esas 286 (96,5 %) son la
  hermana `D`/`C` de un papel que ya cotiza en pesos**. Con los `n_rv` reales (4 en moderado, 9 en
  agresivo sobre `n_total=15`) cualquier tope por debajo de 100 fuerza al menos una posición no-ARS,
  y con esa proporción la posición forzada es, casi con seguridad, `NVDAD` al lado de `NVDA`: el
  mismo papel dos veces, comprado para cumplir una diversificación que no existe. El eje no admite
  un default "laxo" —o no hace nada, o hace daño—, así que queda disponible para que el asesor lo
  encienda a mano y apagado de fábrica.

  El eje además es más chico de lo que parece: en la selección tiene **exactamente dos categorías**,
  ARS y USD. Las otras 360 especies del panel declaran `EXT` o no declaran moneda y nunca llegan,
  porque `volumen_usd` no se calcula sobre un código que BYMA no documenta (regla 11) y la guarda de
  liquidez las descarta antes. Un tope sobre un eje binario no reparte: elige cuántas hermanas
  comprar.
"""

EJES_RV: dict[str, str] = {
    "rubro": "sector_codigo",
    "pais": "pais",
    "region": "region",
    "moneda": "moneda_cotizacion",
    "mercado": "mercado_origen",
}
"""Qué atributo de `EspecieRentaVariable` mide cada eje. El orden fija el de las alertas: se
serializan a la respuesta del endpoint y no pueden depender del orden de un `set`.

**"rubro" mide `sector_codigo` desde F-079 (29/08/2026), no `sic_oficina`.** `sic_oficina` es la
oficina de la SEC —12 valores, 78 especies caían en oficinas ambiguas ("X or Y", "Multiple
Offices")— y `sector_codigo` es el major group SIC de dos dígitos (43 valores presentes), más
específico y siempre derivable de `sic_codigo` sin ningún curado. `FiltroRv.rubros` (que filtra por
`sic_oficina`) y `rubro_rv` **no** migran: quedan como estaban, por compatibilidad — ver
`app.armado.parametros.FiltroRv`."""

NOMBRE_EJE: dict[str, str] = {
    "rubro": "rubro",
    "pais": "país",
    "region": "región",
    "moneda": "moneda de cotización",
    "mercado": "mercado de origen",
}
"""Cómo se lee cada eje en el mensaje de la alerta. `eje` es para el código que agrupa y filtra;
esto es para la persona que lo lee — la misma separación que `Alerta.codigo` y `Alerta.mensaje`."""

CODIGO_RV_SIN_VOLUMEN_USD = "rv_sin_volumen_usd"
CODIGO_RV_SIN_PRECIO = "rv_sin_precio"
CODIGO_RV_SIN_PERFIL_SECTORIAL = "rv_sin_perfil_sectorial"
"""Es la llave con la que el frontend reconoce la alerta: renombrarla la rompería sin cambiar lo
que significa."""
CODIGO_RV_SIN_CANDIDATOS = "rv_sin_candidatos"
CODIGO_RV_TOPE_LIMITA_SELECCION = "rv_tope_limita_seleccion"
CODIGO_RV_TOPE_EXCEDIDO = "rv_tope_excedido"
CODIGO_RV_TOPE_SIN_DATO_EN_EJE = "rv_tope_sin_dato_en_eje"


def _alerta(codigo: str, mensaje: str, **detalle: object) -> Alerta:
    """Mismo contrato que `app.armado.motor._alerta`: informa, no bloquea."""
    return Alerta(
        codigo=codigo,
        mensaje=mensaje,
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle=detalle,
    )


def _pct(valor: float) -> str:
    """El porcentaje con coma decimal, como se escribe en castellano. Igual que
    `app.jobs.guardas._porcentaje`."""
    return f"{valor:.1f}".replace(".", ",")


def topes_del_perfil(perfil: str, topes_rv: TopesRv | None) -> TopesRv:
    """Los topes que se van a aplicar: los que mandó el llamador, o los del perfil.

    Misma forma en que el endpoint resuelve `pct_rv` contra `PCT_RV_PERFIL`, y por la misma razón:
    no hay número que signifique "usá el default", así que la ausencia es la señal. Se resuelve
    acá —al lado de la tabla de defaults— y no adentro de `armar_renta_variable`, para que la
    función de armado siga sin saber qué perfil pidió la cartera: recibe topes, no perfiles.

    Un `TopesRv` parcial **no** se completa con el default: lo que el llamador declara es la lista
    entera de lo que quiere acotar. Completarlo haría que apagar un eje fuera imposible de expresar.
    """
    return topes_rv if topes_rv is not None else TOPES_RV_DEFAULT[perfil]


def _contiene_palabra(texto: str, palabra: str) -> bool:
    """`palabra` adentro de `texto`, **como palabra entera y sin distinguir mayúsculas**.

    Por palabra entera y no por substring por el mismo bug que `app/renta_variable/etfs.py` ya
    tuvo: `ETF` adentro de `NETFLIX` clasificó a Netflix como fondo. Acá el caso medido es `gold`
    adentro de `Goldman`, que dejaría entrar a Goldman Sachs al preset de metales preciosos.
    """
    return re.search(rf"\b{re.escape(palabra)}\b", texto, re.IGNORECASE) is not None


def _condiciones_del_filtro(especie: EspecieRentaVariable, filtro: FiltroRv) -> list[bool]:
    """Una entrada por dimensión **declarada** del filtro, con si esta especie la cumple.

    Espejo exacto de `condiciones()` en `frontend/src/lib/presetsRv.ts`: el mismo preset tiene que
    traer el mismo conjunto en el monitor y en el armador, o el asesor vería una cosa y compraría
    otra. Una dimensión sin declarar (o en lista vacía) no produce condición; un dato faltante
    nunca cumple una condición activa.
    """
    evaluadas: list[bool] = []
    if filtro.rubros:
        evaluadas.append(especie.sic_oficina in set(filtro.rubros))
    if filtro.sectores:
        evaluadas.append(especie.sector_codigo in set(filtro.sectores))
    if filtro.sic_codigos:
        evaluadas.append(especie.sic_codigo in set(filtro.sic_codigos))
    if filtro.estrategias_etf:
        evaluadas.append(especie.estrategia_etf in set(filtro.estrategias_etf))
    if filtro.paises:
        evaluadas.append(especie.pais in set(filtro.paises))
    if filtro.regiones:
        evaluadas.append(especie.region in set(filtro.regiones))
    if filtro.mercados:
        # Sin distinguir caja: la fuente escribe el mismo mercado de dos maneras, `NYSE Arca` en 81
        # papeles y `NYSE ARCA` en 12 (medido el 28/08/2026). Comparar sin caja es comparar, no
        # reescribir el dato: lo que se muestra y lo que se guarda sigue siendo lo que dice BYMA.
        mercado = especie.mercado_origen
        pedidos = {m.casefold() for m in filtro.mercados}
        evaluadas.append(mercado is not None and mercado.casefold() in pedidos)
    if filtro.palabras_en_nombre:
        nombre = especie.nombre_largo
        evaluadas.append(
            nombre is not None
            and any(_contiene_palabra(nombre, p) for p in filtro.palabras_en_nombre)
        )
    return evaluadas


def cumple_filtro_rv(especie: EspecieRentaVariable, filtro: FiltroRv) -> bool:
    """Si la especie participa del armado con este filtro activo.

    Un filtro sin ninguna dimensión declarada no filtra: devuelve todo. Es distinto de no devolver
    nada — un preset vacío es un preset mal armado, no un universo vacío.
    """
    evaluadas = _condiciones_del_filtro(especie, filtro)
    if not evaluadas:
        return True
    return any(evaluadas) if filtro.modo == "union" else all(evaluadas)


def _categoria(especie: EspecieRentaVariable, eje: str) -> str | None:
    """El valor de la especie en ese eje, tal como lo declara la fuente, o `None` si no lo declara.

    `None` es lo que hace que la categoría no compute contra el tope: mismo criterio y mismo
    motivo que `app.concentracion.perfiles.sector_computable()`.
    """
    valor = getattr(especie, EJES_RV[eje])
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    return limpio or None


def _clave(categoria: str) -> str:
    """Con qué se agrupan dos categorías del mismo eje. Sin caja, por el mismo caso medido que en
    el filtro: `NYSE Arca` y `NYSE ARCA` son un solo mercado escrito de dos maneras, y contarlos
    como dos categorías haría que el tope de mercado mida la mitad de la concentración real —el
    lado peligroso del error. El literal de la fuente se conserva aparte, para mostrarlo."""
    return categoria.casefold()


def _etiqueta(especie: EspecieRentaVariable, eje: str, categoria: str) -> str:
    """Cómo se nombra la categoría en el mensaje de una alerta (F-079).

    Sólo el eje "rubro" tiene traducción: `categoria` ahí es `sector_codigo` (`"73"`), un código de
    auditoría y no algo que un asesor lea. Si el curado de `sic_es.py` tradujo ese major group
    (`especie.sector`), se muestra la etiqueta ES; si no, se muestra el código crudo — mismo
    fallback declarado que usa `especies.py`. Los demás ejes siguen mostrando el valor de la fuente
    tal cual, sin traducir (regla 11)."""
    if eje == "rubro" and especie.sector:
        return especie.sector
    return categoria


def _cupos(topes: TopesRv, n_rv: int) -> dict[str, int]:
    """Cuántas posiciones puede llevarse cada categoría, por eje. Ver el punto 5 del docstring del
    módulo para el porqué del `max(1, ...)`."""
    cupos: dict[str, int] = {}
    for eje in EJES_RV:
        tope = getattr(topes, f"max_pct_{eje}")
        if tope is not None:
            cupos[eje] = max(1, math.floor(tope / 100 * n_rv))
    return cupos


class _Cupos:
    """El estado de los cupos durante la selección: cuánto se usó de cada categoría de cada eje.

    Es una clase y no un par de diccionarios sueltos porque las dos pasadas de la selección tienen
    que consultar y actualizar exactamente lo mismo, y porque hay un tercer dato que se arrastra —
    qué (eje, categoría) frenó a algún candidato— que alimenta `rv_tope_limita_seleccion`.
    """

    def __init__(self, cupos: dict[str, int]) -> None:
        self.cupos = cupos
        self.usados: dict[str, Counter[str]] = {eje: Counter() for eje in cupos}
        self.etiquetas: dict[str, dict[str, str]] = {eje: {} for eje in cupos}
        """Clave agrupadora -> primer literal visto, para nombrar la categoría como la escribe la
        fuente en vez de en la forma plegada con la que se agrupa."""
        self.frenaron: dict[str, set[str]] = {eje: set() for eje in cupos}

    def entra(self, especie: EspecieRentaVariable) -> bool:
        """Si esta especie cabe en todos los ejes con tope. Registra qué eje la frenó."""
        cabe = True
        for eje in self.cupos:
            categoria = _categoria(especie, eje)
            if categoria is None:
                continue
            clave = _clave(categoria)
            if self.usados[eje][clave] >= self.cupos[eje]:
                etiqueta = self.etiquetas[eje].get(clave) or _etiqueta(especie, eje, categoria)
                self.frenaron[eje].add(etiqueta)
                cabe = False
        return cabe

    def registrar(self, especie: EspecieRentaVariable) -> None:
        for eje in self.cupos:
            categoria = _categoria(especie, eje)
            if categoria is None:
                continue
            clave = _clave(categoria)
            self.usados[eje][clave] += 1
            self.etiquetas[eje].setdefault(clave, _etiqueta(especie, eje, categoria))

    def topados(self) -> list[tuple[str, list[str]]]:
        """Los (eje, categorías) que frenaron a algún candidato, en el orden fijo de `EJES_RV` y
        con las categorías ordenadas: esto viaja a la respuesta del endpoint."""
        return [
            (eje, sorted(categorias)) for eje, categorias in self.frenaron.items() if categorias
        ]


def _alerta_tope_limita(topados: list[tuple[str, list[str]]], elegidas: int, n_rv: int) -> Alerta:
    """Los cupos dejaron la selección corta: se declara cuántas se pidieron, cuántas salieron y
    qué categoría de qué eje se llenó."""
    detalle_ejes = "; ".join(
        f"{NOMBRE_EJE[eje]}: {', '.join(categorias)}" for eje, categorias in topados
    )
    return _alerta(
        CODIGO_RV_TOPE_LIMITA_SELECCION,
        f"Los topes de renta variable dejaron la selección en {elegidas} de las {n_rv} "
        f"posiciones pedidas: se agotó el cupo de {detalle_ejes}. No se completa con un papel que "
        "excedería el tope ni se afloja el tope por su cuenta.",
        pedidas=n_rv,
        elegidas=elegidas,
        topados=[{"eje": eje, "categorias": categorias} for eje, categorias in topados],
    )


def _alertas_post_seleccion(
    elegidas: Sequence[EspecieRentaVariable], topes: TopesRv
) -> list[Alerta]:
    """Los dos avisos que sólo se pueden dar con la cartera ya armada — puntos 8 y "Qué acota un
    tope" del docstring del módulo.

    `rv_tope_excedido` porque los pesos crecen cuando se eligieron menos papeles de los pedidos, y
    `rv_tope_sin_dato_en_eje` porque un tope medido sobre 2 de 5 posiciones no es el mismo tope.
    Se recorren los ejes en el orden de `EJES_RV` para que la lista de alertas sea determinística.
    """
    alertas: list[Alerta] = []
    total = len(elegidas)
    for eje in EJES_RV:
        tope = getattr(topes, f"max_pct_{eje}")
        if tope is None:
            continue

        categorias = [(e, _categoria(e, eje)) for e in elegidas]
        medidas = [c for _, c in categorias if c is not None]
        etiquetas: dict[str, str] = {}
        cuenta: Counter[str] = Counter()
        for especie, categoria in categorias:
            if categoria is None:
                continue
            clave = _clave(categoria)
            cuenta[clave] += 1
            etiquetas.setdefault(clave, _etiqueta(especie, eje, categoria))

        # Contra `total` y no contra `len(medidas)`: el porcentaje es sobre el bloque entero de
        # renta variable, que es lo que el tope promete acotar. Medirlo sólo sobre las posiciones
        # con dato repartiría el faltante entre las conocidas, que es justo lo que la regla 1
        # prohíbe -- por eso el faltante se declara aparte, con su propia alerta.
        for clave, veces in sorted(cuenta.items()):
            pct = veces / total * 100
            if pct > tope + TOLERANCIA_TOPE:
                alertas.append(
                    _alerta(
                        CODIGO_RV_TOPE_EXCEDIDO,
                        f"El {NOMBRE_EJE[eje]} {etiquetas[clave]} quedó en {_pct(pct)} % del "
                        f"bloque de renta variable ({veces} de {total} posiciones), por encima "
                        f"del tope de {_pct(float(tope))} %: el universo no ofreció con qué "
                        "cumplirlo. Se declara y no se corrige — reponderar exigiría comprar un "
                        "papel que no está.",
                        eje=eje,
                        categoria=etiquetas[clave],
                        pct=pct,
                        tope=tope,
                        posiciones=veces,
                        total=total,
                    )
                )

        sin_dato = total - len(medidas)
        if sin_dato > 0:
            alertas.append(
                _alerta(
                    CODIGO_RV_TOPE_SIN_DATO_EN_EJE,
                    f"El tope de {NOMBRE_EJE[eje]} se midió sobre {len(medidas)} de {total} "
                    f"posiciones: {sin_dato} no declara(n) {NOMBRE_EJE[eje]} y no se acota lo que "
                    "no se conoce. El tope se cumple sobre lo medido, no sobre el bloque entero.",
                    eje=eje,
                    medidas=len(medidas),
                    total=total,
                    sin_dato=sin_dato,
                    tope=tope,
                )
            )
    return alertas


def _descripcion_filtro(filtro: FiltroRv | None) -> str:
    """Cómo se nombra el filtro activo dentro de `rv_sin_candidatos`. Vacío si no filtra nada."""
    if filtro is None:
        return ""
    partes = [
        f"{campo}={valores}"
        for campo, valores in (
            ("rubros", filtro.rubros),
            ("sectores", filtro.sectores),
            ("sic_codigos", filtro.sic_codigos),
            ("estrategias_etf", filtro.estrategias_etf),
            ("paises", filtro.paises),
            ("regiones", filtro.regiones),
            ("mercados", filtro.mercados),
            ("palabras_en_nombre", filtro.palabras_en_nombre),
        )
        if valores
    ]
    if not partes:
        return ""
    return f" con el filtro {filtro.modo} ({'; '.join(partes)})"


def armar_renta_variable(
    especies: Sequence[EspecieRentaVariable],
    *,
    pct_rv: float,
    n_rv: int,
    monto_total: float,
    rubro_rv: str | None = None,
    topes_rv: TopesRv | None = None,
    filtro_rv: FiltroRv | None = None,
) -> tuple[list[PosicionArmada], list[Alerta]]:
    """El bloque de renta variable de la cartera, seleccionado por liquidez, recortado por
    `filtro_rv` y acotado por `topes_rv`. Ver el docstring del módulo por el algoritmo completo.

    `topes_rv=None` **no** aplica los defaults del perfil: acá es "sin ningún tope", que es el
    comportamiento previo a F-078 bit a bit. Quien quiera los del perfil los resuelve antes con
    `topes_del_perfil()` — la función no sabe qué perfil pidió la cartera y no tiene por qué.
    """
    if pct_rv <= 0 or n_rv <= 0:
        return [], []

    alertas: list[Alerta] = []

    # Guarda de precio, contraparte de la que `motor.aplicar_guardas_de_candidatos` aplica a renta
    # fija (28/08/2026): no se propone lo que no se puede valuar. Se comparte el criterio, no el
    # código, porque `EspecieRentaVariable` no es un `EspecieUniverso` y **no lleva
    # `capturado_en`**: acá se puede exigir que el precio exista, pero no se puede decir si es de la
    # corrida más reciente, así que la mitad "huérfana" de aquella guarda no tiene con qué
    # evaluarse. Queda declarado como faltante y no se sustituye por otro criterio inventado.
    #
    # **La guarda de emisor no aplica a renta variable y no es un olvido**: una acción o un CEDEAR
    # es su propio emisor —el ticker lo nombra—, así que exigir una columna `emisor` acá dejaría
    # afuera todo el universo por un dato que no falta. No "arreglar" agregándola.
    con_precio = [e for e in especies if e.precio is not None]
    sin_precio = len(especies) - len(con_precio)
    if sin_precio > 0:
        alertas.append(
            _alerta(
                CODIGO_RV_SIN_PRECIO,
                f"{sin_precio} especie(s) de renta variable no tienen precio publicado y no se "
                "proponen: sin precio no hay con qué valuar la posición.",
                cantidad=sin_precio,
            )
        )

    con_volumen = [e for e in con_precio if e.volumen_usd is not None]
    # Contra `con_precio` y no contra `especies`: las que ya cayeron por precio no se cuentan dos
    # veces, para que cada alerta declare el motivo por el que la especie no entró y no todos los
    # que podría haber tenido (mismo criterio en cascada que la guarda de renta fija).
    descartadas = len(con_precio) - len(con_volumen)
    if descartadas > 0:
        alertas.append(
            _alerta(
                CODIGO_RV_SIN_VOLUMEN_USD,
                f"{descartadas} especie(s) de renta variable no tienen volumen en dólares "
                "medible y se descartan del ranking de liquidez.",
                cantidad=descartadas,
            )
        )

    # `rubro_rv` es un `filtro_rv` de una dimensión y un valor: se pliegan en uno solo, con la
    # misma función que usa el validador de `ParametrosArmado` para rechazar la contradicción.
    filtro = normalizar_filtro_rv(filtro_rv, rubro_rv)

    universo = con_volumen
    if filtro is not None:
        universo = [e for e in universo if cumple_filtro_rv(e, filtro)]

    if not universo:
        alertas.append(
            _alerta(
                CODIGO_RV_SIN_CANDIDATOS,
                f"No hay especies de renta variable candidatas para el bloque de {pct_rv:g}%"
                + _descripcion_filtro(filtro)
                + ": la cartera queda sin renta variable.",
                pct_rv=pct_rv,
                rubro_rv=rubro_rv,
                filtro_rv=filtro.model_dump() if filtro is not None else None,
            )
        )
        return [], alertas

    ordenadas = sorted(universo, key=lambda e: (-(e.volumen_usd or 0.0), e.ticker))

    topes = topes_rv if topes_rv is not None else TopesRv()
    cupos = _Cupos(_cupos(topes, n_rv))

    elegidas: list[EspecieRentaVariable] = []
    # Rubro nuevo se mide por `sector_codigo` (F-079) y no por `sic_oficina`: mismo criterio que
    # `EJES_RV["rubro"]`, más específico y sin depender de ningún curado.
    rubros_presentes: set[str] = set()
    for especie in ordenadas:
        if len(elegidas) >= n_rv:
            break
        if especie.sector_codigo is not None and especie.sector_codigo not in rubros_presentes:
            if not cupos.entra(especie):
                continue
            elegidas.append(especie)
            cupos.registrar(especie)
            rubros_presentes.add(especie.sector_codigo)

    if len(elegidas) < n_rv:
        elegidas_tk = {e.ticker for e in elegidas}
        for especie in ordenadas:
            if len(elegidas) >= n_rv:
                break
            if especie.ticker in elegidas_tk:
                continue
            if not cupos.entra(especie):
                continue
            elegidas.append(especie)
            cupos.registrar(especie)
            elegidas_tk.add(especie.ticker)

    if not elegidas:
        # Había candidatos y los cupos no dejaron entrar a ninguno. Sólo puede pasar con `n_rv`
        # tan chico que `max(1, ...)` no alcance a repartir; se declara con el mismo código que
        # el universo vacío, porque para quien lee la cartera el hecho es el mismo: no hay bloque.
        alertas.append(
            _alerta(
                CODIGO_RV_SIN_CANDIDATOS,
                f"Ningún candidato de renta variable entró dentro de los topes del bloque de "
                f"{pct_rv:g}%: la cartera queda sin renta variable.",
                pct_rv=pct_rv,
                rubro_rv=rubro_rv,
                topados=[{"eje": eje, "categorias": cats} for eje, cats in cupos.topados()],
            )
        )
        return [], alertas

    if len(elegidas) < n_rv and cupos.topados():
        alertas.append(_alerta_tope_limita(cupos.topados(), len(elegidas), n_rv))

    if all(e.sector_codigo is None for e in elegidas):
        alertas.append(
            _alerta(
                CODIGO_RV_SIN_PERFIL_SECTORIAL,
                "Ninguna de las especies elegidas para renta variable tiene rubro informado: "
                "no se pudo diversificar por rubro dentro del bloque.",
                cantidad=len(elegidas),
            )
        )

    alertas.extend(_alertas_post_seleccion(elegidas, topes))

    peso_posicion = pct_rv / len(elegidas)
    posiciones = [
        PosicionArmada(
            ticker=especie.ticker,
            pct_cartera=peso_posicion,
            monto=peso_posicion / 100 * monto_total,
            clase="renta_variable",
        )
        for especie in elegidas
    ]
    return posiciones, alertas
