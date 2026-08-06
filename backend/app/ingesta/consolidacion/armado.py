"""Las tres fuentes se vuelven un universo. Función pura: sin base, sin red, sin reloj.

Toda la lógica que decide qué valor termina en qué columna vive acá, y por eso todo esto se prueba
sin levantar Postgres. `persistencia.py` no decide nada: escribe lo que este módulo armó.

**La precedencia es por columna y está fijada acá, no en los datos.** Cada columna tiene una única
fuente posible y ninguna se completa desde otra:

| Columna                                          | Fuente   | Grano          |
|--------------------------------------------------|----------|----------------|
| moneda_cotizacion, plazo_liquidacion, maturity   | BYMA     | especie        |
| last_price, effective_volume, px_bid, px_ask     | BYMA     | especie        |
| law, coupon_currency, underlying, estructura     | IAMC     | emisión (raíz) |
| tir, duration, paridad, convexidad, residual     | IAMC     | ticker exacto  |
| clase_activo, tipo_tasa                          | Docta    | emisión (raíz) |
| el cronograma entero                             | Docta    | ticker exacto  |
| tna                                              | ninguna  | —              |

Dos granos distintos para IAMC, y la diferencia es de fondo. Ley y moneda de pago son atributos de
la emisión: AL30, AL30D y AL30C se pagan bajo la misma ley, así que se heredan por raíz. La TIR no:
depende del precio de cada especie y de la moneda en que ese precio está, y AL30 y AL30D tienen TIR
distintas aunque sean el mismo bono. Escribir la TIR de una en la otra sería inventar un número que
nadie calculó. Por eso las métricas se escriben sólo en el ticker que IAMC nombra y las demás
especies quedan con el campo vacío, contado en la cobertura.

`tna` no tiene fuente en F-007: venía del endpoint de Rendimiento de Bonos de Docta, que ya no se
consume. Queda nula en todo el universo y con alerta propia, porque una columna que el motor usa y
que nadie llena tiene que doler a la vista y no descubrirse tres features después.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

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
    subtipo_de,
)
from app.ingesta.consolidacion.raiz import raiz_emision
from app.ingesta.docta.normalizacion import COLUMNAS_CONTRACTUALES
from app.ingesta.iamc.parser import FilaInforme

CLASES_RENTA_VARIABLE = ("accion", "cedear")

# Los cuatro atributos de la emisión que se heredan entre especies, con el campo de IAMC del que
# sale cada uno. Es la misma lista que propagaba el motor viejo, menos `lamina` y `calificacion`,
# que ninguna fuente de F-007 publica y que llegan con F-009 desde el CSV curado.
HERENCIA_POR_RAIZ: dict[str, str] = {
    "law": "ley",
    "coupon_currency": "moneda_pago",
    "underlying": "emisor",
    "estructura_cupon": "estructura_cupon",
}

# Métricas del día que IAMC publica por especie. No se heredan (ver docstring del módulo).
# El valor es el campo de `FilaInforme`; `divide_por_cien` marca las que vienen en puntos
# porcentuales y el contrato del Resumen guarda en fracción (verificado el 06/08/2026: el
# consolidado histórico tiene AL30 con tir 0.0757 y paridad 0.8807).
METRICAS_POR_TICKER: dict[str, tuple[str, bool]] = {
    "tir": ("tir", True),
    "paridad": ("paridad_pct", True),
    "duration": ("duracion_modificada", False),
    "convexidad": ("convexidad", False),
    "residual_value": ("valor_residual", False),
}

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
CODIGO_HERENCIA_CONTRADICTORIA = "herencia_contradictoria"
CODIGO_ESPECIE_REPETIDA = "especie_en_varios_endpoints"


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
    precio y volumen. Así que el colapso no puede perder un atributo, sólo elegir una cotización.
    Se prefiere el plazo 2 —el estándar de liquidación— y a igualdad, la que más operó.
    """
    return max(
        filas,
        key=lambda f: (f["plazo_liquidacion"] == "2", f["monto_operado"] or float("-inf")),
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


def _indice_iamc(
    filas_iamc: list[FilaInforme] | None,
) -> tuple[dict[str, dict[str, object]], set[str], list[Alerta]]:
    """Raíz → atributos de la emisión, más las raíces cuyos valores se contradicen.

    Cuando dos filas del informe caen en la misma raíz declarando valores distintos para un campo,
    ese campo no se propaga a esa raíz y la emisión queda marcada para revisión. No se elige una de
    las dos por cuenta propia y tampoco se vacía lo que ya estuviera guardado: vaciar es tarea de
    F-009, que es quien tiene el dato curado para desempatar.
    """
    por_raiz: dict[str, dict[str, object]] = {}
    valores: dict[str, dict[str, set[object]]] = defaultdict(lambda: defaultdict(set))

    for fila in filas_iamc or []:
        raiz = raiz_emision(fila["ticker"])
        destino = por_raiz.setdefault(raiz, {})
        for columna, campo in HERENCIA_POR_RAIZ.items():
            valor = fila[campo]  # type: ignore[literal-required]
            if valor is None:
                continue
            valores[raiz][columna].add(valor)
            destino.setdefault(columna, valor)

    contradictorias: set[str] = set()
    detalle: dict[str, list[str]] = defaultdict(list)
    for raiz, campos in valores.items():
        for columna, distintos in campos.items():
            if len(distintos) > 1:
                contradictorias.add(raiz)
                detalle[columna].append(raiz)
                por_raiz[raiz].pop(columna, None)

    alertas: list[Alerta] = []
    if detalle:
        resumen = "; ".join(
            f"{columna}: {len(raices)} ({', '.join(sorted(raices)[:5])})"
            for columna, raices in sorted(detalle.items())
        )
        alertas.append(
            Alerta(
                codigo=CODIGO_HERENCIA_CONTRADICTORIA,
                mensaje=(
                    f"Emisiones cuyas especies declaran valores distintos para el mismo atributo "
                    f"({resumen}). Esos campos no se propagaron y las especies quedaron marcadas "
                    f"para revisión."
                ),
                severidad=Severidad.ADVERTENCIA,
                accion_requerida=None,
                detalle={c: sorted(r) for c, r in detalle.items()},
            )
        )
    return por_raiz, contradictorias, alertas


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
        # Determinístico aunque la fuente empiece a repetir una especie entre paneles: se ordena
        # por nombre de endpoint antes de elegir, así la corrida no depende del orden del dict.
        endpoint = sorted(endpoints)[0]
        filas = [f for ep, f in candidatas if ep == endpoint]
        elegidas[ticker] = (endpoint, _elegir_por_plazo(filas), len(candidatas) > 1)

    if en_varios:
        alertas.append(
            Alerta(
                codigo=CODIGO_ESPECIE_REPETIDA,
                mensaje=(
                    f"{len(en_varios)} especies aparecen en más de un endpoint de BYMA "
                    f"({', '.join(sorted(en_varios)[:5])}). Se conservó la del primero por orden "
                    f"alfabético; la clase de activo puede estar mal declarada."
                ),
                severidad=Severidad.ADVERTENCIA,
                accion_requerida=None,
                detalle={"total": len(en_varios), "muestra": sorted(en_varios)[:20]},
            )
        )
    return elegidas, alertas


def _metricas_de(
    del_informe: FilaInforme | None,
    fecha_informe: date | None,
    previas: dict[str, object] | None,
) -> dict[str, object]:
    """Las métricas de IAMC de una especie, del informe de hoy o del último que las tuvo.

    Que la corrida no traiga informe no borra lo que ya se sabía: la fila conserva el valor y lo
    rotula con `fecha_metricas`, que es la fecha del informe del que salió. Sin ese rótulo esto
    sería presentar el dato de un día como el de otro; con él, la fila dice exactamente qué está
    mostrando y de cuándo.
    """
    del_hoy: dict[str, object] = {}
    if del_informe is not None and fecha_informe is not None:
        for columna, (campo, en_puntos) in METRICAS_POR_TICKER.items():
            valor = del_informe[campo]  # type: ignore[literal-required]
            del_hoy[columna] = valor / 100 if (en_puntos and valor is not None) else valor
        del_hoy["fecha_metricas"] = fecha_informe

    fecha_previa = (previas or {}).get("fecha_metricas")
    # Que el informe de hoy sea más viejo que el guardado no debería pasar, pero si pasa gana el
    # más reciente: nunca se retrocede a una métrica anterior a la que ya está publicada.
    if del_hoy and (fecha_previa is None or fecha_informe >= fecha_previa):
        return del_hoy
    if previas:
        return {
            columna: previas.get(columna) for columna in (*METRICAS_POR_TICKER, "fecha_metricas")
        }
    return dict.fromkeys((*METRICAS_POR_TICKER, "fecha_metricas"))


def armar_consolidacion(
    *,
    especies_por_endpoint: dict[str, list[FilaRueda]],
    filas_iamc: list[FilaInforme] | None = None,
    filas_cashflow: list[dict[str, object]] | None = None,
    archivo_iamc: str | None = None,
    fecha_informe: date | None = None,
    metricas_previas: dict[str, dict[str, object]] | None = None,
) -> Consolidacion:
    """Une las tres fuentes en las filas que van a las cuatro tablas de mercado.

    Cada fuente puede faltar y la consolidación sigue: sin IAMC el universo queda sin atributos de
    emisión, sin cronograma la renta fija queda sin clasificar. Lo que falta se declara en la
    cobertura y en las alertas, nunca se completa desde otra fuente.

    `metricas_previas` son las métricas del último informe conocido, por ticker, tal como quedaron
    en la base. Se usan sólo cuando esta corrida no trae informe para ese ticker, y viajan con su
    `fecha_metricas`: es la diferencia entre conservar un dato rotulado y presentar el de ayer como
    si fuera el de hoy.
    """
    alertas: list[Alerta] = []

    tipo_por_raiz = _indice_cronograma(filas_cashflow)
    iamc_por_raiz, raices_contradictorias, alertas_iamc = _indice_iamc(filas_iamc)
    iamc_por_ticker = {f["ticker"]: f for f in filas_iamc or []}
    alertas.extend(alertas_iamc)

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
        puntas.append(
            {
                "ticker": ticker,
                "px_bid": _precio(fila["precio_compra"]),
                "px_ask": _precio(fila["precio_venta"]),
                "operaciones": fila["operaciones"],
                "fuente": "byma",
            }
        )

        clasificacion = clasificar(endpoint, tipo_cronograma)
        if clasificacion is None:
            sin_clase[tipo_cronograma or ""] += 1
            continue
        if hay_discrepancia(endpoint, tipo_cronograma):
            discrepantes.append((ticker, tipo_cronograma or ""))

        clase_activo, tipo_tasa = clasificacion
        heredado = iamc_por_raiz.get(raiz, {}) if clase_activo not in CLASES_RENTA_VARIABLE else {}

        maturity = _a_fecha(fila["vencimiento"])
        if fila["vencimiento"] and maturity is None:
            vencimientos_ilegibles += 1

        law = heredado.get("law")
        underlying = heredado.get("underlying")
        if underlying is None and clase_activo == "bono_soberano":
            # El Tesoro no aparece como emisor en ninguna fuente: no es un dato que falte, es uno
            # que la clase ya determina.
            underlying = EMISOR_SOBERANO

        instrumentos.append(
            {
                "ticker": ticker,
                "clase_activo": clase_activo,
                "tipo_tasa": tipo_tasa,
                "subtipo": subtipo_de(tipo_tasa, law if isinstance(law, str) else None),
                "underlying": underlying,
                "sector": SECTOR_POR_CLASE.get(clase_activo),
                "maturity": maturity,
                "law": law,
                "coupon_currency": heredado.get("coupon_currency"),
                "lamina": None,
                "calificacion": None,
                "revisar": raiz in raices_contradictorias,
                "duplicado": duplicado,
                "archivo_origen": archivo_iamc if heredado else "BYMA",
                "estructura_cupon": heredado.get("estructura_cupon"),
                "moneda_cotizacion": fila["moneda_cotizacion"],
                "plazo_liquidacion": fila["plazo_liquidacion"],
            }
        )

        metricas = _metricas_de(
            iamc_por_ticker.get(ticker),
            fecha_informe,
            (metricas_previas or {}).get(ticker),
        )
        precios.append(
            {
                "ticker": ticker,
                "last_price": _precio(fila["precio_ultimo"]),
                "tna": None,
                "effective_volume": fila["monto_operado"],
                "fuente": "byma+iamc" if metricas["fecha_metricas"] else "byma",
                **metricas,
            }
        )

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
    return [{columna: fila.get(columna) for columna in COLUMNAS_CONTRACTUALES} for fila in filas]
