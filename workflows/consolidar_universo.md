# Workflow — Consolidar Universo (v4, vía API)

## Objetivo

Generar `data/output/universo_consolidado.xlsx`: un único Excel con bonos soberanos, subsoberanos y ONs (todos los tipos de tasa) **más acciones locales y CEDEARs**, normalizados y clasificados. Es la base de datos sobre la que se hacen los análisis de swap y armado de carteras.

**Alcance: renta fija + renta variable.** Las acciones y los CEDEARs entran porque son la parte de renta variable de las carteras sugeridas por la mesa. **Los FCI no están**: ninguna de las fuentes actuales los publica (verificado — no hay submercado FCI en Docta ni cuotapartes en data912).

**Las dos familias no se mezclan.** Una acción no tiene TIR, duration ni cashflow, así que no es comparable con un bono. La frontera se aplica en un solo lugar, `segmentos.cargar_universo()`, que devuelve renta fija y nada más; quien necesite renta variable la pide con `segmentos.cargar_renta_variable()`. Por eso el armador y el swaper no se enteran del cambio.

**No hay descarga manual.** Todo sale de la API de Docta con el token guardado en `.env`.

## Inputs requeridos

1. **`.env`** con `DOCTA_API_TOKEN` y 3 links guardados:
   - `DOCTA_SERIE_PRECIOS_URL` — precio/volumen de Bonos, Acciones y CEDEARs (los tres vienen en la misma respuesta)
   - `DOCTA_YIELD_BONDS_URL` — TIR/TNA/duration/paridad de Bonos
   - `DOCTA_CASHFLOW_URL` — cupones (de ahí se deriva el valor residual actual y el vencimiento)
   - Si algún link vence o Docta cambia el token, hay que regenerarlo en Docta Terminal ("Generar Link") y reemplazarlo en `.env`.
2. **`data/condiciones_estaticas.csv`** (`ticker, ley, moneda_pago, underlying, sector`): la API no expone la ley de emisión, la moneda de pago del cupón ni el nombre del emisor — se mantiene a mano, cargado una vez desde un CSV de doctacapital.com. Cubre hoy 272 tickers (ONs y soberanos hard-dollar). **Instrumentos fuera de esta lista quedan sin ese dato** (se ve como `NaN`/"verificar" en vez de inventarse) — ampliar el archivo si hace falta más cobertura.

## Herramienta

```
python3 tools/consolidar_universo.py
```

Requiere `pandas` y `openpyxl`.

## Outputs

- `data/output/universo_consolidado.xlsx` — hoja **Resumen** + una hoja por clase (Soberanos, Subsoberanos, ONs Corporativos, Acciones, CEDEARs).
- `data/output/cashflow_completo.csv` — todos los pagos futuros de cada emisión (fecha, capital, interés, residual). Lo consumen `armar_cartera.py` y `detectar_swaps.py` para el análisis de cupones. **Sin este archivo ambos siguen funcionando, pero sin calendario de cobros.**
- `data/output/log_<fecha>.txt` — instrumentos por clase, altas/bajas vs. la corrida anterior, alertas.
- `data/output/.ultimo_universo.json` — snapshot interno, no tocar.

## Casos límite y comportamiento

- **La API devuelve 0 filas de forma transitoria**: el script reintenta automáticamente (2 intentos) antes de alertar.
- **Cambia el schema de un link** (columna esperada ausente): se alerta explícito, esa fuente se saltea, el resto sigue.
- **Ticker sin ley/moneda/emisor en `condiciones_estaticas.csv`**: queda `NaN`, nunca se infiere del ticker.
- **Valor residual actual**: se deriva del cashflow — residual del último cupón ya pagado (o 100% si todavía no pagó nada).
- **Sin fuente de precios base**: el script corta con error claro, no genera un consolidado vacío.

## Alcance

**Renta fija + acciones locales y CEDEARs.** La serie de precios de Docta trae las tres familias juntas y las tres entran: 125 soberanos, 47 subsoberanos, 765 ONs, 69 acciones y 683 CEDEARs.

Lo que queda afuera:

- **FCI** — ninguna fuente actual publica el valor de cuotaparte. Las carteras de la mesa los incluyen (Balanz Estrategia 1, Ahorro Dólar, Renta Fija Global), así que aparecen como línea con su peso pero sin precio. Cerrarlo requiere una fuente nueva.
- **Opciones** — fuera de alcance.

**Los CEDEARs cotizan en pesos.** Para expresarlos en dólares hay que usar `segmentos.tipo_cambio_implicito()`, que deriva el MEP del propio universo de bonos. No se toma un tipo de cambio de afuera.

## La API devuelve 0 filas de forma errática

**No es una regla de fechas ni de días hábiles: es inestabilidad del endpoint.** La misma consulta que responde vacía trae datos segundos después (medido: `fromDate=24/07` devolvió 0 y al rato 1.660 filas). Por eso el script reintenta 5 veces con espera creciente.

Además, el link que genera Docta trae la fecha del día en que se creó **hardcodeada** en `fromDate`. El script la reescribe a una ventana móvil de 15 días en cada corrida — sin eso el pipeline se rompía en silencio a medida que el link envejecía.

## Si la API devuelve HTTP 500 "Error al verificar el token"

El token venció (los 3 links comparten el mismo). Un 401 "Token inválido" sería otra cosa: token inexistente. Regenerar UN link en Docta Terminal → "Generar Link" y actualizar `.env`; el token nuevo sirve para los tres.

El link de cashflow tiene que incluir sí o sí las columnas `capital`, `interest_amount` y `cash_flow`, además de `ticker`, `payment_date` y `residual_value`: sin ellas no se puede separar renta de amortización.

## Próximo paso del proyecto

Los dos pilares están construidos. Pendiente: columna `sector` en `condiciones_estaticas.csv` para habilitar el límite de concentración por sector.
