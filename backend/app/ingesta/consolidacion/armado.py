"""Las fuentes se vuelven un universo. Función pura: sin base, sin red, con el reloj afuera.

Toda la lógica que decide qué valor termina en qué columna vive acá, y por eso todo esto se prueba
sin levantar Postgres. `persistencia.py` no decide nada: escribe lo que este módulo armó.

**La precedencia es por columna y está fijada acá, no en los datos.** Cada columna tiene una única
fuente posible y ninguna se completa desde otra:

| Columna                                          | Fuente          | Grano          |
|--------------------------------------------------|-----------------|----------------|
| moneda_cotizacion, plazo_liquidacion, maturity   | BYMA            | especie        |
| last_price, effective_volume, px_bid, px_ask     | BYMA            | especie        |
| law, coupon_currency, estructura_cupon           | ninguna         | —              |
| underlying — sólo soberanos                      | la clase        | especie        |
| tir, duration, paridad — especies calculables    | cálculo propio  | especie        |
| tir, duration, paridad — el resto                | ninguna         | —              |
| residual_value, valor_tecnico — con cronograma   | cálculo propio  | especie        |
| residual_value — el resto (sin cronograma)       | ninguna         | —              |
| convexidad                                       | ninguna         | —              |
| clase_activo, tipo_tasa                          | cronograma      | emisión (raíz) |
| el cronograma entero                             | `public.cashflow` | ticker exacto |
| tna                                              | ninguna         | —              |

**IAMC se eliminó del código el 26/08/2026.** Estaba pausado desde el 13/08 —el informe llegaba por
subida manual y envejecía sin que nada lo declarara, así que el universo mostraba una TIR de ocho
días antes al lado de un precio de hoy— y la pausa se volvió definitiva. Lo que se borró es el
código, no el dato: `law`, `coupon_currency`, `underlying` y `estructura_cupon` viajan `None` en
cada fila y el upsert de `persistencia.py` los conserva con COALESCE, porque la ley de un bono no
envejece y el valor ya escrito sigue siendo el bueno. Lo que sí quedó sin fuente es `convexidad`:
ninguna otra la publica y el cálculo propio no la produce, así que la columna existe declarada y
vacía en todo el universo. `residual_value` **no** quedó vacía — desde el 16/08/2026 sale del
propio cronograma para toda especie que tenga uno, sea o no calculable por moneda, porque es
contractual y sólo dependía de IAMC por no haberse expuesto antes.

**El cronograma ya no tiene fuente viva.** Docta era la única que lo publicaba y se dio de baja el
12/08/2026 por costo: el flujo contractual sale de lo que quedó persistido en `public.cashflow`, que
`corrida.py` lee en cada pasada. No es dato viejo presentado como nuevo —un cronograma es
contractual y no envejece—, pero sí quedó **cerrado**: una emisión que empiece a cotizar de ahora en
más entra sin cronograma, y por lo tanto sin `tipo_tasa` y sin métricas propias. Se declara faltante
y no se clasifica por analogía con una especie hermana (regla 1).

**La TIR es de la especie, no de la emisión, y eso no se relaja.** AL30 y AL30D son el mismo bono y
se pagan bajo la misma ley, pero tienen TIR distintas porque cada una depende del precio propio y de
la moneda en la que ese precio está. Escribir la de una en la otra sería inventar un número que
nadie calculó, y sigue prohibido — **con cálculo propio o sin él**.

**F-051 movió tir, duration y paridad de "ingeridas" a "calculadas" donde se puede calcularlas.**
Se descuenta el flujo contractual persistido contra el precio de BYMA de esa especie, y por eso el
requisito es que los dos estén en la misma moneda: AL30D contra su precio en dólares sí, AL30 —que
cotiza en pesos y paga en dólares— no. La decisión de qué especie entra la toma `metricas.py` de
este mismo paquete, que también explica por qué CER, dollar-linked, badlar y tamar quedan afuera.
Lo que no se calcula queda vacío y declarado: `metricas.py` nombra a cada especie excluida con su
motivo y las junta en una alerta. La columna `fuente` de cada fila dice de dónde salió su número.

`tna` sigue sin fuente: venía de un endpoint de Docta que ya no se consume, y **el cálculo propio
no la llena**. La TIR que resuelve el solver es efectiva anual; convertirla a
nominal exige una convención de capitalización que ninguna fuente declara, y elegirla nosotros sería
inventar. Queda nula en todo el universo y con alerta propia, porque una columna que el motor usa y
que nadie llena tiene que doler a la vista y no descubrirse tres features después.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.calendario.cupones import Cronograma, componentes_valor_tecnico, indexar_cronograma
from app.calendario.metricas import (
    MOTIVO_RESIDUAL_CONTRADICTORIO,
    MetricasEspecie,
    metricas_de,
)
from app.ingesta.alertas import (
    Alerta,
    Severidad,
    campo_sin_cobertura,
    formato_inesperado,
)
from app.ingesta.byma.normalizacion import FilaRueda
from app.ingesta.cobertura import Cobertura, medir_cobertura
from app.ingesta.consolidacion.clasificacion import (
    EMISOR_SOBERANO,
    SECTOR_POR_CLASE,
    clase_discrepante,
    clase_sin_mapeo,
    clasificar,
    hay_discrepancia,
    subtipo_en_corrida,
)
from app.ingesta.consolidacion.metricas import (
    FUENTE_CALCULO,
    MOTIVO_SIN_CRONOGRAMA,
    MOTIVO_SIN_PRECIO,
    ResultadoMetricas,
    fuente_de_metricas,
    motivo_de_exclusion,
)
from app.ingesta.raiz import raiz_emision

CLASES_RENTA_VARIABLE = ("accion", "cedear")

# El contrato de columnas de un cronograma de pagos, que es también el de la tabla `cashflow`.
# Vivía en `ingesta/docta/normalizacion.py` mientras Docta era la fuente que lo llenaba; se movió
# acá cuando se dio de baja esa ingesta, porque el contrato es de la tabla y no del proveedor: si
# mañana otra fuente publica cronogramas, se normaliza contra estas nueve columnas igual.
# `persistencia.py` la importa de acá para que haya una sola definición.
COLUMNAS_CASHFLOW: tuple[str, ...] = (
    "ticker",
    "type",
    "issue_date",
    "payment_date",
    "capital",
    "interest_rate",
    "interest_amount",
    "residual_value",
    "cash_flow",
)

CAMPOS_COBERTURA_INSTRUMENTOS = (
    "clase_activo",
    "tipo_tasa",
    "law",
    "coupon_currency",
    "underlying",
    "estructura_cupon",
    "maturity",
    "moneda_cotizacion",
)
CAMPOS_COBERTURA_PRECIOS = (
    "last_price",
    "tir",
    "tna",
    "duration",
    "paridad",
    "convexidad",
    "residual_value",
    "effective_volume",
)
CAMPOS_COBERTURA_PUNTAS = ("px_bid", "px_ask")

CODIGO_SIN_TICKER = "especie_sin_ticker"
CODIGO_ESPECIE_REPETIDA = "especie_en_varios_endpoints"

# Qué endpoint gana cuando BYMA publica la misma especie en dos paneles (`_colapsar`). Antes era el
# orden alfabético del nombre, que es determinístico pero arbitrario: quién gana no debería
# depender del abecedario.
#
# Los cinco primeros están en el orden que el alfabético ya les daba, así que sobre los
# solapamientos que existen hoy el comportamiento no cambia. **`lebacs` va último a propósito**
# (28/08/2026): BYMA mueve especies de panel —BUN26, BUN6C y BUN6D estaban en
# `negociable-obligations` el 17/08 y hoy están en `lebacs`— y si una aparece en los dos, la clase
# buena es la del panel que sí declara una clase propia, o la que la especie ya venía teniendo. El
# alfabético hubiera hecho ganar a `lebacs` sobre `negociable-obligations`, `public-bonds` y
# `leading-equity`, y esas tres ONs habrían cambiado de clase de activo sin que nada lo pidiera.
ORDEN_DESEMPATE_ENDPOINTS: tuple[str, ...] = (
    "cedears",
    "general-equity",
    "leading-equity",
    "negociable-obligations",
    "public-bonds",
    "lebacs",
)


@dataclass(frozen=True, slots=True)
class Consolidacion:
    """Lo que hay que escribir, ya resuelto. `persistencia.py` no vuelve a decidir nada.

    `filas_cashflow is None` propaga el contrato de F-006: la corrida no trajo un cronograma
    usable y hay que conservar el que ya está persistido, que es distinto de traer cero filas.
    """

    filas_instrumentos: list[dict[str, object]] = field(default_factory=list)
    filas_precios: list[dict[str, object]] = field(default_factory=list)
    filas_puntas: list[dict[str, object]] = field(default_factory=list)
    filas_cashflow: list[dict[str, object]] | None = None
    alertas: list[Alerta] = field(default_factory=list)
    cobertura: list[Cobertura] = field(default_factory=list)


def _precio(valor: float | None) -> float | None:
    """Un precio de cero no es un precio: es que la especie no operó.

    Es la excepción declarada a la regla de la base común, que preserva el cero porque un volumen
    cero sí es un dato ("no operó" es información). Con el precio pasa al revés: guardar 0.0 lo
    haría entrar a los cálculos como si valiera nada.
    """
    return valor if valor else None


def _a_fecha(texto: str | None) -> date | None:
    """El `maturityDate` de BYMA viene en ISO. Lo que no parsea queda vacío y se cuenta."""
    if not texto:
        return None
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        return None


def _elegir_por_plazo(filas: list[FilaRueda]) -> FilaRueda:
    """Una especie que cotiza en los dos plazos entra una sola vez. Cuál se guarda es una regla.

    Verificado el 06/08/2026 contra la fuente: 2.418 de 3.325 tickers vienen en plazo 1 y en plazo
    2, y ninguno difiere en moneda de cotización ni en vencimiento entre los dos: sólo cambian
    precio y volumen. Revalidado el 27/08/2026 sobre el panel completo, que es más grande: de 4.814
    tickers, 4.018 traen más de una fila y **cero** difieren en moneda o en vencimiento. Así que el
    colapso no puede perder un atributo, sólo elegir una cotización.

    El orden: primero la fila que tiene precio, después el plazo 2 —el estándar de liquidación— y a
    igualdad, la que más operó. **El precio va antes que el plazo desde el 27/08/2026**, cuando el
    cliente empezó a pedirle a BYMA el panel completo (ver `EXCLUIR_SIN_COTIZACION` en
    `byma/cliente.py`): con el panel recortado casi todas las filas traían cotización y el desempate
    por plazo alcanzaba, pero el panel completo incluye la fila que no operó y ésa venía ganando por
    ser plazo 2, dejando la especie sin `last_price` aunque la fuente lo publicara en el otro plazo.
    Medido ese día: 52 tickers cotizan sólo fuera del plazo 2 —BYZ1X con 160.200 en plazo 1 contra
    una fila de plazo 2 en cero es el caso testigo— y con el criterio viejo los 52 quedaban sin
    precio. No es preferir una cotización peor: un plazo sin precio no es una cotización.
    """
    return max(
        filas,
        key=lambda f: (
            bool(f["precio_ultimo"]),
            f["plazo_liquidacion"] == "2",
            f["monto_operado"] or float("-inf"),
        ),
    )


def _indice_cronograma(
    filas_cashflow: list[dict[str, object]] | None,
) -> dict[str, str]:
    """Raíz de emisión → submarket declarado por el cronograma. Primera aparición gana.

    Verificado que ninguna raíz declara dos submarkets distintos en las 6.150 filas del feed, así
    que la primera aparición y "la que más se repite" dan lo mismo.
    """
    if not filas_cashflow:
        return {}
    tipos: dict[str, str] = {}
    for fila in filas_cashflow:
        ticker = fila.get("ticker")
        tipo = fila.get("type")
        if isinstance(ticker, str) and ticker and isinstance(tipo, str) and tipo:
            tipos.setdefault(raiz_emision(ticker), tipo)
    return tipos


def _colapsar(
    especies_por_endpoint: dict[str, list[FilaRueda]],
) -> tuple[dict[str, tuple[str, FilaRueda, bool]], list[Alerta]]:
    """Ticker → (endpoint que lo declaró, fila elegida, vino en más de un plazo)."""
    agrupadas: dict[str, list[tuple[str, FilaRueda]]] = defaultdict(list)
    sin_ticker = 0

    for endpoint, filas in especies_por_endpoint.items():
        for fila in filas:
            ticker = fila["ticker"]
            if not ticker:
                sin_ticker += 1
                continue
            agrupadas[ticker].append((endpoint, fila))

    alertas: list[Alerta] = []
    if sin_ticker:
        alertas.append(
            formato_inesperado(
                "BYMA", f"{sin_ticker} especies sin symbol", especies_descartadas=sin_ticker
            )
        )

    elegidas: dict[str, tuple[str, FilaRueda, bool]] = {}
    en_varios: list[str] = []
    for ticker, candidatas in agrupadas.items():
        endpoints = {endpoint for endpoint, _ in candidatas}
        if len(endpoints) > 1:
            en_varios.append(ticker)
        # Determinístico aunque la fuente empiece a repetir una especie entre paneles: gana el
        # primero de `ORDEN_DESEMPATE_ENDPOINTS`, así la corrida no depende del orden del dict.
        endpoint = min(endpoints, key=ORDEN_DESEMPATE_ENDPOINTS.index)
        filas = [f for ep, f in candidatas if ep == endpoint]
        elegidas[ticker] = (endpoint, _elegir_por_plazo(filas), len(candidatas) > 1)

    if en_varios:
        alertas.append(
            Alerta(
                codigo=CODIGO_ESPECIE_REPETIDA,
                mensaje=(
                    f"{len(en_varios)} especies aparecen en más de un endpoint de BYMA "
                    f"({', '.join(sorted(en_varios)[:5])}). Se conservó la del panel que gana en "
                    f"ORDEN_DESEMPATE_ENDPOINTS; la clase de activo puede estar mal declarada."
                ),
                severidad=Severidad.ADVERTENCIA,
                accion_requerida=None,
                detalle={"total": len(en_varios), "muestra": sorted(en_varios)[:20]},
            )
        )
    return elegidas, alertas


def _metricas_de(
    *,
    propias: MetricasEspecie | None = None,
    residual: float | None = None,
    valor_tecnico: float | None = None,
) -> dict[str, object]:
    """Las siete columnas de métricas de una especie. Las que nadie calcula van `None`, declaradas.

    `convexidad` y `fecha_metricas` **siguen en el dict aunque siempre valgan `None`** desde que se
    eliminó IAMC (26/08/2026). Eran suyas: la convexidad la publicaba el informe y nadie más la
    calcula, y `fecha_metricas` rotulaba de qué informe salía cada número. Se conservan porque las
    columnas existen en `precios` y una columna que la fila deja de nombrar no queda vacía: queda
    con lo que hubiera antes. Escribir `None` explícito es lo que declara el faltante, que es
    exactamente lo que ya pasaba con la pausa activa.

    **`residual_value` y `valor_tecnico` son cálculo propio siempre que haya cronograma** —
    relevamiento de confiabilidad de datos, 16/08/2026: `componentes_valor_tecnico` no necesita que
    la moneda del flujo y la de cotización coincidan (a diferencia de `tir`/`paridad`, que sí la
    necesitan para poder comparar contra el precio), así que llegan con valor aunque `propias` sea
    `None` — un CER o un bono en moneda cruzada declaran su residual igual.
    """
    return {
        "tir": propias.tir if propias is not None else None,
        "paridad": propias.paridad if propias is not None else None,
        "duration": propias.duration if propias is not None else None,
        "convexidad": None,
        "residual_value": residual,
        "fecha_metricas": None,
        "valor_tecnico": valor_tecnico,
    }


def _calcular_metricas(
    *,
    ticker: str,
    raiz: str,
    clase_activo: str,
    tipo_tasa: str | None,
    moneda_cotizacion: object,
    precio: float | None,
    cronograma: Cronograma,
    hoy: date,
    resultado: ResultadoMetricas,
) -> MetricasEspecie | None:
    """Las métricas propias de una especie, o `None` si esta especie no se calcula.

    Devolver `None` no es un error, pero **nunca es silencioso**: cada motivo se anota en
    `resultado` para que la alerta pueda nombrar a la especie, que es lo que la regla 1 pide — un
    faltante sin nombre es un faltante que nadie va a buscar. Hasta el 26/08/2026 había una
    excepción: las especies sin `tipo_tasa` y las de naturaleza sin regla caían en `FUENTE_IAMC` y
    volvían `None` sin anotar nada, porque se daba por hecho que IAMC las llenaba. Eliminada esa
    fuente, `fuente_de_metricas` las manda a `FUENTE_FUERA` con motivo propio y aparecen en la
    alerta como todas las demás.

    **Un precio `data912-arrastre` se calcula igual, a propósito**: el arrastre es el último cierre
    conocido de una fecha que la fuente no declara, y el caso típico es un sábado con el cierre del
    viernes — no hay una punta "más de hoy" que esa, y negarle la métrica sería peor que calcularla
    con el mejor precio disponible. Ver `test_un_arrastre_de_data912_con_calculo_se_rotula_
    data912_arrastre_mas_calculo`. Se distingue de un precio ausente (`None`), que sí se declara.
    """
    if clase_activo in CLASES_RENTA_VARIABLE:
        return None  # una acción no tiene TIR, y no es un faltante que haya que declarar

    moneda = moneda_cotizacion if isinstance(moneda_cotizacion, str) else None
    if fuente_de_metricas(tipo_tasa, moneda) != FUENTE_CALCULO:
        resultado.anotar(motivo_de_exclusion(tipo_tasa, moneda), ticker)
        return None

    pagos = cronograma.pagos_de(raiz)
    if not pagos:
        resultado.anotar(MOTIVO_SIN_CRONOGRAMA, ticker)
        return None
    if precio is None:
        resultado.anotar(MOTIVO_SIN_PRECIO, ticker)
        return None

    propias = metricas_de(pagos, precio, hoy)
    resultado.registrar(ticker, propias)
    return propias


def _fuente_de(propias: MetricasEspecie | None, *, origen: str = "byma") -> str:
    """De dónde salió lo que esta fila muestra. Se componen los términos que efectivamente hay.

    `origen` es el experimento data912: `_colapsar` conserva `fila["origen_precio"]` cuando el
    overlay pisó el precio de esta especie (`'data912'` u `'data912-arrastre'`), y ese valor llega
    acá tal cual. El default `"byma"` es lo que cae cuando el overlay no tocó la fila.

    `calculo` sólo aparece si el cálculo **produjo** algún número. Que se haya intentado y no haya
    salido nada no es una fuente: la fila no tiene nada que atribuirle, y decir que sí haría creer
    que las columnas vacías las dejó vacías el cálculo cuando lo que faltó fue el insumo.
    """
    partes = [origen]
    if propias is not None and (
        propias.tir is not None or propias.duration is not None or propias.paridad is not None
    ):
        partes.append("calculo")
    return "+".join(partes)


def armar_consolidacion(
    *,
    especies_por_endpoint: dict[str, list[FilaRueda]],
    filas_cashflow: list[dict[str, object]] | None = None,
    cronograma_persistido: list[dict[str, object]] | None = None,
    hoy: date,
) -> Consolidacion:
    """Une las fuentes en las filas que van a las cuatro tablas de mercado.

    Cada fuente puede faltar y la consolidación sigue: sin cronograma la renta fija queda sin
    clasificar y sin métricas propias. Lo que falta se declara en la cobertura y en las alertas,
    nunca se completa desde otra fuente.

    `cronograma_persistido` es el cashflow que ya está en la base, para las corridas que no traen
    uno nuevo. **El cronograma es contractual y no envejece**: reusarlo no es presentar un dato
    viejo como nuevo, y sin él una corrida sin Docta perdería tanto la clasificación por submarket
    como todas las métricas calculadas. Lo que sí es del día es el precio, y ése viene de BYMA.

    `hoy` se inyecta y no se consulta: el módulo sigue sin reloj propio. Es la fecha contra la que
    se devengan los intereses corridos y se miden los plazos al descuento, así que dos corridas del
    mismo día con el mismo insumo dan el mismo número.
    """
    alertas: list[Alerta] = []

    # El cronograma del día si Docta entregó, y el persistido si no. La clasificación por submarket
    # y las métricas propias salen los dos de acá: antes de F-051 una corrida sin Docta perdía la
    # clase de `public-bonds` en silencio.
    pagos_crudos = filas_cashflow if filas_cashflow is not None else (cronograma_persistido or [])
    cronograma = indexar_cronograma(pagos_crudos)
    tipo_por_raiz = _indice_cronograma(pagos_crudos)
    resultado_metricas = ResultadoMetricas()

    elegidas, alertas_colapso = _colapsar(especies_por_endpoint)
    alertas.extend(alertas_colapso)

    instrumentos: list[dict[str, object]] = []
    precios: list[dict[str, object]] = []
    puntas: list[dict[str, object]] = []
    sin_clase: dict[str, int] = defaultdict(int)
    discrepantes: list[tuple[str, str]] = []
    vencimientos_ilegibles = 0

    for ticker, (endpoint, fila, duplicado) in sorted(elegidas.items()):
        raiz = raiz_emision(ticker)
        tipo_cronograma = tipo_por_raiz.get(raiz)

        # La punta se guarda siempre, incluso para lo que no entra al universo: `puntas` no tiene
        # FK justamente para no perder el precio de compra y venta de una especie sin clasificar.
        # La excepción es un libro sin bid ni ask: mismo caso que el de `precios` más abajo — si
        # BYMA declaró el ticker sin ninguna punta, no insertar la fila deja al ticker "ausente"
        # para `sql_poda`, que conserva el último libro bueno en vez de reemplazarlo por uno vacío.
        px_bid = _precio(fila["precio_compra"])
        px_ask = _precio(fila["precio_venta"])
        if px_bid is not None or px_ask is not None:
            puntas.append(
                {
                    "ticker": ticker,
                    "px_bid": px_bid,
                    "px_ask": px_ask,
                    "operaciones": fila["operaciones"],
                    # Experimento data912: si el overlay pisó esta especie, la punta es la que
                    # trajo data912 y se rotula igual — incluido `-arrastre`, porque si no operó,
                    # la fecha del libro es tan desconocida como la del precio (regla 11).
                    "fuente": fila.get("origen_precio", "byma"),
                }
            )

        clasificacion = clasificar(endpoint, tipo_cronograma)
        if clasificacion is None:
            sin_clase[tipo_cronograma or ""] += 1
            continue
        if hay_discrepancia(endpoint, tipo_cronograma):
            discrepantes.append((ticker, tipo_cronograma or ""))

        clase_activo, tipo_tasa = clasificacion

        maturity = _a_fecha(fila["vencimiento"])
        if fila["vencimiento"] and maturity is None:
            vencimientos_ilegibles += 1

        # El Tesoro no aparece como emisor en ninguna fuente: no es un dato que falte, es uno que
        # la clase ya determina. Es el único `underlying` que este módulo escribe desde que se
        # eliminó IAMC; el del resto viaja `None` y el COALESCE del upsert conserva el que haya.
        underlying = EMISOR_SOBERANO if clase_activo == "bono_soberano" else None

        instrumentos.append(
            {
                "ticker": ticker,
                "clase_activo": clase_activo,
                "tipo_tasa": tipo_tasa,
                # Sólo los dos subtipos que salen de esta fila: `letra` (panel `lebacs` + clase
                # soberana) y `bopreal` (tipo de tasa del cronograma). Sin `law` en la fila el
                # subtipo no puede afinarse por legislación, y no se lee la que ya está persistida
                # para desempatar: eso es tarea de F-009, que tiene el CSV curado, y adivinarla acá
                # sería completar por analogía (regla 1). Cuando esto vale `None` el COALESCE del
                # upsert conserva el bonar/global que hubiera escrito.
                "subtipo": subtipo_en_corrida(endpoint, clase_activo, tipo_tasa),
                "underlying": underlying,
                "sector": SECTOR_POR_CLASE.get(clase_activo),
                "maturity": maturity,
                # Atributos de la emisión que sólo publicaba IAMC. Van `None` y el upsert los
                # conserva con COALESCE: la ley de un bono no envejece, así que lo ya escrito sigue
                # siendo el dato bueno y esta corrida no tiene con qué mejorarlo ni por qué pisarlo.
                "law": None,
                "coupon_currency": None,
                "lamina": None,
                "calificacion": None,
                # Sin herencia por raíz no hay dos especies que puedan contradecirse entre sí, así
                # que ninguna fila nace marcada para revisión.
                "revisar": False,
                "duplicado": duplicado,
                "archivo_origen": "BYMA",
                "estructura_cupon": None,
                "moneda_cotizacion": fila["moneda_cotizacion"],
                "plazo_liquidacion": fila["plazo_liquidacion"],
            }
        )

        precio = _precio(fila["precio_ultimo"])
        propias = _calcular_metricas(
            ticker=ticker,
            raiz=raiz,
            clase_activo=clase_activo,
            tipo_tasa=tipo_tasa,
            moneda_cotizacion=fila["moneda_cotizacion"],
            precio=precio,
            cronograma=cronograma,
            hoy=hoy,
            resultado=resultado_metricas,
        )
        # Residual y valor técnico son contractuales: no exigen que la moneda del flujo y la de
        # cotización coincidan (a diferencia de tir/paridad, que sí), así que se calculan del
        # cronograma de la raíz para toda especie de renta fija, la use o no `_calcular_metricas`.
        componentes = (
            componentes_valor_tecnico(cronograma.pagos_de(raiz), hoy)
            if clase_activo not in CLASES_RENTA_VARIABLE
            else None
        )
        # `propias is None` evita anotar dos veces el mismo ticker: desde el 26/08/2026
        # `metricas_de` devuelve este mismo motivo cuando el residual no cierra, y las especies que
        # pasaron por el cálculo ya lo tienen anotado vía `registrar`. Lo que queda para este
        # bloque son las que no llegaron al solver —fuera por moneda o por naturaleza, sin precio,
        # sin cronograma— y que igual arrastran el problema en el cronograma de su raíz: si no se
        # anotaran acá, el residual roto de una emisión sólo se vería a través de una de sus
        # especies.
        if componentes is not None and not componentes.coherente and propias is None:
            resultado_metricas.anotar(MOTIVO_RESIDUAL_CONTRADICTORIO, ticker)
        metricas = _metricas_de(
            propias=propias,
            residual=componentes.residual_vigente if componentes else None,
            valor_tecnico=componentes.valor_tecnico if componentes else None,
        )
        cierre_anterior = _precio(fila["precio_cierre_anterior"])
        precio_apertura = _precio(fila["precio_apertura"])
        precio_maximo = _precio(fila["precio_maximo"])
        precio_minimo = _precio(fila["precio_minimo"])
        vwap = _precio(fila["vwap"])

        # BYMA declaró el ticker en el panel de hoy, pero sin un solo campo de precio: ni operó
        # hoy, ni trae el cierre de ayer, ni ninguna punta de la rueda. Pasa en la pre-apertura con
        # especies poco líquidas — no es un error de la fuente, es que todavía no hay nada que
        # publicar. `sql_poda` (`persistencia.py`) sólo conserva la fila más vieja de un ticker
        # **ausente** del panel de hoy; un ticker presente pero vacío arma una fila nueva con
        # `capturado_en` de ahora, que pasa a ser el máximo, y la poda borra la fila de la corrida
        # anterior que sí tenía precio — perdiendo un dato real por uno vacío. No insertar esta
        # fila dejar el ticker "ausente" a ojos de la poda es lo que ya protege a un ticker que el
        # panel dejó de declarar del todo: mismo mecanismo, extendido al caso que hoy no cubría
        # (hallazgo del 30/08/2026, EXT/MGCOC y afines). `effective_volume` no entra en la
        # condición: un volumen en 0 es un dato válido ("no operó hoy"), no ausencia de dato.
        sin_ningun_precio = (
            precio is None
            and cierre_anterior is None
            and precio_apertura is None
            and precio_maximo is None
            and precio_minimo is None
            and vwap is None
        )
        if not sin_ningun_precio:
            precios.append(
                {
                    "ticker": ticker,
                    "last_price": precio,
                    "tna": None,
                    "effective_volume": fila["monto_operado"],
                    "fuente": _fuente_de(propias, origen=fila.get("origen_precio", "byma")),
                    "cierre_anterior": cierre_anterior,
                    # Siempre de BYMA, aunque `fuente` diga data912: el overlay no los pisa (no
                    # están en `CAMPOS_PISADOS`) y una fila sólo-data912 los trae `None` de
                    # fábrica. Por `_precio()`: un 0 no es un precio, es "no operó".
                    "precio_apertura": precio_apertura,
                    "precio_maximo": precio_maximo,
                    "precio_minimo": precio_minimo,
                    "vwap": vwap,
                    **metricas,
                }
            )

    alertas.extend(resultado_metricas.alertas)

    if sin_clase:
        alertas.append(clase_sin_mapeo(dict(sin_clase), sum(sin_clase.values())))
    if discrepantes:
        alertas.append(clase_discrepante(discrepantes))
    if vencimientos_ilegibles:
        alertas.append(
            formato_inesperado(
                "BYMA",
                f"{vencimientos_ilegibles} vencimientos que no son una fecha ISO",
                vencimientos_ilegibles=vencimientos_ilegibles,
            )
        )

    cobertura = (
        medir_cobertura(instrumentos, CAMPOS_COBERTURA_INSTRUMENTOS)
        + medir_cobertura(precios, CAMPOS_COBERTURA_PRECIOS)
        + medir_cobertura(puntas, CAMPOS_COBERTURA_PUNTAS)
    )
    alertas.extend(
        campo_sin_cobertura(c.campo, c.total) for c in cobertura if c.total and not c.presentes
    )

    return Consolidacion(
        filas_instrumentos=instrumentos,
        filas_precios=precios,
        filas_puntas=puntas,
        filas_cashflow=_filas_de_cashflow(filas_cashflow),
        alertas=alertas,
        cobertura=cobertura,
    )


def _filas_de_cashflow(
    filas: list[dict[str, object]] | None,
) -> list[dict[str, object]] | None:
    """Sólo las nueve columnas del contrato. Las passthrough del feed no se persisten.

    `days_convention`, `theoretical_payment_date` y `theoretical_days_before` llegan del Excel sin
    tipar y sin documentación de la fuente. Guardar una columna cuya semántica no está declarada es
    prometer un dato que después nadie puede sostener; si F-015 necesita la convención de días, se
    la agrega con una migración y su verificación propia.
    """
    if filas is None:
        return None
    return [{columna: fila.get(columna) for columna in COLUMNAS_CASHFLOW} for fila in filas]
