# Feature Plan: F-016 — Grilla-selector de doce meses

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (líneas ~757–793) · diseño Cordillera v2 en
  `claude-docs/planning/design-system.md` (paneles A2 y A5)
- **Complexity**: L — es la feature de UI más pesada del camino crítico
- **Modo**: este plan es prescriptivo. Las decisiones ya están tomadas; el trabajo es transcribirlas.
  Si algo del plan no cierra contra la realidad del código, **frenar y reportar**, no improvisar.

## Qué es

La pantalla que invierte el producto: el calendario es la entrada, no la salida. Doce columnas, una
por mes, con los papeles que pagan renta ese mes. Clic en un papel → entra a la cartera y se
ilumina **en todos los meses en que paga, a la vez**. Clic de nuevo → sale y se apaga en todos.
Clic en un mes → panel de detalle con tarjetas comparables. Trabaja sobre la vista colapsada:
un papel, una emisión.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN la grilla de doce meses cargada
WHEN el asesor hace clic en un papel que paga en marzo, julio y noviembre
THEN el papel entra a la cartera y queda iluminado en las tres tarjetas simultáneamente

GIVEN un papel ya seleccionado
WHEN el asesor vuelve a hacer clic sobre él en cualquiera de sus meses
THEN sale de la cartera y se apaga en todos los meses a la vez

GIVEN una cartera en la que ningún papel paga en febrero
WHEN se mira la grilla
THEN la tarjeta de febrero está marcada como mes sin cobertura de forma visualmente distinguible

GIVEN un papel listado en una tarjeta
WHEN se lee su renglón
THEN muestra ticker, moneda de liquidación, monto del cupón, TIR y año de vencimiento en una sola línea
```

## El dato: `GET /api/v1/calendario/universo?detalle=true`

Ya existe (F-015). **Sin paginar, a propósito**: doce meses fijos que **arrancan el mes que
viene**; el mes vacío es dato. Forma exacta (leer `backend/app/calendario/grilla.py` si hace falta
confirmar):

```jsonc
{
  "resumen": { "hoy", "desde", "hasta", "con_montos": false, "monedas": [],
               "instrumentos": 71, "meses_sin_renta": ["11/2026", ...],
               "renta_anual": null, "amortizacion_anual": null,
               "pendientes_este_mes": 3,
               "flujos": { "evaluados", "con_flujos", "pagos", "sin_cronograma",
                           "sin_paridad", "sin_paridad_que_cotizan", "vencidos" } },
  "meses": [   // siempre 12
    { "anio", "mes", "etiqueta": "09/2026", "nombre": "Septiembre 2026",
      "con_renta": 12, "con_amortizacion": 3, "sin_renta": false,
      "renta": null, "amortizacion": null,
      "instrumentos": [
        { "ticker", "emision", "fechas": ["2026-09-09"],
          "pct_renta", "pct_amortizacion",      // fracción del monto invertido (0.0075 = 0,75%)
          "renta": null, "amortizacion": null,  // sin montos en la vista universo
          "moneda", "rendimiento", "naturaleza", "naturaleza_nombre", "vencimiento" } ] } ],
  "alertas": [ { "codigo", "mensaje", "severidad", "accion_requerida", "detalle", "origen" } ]
}
```

Notas duras:
- `rendimiento` puede ser `null` → se muestra `s/d` (**nunca** se estima ni se omite la fila).
- La grilla hoy cubre **70 de 431 emisiones** y el endpoint lo declara con la alerta
  `cobertura_del_calendario`. **Las alertas se muestran en pantalla, no se filtran.**
- Regla del dominio: renta y amortización **no se suman**, y nada cruza monedas. Dentro de cada
  mes, los renglones se agrupan por `moneda`; los rendimientos llevan el rótulo de su naturaleza
  (usar `unidadDeNaturaleza` de `@/components/SelectorSegmento`) y jamás se agregan entre sí.

## File Structure

### Create — todo dentro de `frontend/src/features/armador/`
- `lib/schema.ts` — zod del response completo (patrón: `features/estado-dato/lib/schema.ts`;
  validar TODO el contrato, tipos exportados con `z.infer`).
- `hooks/useCalendarioUniverso.ts` — `useQuery` + `apiFetch('/api/v1/calendario/universo?detalle=true', esquema)`,
  `queryKey: claves.mercado.calendarioUniverso` (**ya existe** en `lib/api/queryKeys.ts` — no tocar
  ese archivo), `staleTime` con `TIEMPOS.mercado` de `app/queryClient.ts`, `retry: false`.
- `store/carteraStore.tsx` — **el store del armador que F-017 y F-018 heredan.** Contexto React +
  `useReducer`, sin dependencia nueva. Shape:

  ```ts
  export interface PosicionArmador {
    ticker: string
    // F-018 agrega acá: peso pedido, nominales. No agregar ahora.
  }
  interface EstadoArmador {
    pos: PosicionArmador[]        // orden de incorporación
    selMes: number | null         // índice 0–11 en la ventana de la grilla, no mes calendario
    // F-017 agrega acá: filtros. No agregar ahora.
  }
  // acciones: alternarPapel(ticker) — agrega si no está, saca si está;
  //           alternarMes(indice)  — selecciona, o des-selecciona si ya era el activo.
  ```

  Exportar `ArmadorProvider`, `useArmador()` (estado) y `useArmadorAcciones()`. Documentar en el
  docstring del archivo que F-017/F-018 extienden este shape y por eso el plan las serializa.
- `components/GrillaDoceMeses.tsx` — las doce columnas (diseño A2): cabecera con `nombre` del mes,
  conteo `con_renta`, y la lista de renglones. Columna del mes seleccionado con fondo `var(--sel)`
  y nombre en `var(--ac)` peso 700.
- `components/RenglonPapel.tsx` — **una sola línea** (GWT-4): ticker (mono), moneda, cupón como
  `%` del invertido (`fmtPct(pct_renta * 100)` — ojo: `pct_renta` viene como fracción),
  rendimiento con su rótulo de unidad o `s/d`, año de `vencimiento`. Clickeable entero
  (`<button>`); si su ticker está en `pos`, iluminado: fondo `var(--sel)`, borde izquierdo 2 px
  `var(--ac)`. La iluminación multi-mes sale sola de que cada mes pinta contra el mismo `pos`.
- `components/DetalleMes.tsx` — panel A5, visible cuando `selMes !== null`: borde `var(--ac)`,
  título con el nombre del mes y cuántos papeles pagan, grilla
  `repeat(auto-fill, minmax(232px, 1fr))` de tarjetas: ticker + emisión, tres métricas grandes
  (rendimiento rotulado / cupón % / cantidad de meses que paga), línea de detalle (naturaleza,
  vencimiento), `<MiniCalendario>` de `@/components/MiniCalendario` con los 12 meses de la ventana
  (`'renta'` si el papel paga ese mes — derivarlo cruzando el ticker contra `meses[]`), y el botón
  de agregar/sacar (mismo `alternarPapel`).
- `components/CoberturaSeleccion.tsx` — la fila de cobertura del año de la cartera seleccionada
  (GWT-3): para cada uno de los 12 meses, si **algún papel de `pos`** paga ahí. Mes sin cobertura:
  `—` en `var(--neg)`. Distinguir del mes donde el universo entero no paga (`sin_renta: true`),
  que se marca en la propia columna con su etiqueta en `var(--dim)` y la nota "sin pagos en el
  universo". Son dos cosas distintas y las dos se ven.
- `components/AlertasCalendario.tsx` — lista de `alertas[]` del response: mensaje completo,
  color por severidad (`advertencia` → `var(--ac2)`, `error` → `var(--neg)`, `info` →
  `var(--dim)`). Sin colapsar, sin filtrar, sin umbral.
- `__tests__/` — ver Test Strategy.

### Modify
- `ArmadorPage.tsx` — reemplazar el `EstadoVacio` por `<ArmadorProvider>` envolviendo grilla +
  cobertura + detalle + alertas. Mantener `Pantalla`/`Panel` y la bajada existente.
  `EstadoCarga`/`EstadoError` de `@/components` para los estados de la query.

### PROHIBIDO tocar
`app/__tests__/rutas.test.tsx` · `lib/api/queryKeys.ts` · `components/MiniCalendario.tsx` ·
`components/SelectorSegmento.tsx` · `package.json` · **cualquier archivo de
`features/monitor/`** o del backend · nada de `git add`/`git commit`.

## Reglas del dominio que esta pantalla NO puede violar
1. Ningún total suma monedas ni mezcla renta con amortización.
2. Ningún rendimiento se promedia ni comparte columna sin rótulo de unidad.
3. `null` → `s/d` (usar `SIN_DATO` de `@/lib/fmt`). Jamás `0`, jamás celda muda.
4. Las fechas `YYYY-MM-DD` se muestran con `fmtFecha` (parsea por componentes, no `new Date(str)`).
5. Las alertas del backend llegan a la pantalla tal cual.

## Test Strategy (patrón: `features/estado-dato/__tests__/BarraEstadoDato.test.tsx`)
Mock de `@/lib/supabase` + `vi.stubGlobal('fetch', ...)` con `Response` JSON; render envuelto en
`QueryClientProvider` con `crearQueryClient()`. Factory tipada del response con `Partial<>`.
- Store: `alternarPapel` agrega y saca; `alternarMes` selecciona y des-selecciona.
- GWT-1: fixture con un papel que paga en 3 meses → clic → los 3 renglones iluminados.
- GWT-2: segundo clic (desde otro mes) → apagado en los 3.
- GWT-3: selección que no cubre un mes → ese mes marcado sin cobertura; y mes con
  `sin_renta: true` marcado distinto.
- GWT-4: el renglón muestra los cinco campos; con `rendimiento: null` muestra `s/d`.
- Alertas: una alerta `advertencia` del fixture aparece con su mensaje completo.
- Schema: el fixture pasa el zod; un campo faltante lo hace fallar con `contract_mismatch`.

## Comandos de verificación (correr desde `frontend/`, rutas absolutas en cd)
```
npx vitest run src/features/armador
npx tsc --noEmit    (via: npm run build — o tsc -b)
npm run lint
```
No correr la suite entera del frontend (otra feature está trabajando en paralelo); la suite
completa la corre el cierre de la tanda.

## Al terminar, reportar
Archivos creados/modificados, resultado textual de los tres comandos, y cualquier punto donde el
plan no cerró contra la realidad y qué se hizo (que debe ser: frenar esa parte y reportarla).
