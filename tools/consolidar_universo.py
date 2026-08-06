#!/usr/bin/env python3
"""
Consolidador de Universo (v4 - via API de Docta).

Cubre renta fija (bonos soberanos, subsoberanos y Obligaciones Negociables de
todos los tipos de tasa) y renta variable (acciones locales y CEDEARs), que la
Serie de precios ya devuelve en la misma respuesta.

Las dos familias conviven en el mismo Excel pero NO se mezclan: una accion no
tiene TIR, ni duration, ni cashflow, asi que no es comparable con un bono ni
puede entrar al armador o al motor de swaps. La frontera se aplica en un solo
lugar, segmentos.cargar_universo(), que deja la renta variable afuera; quien la
necesite la pide explicitamente con segmentos.cargar_renta_variable().

Los FCI no los publica ninguna de las fuentes actuales y por lo tanto no estan.

Llama a los links de la API de Docta guardados en .env (Serie de precios,
Rendimiento de Bonos, Cashflow de Bonos), los cruza con el archivo estatico
de ley/moneda de pago/emisor (data/condiciones_estaticas.csv, dato que la
API no expone) y genera un unico Excel consolidado en
data/output/universo_consolidado.xlsx junto con un log de corrida.

No hay descarga manual de CSV: todo sale de la API con el token de .env.

Spec original (v1, manual): docs/historial/2026-07-diseno-wat/04-spec.md
Uso: python3 tools/consolidar_universo.py
"""

import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import segmentos  # noqa: E402  (solo raiz_emision: la regla de especies vive en un lugar)

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
CONSOLIDADO_PATH = os.path.join(OUTPUT_DIR, "universo_consolidado.xlsx")
SNAPSHOT_PATH = os.path.join(OUTPUT_DIR, ".ultimo_universo.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")
CONDICIONES_ESTATICAS_PATH = os.path.join(BASE_DIR, "data", "condiciones_estaticas.csv")

# ---------------------------------------------------------------------------
# Mapeo submarket (API) -> (clase_activo, tipo_tasa) del proyecto
# Los soberanos hard-dollar se distinguen Global/Bonar despues, por 'ley'.
#
# STOCK y CEDEAR entran con tipo_tasa None a proposito: no tienen tasa, y ese
# None es justamente lo que hace que asignar_segmento() los deje sin segmento
# y no lleguen al armador ni al swaper.
# ---------------------------------------------------------------------------
SUBMARKET_MAP = {
    "HARD_DOLLAR": ("bono_soberano", "hard-dollar"),
    "FIXED_RATE": ("bono_soberano", "tasa-fija"),
    "CER": ("bono_soberano", "cer"),
    "DOLLAR_LINKED": ("bono_soberano", "dollar-linked"),
    "BADLAR": ("bono_soberano", "badlar"),
    "TAMAR": ("bono_soberano", "tamar"),
    "BOPREAL": ("bono_soberano", "bopreal"),
    "ON": ("on_corporativo", "hard-dollar"),
    "ON_FIXED_RATE": ("on_corporativo", "tasa-fija"),
    "ON_CER": ("on_corporativo", "cer"),
    "ON_UVA": ("on_corporativo", "cer"),  # UVA: mismo casillero que CER (naming distinto segun endpoint)
    "ON_BADLAR": ("on_corporativo", "badlar"),
    "ON_TAMAR": ("on_corporativo", "tamar"),
    "ON_DOLLAR_LINKED": ("on_corporativo", "dollar-linked"),
    "SUB_SOBERANO": ("bono_subsoberano", "hard-dollar"),
    "SUB_SOBERANO_FIXED_RATE": ("bono_subsoberano", "tasa-fija"),
    "SUB_SOBERANO_CER": ("bono_subsoberano", "cer"),
    "SUB_SOBERANO_BADLAR": ("bono_subsoberano", "badlar"),
    "SUB_SOBERANO_TAMAR": ("bono_subsoberano", "tamar"),
    "SUB_SOBERANO_DOLLAR_LINKED": ("bono_subsoberano", "dollar-linked"),
    "STOCK": ("accion", None),
    "CEDEAR": ("cedear", None),
}

# Clases sin tasa: se consolidan y se exportan, pero no son renta fija.
CLASES_RENTA_VARIABLE = ("accion", "cedear")

ORDEN_CLASES = ["bono_soberano", "bono_subsoberano", "on_corporativo",
                "accion", "cedear"]
NOMBRE_HOJA = {
    "bono_soberano": "Soberanos",
    "bono_subsoberano": "Subsoberanos",
    "on_corporativo": "ONs Corporativos",
    "accion": "Acciones",
    "cedear": "CEDEARs",
}

COLUMNAS_RESUMEN = [
    "ticker", "clase_activo", "tipo_tasa", "subtipo", "underlying", "sector", "tir",
    "tna", "duration", "maturity", "law", "couponCurrency", "lamina", "calificacion", "paridad",
    "residualValue", "lastPrice", "effectiveVolume",
    "revisar", "duplicado", "archivo_origen",
]


# ---------------------------------------------------------------------------
# .env — parser simple (soporta comillas y expansion de ${VAR})
# ---------------------------------------------------------------------------
def cargar_env():
    valores = {}
    if not os.path.exists(ENV_PATH):
        print(f"ERROR: no existe {ENV_PATH}. Ahi debe estar DOCTA_API_TOKEN y los links guardados.")
        sys.exit(1)
    with open(ENV_PATH, encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, val = linea.split("=", 1)
            val = val.strip().strip('"').strip("'")
            for k, v in valores.items():
                val = val.replace("${%s}" % k, v)
            valores[clave.strip()] = val
    return valores


def pedir_excel(url, nombre, log, intentos=5, timeout=90):
    """Descarga un link de Docta y lo devuelve como dict de DataFrames (hojas).

    La API devuelve 0 filas de forma ERRATICA: la misma consulta que responde
    vacia vuelve a traer datos segundos despues (medido: fromDate=24/07 dio 0
    y al rato 1660 filas). No es una regla de fechas ni de dias habiles, es
    inestabilidad del endpoint — por eso se reintenta varias veces con espera
    creciente antes de darla por perdida.

    El timeout es amplio a proposito: una ventana de 15 dias con todas las
    columnas puede tardar ~25s en responder.
    """
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if resp.status != 200:
                    ultimo_error = f"HTTP {resp.status}"
                    data = None
                else:
                    data = resp.read()
        except urllib.error.HTTPError as exc:
            cuerpo = ""
            try:
                cuerpo = exc.read()[:120].decode("utf-8", "replace")
            except Exception:
                pass
            # 500 "Error al verificar el token" = token vencido; 401 = inexistente.
            # Reintentar no lo va a arreglar: hay que regenerar el link en Docta.
            if "token" in cuerpo.lower():
                log["alertas"].append(
                    f"{nombre}: HTTP {exc.code} '{cuerpo}'. El token vencio — regenerar "
                    "un link en Docta Terminal ('Generar Link') y actualizar .env. "
                    "El token nuevo sirve para los tres links."
                )
                return None
            ultimo_error = f"HTTP {exc.code} {cuerpo}"
            data = None
        except urllib.error.URLError as exc:
            ultimo_error = f"no se pudo conectar ({exc})"
            data = None

        if data is not None:
            try:
                hojas = pd.read_excel(io.BytesIO(data), sheet_name=None)
                primera = next(iter(hojas.values()), None)
                if primera is not None and len(primera) > 0:
                    if intento > 1:
                        print(f"  {nombre}: respondio en el intento {intento}.")
                    return hojas
                ultimo_error = "la API devolvio 0 filas"
            except Exception as exc:
                ultimo_error = f"respuesta no es un Excel valido ({exc})"

        if intento < intentos:
            time.sleep(3 * intento)  # 3s, 6s, 9s, 12s
    log["alertas"].append(f"{nombre}: {ultimo_error} tras {intentos} intento(s). Se saltea.")
    return None


def validar_columnas(df, esperadas, nombre, log):
    faltan = [c for c in esperadas if c not in df.columns]
    if faltan:
        log["alertas"].append(
            f"{nombre}: faltan columnas {faltan} respecto a lo esperado — "
            "es posible que Docta haya cambiado el formato de esta serie."
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Ingesta de cada fuente
# ---------------------------------------------------------------------------
DIAS_VENTANA_PRECIOS = 15


def url_con_ventana_movil(url, dias=DIAS_VENTANA_PRECIOS):
    """Reescribe fromDate a hoy - `dias`.

    El link que genera Docta trae la fecha del dia en que se creo, hardcodeada.
    Con el correr de los dias esa fecha queda vieja y el endpoint empieza a
    devolver 0 filas SIN error: el pipeline se rompia en silencio.

    Ademas la serie es erratica — pedir desde el 20/07 devolvia 0 filas pero
    desde el 13/07 traia ese mismo dia. Una ventana amplia lo absorbe: despues
    nos quedamos con el ultimo precio de cada ticker igual.
    """
    if "fromDate=" not in url:
        return url
    desde = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    return re.sub(r"fromDate=[^&]*", f"fromDate={desde}", url)


def cargar_serie_precios(env, log):
    url = url_con_ventana_movil(env.get("DOCTA_SERIE_PRECIOS_URL", ""))
    hojas = pedir_excel(url, "Serie de precios", log)
    if not hojas:
        return None
    df = next(iter(hojas.values()))
    esperadas = ["date", "ticker", "closing_price", "effective_volume", "trade_volume", "submarket"]
    if not validar_columnas(df, esperadas, "Serie de precios", log):
        return None
    if "last_price" not in df.columns:
        # A veces la API no incluye last_price (ej. fuera de horario de rueda):
        # el precio de cierre es el mejor sustituto disponible.
        df["last_price"] = df["closing_price"]
        log["alertas"].append(
            "Serie de precios: 'last_price' no vino en esta corrida, se usa "
            "'closing_price' como equivalente."
        )
    # Puede traer varios dias acumulados (la serie crece dia a dia): nos
    # quedamos con la fecha mas reciente por ticker.
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset="ticker", keep="last")
    # El link trae Acciones y CEDEARs ademas de Bonos, y entran: son la parte
    # de renta variable de las carteras sugeridas por la mesa. Se separan de la
    # renta fija por clase_activo, no descartandolas aca.
    return df


def cargar_yield_bonds(env, log):
    hojas = pedir_excel(env.get("DOCTA_YIELD_BONDS_URL", ""), "Rendimiento de Bonos", log)
    if not hojas:
        return None
    df = next(iter(hojas.values()))
    esperadas = ["date", "ticker", "tir", "duration", "parity"]
    if not validar_columnas(df, esperadas, "Rendimiento de Bonos", log):
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates(subset="ticker", keep="last")
    return df


def cargar_cashflow_resumen(env, log):
    """Del cashflow completo (todos los pagos), derivamos por ticker:
    residual actual (residual del ultimo pago ya ocurrido, o 100 si ninguno
    ocurrio todavia) y vencimiento (fecha del ultimo pago programado).

    Ademas persiste el cashflow COMPLETO en disco. El calendario de cobros es
    la base del analisis de renta fija, asi que los dos pilares lo necesitan
    entero: colapsarlo aca a dos numeros por ticker tiraba el dato que despues
    hace falta para proyectar cupones.
    """
    hojas = pedir_excel(env.get("DOCTA_CASHFLOW_URL", ""), "Cashflow de Bonos", log)
    if not hojas:
        return None
    df = next(iter(hojas.values()))
    esperadas = ["ticker", "payment_date", "residual_value"]
    if not validar_columnas(df, esperadas, "Cashflow de Bonos", log):
        return None
    df["payment_date"] = pd.to_datetime(df["payment_date"])
    hoy = pd.Timestamp.now().normalize()

    guardar_cashflow_completo(df, log)

    resumenes = []
    for ticker, grupo in df.groupby("ticker"):
        grupo = grupo.sort_values("payment_date")
        pasados = grupo[grupo["payment_date"] <= hoy]
        residual_actual = pasados["residual_value"].iloc[-1] if len(pasados) else 100.0
        vencimiento = grupo["payment_date"].max()
        resumenes.append({"ticker": ticker, "residualValue": residual_actual, "maturity": vencimiento})
    return pd.DataFrame(resumenes)


def guardar_cashflow_completo(df, log):
    """Deja el cashflow entero en data/output/cashflow_completo.csv para que
    armar_cartera.py y detectar_swaps.py proyecten cupones sin volver a pegarle
    a la API."""
    columnas = [c for c in ("ticker", "type", "issue_date", "payment_date", "capital",
                            "interest_rate", "interest_amount", "residual_value",
                            "cash_flow") if c in df.columns]
    faltan = [c for c in ("capital", "interest_amount", "cash_flow") if c not in df.columns]
    if faltan:
        log["alertas"].append(
            f"El link de cashflow no trae {faltan}: sin esas columnas no se puede "
            "separar renta de amortizacion. Regenerar el link en Docta incluyendolas."
        )
    ruta = os.path.join(OUTPUT_DIR, "cashflow_completo.csv")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df[columnas].to_csv(ruta, index=False, encoding="utf-8")
    print(f"  Cashflow completo: {len(df):,} pagos de {df['ticker'].nunique()} emisiones "
          f"-> {os.path.basename(ruta)}")


def cargar_condiciones_estaticas(log):
    """ley / moneda de pago / emisor / lamina minima / calificacion: la API no
    expone ninguno de los cinco, se mantienen en un archivo aparte.

    La lamina y la calificacion se incorporan con tools/merge_condiciones.py
    desde fuentes que si las publican."""
    if not os.path.exists(CONDICIONES_ESTATICAS_PATH):
        log["alertas"].append(
            "No existe data/condiciones_estaticas.csv: quedan sin dato de ley, "
            "moneda de pago y emisor para todos los bonos."
        )
        return pd.DataFrame(columns=["ticker", "ley", "moneda_pago", "underlying", "sector"])
    df = pd.read_csv(CONDICIONES_ESTATICAS_PATH, encoding="utf-8-sig", dtype=str)
    for col in ("ley", "moneda_pago", "underlying", "sector", "lamina", "calificacion"):
        if col not in df.columns:
            df[col] = None
    faltantes = [c for c in ("ticker", "ley", "moneda_pago") if c not in df.columns]
    if faltantes:
        log["alertas"].append(f"condiciones_estaticas.csv sin columnas {faltantes}: revisar el archivo.")
    return df


# ---------------------------------------------------------------------------
# Armado del universo
# ---------------------------------------------------------------------------
def submarket_a_clase(sub):
    return SUBMARKET_MAP.get(sub, (None, None))


def armar_universo(precios, yields_, cashflow, estaticas, log):
    if precios is None or len(precios) == 0:
        log["alertas"].append("Serie de precios vino vacia tras los reintentos: no se genero universo.")
        return pd.DataFrame(columns=COLUMNAS_RESUMEN)
    base = precios.copy()
    base["clase_activo"], base["tipo_tasa"] = zip(*base["submarket"].map(submarket_a_clase))
    sin_clasificar = base[base["clase_activo"].isna()]["submarket"].unique()
    if len(sin_clasificar):
        log["alertas"].append(
            f"Submercados sin mapeo conocido (revisar SUBMARKET_MAP en el script): {list(sin_clasificar)}"
        )

    base = base.rename(columns={"last_price": "lastPrice", "effective_volume": "effectiveVolume"})

    if yields_ is not None:
        cols_yield = ["ticker", "tir", "tna", "duration", "parity", "accured_interest"]
        cols_yield = [c for c in cols_yield if c in yields_.columns]
        base = base.merge(yields_[cols_yield], on="ticker", how="left")
        base = base.rename(columns={"parity": "paridad", "accured_interest": "interesCorrido"})
    else:
        for c in ("tir", "tna", "duration", "paridad", "interesCorrido"):
            base[c] = None

    if cashflow is not None:
        base = base.merge(cashflow, on="ticker", how="left")
    else:
        base["residualValue"] = None
        base["maturity"] = None

    estaticas_cols = estaticas.rename(columns={"ley": "law", "moneda_pago": "couponCurrency"})
    base = base.merge(
        estaticas_cols[["ticker", "law", "couponCurrency", "underlying", "sector",
                        "lamina", "calificacion"]],
        on="ticker", how="left",
    )

    # Ley, moneda de pago, lamina y calificacion son atributos de la EMISION:
    # AL30, AL30D y AL30C son el mismo bono en tres especies de liquidacion.
    # Si una especie tiene el dato cargado, las otras lo heredan. No inventa
    # nada: extiende un dato ya cargado (mismo patron que el sector por grupo
    # emisor). Si dos especies declaran valores DISTINTOS no se elige ninguno:
    # se alerta y esa emision queda como esta.
    #
    # Se limita a la renta fija: ley y calificacion son atributos de una
    # emision de deuda, y un CEDEAR puede compartir raiz de ticker con un bono
    # sin tener nada que ver con el (AALD es la especie MEP de un CEDEAR, no
    # una especie de bono). Propagar entre familias inventaria un dato.
    es_rf = ~base["clase_activo"].isin(CLASES_RENTA_VARIABLE)
    rf = base[es_rf]
    base["_raiz"] = segmentos.raiz_emision(base["ticker"])
    for col in ("law", "couponCurrency", "lamina", "calificacion"):
        por_raiz = rf[rf[col].notna()].groupby(base.loc[rf.index, "_raiz"])[col].agg(["nunique", "first"])
        contradictorias = por_raiz[por_raiz["nunique"] > 1]
        if len(contradictorias):
            log["alertas"].append(
                f"{col}: {len(contradictorias)} emisiones cuyas especies declaran valores "
                f"distintos ({', '.join(contradictorias.index[:5])}): no se propaga ahi."
            )
        unicas = por_raiz[por_raiz["nunique"] == 1]["first"]
        huecos = base[col].isna() & es_rf
        base.loc[huecos, col] = base.loc[huecos, "_raiz"].map(unicas)
        propagados = int((base.loc[huecos, col].notna()).sum())
        if propagados:
            log["propagaciones"] = log.get("propagaciones", {})
            log["propagaciones"][col] = propagados
    base = base.drop(columns=["_raiz"])
    # Un bono soberano ES el sector soberano por definicion: no hace falta que
    # este cargado en el CSV. Idem subsoberano (provincias y municipios).
    base.loc[base["sector"].isna() & (base["clase_activo"] == "bono_soberano"), "sector"] = "Soberano"
    base.loc[base["sector"].isna() & (base["clase_activo"] == "bono_subsoberano"), "sector"] = "Subsoberano"

    # Solo la renta fija tiene ley de emision: contar los CEDEARs aca inflaria
    # el pendiente con instrumentos a los que el dato no les corresponde.
    sin_ley = int((base["law"].isna() & es_rf).sum())
    if sin_ley > 0:
        log["alertas"].append(
            f"{sin_ley} instrumentos de renta fija sin ley/moneda de pago informada "
            "(no estan en data/condiciones_estaticas.csv — probablemente bonos nuevos "
            "o de un submercado que todavia no se cargo ahi)."
        )

    base["subtipo"] = None
    hd = base["tipo_tasa"] == "hard-dollar"
    base.loc[hd & base["law"].str.contains("N.Y", na=False), "subtipo"] = "global"
    base.loc[hd & base["law"].str.contains("Argentina", na=False), "subtipo"] = "bonar"

    # Soberanos: emisor fijo (no viene de ninguna fuente para este segmento)
    es_soberano = base["clase_activo"] == "bono_soberano"
    base.loc[es_soberano & base["underlying"].isna(), "underlying"] = "Gobierno Argentino"

    base["revisar"] = base["clase_activo"].isna()
    base["duplicado"] = base.duplicated(subset="ticker", keep=False)
    base["archivo_origen"] = "API Docta"

    universo = base[base["clase_activo"].notna()].copy()
    return universo[COLUMNAS_RESUMEN]


# ---------------------------------------------------------------------------
# Output: Excel + log (mismo formato que la v1)
# ---------------------------------------------------------------------------
def exportar(resumen, log):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    orden_clase = {c: i for i, c in enumerate(ORDEN_CLASES)}
    resumen = resumen.copy()
    resumen["_orden"] = resumen["clase_activo"].map(orden_clase)
    resumen = resumen.sort_values(["_orden", "tipo_tasa", "ticker"]).drop(columns="_orden")

    with pd.ExcelWriter(CONSOLIDADO_PATH, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="Resumen", index=False)
        for clase in ORDEN_CLASES:
            hoja = resumen[resumen["clase_activo"] == clase]
            if len(hoja):
                hoja.to_excel(writer, sheet_name=NOMBRE_HOJA[clase], index=False)
    log["output"] = CONSOLIDADO_PATH
    return resumen


def comparar_con_snapshot(resumen, log):
    actual = {}
    for clase in ORDEN_CLASES:
        tickers = resumen.loc[resumen["clase_activo"] == clase, "ticker"].dropna()
        if len(tickers):
            actual[clase] = sorted(set(tickers))

    anterior = {}
    if os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH, encoding="utf-8") as fh:
                anterior = json.load(fh)
        except Exception:
            anterior = {}

    for clase, tickers in actual.items():
        if clase not in anterior:
            continue
        previos = set(anterior[clase])
        altas = sorted(set(tickers) - previos)
        bajas = sorted(previos - set(tickers))
        if altas:
            log["altas"].append(f"{NOMBRE_HOJA[clase]}: {', '.join(altas)}")
        if bajas:
            log["bajas"].append(f"{NOMBRE_HOJA[clase]}: {', '.join(bajas)}")

    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as fh:
        json.dump(actual, fh, ensure_ascii=False, indent=1)


def escribir_log(log, resumen):
    ahora = datetime.now()
    lineas = [
        "=" * 70,
        f"CONSOLIDADOR DE UNIVERSO (API) — corrida {ahora:%d/%m/%Y %H:%M}",
        "=" * 70,
        "",
        "Instrumentos por clase:",
    ]
    for clase in ORDEN_CLASES:
        n = int((resumen["clase_activo"] == clase).sum())
        if n:
            lineas.append(f"  - {NOMBRE_HOJA[clase]}: {n}")
    lineas.append(f"  TOTAL: {len(resumen)}")

    if log.get("propagaciones"):
        lineas.append("")
        lineas.append("Datos heredados entre especies de la misma emision:")
        for col, n in log["propagaciones"].items():
            lineas.append(f"  · {col}: {n} tickers tomaron el dato de otra especie del mismo bono")

    if log["altas"]:
        lineas.append("")
        lineas.append("Altas vs. corrida anterior:")
        lineas.extend(f"  + {a}" for a in log["altas"])
    if log["bajas"]:
        lineas.append("")
        lineas.append("Bajas vs. corrida anterior:")
        lineas.extend(f"  - {b}" for b in log["bajas"])

    if log["alertas"]:
        lineas.append("")
        lineas.append("⚠ ALERTAS:")
        lineas.extend(f"  ! {a}" for a in log["alertas"])
    else:
        lineas.append("")
        lineas.append("Sin alertas.")

    lineas.append("")
    lineas.append(f"Output: {log.get('output', '(no generado)')}")
    texto = "\n".join(lineas)
    print(texto)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ruta_log = os.path.join(OUTPUT_DIR, f"log_{ahora:%Y-%m-%d_%H-%M-%S}.txt")
    with open(ruta_log, "w", encoding="utf-8") as fh:
        fh.write(texto + "\n")
    segmentos.podar_outputs("log_")
    print(f"Log guardado en: {ruta_log}")


def main():
    log = {"alertas": [], "altas": [], "bajas": []}
    env = cargar_env()
    if not env.get("DOCTA_API_TOKEN"):
        print("ERROR: falta DOCTA_API_TOKEN en .env")
        sys.exit(1)

    precios = cargar_serie_precios(env, log)
    if precios is None:
        print("ERROR: no se pudo obtener la Serie de precios (fuente base). Revisar alertas:")
        for a in log["alertas"]:
            print(f"  ! {a}")
        sys.exit(1)

    yields_ = cargar_yield_bonds(env, log)
    cashflow = cargar_cashflow_resumen(env, log)
    estaticas = cargar_condiciones_estaticas(log)

    resumen = armar_universo(precios, yields_, cashflow, estaticas, log)

    resumen = exportar(resumen, log)
    comparar_con_snapshot(resumen, log)
    escribir_log(log, resumen)


if __name__ == "__main__":
    main()
