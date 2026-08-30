# F-078 — Mission control de diversificación de CEDEARs

## Contexto

Es difícil armar carteras de renta variable diversificadas porque no se sabe en qué se está
invertido con tanto activo. El pedido: un "mission control" donde el asesor toca filtros por
ejes de diversificación —moneda, geografía, rubro económico, temáticas como metales
preciosos— y ve los activos que responden a ese criterio; el armador propone automáticamente
respetando topes configurables, la propuesta se edita a mano (ya existe), y la composición
resultante se le muestra al cliente: qué % está en cada país/región, moneda, rubro.
Markowitz conceptual: diversificar por exposición, sin históricos ni covarianzas. Universo:
estrictamente los CEDEARs de BYMA (las acciones locales ya están fuera del armado por
decisión previa).

**Estado del dato (medido):** de los ejes pedidos, cinco ya tienen fuente declarada en
`public.perfil_renta_variable` (1.641 papeles): rubro `sic_oficina` (SEC, 870 con SIC),
eslabón `division_cadena`, estrategia de ETF (123 fondos, del nombre oficial de BYMA),
`mercado_origen` (413, PDF de BYMA), `moneda_cotizacion` (ARS/USD/EXT crudo). **País/región
no tiene fuente**: la columna `pais` quedó huérfana al eliminar Yahoo (23/08) y el domicilio
SEC no sirve (el usuario lo rechazó: quiere la economía a la que queda expuesta la plata, no
el domicilio legal).

**Decisiones del dueño (28/08, no reabrir):**
1. **Geografía = tabla curada por papel** (~427 CEDEARs), investigada con fuente y fecha por
   fila y **validada por él antes de cargarse** — patrón `condiciones_emision.csv` /
   `emisores_arca.csv`. La región se deriva del país con un estándar publicado (ONU M49).
   Los ETFs geográficos llevan la región que declara su propio nombre (leer el nombre no es
   inferir — precedente `etfs.py`). Lo dudoso queda vacío y declarado.
2. **Metales preciosos = preset temático**, no faceta: ETFs `activo_fisico` (GLD, SLV) +
   mineras por código SIC (1040 y afines, verificados contra la base), con la definición
   visible al usuario.
3. **Armador con topes configurables** por eje en la UI (máx % por rubro/país/región/
   moneda/mercado), defaults razonables por perfil; lo incumplible se declara con alerta,
   no bloquea.

Registro en el pipeline: feature nueva **F-078** (el catálogo llega a F-077). Plan en
`claude-docs/plans/F-078-plan.md` (copiar este contenido al iniciar), progreso en
`claude-docs/progress/PROGRESS.md`.

---

## Fase 1 — Backend: `region_etf` + contrato extendido (sin curado)

1. **`backend/app/renta_variable/etfs.py`** — `region_declarada(nombre) -> str | None`:
   extrae el token geográfico del nombre con los patrones ya declarados
   (`japan|china|korea|europe|brazil|latin america|emerging|EAFE|developed|world|ACWI|global`)
   y lo devuelve **tal como aparece** (`Brazil`, `EAFE`) — no se traduce. `None` si no es
   fondo o el nombre no declara geografía.
2. **Migración + rollback**: `ALTER TABLE perfil_renta_variable ADD COLUMN region_etf text`.
   Se escribe donde ya se escribe `estrategia_etf`: `perfiles.py::SQL_UPSERT_SEC` y
   `clasificacion.py` (junto a `estrategia_de(...)`).
3. **Backfill sin tocar la SEC**: `POST /api/v1/jobs/reclasificar-etfs` (en
   `api/v1/jobs.py`, detrás de `cron_o_asesor` como el resto) — re-deriva `estrategia_etf`
   y `region_etf` desde `nombre_largo` ya persistido. Puro, idempotente, liviano.
4. **Mini-curado de los 7 ETFs con nombre truncado** (SPY, DIA, EEM, EWZ, ARKK, VIG, ITA):
   `data/etfs_nombres.csv` (`ticker,nombre_oficial,fuente,verificado`) con el nombre oficial
   que publica el emisor del fondo; validado por el usuario. `estrategia_de`/
   `region_declarada` usan el nombre curado cuando existe. Si el usuario no valida, quedan
   `sin_clasificar` como hoy.
5. **Contrato**: `EspecieRentaVariable` + `como_dict()` suman `region_etf`;
   `lectura.py::COLUMNAS_PERFIL` idem; `frontend/src/lib/rentaVariable.ts` suma
   `region_etf: z.string().nullable()`.

Tests: `region_declarada` (geográfico, no geográfico, empresa, None, falso positivo tipo
NETFLIX), upsert con la columna, reclasificación idempotente, schema frontend.

## Fase 2 — Frontend: mission control en el monitor (sin curado)

La rama RV del monitor (`MonitorPage.tsx` ~línea 396, `RentaVariableDelMonitor`) hoy solo
tiene `SelectorMoneda` + `TablaRentaVariable`; los campos de clasificación ya viajan.

1. **`frontend/src/features/monitor/lib/filtrosRentaVariable.ts`** (nuevo) — sobre el motor
   genérico `facetar()` de `src/lib/facetado.ts` (leave-one-out, ya portado 2 veces):
   dimensiones `region | pais | mercado | rubro | eslabon | estrategiaEtf`, cada una con
   centinela de "sin dato" para poder filtrar hacia el hueco; dato faltante ⇒
   `coincide=false`. La moneda sigue en `SelectorMoneda` como `pasaBase` (elección explícita,
   nunca "todas" — regla 3). Las facetas `region`/`pais` nacen con solo `region_etf` +
   centinela y se llenan solas en Fase 3 sin tocar este módulo.
2. **`frontend/src/features/monitor/components/FiltrosRentaVariable.tsx`** (nuevo) — chips
   con conteo y autoocultado <2 opciones, molde `SelectorCredito.tsx`/
   `SelectorSubtipoSoberano.tsx`.
3. **`frontend/src/lib/presetsRv.ts`** (nuevo, en `lib/` porque monitor y armador no pueden
   importarse entre sí — precedente F-017/F-038):
   `PresetRv { id, etiqueta, filtro: FiltroRv, modo: 'interseccion'|'union', nota }` con
   `FiltroRv { rubros?, sicCodigos?, estrategiasEtf?, paises?, regiones?, mercados? }`.
   **Metales preciosos**: `modo:'union'`, `estrategiasEtf:['activo_fisico']` +
   `sicCodigos` de minería de oro/plata **verificados contra la base antes de hardcodear**
   (candidatos rango 1000–1099: 1000, 1040, 1044); la `nota` enumera los códigos con su
   `sic_titulo`. `tematicas.ts` del armador se extiende para referenciarlo
   (`PresetTematico` gana `filtroRv?`).
4. **`ComposicionUniversoRv.tsx`** (nuevo) — una `DistribucionBarras`
   (`src/components/DistribucionBarras.tsx`, creado justo para esto) por eje sobre el
   universo filtrado; peso = % por cantidad de papeles (agrupados por `emision`), leyenda
   que lo dice; el faltante siempre como tramo "sin dato", nunca repartido.

Tests: vitest de facetas (leave-one-out, centinelas), del preset metales (unión: ETF
activo_fisico sin SIC pasa; minera 1040 sin estrategia pasa; petrolera no), agregación por
papel; `tsc` limpio.

## Fase 3 — Curado de país + región estándar (ruta crítica humana, arranca en paralelo)

1. **CSV fuente de verdad**: `data/paises_cedears.csv` —
   `ticker_papel,pais,fuente,verificado`. `ticker_papel` = papel post-agrupamiento (AAPL,
   no AAPLD): el país es de la empresa y las hermanas son el mismo papel. `pais` en ISO
   3166-1 alfa-2 (un estándar se lee, como ISO 4217). `fuente` cita qué declara la empresa
   y dónde. Dudoso ⇒ `pais` vacío con la duda en `fuente`. ETFs ⇒ vacío (su eje geográfico
   es `region_etf`).
2. **Proceso**: (a) generar `data/paises_cedears_pendientes.csv` con los ~427 papeles desde
   la base (patrón `emisores_cuit_pendientes.csv`); (b) investigar por tandas qué declara
   cada empresa; (c) **validación del usuario antes del merge**; (d) merge + siembra. Un
   CEDEAR nuevo de BYMA aparece sin fila ⇒ "país sin dato" declarado; la siembra reporta
   `papeles_sin_pais` para alimentar la próxima tanda.
3. **Tabla nueva `public.pais_cedear`** (`ticker_papel PK, pais, fuente NOT NULL,
   verificado date NOT NULL, cargado_en`) — NO se recicla la columna huérfana de Yahoo
   (otra semántica, sin fuente por fila). Migración aparte con rollback propio: **DROP de
   las cuatro huérfanas** de Yahoo (`nombre_corto`, `sector`, `industria`, `pais`) de
   `perfil_renta_variable`; el rollback las recrea.
4. **`backend/app/renta_variable/regiones.py`** (nuevo) — `REGION_M49: dict[str, str]`
   (ISO alfa-2 → subregión M49 en español tal como la publica la ONU, estándar citado con
   URL y fecha) + `region_de(pais)`. Subregión, no continente: da "América Latina y el
   Caribe", "América del Norte", "Asia occidental" (≈ Medio Oriente) sin inventar
   agrupación propia. No es columna: se deriva al leer, como `division_cadena`.
5. **`backend/app/renta_variable/paises.py`** (nuevo, patrón `app/condiciones/semilla.py`):
   parser puro del CSV con vocabulario cerrado (país fuera de `REGION_M49` se descarta y se
   alerta), upsert idempotente, `sembrar_paises()` y `leer_paises()`. Ruta en
   `Settings.paises_cedears_csv` (patrón `emisores_arca_csv`). Endpoint
   `POST /api/v1/jobs/sembrar-paises-cedears`.
6. **Lectura**: el join va en Python por papel — `armar_renta_variable()` de `especies.py`
   recibe `paises: dict` y setea por especie `pais`, `region = region_de(pais)`,
   `pais_fuente`, `pais_verificado` mirando `emision or ticker` (hermanas comparten por
   identidad, no analogía). `como_dict()`, endpoint y schema zod suman los cuatro campos.
7. **UI**: las facetas país/región de Fase 2 se llenan solas. Vocabulario geográfico dual a
   propósito: región curada ("América Latina y el Caribe") y región de nombre de ETF
   ("Brazil") se muestran como valores distintos — unificarlos sería traducir. La ficha
   muestra `pais_fuente`/`verificado` como ya muestra `perfil_fuente`.

Tests: parser (vocabulario, repetidos, vacío declarado), `region_de` total sobre el dict,
test de que todo país del CSV versionado tiene región, siembra idempotente, propagación a
hermanas.

## Fase 4 — Armador con topes configurables + composición para el cliente

1. **`backend/app/armado/parametros.py`**: `TopesRv` (`max_pct_rubro/pais/region/moneda/
   mercado`, cada uno `float | None`, 0<x≤100) y `FiltroRv` (espejo backend de
   `presetsRv.FiltroRv`, con `modo`). `ParametrosArmado` suma `topes_rv` y `filtro_rv`;
   `rubro_rv` se mantiene y se normaliza a `filtro_rv.rubros` en un `model_validator`
   (422 si se contradicen).
2. **Defaults por perfil** en `armado/renta_variable.py`: `TOPES_RV_DEFAULT` análogo a
   `concentracion/perfiles.py` (propuesta: rubro 30/40/55 espejando `max_sector`; país
   40/50/60; región/mercado/moneda más laxos), cada número con su porqué en docstring.
   **Los defaults aplican solos** (es la promesa de la feature; cambia las carteras
   propuestas — se documenta y se ajustan los tests de snapshot); `null` explícito por eje
   los apaga.
3. **Algoritmo** (greedy determinístico con restricciones, en `armar_renta_variable()`):
   guardas y filtro como hoy → orden `volumen_usd` desc / `ticker` asc → cupos
   `max(1, floor(max_pct/100 * n_rv))` por (eje, categoría) → las dos pasadas de hoy
   (rubros nuevos primero, liquidez después) salteando candidatos con cupo lleno →
   equiponderación. **Categoría faltante no computa contra ningún tope** (no se acota lo
   que no se conoce, criterio `sector_computable()`) y se cuenta. Alertas nuevas:
   `rv_tope_limita_seleccion` (cupos agotaron candidatos), `rv_tope_excedido`
   (verificación post-selección contra tope + tolerancia — declara, no bloquea),
   `rv_tope_sin_dato_en_eje` ("el tope de país se midió sobre X de Y posiciones").
4. **UI**: `schemaArmado.ts` suma `topes_rv`/`filtro_rv`; `PanelArmadoAsistido.tsx` gana el
   bloque "Topes de renta variable" con inputs numéricos (sin sliders — no existen en el
   design system), defaults del perfil precargados y visibles, formato es-AR.
5. **Composición para el cliente**: `armador/lib/composicionRentaVariable.ts` reusando
   `agrupar()` de `composicion.ts` — `composicionRvPor(posiciones, especiePorTicker, eje)`
   para país/región/moneda/rubro/mercado, renderizado con `DistribucionBarras` en
   `BloqueRentaVariable.tsx` (actualizar su header desactualizado "Sin distribución por
   país ni por rubro").
6. **Migrar el facetado a mano** de `BloqueRentaVariable.tsx` (~líneas 196-217,
   rubro⇄eslabón artesanal) a `facetar()` de `src/lib/facetado.ts`, sumando
   país/región/estrategia al picker — en el mismo commit que agrega las dimensiones.

Tests: determinismo, cupo alcanzado ⇒ siguiente candidato, tope incumplible ⇒ alerta sin
bloqueo, faltante no computa, `max(1,…)`, compat `rubro_rv`, paridad con el comportamiento
actual cuando `topes_rv=None` en un perfil sin defaults; vitest de schema, composición y
picker migrado.

## Orden y dependencias

```
Fase 1 ──► Fase 2 ──► Fase 4          (todo funciona sin el curado)
Fase 3 (curado) — en paralelo desde el día 1; solo 3.3–3.7 tocan código
```

**Sin el curado se entrega**: mission control completo sobre rubro/eslabón/estrategia/
mercado/moneda + `region_etf`, preset de metales, distribuciones, topes de
rubro/moneda/mercado. País/región aparecen "sin dato" declarado hasta la siembra — que es
el contrato del sistema, no un estado roto.

## Verificación end-to-end

1. `pytest` backend + `vitest`/`tsc` frontend en verde; `ruff` sin errores nuevos en lo
   tocado.
2. Local: reclasificar ETFs → los iShares de país muestran `region_etf`; monitor RV →
   filtrar por estrategia "Geográfico" acota los demás chips y las barras; preset metales
   trae GLD/SLV + mineras y la nota muestra la definición.
3. Tras la siembra: AAPL/AAPLC/AAPLD con el mismo país; un papel sin fila con país en
   blanco y contado; armar con tope de rubro 20% y n_rv=5 ⇒ 1 por rubro + alertas
   razonables; barras de composición por país/región en el bloque RV.
4. Producción: migraciones aplicadas a la base real (recordatorio: escribir el .sql no la
   aplica), reclasificación y siembra corridas por los endpoints de jobs, verificación de
   conteos antes/después.

## Riesgos

- Los tres endpoints de clasificación siguen siendo internos de frontends (PDF de BYMA,
  SEC): todo fallo degrada a vacío contado, nunca a dato inventado.
- 112 CEDEARs sin CIK/SIC siguen sin rubro: visibles en el chip/tramo "sin dato";
  declarado, no se resuelve acá.
- Aplicar defaults de topes cambia las carteras que el armador propone hoy: documentado y
  cubierto por tests, con `null` por eje como apagado explícito.
- El curado de país es trabajo humano (investigar ~427 papeles + validación del usuario):
  se hace por tandas y nada del código lo espera para funcionar.
