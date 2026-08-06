# Workflow — Armar Cartera de Renta Fija

## Objetivo

Construir una propuesta de cartera de bonos soberanos, subsoberanos y ONs según el perfil del cliente, priorizando que la cartera **cobre renta todos los meses**.

## Inputs requeridos

1. **`data/output/universo_consolidado.xlsx`** — correr antes `python3 tools/consolidar_universo.py`.
2. **`data/output/cashflow_completo.csv`** — sale de la misma corrida. Si falta, la herramienta funciona igual pero sin calendario de cobros (lo avisa).

## Herramienta

```bash
python3 tools/armar_cartera.py --monto 100000
python3 tools/armar_cartera.py --monto 50000 --perfil conservador --horizonte corto
python3 tools/armar_cartera.py --monto 80000 --cobertura devaluacion
python3 tools/armar_cartera.py --monto 80000 --mix "usd_hard=60,cer=40"
```

**Parámetros principales**

| Flag | Qué hace |
|---|---|
| `--monto` | Obligatorio. Monto total a invertir |
| `--perfil` | `conservador` / `moderado` (default) / `agresivo`. Define exigencia de calidad: tope de rendimiento, liquidez mínima y concentración máxima |
| `--horizonte` | `corto` (0-2 años) / `medio` (1,5-5) / `largo` (4+). Rango de duration objetivo |
| `--moneda` | `usd` / `ars` / `todas` (default) |
| `--cobertura` | `devaluacion` / `inflacion` / `tasa-pesos` / `mixta`. Define el mix de segmentos |
| `--mix` | Mix manual, ej. `"usd_hard=60,cer=40"`. Tiene prioridad sobre `--cobertura` |
| `--n-total` | Cantidad objetivo de posiciones (default 15) |
| `--sin-pago-mensual` | Desactiva la priorización de cobertura mensual: elige solo por rendimiento |
| `--max-emisor` / `--max-soberano` / `--max-sector` | Sobreescriben los topes de concentración del perfil |

## Outputs

`data/output/cartera_<perfil>_<horizonte>_<fecha>_<hora>.xlsx` con 6 hojas:

- **Cartera** — una fila por posición: ticker, emisor, segmento, rinde, duration, vencimiento, ley, moneda de pago, % y monto
- **Resumen** — duration ponderada, rendimiento **abierto por naturaleza de tasa**, riesgo soberano agregado, renta esperada a 12 meses, y aperturas por segmento y por emisor
- **Calendario** — cobros mes a mes de los próximos 12 meses, separando renta de amortización
- **Alertas** — todo lo que no cerró en esta corrida
- **Leyenda** — qué significa cada columna
- **Parametros** — los umbrales usados

**Poda automática**: se conservan las últimas 10 carteras; las más viejas se borran solas en cada corrida (`segmentos.podar_outputs`). El universo y el cashflow nunca se tocan.

## Lógica de armado

1. **Mix por segmento**: del `--cobertura`, del `--mix` manual, o el default mixto.
2. **Filtro de candidatos** por segmento: horizonte (duration), perfil (tope de rendimiento como proxy de distress, percentil de liquidez), rendimiento mínimo.

   La segmentación y la carga del universo viven en `tools/segmentos.py`, **compartidas con el motor de swaps** — una sola definición para los dos pilares.

   El **percentil de liquidez** se calcula sobre el monto operado llevado a dólares. Es importante: `effectiveVolume` viene en la moneda de cotización de cada especie, así que la especie en pesos de un bono muestra ~1.500× más volumen que su especie en dólares por el tipo de cambio, no por operarse más. Con los números crudos el filtro descartaba sistemáticamente las especies en dólares (sobrevivía el 98% de las especies en pesos contra el 63% de las MEP), o sea que filtraba por moneda de cotización en vez de por liquidez. El tipo de cambio se deriva del propio universo: la misma emisión cotiza en las dos puntas y ese cociente es el MEP del día.

   Antes de todo eso, `segmentos.py` descarta los instrumentos cuyo rendimiento **no puede ser cierto** (una especie que declara una TIR incompatible con las otras especies del mismo bono, o que supera el techo de lo posible para su segmento). No es criterio económico, es integridad del dato, y cada corrida alerta cuáles fueron.
3. **Selección con control de concentración GLOBAL** — un emisor puede aparecer en varios segmentos, así que limitarlo dentro de cada segmento por separado no acota nada.
4. **Desempate por calendario**: entre candidatos que rinden dentro de 0,5pp del mejor, gana el que suma un mes de cobro todavía descubierto.
5. **Reponderación** si algún segmento quedó corto, y verificación post-hoc de los topes.

## Casos límite y comportamiento

- **Concentración sectorial**: tope por sector económico (30/40/55% según perfil). Soberano y Subsoberano quedan **exentos** — ya los acota `max_soberano`, contarlos dos veces no aporta. Las posiciones sin sector cargado quedan fuera del límite: no se acota lo que no se conoce, y se avisa cuántas son.
- **Riesgo soberano**: el Tesoro emite bajo muchos prefijos (GD, AE, DIC, TZX, TY3…) y **todos son el mismo riesgo de crédito**. Se agrupan bajo una clave única `SOBERANO_AR`, con su propio tope (`max_soberano`), separado del tope corporativo. Sin esto una cartera 100% soberana pasaba como diversificada.
- **Especies de liquidación**: MR46O/MR46D/MR46C son la misma emisión. Se colapsan por raíz del ticker para no duplicar posiciones (con chequeo de consistencia de duration).
- **Segmento sin candidatos suficientes**: cada posición conserva el peso con el que se validó contra los topes; el sobrante se redistribuye proporcionalmente. **No** se reparte el peso completo del segmento entre menos posiciones — eso inflaba cada una por encima del límite ya verificado.
- **Cobertura de inflación**: el universo CER argentino es casi íntegramente soberano, así que esa cartera siempre va a superar el tope. Sale con alerta explícita: no hay forma de diversificar crédito dentro de CER con el universo disponible.
- **Monto chico**: alerta si alguna posición queda por debajo de 1.000 y sugiere un `--n-total` acorde.
- **Sin cashflow**: arma igual, avisa que no pudo priorizar cobertura mensual.

## De dónde sale el sector

`data/condiciones_estaticas.csv`, columna `sector`. Se completa en tres pasos, ninguno inventa dato:

1. **Soberanos y subsoberanos** — se derivan de `clase_activo`: un bono del Tesoro *es* el sector soberano por definición.
2. **Corporativos cargados** — 68 emisores clasificados por actividad conocida de la empresa, con la taxonomía que usás en tu Excel (`Propuesta Base 7-26`). 14 de ellos vienen literalmente de ahí; el resto es propuesta a revisar.
3. **Propagación por emisor** — si un ticker del grupo tiene sector, los demás del mismo prefijo son el mismo emisor y por lo tanto el mismo sector.

Cobertura actual: 423 de 927 instrumentos del universo (46%). Para ampliarla, agregar filas al CSV.

## Lo que NO contempla

- **Calificación crediticia** — no está en la fuente; el análisis crediticio es del usuario
- **Lámina mínima** — los montos por posición no están ajustados a lámina operable
- **Bonos ajustables** — el calendario proyecta con el coeficiente CER/dólar de hoy; el nominal futuro va a diferir
