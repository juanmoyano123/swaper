# Spec — Motor de Detección de Swaps (Opportunity B)

Segundo ciclo del proceso diseñado en `01-process-map.md` / `02-scorecard.md`. Construido sobre el universo consolidado que genera `tools/consolidar_universo.py` (Quick Win A).

## Resumen

**Nombre**: Motor de Detección de Swaps (`detectar_swaps`)

**Qué hace**: recorre el universo consolidado buscando instrumentos con rendimiento bajo (o los de una cartera provista por el usuario) y propone rotaciones hacia alternativas de mayor rendimiento o mejor perfil, dentro del mismo segmento comparable, cuantificando el diferencial de TIR, el cambio de duration, el costo de la operación y el tiempo de repago de la comisión.

**Lógica 100% determinística** (decisión del usuario en Fase 3): reglas y umbrales configurables, sin IA. El motor **propone**; la decisión final y el análisis crediticio profundo son del usuario.

## Reglas (derivadas de los ejemplos reales de la mesa — capturas de WhatsApp del 24/07/2026)

### Tipos de oportunidad

**Tipo A — Mejora de rendimiento** (caso PNDCO -4.7% → YM37O 3.6% / PN34O 3.7%):
- `tir_destino - tir_origen >= min_dtir` (default **0.5 pp**)
- `duration_destino <= duration_origen + max_mas_duration` (default **+1.5 años**)
- Mismo segmento comparable (ver abajo)

**Tipo B — Mejora de perfil** (caso TLCWO 5.6% → TLCMO 5.7%, mismo rendimiento pero Cable + más volumen + ley NY):
- Mismo emisor
- `tir_destino - tir_origen >= -0.1 pp` (rendimiento neutro o mejor)
- `duration_destino <= duration_origen + max_mas_duration`
- Y al menos una mejora concreta: pasa MEP→Cable, pasa ley ARG→NY, o volumen del destino ≥ 3× el del origen

### Segmentos comparables (no se cruzan entre sí)

| Segmento | Incluye | Métrica de rendimiento |
|---|---|---|
| `usd_hard` | ONs hard-dollar + soberanos hard-dollar + subsoberanos hard-dollar + **bopreales** (pedido explícito de la mesa) | TIR |
| `cer` | Soberanos CER | TIR |
| `tasa_fija` | Soberanos tasa fija (LECAP/BONCAP) | TNA |
| `dollar_linked` | Soberanos dólar-linked | TIR |
| `badlar` | Soberanos Badlar | TIR |

Cruces entre segmentos (ej. CER → hard-dollar) implican una visión de tipo de cambio/inflación: quedan como decisión humana, fuera del motor.

### Selección de instrumentos "origen"

- **Sin cartera**: se analizan los instrumentos con TIR bajo el umbral `umbral_origen` (default **0** = TIR negativa, como el disparador de la mesa: "corpo que tengan TIR baja o negativa").
- **Con cartera** (`data/cartera.csv`, columnas `ticker` y opcional `vn`/`monto`): se analizan todas las tenencias del usuario, tengan la TIR que tengan.
- Modo `--origen todos`: analiza todo el universo (para revisión exhaustiva).

### Costos y payback

- Arancel por pata: default **0.75%** (dato de la mesa), configurable. Rotación = 2 patas ≈ **1.5%** del monto.
- `payback_meses = (2 × arancel) / Δtir × 12` — en cuántos meses el diferencial de rendimiento recupera la comisión. Solo para Δtir > 0.
- Si la cartera trae `monto`, se estima la comisión en valor absoluto.
- El costo implícito del canje MEP→Cable (~4% según la mesa, variable) NO se suma automáticamente: se reporta la columna `pasa_a_cable` y el usuario lo pondera según la necesidad del cliente.

### Riesgo crediticio (sin ratings en la fuente)

- `mismo emisor` → "mismo riesgo crediticio" (swap más limpio).
- ON → soberano/bopreal o viceversa → "cambia riesgo corporativo↔soberano — verificar".
- Distinto emisor corporativo → "verificar calidad crediticia" (análisis interno del usuario, fuera del motor).

### Filtros de calidad

- Destinos sin precio o sin TIR/TNA parseable: excluidos.
- Filas con flag `revisar` del consolidador: excluidas como destino (pueden ser origen, con nota).
- Máximo `top_n` destinos por origen (default **3**, como presenta la mesa sus ideas).
- `--solo-balanz`: limita destinos a los marcados `disponible_balanz = "si"` (requiere whitelist real cargada).

## Input / Output

- **Input**: `data/output/universo_consolidado.xlsx` (correr antes `consolidar_universo.py`) + opcional `data/cartera.csv`.
- **Output**: `data/output/swaps_<fecha>.xlsx` con hojas "Oportunidades" (una fila por par origen→destino, con todos los diferenciales y flags) y "Parametros" (los umbrales usados en la corrida) + resumen en consola.

## Manejo de excepciones

- Consolidado inexistente → error claro pidiendo correr primero el consolidador.
- Cartera con tickers que no están en el universo → alerta por ticker, se sigue con el resto.
- Segmento sin candidatos → se informa, no es error.
- Sin oportunidades halladas → se informa explícitamente con los umbrales usados (puede ser que los umbrales estén estrictos, no que "no ande").

## Fuera de alcance (v1)

- Acciones, CEDEARs, opciones y FCI (variables distintas: volatilidad, tracking — otro ciclo).
- Swap entre segmentos (visión macro humana).
- Score crediticio automático (análisis interno del usuario).
- Cálculo del canje MEP/Cable en tiempo real (se reporta el flag, no el costo del día).
