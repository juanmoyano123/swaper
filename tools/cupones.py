"""Motor de cupones: calendario de cobros de renta fija.

Modulo compartido por los dos pilares del proyecto (armar_cartera.py y
detectar_swaps.py). No se ejecuta solo.

QUE RESUELVE
------------
El cashflow de Docta trae, por ticker y fecha, cuanto paga el bono cada 100
nominales EN SU MONEDA DE EMISION. Para traducir eso a plata sobre un monto
invertido hay que pasar por nominales, y ahi aparece la trampa: `lastPrice`
del universo viene en monedas mezcladas. La misma emision cotiza en pesos sin
sufijo y en dolares con sufijo D/C (AE38 a 127.360 son pesos; PNDCD a 43,77
son dolares). Dividir un monto por ese precio da cualquier cosa.

La salida es normalizar contra la paridad, que es adimensional:

    precio sucio (moneda de emision, c/100 nominales) = paridad x valor tecnico
    valor tecnico = residual vivo + intereses corridos
    nominales     = monto / (precio sucio / 100)

y entonces cada pago, como fraccion del monto invertido, es:

    cobro / monto = cash_flow / precio sucio

que es adimensional y por lo tanto independiente de la moneda de cotizacion.

Validado contra el Excel real de la mesa ("Propuesta Base 7-26", hoja "Renta
Fija pago mensual"): la formula de nominales reproduce exacto RUCED, SBC2D,
CS47D y LOC5D.

EL CRUCE DE TICKERS
-------------------
El cashflow indexa una sola especie por emision (RUCEO, PNDCO, CS47O) mientras
el universo trae las tres especies de liquidacion (RUCED/RUCEO/RUCEC). Como el
cashflow es el mismo bono, se cruza por raiz del ticker. Cobertura actual: 97%
de las emisiones del universo.
"""

import os

import pandas as pd

CASHFLOW_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "output", "cashflow_completo.csv",
)

MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

COLUMNAS_CASHFLOW = ["ticker", "payment_date", "capital", "interest_rate",
                     "interest_amount", "residual_value", "cash_flow"]


def raiz_ticker(t):
    """RUCED / RUCEO / RUCEC -> RUCE. Deja intactos los soberanos cortos
    (AE38, AL30) y los que terminan en otra letra (TY30P)."""
    t = str(t)
    return t[:-1] if len(t) > 4 and t[-1] in "ODC" else t


def cargar_cashflow(alertas, ruta=CASHFLOW_PATH):
    """Lee el cashflow persistido por consolidar_universo.py.

    Devuelve None (y alerta) si no esta: los dos pilares tienen que poder
    seguir funcionando sin analisis de cupones, no romperse.
    """
    if not os.path.exists(ruta):
        alertas.append(
            "No existe data/output/cashflow_completo.csv: el analisis de cupones "
            "queda afuera. Correr primero tools/consolidar_universo.py."
        )
        return None
    df = pd.read_csv(ruta, encoding="utf-8")
    faltan = [c for c in COLUMNAS_CASHFLOW if c not in df.columns]
    if faltan:
        alertas.append(f"cashflow_completo.csv sin columnas {faltan}: se saltea el analisis de cupones.")
        return None
    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce")
    df = df[df["payment_date"].notna()].copy()
    df["raiz"] = df["ticker"].map(raiz_ticker)
    return df.sort_values(["raiz", "payment_date"])


def valor_tecnico(pagos, hoy):
    """Residual vivo + intereses corridos, cada 100 nominales.

    Los corridos se devengan linealmente entre el ultimo pago y el proximo.
    Si el bono todavia no pago ningun cupon se usa la fecha de emision como
    inicio del devengamiento; si tampoco esta, se asume 0 corridos (subestima
    el precio, nunca lo infla).
    """
    pagos = pagos.sort_values("payment_date")
    pasados = pagos[pagos["payment_date"] <= hoy]
    futuros = pagos[pagos["payment_date"] > hoy]
    if not len(futuros):
        return None  # bono ya vencido: no proyecta nada

    residual = float(pasados["residual_value"].iloc[-1]) if len(pasados) else 100.0
    if residual <= 0:
        return None

    prox = futuros.iloc[0]
    if len(pasados):
        desde = pasados["payment_date"].iloc[-1]
    elif "issue_date" in pagos.columns and pd.notna(pagos["issue_date"].iloc[0]):
        desde = pd.to_datetime(pagos["issue_date"].iloc[0])
    else:
        desde = None

    corridos = 0.0
    if desde is not None and prox["payment_date"] > desde:
        transcurrido = (hoy - desde).days
        total = (prox["payment_date"] - desde).days
        if total > 0 and transcurrido > 0:
            corridos = float(prox["interest_amount"]) * min(transcurrido / total, 1.0)
    return residual + corridos


def flujos_por_peso(universo, cashflow, hoy, alertas):
    """Para cada ticker del universo, sus pagos futuros expresados como
    FRACCION DEL MONTO INVERTIDO.

    Devuelve un DataFrame: ticker, payment_date, pct_interes, pct_capital,
    pct_total. Multiplicando por el monto de la posicion se obtiene la plata.
    """
    if cashflow is None:
        return None

    idx = {r: g for r, g in cashflow.groupby("raiz")}
    filas, sin_dato, sin_paridad = [], [], []

    for _, act in universo.iterrows():
        pagos = idx.get(raiz_ticker(act["ticker"]))
        if pagos is None:
            sin_dato.append(act["ticker"])
            continue
        paridad = act.get("paridad")
        if pd.isna(paridad) or paridad <= 0:
            # Sin TIR ni duration el instrumento no cotiza: nunca iba a ser
            # candidato de cartera, asi que no se reporta como dato faltante.
            if pd.notna(act.get("tir")) or pd.notna(act.get("duration")):
                sin_paridad.append(act["ticker"])
            continue
        vt = valor_tecnico(pagos, hoy)
        if vt is None:
            continue
        precio_sucio = float(paridad) * vt  # moneda de emision, c/100 nominales
        if precio_sucio <= 0:
            continue
        fut = pagos[pagos["payment_date"] > hoy]
        for _, p in fut.iterrows():
            filas.append({
                "ticker": act["ticker"],
                "payment_date": p["payment_date"],
                "pct_interes": float(p["interest_amount"]) / precio_sucio,
                "pct_capital": float(p["capital"]) / precio_sucio,
                "pct_total": float(p["cash_flow"]) / precio_sucio,
            })

    if sin_dato:
        alertas.append(
            f"{len(sin_dato)} instrumentos sin cashflow en la fuente "
            f"(ej. {', '.join(sin_dato[:5])}): no entran al calendario de cobros."
        )
    if sin_paridad:
        alertas.append(
            f"{len(sin_paridad)} instrumentos sin paridad utilizable: no se puede "
            "convertir su cupon a plata sin inventar un tipo de cambio."
        )
    return pd.DataFrame(filas) if filas else None


def meses_cubiertos(flujos, tickers, hoy, horizonte_meses=12):
    """Meses del calendario (1-12) en los que cobra al menos uno de los tickers
    dados, mirando los proximos `horizonte_meses`.

    Mismo criterio que `calendario`: la ventana arranca el mes que viene, asi
    el mes en curso (con sus cupones ya pagados) no distorsiona el desempate.
    """
    if flujos is None:
        return set()
    tope = hoy + pd.DateOffset(months=horizonte_meses + 1)
    f = flujos[(flujos["ticker"].isin(tickers)) & (flujos["payment_date"] <= tope)]
    f = f[f["pct_interes"] > 0]  # cobrar amortizacion no es renta
    return set(f["payment_date"].dt.month)


def calendario(cartera, flujos, hoy, horizonte_meses=12):
    """Matriz de cobros de los proximos 12 meses de la cartera propuesta.

    Devuelve (detalle_mensual, totales) donde detalle_mensual tiene una fila
    por mes con: renta (intereses), amortizacion, total y cuantas posiciones
    pagan ese mes.
    """
    if flujos is None:
        return None, None

    monto = cartera.set_index("ticker")["monto"]
    tope = hoy + pd.DateOffset(months=horizonte_meses + 1)
    f = flujos[(flujos["ticker"].isin(monto.index)) & (flujos["payment_date"] <= tope)].copy()
    if not len(f):
        return None, None

    f["monto_pos"] = f["ticker"].map(monto)
    f["interes"] = f["pct_interes"] * f["monto_pos"]
    f["amortizacion"] = f["pct_capital"] * f["monto_pos"]
    f["total"] = f["pct_total"] * f["monto_pos"]
    f["mes_orden"] = f["payment_date"].dt.to_period("M")

    det = (
        f.groupby("mes_orden")
        .agg(renta=("interes", "sum"), amortizacion=("amortizacion", "sum"),
             total=("total", "sum"), pagos=("ticker", "size"),
             posiciones=("ticker", "nunique"))
        .reset_index()
    )
    # Rellena los meses sin ningun cobro: un cero explicito vale mas que una
    # fila ausente cuando lo que se evalua es la continuidad del ingreso.
    # Arranca en el mes que viene: los cupones de este mes con fecha anterior a
    # hoy ya se pagaron y contarlo como "mes sin renta" seria un falso negativo.
    todos = pd.period_range((hoy + pd.DateOffset(months=1)).to_period("M"),
                            periods=horizonte_meses, freq="M")
    det = (det.set_index("mes_orden").reindex(todos, fill_value=0)
              .rename_axis("mes_orden").reset_index())
    det["Mes"] = det["mes_orden"].dt.strftime("%m/%Y")

    totales = {
        "renta_anual": det["renta"].sum(),
        "amortizacion_anual": det["amortizacion"].sum(),
        "cobro_total": det["total"].sum(),
        "renta_mensual_promedio": det["renta"].mean(),
        "meses_sin_renta": int((det["renta"] <= 0).sum()),
        "mes_mas_flaco": det.loc[det["renta"].idxmin(), "Mes"],
        "mes_mas_fuerte": det.loc[det["renta"].idxmax(), "Mes"],
    }
    return det, totales


# Cada cuanto paga renta un bono, leido de la distancia mediana entre cobros
# futuros. Los topes estan holgados a proposito: los calendarios reales se
# corren por fines de semana y feriados, un semestral no cae exacto en 182 dias.
ESCALA_FRECUENCIA = [
    (45, "mensual", 1),
    (75, "bimestral", 2),
    (135, "trimestral", 3),
    (225, "semestral", 6),
    (400, "anual", 12),
]
# Orden de "menos frecuente que cualquier etiqueta conocida", para desempatar.
MESES_DESCONOCIDO = 99


def frecuencia_pagos(cashflow, hoy):
    """Frecuencia de cobro de renta por raiz de emision.

    Devuelve {raiz: (etiqueta, meses_entre_pagos)} o None sin cashflow.

    Se mide sobre los pagos FUTUROS, que son los que efectivamente va a cobrar
    quien compra hoy: un bono semestral al que le queda un solo cupon paga una
    vez y ya, y para decidir una rotacion eso es lo que importa. Por eso el caso
    de un unico cobro restante se etiqueta "al vencimiento" y no por la
    estructura historica del bono.
    """
    if cashflow is None:
        return None
    f = cashflow[cashflow["payment_date"] > hoy].copy()
    f["interest_amount"] = pd.to_numeric(f["interest_amount"], errors="coerce")
    f = f[f["interest_amount"] > 0]
    if not len(f):
        return None

    out = {}
    for raiz, grupo in f.groupby("raiz"):
        fechas = grupo["payment_date"].sort_values().drop_duplicates()
        if len(fechas) < 2:
            out[raiz] = ("al vencimiento", MESES_DESCONOCIDO)
            continue
        dias = fechas.diff().dt.days.dropna().median()
        etiqueta, meses = "irregular", MESES_DESCONOCIDO
        for tope, et, m in ESCALA_FRECUENCIA:
            if dias <= tope:
                etiqueta, meses = et, m
                break
        out[raiz] = (etiqueta, meses)
    return out


def _flujos_futuros(cashflow, ticker, hoy):
    """Pagos futuros crudos (c/100 nominales) y años hasta cada uno."""
    if cashflow is None:
        return None
    pagos = cashflow[cashflow["raiz"] == raiz_ticker(ticker)]
    fut = pagos[pagos["payment_date"] > hoy]
    if not len(fut):
        return None
    t = ((fut["payment_date"] - hoy).dt.days / 365.25).to_numpy(dtype=float)
    cf = pd.to_numeric(fut["cash_flow"], errors="coerce").to_numpy(dtype=float)
    if pd.isna(cf).any() or not len(cf):
        return None
    return t, cf


def _valor_presente(t, cf, y):
    return float((cf / (1.0 + y) ** t).sum())


def retorno_por_tir(cashflow, ticker, tir_actual, deltas, hoy):
    """Cuanto se movería el precio si la TIR del bono cambiara.

    Repricing completo del cashflow contractual, no una aproximacion por
    duration: se descuentan todos los flujos a la TIR nueva y se compara contra
    descontarlos a la TIR de hoy. En bonos largos la aproximacion lineal por
    duration subestima fuerte la suba ante compresiones grandes, y justamente
    esos son los escenarios que interesan.

    `deltas` en fracciones (-0.01 = comprime 100 bps). Devuelve
    {delta: retorno} o None si falta cashflow o TIR.
    """
    if tir_actual is None or pd.isna(tir_actual):
        return None
    fl = _flujos_futuros(cashflow, ticker, hoy)
    if fl is None:
        return None
    t, cf = fl
    base = _valor_presente(t, cf, float(tir_actual))
    if base <= 0:
        return None
    out = {}
    for d in deltas:
        y = float(tir_actual) + d
        if y <= -0.99:  # descuento degenerado: no se reporta un numero inventado
            continue
        out[d] = _valor_presente(t, cf, y) / base - 1
    return out or None


def proximo_cupon(flujos, ticker, hoy):
    """Proximo pago de un ticker: (fecha, dias, pct_interes, pct_total).
    Devuelve None si no hay dato o no quedan pagos."""
    if flujos is None:
        return None
    f = flujos[(flujos["ticker"] == ticker) & (flujos["payment_date"] > hoy)]
    if not len(f):
        return None
    p = f.sort_values("payment_date").iloc[0]
    return {
        "fecha": p["payment_date"],
        "dias": int((p["payment_date"] - hoy).days),
        "pct_interes": p["pct_interes"],
        "pct_total": p["pct_total"],
    }
