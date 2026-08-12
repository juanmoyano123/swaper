# Plan: F-035 — Costo real de rotar y aviso de cupón próximo

## Contexto

F-032 (tanda 12) dejó el motor de rotaciones sin el bloque de costo/spread/payback, con la alerta
`costo_rotacion_no_calculado` viajando siempre para dejarlo explícito. F-035 (tanda 13) lo cierra:
cada candidata trae ahora arancel + spread bid/ask desagregado por pata, el total, si es elevado
(>5%) y el payback en meses — o, si a alguna pata le falta punta viva, un costo `verificable=false`
en vez de un número inventado (regla 1/11 del dominio: nunca se asume un spread por defecto). El
aviso de cupón próximo ya lo calculaba `frecuencia.py::proximo_cupon`; sólo faltaba exponer la
`fecha` en el bloque `cupon` del contrato.

## Archivos nuevos

- **`backend/app/rotaciones/costos.py`** — módulo puro, sin I/O. `spread_pct(px_bid, px_ask)`
  calcula el spread como % del punto medio, `None` si falta una punta, si están cruzadas, o si la
  relación ask/bid alcanza `MAX_RELACION_PUNTAS` (puntas en escalas distintas). `CostoRotacion`
  (dataclass frozen+slots) con `como_dict()`. `calcular_costo(spread_origen, spread_destino,
  d_rend_pp)` arma el costo o, si falta cualquiera de los dos spreads, devuelve
  `verificable=False` con todo lo demás en `None` — la divergencia deliberada contra
  `tools/mercado.py::costo_rotacion`, que cuenta un spread faltante como cero y da un costo
  "piso". El docstring del módulo documenta la divergencia.

- **`backend/app/rotaciones/puntas.py`** — `leer_puntas(conn, tickers)` trae la última punta por
  ticker con el mismo molde LATERAL de `renta_variable/lectura.py`, adaptado para arrancar de
  `unnest($1::text[])` en vez de una vista de universo (acá no hay una de la que colgar el
  LATERAL). Una fila con `fuente` terminada en `-arrastre` se trata como sin punta viva.

## Archivos modificados

- **`backend/app/rotaciones/constantes.py`** — `ARANCEL_POR_PATA = 0.0075`,
  `UMBRAL_COSTO_ELEVADO = 0.05`, `MAX_RELACION_PUNTAS = 3.0`.

- **`backend/app/rotaciones/motor.py`** — `Candidata` gana `costo: CostoRotacion | None = None` y
  `cupon_fecha: date | None = None` (al final, con default, para no romper construcciones
  existentes). `evaluar_par` ahora setea `cupon_fecha` desde el mismo `proximo_cupon(...)` que ya
  calculaba `cupon_dias`/`cupon_pct` — no se recalcula nada. `como_dict()` agrega `"fecha"` al
  bloque `cupon` (ISO o `null`, presente siempre que `cupon_dias` no sea `None`, sin depender de la
  ventana de aviso de 45 días que sólo gobierna `cupon_nota`) y agrega la clave `"costo"`. El motor
  sigue puro: `Candidata.costo` sale `None` de `evaluar_par`/`detectar`, y lo completa
  `servicio.py` después de leer las puntas (es I/O). Docstring del módulo actualizado para
  reflejar que el bloque de costo ya existe, con la nota de la divergencia.

- **`backend/app/rotaciones/servicio.py`** — borrados `_alerta_costo_no_calculado` y
  `CODIGO_COSTO_NO_CALCULADO`. Después de `detectar()`, junta los tickers de todas las candidatas
  (origen ∪ destino), llama a `leer_puntas`, y por cada candidata arma su `CostoRotacion` vía
  `calcular_costo(spread_pct(bid_o, ask_o), spread_pct(bid_d, ask_d), candidata.d_rend_pp)` y la
  reemplaza con `dataclasses.replace`. Si alguna queda `verificable=False`, agrega la alerta nueva
  `costo_no_verificable` (ADVERTENCIA) listando los pares afectados en `detalle`. Agrega
  `"arancel_pct_por_pata"` al bloque `parametros` de `ResultadoRotaciones.como_dict()`.

- **`backend/app/api/v1/rotaciones.py`** — sólo el docstring del endpoint, para reflejar que las
  candidatas ya traen costo y que la alerta relevante ahora es `costo_no_verificable`.

## Decisión de diseño: unidades del payback

`Candidata.d_rend_pp` ya está en **puntos porcentuales** (`round(d_rend_fracción * 100, 2)`), no en
fracción. La fórmula del CLI es `payback = costo_fracción / d_rend_fracción * 12`. Como
`total_pct` (nuestro costo, en %) y `d_rend_pp` comparten el mismo factor 100 respecto de sus
versiones en fracción, ese factor se cancela en el cociente: `payback_meses = round(total_pct /
d_rend_pp * 12, 1)` da exactamente el mismo resultado que la fórmula del CLI, sin tener que
reconvertir unidades. Verificado en `test_rotaciones_costos.py` contra
`tools/mercado.py::costo_rotacion`.

## Contrato del bloque `costo` (JSON)

```json
"costo": {
  "arancel_pct_por_pata": 0.75,
  "spread_origen_pct": 1.23,
  "spread_destino_pct": 0.87,
  "total_pct": 2.55,
  "verificable": true,
  "elevado": false,
  "payback_meses": 15.3
}
```

Nota: el ejemplo de `total_pct` en la spec original de la tarea (3.10) no cerraba aritméticamente
contra la fórmula textual que la misma spec describe (`2*arancel_frac*100 + spread_o/2 +
spread_d/2`). Se implementó la fórmula textual — que es también la que reproduce
`tools/mercado.py::costo_rotacion` bajo test de paridad — y no el número de ejemplo, que se leyó
como ilustrativo y no como valor de referencia a reproducir.

## Tests

- `backend/tests/test_rotaciones_costos.py` (nuevo, propio de esta feature): `spread_pct` con
  punta faltante/cruzada/cero/relación excesiva; paridad numérica contra
  `tools.mercado.costo_rotacion`; la divergencia explícita (CLI da piso, acá da
  `verificable=False`); `elevado` en el borde exacto de 5% (`>`, no `>=`); `payback_meses` con
  `d_rend_pp <= 0` → `None`.
- `backend/tests/test_rotaciones_motor.py`: `costo` es `None` al salir del motor puro;
  `cupon_fecha` viaja en la candidata y en `como_dict()["cupon"]["fecha"]`.
- `backend/tests/test_rotaciones_api.py`: el fake de conexión ahora también despacha el SQL de
  `leer_puntas` (dispatch por `"public.puntas" in query`, con un parámetro `puntas` nuevo en el
  fixture). Casos: candidata con las dos patas con punta → `costo.verificable=true`; sin puntas →
  `verificable=false` + alerta `costo_no_verificable`; fila con `fuente` de arrastre tratada como
  sin punta; la alerta vieja `costo_rotacion_no_calculado` ya no aparece nunca; el contrato de
  claves de la candidata (incluye `"costo"`) y del bloque `costo` mismo.
- `backend/tests/test_rotaciones_paridad_motor.py`: sin cambios de lógica — sólo se actualizó el
  docstring de la divergencia declarada (el motor puro sigue sin calcular costo; lo hace
  `servicio.py`, fuera del alcance de este test).

Suite completa: `cd backend && python -m pytest` → **1104 passed, 98 deselected**.

## Desvíos del plan original

Ninguno funcional. Los dos ajustes fueron de forma:

1. La query de `leer_puntas` no puede colgarse de una vista de universo (no hay una acá), así que
   el LATERAL arranca de `unnest($1::text[])` en vez de la tabla base que usa
   `renta_variable/lectura.py` — mismo patrón LATERAL, distinto punto de partida.
2. El número de ejemplo del contrato JSON (`total_pct: 3.10`) no era consistente con la fórmula
   textual dada en la misma spec; se priorizó la fórmula (y su paridad verificada contra el CLI)
   por sobre el número de ejemplo.
