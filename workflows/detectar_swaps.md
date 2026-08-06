# Workflow — Detectar Swaps

## Objetivo

Proponer rotaciones de instrumentos (swaps) con datos duros: instrumentos de rendimiento bajo → alternativas de mayor TIR o mejor perfil (moneda de pago, ley, liquidez) dentro del mismo segmento comparable, con costo de la operación y payback cuantificados. **El motor propone; la decisión y el análisis crediticio profundo son del usuario.**

## Prerrequisito

Correr primero el consolidador (ver `workflows/consolidar_universo.md`):

```
python3 tools/consolidar_universo.py
```

## Uso

```
python3 tools/detectar_swaps.py                        # origenes = TIR negativa (default)
python3 tools/detectar_swaps.py --origen todos         # analiza todo el universo
python3 tools/detectar_swaps.py --cartera data/cartera.csv   # analiza tenencias propias
```

Si existe `data/cartera.csv` (columnas: `ticker`, opcional `monto`) se usa automáticamente como origen; `--sin-cartera` lo ignora.

### Parámetros (defaults calibrados con los criterios reales de la mesa)

| Flag | Default | Qué controla |
|---|---|---|
| `--min-dtir` | 0.5 pp | Mejora mínima de rendimiento para swap tipo A |
| `--max-mas-duration` | 1.5 años | Máximo estiramiento de duration |
| `--umbral-origen` | 0 % | TIR bajo la cual un instrumento es candidato a rotar |
| `--umbral-neutro` | -0.3 pp | Pérdida tolerada en swaps de perfil (tipo B) |
| `--arancel` | 0.75 % | Arancel por pata (rotación = 2 patas) |
| `--factor-volumen` | 3× | Volumen extra para contar "mejora de liquidez" (medido en dólares, ver más abajo) |
| `--percentil-liquidez` | 25 | Excluye como destino a los que quedan bajo ese percentil de volumen operado (en USD) **dentro de su segmento**. El 25 es el mismo default del perfil moderado del armador. `0` lo desactiva. Solo filtra destinos: los orígenes ilíquidos se analizan igual. Con menos de 10 candidatos en el segmento no se aplica (sale alerta: revisar el volumen a mano) |
| `--min-rend` | 0 % | Rendimiento mínimo para proponer un destino, en la unidad de cada segmento — mismo flag que el armador. Evita rotar hacia una TIR negativa |
| `--tope-distress` | `usd_hard=15` | Tope de rendimiento **por segmento**: los destinos por encima se excluyen. Ver "El tope anti-distress" |
| `--max-rend-destino` | — | Tope único para TODOS los destinos; anula los topes por segmento |
| `--percentil-distress` | 95 | Marca (no excluye) al destino que cae en la cola alta de su segmento |
| `--frecuencia-cupon` | — | Solo propone destinos que paguen renta con esa frecuencia |
| `--escenarios-tir` | `-500,…,+200` | Movimientos de TIR (bps) para la hoja de sensibilidad |
| `--sin-spread` | — | No consulta las puntas de data912; el costo de rotar queda solo con el arancel |
| `--top-n` | 3 | Destinos propuestos por origen **por tipo** (A y B no compiten por cupo) |

## Tipos de oportunidad

- **A — mejora de rendimiento**: Δrend ≥ min-dtir, duration similar, mismo segmento. (Caso mesa: PNDCO -4.4% → PN34O 4.1% / YM37O 3.7% — el motor reproduce esta propuesta.)
- **B — mejora de perfil**: mismo emisor, rendimiento neutro, pero gana Cable, Ley NY o volumen. (Caso mesa: TLCWO → TLCMO, mismo riesgo, →Cable →Ley NY +volumen — también reproducida.)

## Segmentos (no se cruzan)

La segmentación vive en `tools/segmentos.py`, **compartida con el armador de carteras**: una sola definición para los dos pilares.

`usd_hard` (hard-dollar y bopreales) · `cer` · `tasa_fija` (usa TNA) · `dollar_linked` · `badlar` · `tamar`

Se clasifica **solo por tipo de tasa**. Que un instrumento sea del Tesoro, de una provincia o una ON es riesgo de crédito, no naturaleza de tasa, así que no define con quién es comparable: un Tamar provincial y un Tamar corporativo se miden con la misma vara, y la diferencia de riesgo se resuelve en `riesgo_nota` y en los topes de concentración. Cruces entre segmentos = visión macro humana, fuera del motor.

**Qué queda afuera y por qué.** Acciones, CEDEARs, FCI y opciones están fuera de alcance por decisión de diseño. Ya no se descartan en silencio: cada corrida alerta cuántos tickers quedaron fuera y de qué clase.

## Frecuencia de cobro de cupones

Cada propuesta informa cada cuánto paga renta el bono que sale y el que entra: mensual, bimestral, trimestral, semestral, anual, o "al vencimiento" cuando queda un solo cobro. Se mide sobre los pagos **futuros** — lo que efectivamente cobra quien compra hoy.

- `--frecuencia-cupon mensual|bimestral|trimestral|semestral|anual`: filtra los destinos a esa frecuencia.
- **Sin el flag**, entre destinos parejos en rendimiento (dentro de 0,5 pp, el mismo umbral con el que la mesa decide si una diferencia justifica mover) se prioriza al que paga más seguido.
- Requiere `data/output/cashflow_completo.csv`. Sin él la columna queda vacía y el motor avisa.

## El tope anti-distress

Un destino que rinde muy por encima de sus pares **no suele ser una oportunidad**: es el mercado pidiendo prima porque duda del cobro. Comprar el extremo de la curva no es ganar tasa, es comprar el riesgo que esa tasa está pagando. Por eso el motor tiene dos capas, y la que decide sos vos:

1. **Tope duro por segmento** (`--tope-distress "usd_hard=15,tamar=60"`): los destinos por encima del número **se excluyen**. Viene con un solo default cargado, `usd_hard=15%`, que es el valor calibrado con la mesa. Los segmentos en pesos vienen **sin tope**, porque ahí una TNA de 40% es tasa normal y no señal de nada — poner un número inventado sería peor que no poner ninguno. El flag se suma a los defaults en vez de reemplazarlos; `usd_hard=none` lo quita.
2. **Marcador informativo** (`--percentil-distress`, default 95): los destinos en la cola alta de su propio segmento salen señalados como "posible distress" pero **no se descartan**. Se define por percentil y no por un múltiplo de la mediana porque el múltiplo ignora la dispersión: en hard-dollar la mediana es 6,3% y 1,5 veces esa mediana marcaba como sospechoso a cualquier corporativo de 10%, que es tasa normal para el crédito corporativo local.

Cada corrida deja los topes efectivos en la hoja "Parametros".

## Premio por legislación

Cuando un swap cambia de ley, el reporte dice cuántos bps de tasa cuesta o paga ese cambio, y **contra qué vara**. La hoja "Premio por legislacion" arma la referencia: cuánto más rinde hoy un Ley Argentina que un Ley N.Y. **del mismo emisor** y duration comparable.

La restricción a mismo emisor es lo que hace que el número signifique algo. Comparar una ON en distress al 55% contra un Global al 5% da un spread de 5.000 bps que no es premio por ley: es riesgo de crédito. Solo cuando el deudor es el mismo (AL30 contra GD30, los dos del Tesoro) lo único que queda variando es la legislación.

Así, un swap que resigna 138 bps por pasar a Ley N.Y. cuando la mediana de la curva es 78 bps está pagando la ley cara, y eso se ve en la columna "vs. mediana de la curva".

El motor también avisa cuando un swap **empeora** la ley (N.Y. → Argentina), cosa que antes pasaba sin mención.

## Sensibilidad a compresión de TIR

La hoja "Sensibilidad" muestra cuánto se movería el precio de cada instrumento propuesto si su TIR comprimiera o se abriera. Se calcula **descontando todos los flujos contractuales a la tasa nueva**, no por aproximación de duration: en bonos largos la aproximación lineal subestima fuerte la suba ante compresiones grandes, que son justo los escenarios que interesan.

Es un movimiento instantáneo de precio: no incluye el cupón que se cobra en el camino.

## Output

- Consola: resumen por origen en formato "idea de swap" (como las publica la mesa).
- `data/output/swaps_<fecha>.xlsx`: hoja "Oportunidades" (todos los pares con diferenciales, flags y nota de riesgo) + hoja "Parametros" (umbrales usados, para trazabilidad).
- **Poda automática**: se conservan los últimos 10 `swaps_*.xlsx`; los más viejos se borran solos (ídem carteras y logs). El universo y el cashflow nunca se tocan.

## Chequeo de cupón próximo

Antes de proponer una rotación, el motor mira si el bono que SALE cobra cupón pronto. Vender antes del pago resigna ese cobro, y en varios casos reales el cupón resignado supera la mejora que aporta el swap.

- `--dias-cupon N` (default 45): dentro de ese plazo, el swap sale con aviso.
- **No bloquea**: la propuesta aparece igual, con los días al cupón y el % del capital que se resigna, para poder compararlo contra el payback de la comisión.
- Requiere `data/output/cashflow_completo.csv`. Sin ese archivo el motor sigue funcionando, sin el chequeo.

Ejemplo real: `AEC2D` paga cupón en 36 días y resigna **3,28% del capital**, contra un payback de comisión de 1,5 meses. Conviene esperar al cobro y recién después rotar.

## El costo real de rotar

Rotar no cuesta solo el arancel. Se vende contra el bid y se compra contra el ask, así que cada pata resigna media punta de spread. El motor ahora suma las dos cosas:

```
costo = 2 patas de arancel  +  spread_origen/2  +  spread_destino/2
```

El efecto es grande: el costo mediano de las rotaciones detectadas pasó de **1,50%** (solo arancel) a **3,10%**, y 12 de 51 superan el 5%. Antes el motor proponía swaps que en la práctica no convenían, porque el payback estaba calculado sobre la mitad del costo.

Las puntas salen de **data912.com**, una API pública sin token (`tools/mercado.py`). Cobertura: 674 de 927 instrumentos. Donde falta el spread, el costo devuelto es un **piso**, no el costo completo — las columnas de spread dejan ver cuándo pasa. Si la API no responde, la corrida sigue con el arancel solo y avisa.

> **De dónde salen ley, moneda, calificación y lámina.** No los da la API de Docta. Se cargan a `data/condiciones_estaticas.csv` desde el export de ONs del monitor de mesa (botón "Exportar Excel") con `tools/merge_condiciones.py`, que solo completa huecos y **vacía los valores que se contradicen entre especies del mismo bono**, dejándolos en `data/conflictos_condiciones.csv` para revisión manual. Es una extracción puntual, no una conexión: la herramienta nunca consulta el monitor al correr.

> **Qué NO aporta data912.** Precios. Se verificó: 572 de 576 tickers coinciden con Docta con menos de 0,1% de diferencia — las dos fuentes leen BYMA. Y donde Docta no publica precio es porque el instrumento no opera: de los 145 tickers que solo aparecen en data912, apenas 6 registraron operaciones, contra el 92% de los que Docta ya cubre. Recalcular una TIR sobre un precio que nadie convalidó sería inventar tasa, no medirla.

## Interpretación y límites

- `Recupera el costo en (meses)`: en cuántos meses el diferencial de rendimiento paga el costo total de rotar. No incluye el costo del canje MEP↔Cable (variable diaria): la columna `pasa_a_cable` lo señala y el usuario lo pondera.
- `riesgo_nota`: cuando el swap cambia de emisor y las dos puntas tienen calificación cargada, el salto de rating sale explícito (`[AAA(arg) → CCC+ (Fitch)]`). La calificación **no filtra**: se muestra para que decidas.
- `riesgo_nota` (base): "mismo emisor" = swap limpio; el resto exige el análisis crediticio interno del usuario. Distingue **soberano / subsoberano / corporativo**: cambiar de categoría cambia el tipo de riesgo, no solo el nombre del deudor. Esto se volvió necesario al abrir la segmentación — antes los segmentos en pesos eran 100% soberanos por construcción y el cruce no podía darse.
- **Mismo emisor** se determina por prefijo del ticker (la clave de riesgo del armador), no por el nombre del emisor: el nombre viene cargado en la mitad de los casos y con él se perdían las rotaciones entre especies de todos los tickers sin `underlying`. El Bopreal se separa del Tesoro porque lo emite el BCRA.
- "Sin oportunidades" con umbrales estrictos NO es un error del motor: el log lo dice explícitamente y sugiere relajar flags.

## Aprendizajes

- Los destinos con TIR desorbitada (ej. 245% en hard-dollar) son distress/precio roto, no oportunidades — de ahí el tope de sanidad de 15% en el segmento USD.
- No se filtra por disponibilidad en Balanz: al ser una ALyC de 20+ años, prácticamente todo lo negociable en Argentina está ahí — ese cruce no aportaba información real y se sacó.

## Pendiente

La segmentación de este motor es más angosta que la de `armar_cartera.py`: deja afuera Tamar, ONs dólar-linked y subsoberanos no hard-dollar (37 instrumentos). Conviene unificar ambas en `asignar_segmento`.
