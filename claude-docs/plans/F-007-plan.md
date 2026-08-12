# Plan: F-007 — Consolidador multi-fuente con precedencia por campo

## Contexto

F-007 es **el primer escritor del backend**: toma las salidas ya construidas de F-004 (BYMA,
`ingerir_rueda` → `ResultadoRueda`), F-005 (IAMC, `parsear_informe` → `ResultadoInforme`) y F-006
(Docta, `ingerir_cashflow` → `ResultadoCashflow`) y puebla `instrumentos`, `precios`, `puntas` y
`cashflow` con la precedencia por campo declarada en la spec (`claude-docs/planning/plan.md:385-423`).
Reemplaza a `tools/consolidar_universo.py` conservando el contrato de las 21 columnas del Resumen —
hoy la vista `resumen` — que el motor (`tools/segmentos.py`, `cupones.py`, `mercado.py`) debe leer
sin modificación (GWT-4).

Hallazgos de la exploración que condicionan el diseño:

1. `ResultadoRueda.especies` aplana los 4 endpoints y pierde cuál declaró cada fila — y el endpoint
   es el dato que determina la clase de activo.
2. BYMA repite ticker por plazo de liquidación (settlementType "1"/"2"): 5.761 filas vs ~1.700
   especies del universo viejo. Sin colapso, el upsert de `instrumentos` rompe ("cannot affect row
   a second time").
3. El esquema no tiene columnas para todo lo que la spec asigna: faltan `estructura_cupon`,
   `moneda_cotizacion` y `plazo_liquidacion` en `instrumentos`, y `convexidad` en `precios`.
4. La vista `resumen` toma UNA fila de `precios` por ticker (LATERAL LIMIT 1): si BYMA e IAMC
   escribieran filas separadas, la última pisaría a la otra. La fila de la corrida tiene que ser
   la consolidada.
5. IAMC declara `moneda_pago` como "USD"/"ARS" pero el CHECK de `coupon_currency` sólo admite
   MEP/CCL. **Decisión del usuario (2026-08-06): ampliar el dominio** — se guarda lo que IAMC
   declara tal cual; F-009 refina el grueso (USD) al fino (MEP/CCL) con el CSV curado.

## Decisiones de diseño

### D1 — La fila de `precios` es la consolidada de la corrida; `fuente` registra la composición
Cada columna tiene exactamente una fuente declarada en código: `last_price` y `effective_volume`
sólo de BYMA; `tir`, `duration`, `paridad`, `convexidad`, `residual_value` sólo de IAMC; `tna` sin
fuente en F-007 (NULL siempre, degradación declarada — era del Rendimiento de Bonos de Docta, que
ya no se consume). `fuente` vale `'byma'`, `'iamc'` o `'byma+iamc'` según qué aportó a la fila.
La migración reescribe el COMMENT de `precios.fuente` con esta semántica (el actual dice "no
mezclar fuentes en una fila", que quedó en tensión con la vista).

### D2 — `clase_activo`: el endpoint la declara; public-bonds se clasifica con el `type` de Docta
- `negociable-obligations` → `on_corporativo` · `cedears` → `cedear` · `general-equity` → `accion`.
- `public-bonds` mezcla soberanos y subsoberanos sin discriminador verificado en BYMA → se cruza la
  **raíz** del ticker contra el `type` del cashflow (que ES el submarket, columna contractual ya
  persistida) con el `SUBMARKET_MAP` portado literal de `tools/consolidar_universo.py:62-85`.
- Fila de public-bonds sin raíz en el cashflow o con `type` fuera del mapa: **no entra a
  `instrumentos` ni `precios`** (paridad con el motor viejo, que descartaba clase nula), alerta
  nueva `clase_sin_mapeo` con valores y conteo; **sus puntas sí se escriben** (sin FK, a propósito).
  `clase_activo` es NOT NULL: inventar una clase violaría la regla 1.
- Conflicto endpoint vs. type: gana el endpoint de BYMA, se alerta la discrepancia.

### D3 — `tipo_tasa`: del `type` del cronograma, por raíz, con el mismo mapa
`tipo_tasa = SUBMARKET_MAP[type][1]` para renta fija; `None` para acción/CEDEAR (los deja fuera del
armador, correcto). Raíz sin cashflow → NULL + cobertura faltante. Nunca se adivina del ticker.

### D4 — Herencia por raíz desde IAMC (GWT-1)
Cada especie de BYMA hereda de la fila IAMC con la misma raíz: `law` ← `ley` (ya canónica),
`coupon_currency` ← `moneda_pago` (tal cual, CHECK ampliado), `underlying` ← `emisor`,
`estructura_cupon` ← `estructura_cupon` (columna nueva). Semántica portada de
`consolidar_universo.py:385-409`: **sólo renta fija**, **sólo llenar huecos** (COALESCE en el
upsert), **conflicto entre filas IAMC de la misma raíz → alertar sin propagar** (no vaciar: eso es
F-009). `lamina`/`calificacion`/`sector` quedan NULL hasta F-009. Defaults deterministas portados:
sector "Soberano"/"Subsoberano" por clase, underlying "Gobierno Argentino" para soberanos sin
emisor, derivación de `subtipo` global/bonar por law (activa recién cuando F-009 siembre ley).
`maturity` ← BYMA `vencimiento` por especie (parser determinístico contra el formato observado en
el paso 0; no parseable → NULL + alerta). La `fecha_vencimiento` de IAMC no se usa: un campo, una
fuente.

### D5 — TIR/duration/paridad/convexidad/residual: SOLO al ticker exacto que IAMC reporta
La TIR de AL30D difiere de la de AL30 (precio en otra moneda): propagarla por raíz sería inventar.
El motor viejo tampoco lo hacía (yields mergeados por ticker exacto, `consolidar_universo.py:361`).
Las especies hermanas quedan NULL y suman cobertura faltante. **Unidades**: IAMC entrega puntos
porcentuales y el Resumen viejo usa fracción (topes de sanidad 3.0 = 300 %) → `tir` y `paridad` se
persisten ÷ 100, conversión documentada; el paso 0 verifica la escala contra el PDF real.

### D6 — No se persisten en F-007
`proximo_cupon`/`proximo_pago_capital` (derivables de `cashflow`, segunda verdad), `FilaIndice`
(sin tabla; F-012 los usará), passthrough de Docta (sólo las 9 contractuales viajan).

### D7 — IAMC en la corrida: se re-parsea el último PDF aceptado del almacén
Nueva `ultimo_informe()` en `iamc/almacen.py`: elige `fuentes/iamc-deuda-corporativa-*.pdf` por
fecha **del nombre** (no mtime), ignora `iamc-rechazado-*`. El consolidador lo re-parsea con
`parsear_informe` vía `run_in_threadpool` (síncrono, CPU-bound). Sin PDF o `InformeInvalido` →
alerta con `accion_requerida` "subir el informe por POST /api/v1/iamc/informe", campos IAMC vacíos,
cobertura faltante. El endpoint de subida de IAMC no cambia (F-008 orquestará).

### D8 — Escritura: funciones puras de armado + capa SQL fina; una transacción por bloque
1. **`armar_consolidacion(...)`** — pura, sin base ni red: recibe las filas de las tres fuentes
   (o `None` por fuente) y devuelve `Consolidacion(filas_instrumentos, filas_precios, filas_puntas,
   filas_cashflow, alertas, cobertura)`. Los GWT 1-3 se testean acá.
2. **`persistir(conn, consolidacion, capturado_en)`** — un solo timestamp por corrida. Tres
   bloques, cada uno con su transacción y su try/except (el fallo de uno no aborta los otros —
   puerta que F-008 necesita):
   - `instrumentos` + `precios` juntos (FK): upsert `ON CONFLICT (ticker) DO UPDATE SET col =
     COALESCE(EXCLUDED.col, instrumentos.col)` — **nunca pisa con NULL lo existente**; `revisar` y
     `duplicado` se escriben directo (NOT NULL, calculados por corrida). `precios`: INSERT plano
     (serie temporal, nunca upsert).
   - `puntas`: INSERT plano, `fuente='byma'`, incluye los tickers excluidos de `instrumentos`.
   - `cashflow`: sólo si `resultado_docta.filas is not None` (contrato de F-006); upsert por
     `(ticker, payment_date)` que sí sobreescribe (el cronograma es la verdad vigente).
   - `executemany` (ON CONFLICT descarta COPY; ~6k filas no lo justifican).
3. **`consolidar(conn, settings, *, dormir)`** — orquestador: `ingerir_rueda` + `ingerir_cashflow`
   con `asyncio.gather`, PDF en threadpool, armar + persistir, resumen serializable. Recibe la
   conexión por parámetro para que F-008 la invoque fuera del ciclo HTTP. `ConfiguracionFaltante`
   de Docta → alerta + se consolida sin cashflow.

### D9 — Colapso de tickers repetidos por plazo
Una fila por ticker: preferir `plazo_liquidacion == "2"`, luego `"1"`, a igualdad el de mayor
`monto_operado`. El repetido se marca `duplicado=true` (resignificación documentada de la bandera).
El paso 0 verifica empíricamente cuántos hay.

### D10 — Modificación mínima a F-004
`ResultadoRueda` gana `especies_por_endpoint: dict[str, list[FilaRueda]]` (default_factory=dict,
compatible; `especies` se mantiene, los tests de F-004 no se tocan).

### D11 — `raiz_emision` portada a `backend/app/ingesta/consolidacion/raiz.py`
Regla idéntica a `tools/segmentos.py:165-170` (corta O/D/C final si len≥4) sobre `str`; docstring
citando el origen (el backend no importa de `tools/`).

### D12 — Cobertura por campo: se devuelve y loguea, no se persiste
`medir_cobertura` sobre las filas consolidadas (instrumentos: clase_activo, tipo_tasa, law,
coupon_currency, underlying, estructura_cupon, maturity, moneda_cotizacion; precios: last_price,
tir, tna, duration, paridad, convexidad, residual_value, effective_volume; puntas: px_bid, px_ask).
Campo con 0 presentes sobre N>0 → alerta con `CODIGO_CAMPO_SIN_COBERTURA` (definido y sin uso);
se agrega el constructor `campo_sin_cobertura` a `alertas.py`. No hay tabla de corridas hasta
F-008: métricas en la respuesta y en structlog.

### D13 — Migración (una sola, con rollback, vía MCP `apply_migration`)
1. CHECK de `coupon_currency` ampliado a `('MEP','CCL','USD','ARS')` (verificar el nombre real del
   constraint en `pg_constraint` antes).
2. `instrumentos`: `ADD COLUMN estructura_cupon text, moneda_cotizacion text, plazo_liquidacion
   text` — crudos, sin CHECK (vocabulario de fuente), con COMMENT de origen.
3. `precios`: `ADD COLUMN convexidad numeric`.
4. COMMENT de `precios.fuente` reescrito según D1.
La vista `resumen` selecciona columnas explícitas: no se rompe. Renombrar el archivo local a la
versión que asigne el servidor (patrón F-002); rollback en `supabase/rollbacks/` que restaura
CHECK y COMMENT y borra su fila del historial. Ensayar rollback + reaplicación.

### D14 — Endpoint
`POST /api/v1/consolidar` (`backend/app/api/v1/consolidar.py`, montado en `router.py`), con
`Depends(get_db)` (503 sin base). Devuelve `{snapshots: {byma, iamc, docta}, escrito: {tabla: n},
cobertura, alertas, capturado_en}` — sin filas (criterio de `/byma/ingesta`). Nunca loguear URLs
de Docta.

## Archivos

```
CREAR
backend/app/ingesta/consolidacion/{__init__,raiz,clasificacion,armado,persistencia,corrida}.py
backend/app/api/v1/consolidar.py
supabase/migrations/<ts>_f007_consolidador.sql + supabase/rollbacks/<ts>_..._down.sql
backend/tests/test_consolidacion_{armado,clasificacion,persistencia}.py
backend/tests/test_consolidar_endpoint.py
backend/tests/test_consolidacion_integration.py
claude-docs/plans/F-007-plan.md            (copia de este plan, patrón del pipeline)

MODIFICAR
backend/app/ingesta/byma/ingesta.py        especies_por_endpoint (D10)
backend/app/ingesta/iamc/almacen.py        ultimo_informe() (D7)
backend/app/ingesta/alertas.py             campo_sin_cobertura (D12)
backend/app/api/v1/router.py               montar el router nuevo
backend/tests/conftest.py                  doble de conexión con escritura
docs/esquema-datos.md                      columnas nuevas, semántica de fuente, precedencia
claude-docs/progress/PROGRESS.md           al cierre

NO SE TOCA
tools/ (GWT-4) · endpoints existentes de las tres fuentes · condiciones_emision (F-009)
```

## Orden de implementación

0. **Captura exploratoria** (script efímero en scratchpad, sin código de producción): corrida real
   de `ingerir_rueda` e `ingerir_cashflow`; enumerar (a) valores de (endpoint, subtipo, mercado,
   plazo_liquidacion) y repetidos por plazo en BYMA, (b) valores de `type` de Docta vs
   `SUBMARKET_MAP`, (c) formato real de `vencimiento`, (d) escala de tir/paridad del PDF vs
   Resumen viejo. Nada no observado se mapea "por las dudas".
1. Migración D13 aplicada + rollback ensayado.
2. `raiz.py` + `clasificacion.py` con tests puros.
3. `byma/ingesta.py` (D10) + test de partición consistente con `filas_por_tramo`.
4. `armado.py` con los GWT 1-3, colapso de plazos, conflictos, unidades.
5. `almacen.ultimo_informe()` + tests (tmp_path, nombres sintéticos).
6. `persistencia.py` + doble de conexión extendido + tests de contrato SQL.
7. `corrida.py` + endpoint + router + tests con respx.
8. `campo_sin_cobertura` + cobertura en la respuesta.
9. Suite offline completa en verde.
10. Verificación end-to-end + `docs/esquema-datos.md` + PROGRESS.md.

## Tests

- **Puros (armado/clasificación)**: GWT-1 (AL30/AL30D/AL30C heredan law/coupon_currency/estructura
  de la raíz IAMC, cada una conserva precio y moneda de cotización), GWT-2 (especie sin raíz en
  IAMC: atributos NULL + cobertura faltante), GWT-3 (TIR de IAMC al ticker exacto, ÷100,
  `fuente='byma+iamc'`; hermanas NULL). Bordes: conflicto IAMC por raíz (alerta, no propaga),
  CEDEAR con raíz compartida (no hereda), duplicados por plazo, `type` desconocido (excluido de
  instrumentos, presente en puntas), IAMC ausente, Docta `filas is None`.
- **Persistencia sin Postgres**: doble de conexión con `execute`/`executemany`/`transaction()` que
  registra `(query, args)`; se afirma el contrato (COALESCE en instrumentos, INSERT plano en
  precios, cashflow intacto con `None`, fallo de un bloque no impide los otros).
- **Endpoint offline**: respx para BYMA y Docta, `_no_dormir`, PDF vía monkeypatch de
  `parsear_informe` (un solo test re-parsea el PDF real).
- **Integración** (`-m integration`): CHECK acepta 'USD' y rechaza 'EUR'; y **GWT-4 de verdad**:
  `SELECT * FROM resumen` → DataFrame → Excel temporal con hoja "Resumen" → monkeypatch de
  `segmentos.CONSOLIDADO_PATH` → `cargar_universo()` y `cargar_renta_variable()` corren sin tocar
  el motor y `asignar_segmento` produce segmentos para la renta fija.

## Verificación end-to-end (contra Supabase)

1. Migración aplicada, rollback ensayado.
2. PDF IAMC vigente en `fuentes/` (subirlo por el endpoint si falta).
3. `POST /api/v1/consolidar` real; verificar con `execute_sql`:
   `instrumentos` entre ~1.500 y ~5.700 con las alertas `clase_sin_mapeo` nombradas; `precios` de
   la corrida == instrumentos escritos; `puntas` ≥ eso; `cashflow` ≈ 6.150; `law IS NOT NULL`
   consistente con 242 raíces IAMC; GWT-3 puntual (tir de un ticker del PDF ÷ 100); un ticker en
   `resumen` con precio BYMA y TIR IAMC en la misma fila; `/api/v1/health` ve el snapshot.
4. `pytest -m integration` (incluye GWT-4).
5. Segunda corrida SIN el PDF (renombrado temporalmente): los atributos IAMC se conservan
   (COALESCE) con alerta de IAMC ausente — el ensayo de la puerta de F-008.

## Riesgos

- **Vocabularios no verificados** (subtipo/mercado de BYMA, formato de maturityDate, types de Docta
  fuera del mapa): mitigado por el paso 0; lo no observado cae en alerta, nunca en mapeo especulativo.
- **Exclusiones en public-bonds**: si muchas raíces soberanas faltan en el cashflow se pierden
  precios de soberanos; el conteo sale en `clase_sin_mapeo` y si es intolerable se escala (cambio
  de esquema, no silencioso).
- **`tna` sin fuente**: pérdida conocida y declarada hasta que una feature la aporte.
- **Corridas concurrentes**: dos POST simultáneos → dos capturado_en; inofensivo para la vista,
  F-008 serializará. Anotado.
- **Batch de ~5.700 upserts** con command_timeout 30 s: debería sobrar; si no, lotes de 1.000 en
  la misma transacción.
- **Resignificación de `duplicado`**: documentada en `docs/esquema-datos.md`.
