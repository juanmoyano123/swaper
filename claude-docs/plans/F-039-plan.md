# Feature Plan: F-039 — Ficha de instrumento

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (líneas ~1756–1792) · diseño Cordillera v2 en
  `claude-docs/planning/design-system.md` (drawer de 430 px, "el mismo papel en las tres monedas")
- **Complexity**: M — backend de tres endpoints de sólo lectura + llenar un placeholder existente
- **Modo**: plan prescriptivo. Si algo no cierra contra el código real, **frenar esa parte y
  reportarla**, no improvisar.

## Qué es

El destino de cada ticker clickeado en el monitor y (más adelante) en el armador. Muestra las
condiciones de emisión con su origen y fecha, el mismo bono en sus tres monedas de liquidación, y
el cronograma de pagos hasta el vencimiento. Vive en el drawer de 430 px que ya existe
(`InstrumentoDrawer.tsx`) y en la página de ficha completa (`InstrumentoPage.tsx`) — los dos ya
montan `FichaInstrumento`, que hoy es un placeholder puro.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN un bono con tres especies de liquidación
WHEN se abre su ficha
THEN las tres aparecen con su precio, sus dos puntas y su moneda de cotización, sin sumarse ni
     promediarse entre sí

GIVEN un bono sin calificación crediticia
WHEN se abre su ficha
THEN el campo aparece marcado como no informado, y no vacío ni inferido de la clase del emisor

GIVEN un bono con cashflow disponible
WHEN se abre su ficha
THEN muestra el flujo de fondos completo hasta el vencimiento, distinguiendo interés de amortización

GIVEN cada condición de emisión mostrada
WHEN se la consulta
THEN trae su origen y su fecha
```

**Sobre GWT-1 — las puntas no existen en la fuente hoy.** Verificado en la tanda anterior: la vista
`resumen` no las trae, `EspecieUniverso` no tiene el campo, y el docstring de
`backend/app/api/v1/universo.py::vista_viva` lo declara explícito. El prototipo del design system
las simulaba con un spread ficticio (0,40%/0,45%/0,70% según moneda) — **eso no se porta**: sería
inventar un número y presentarlo como si viniera del mercado, exactamente lo que la regla 1 del
proyecto prohíbe. Precio, moneda y volumen de las tres especies sí se muestran (GWT-1 cumplido en
esa parte); las dos columnas de punta se muestran `s/d` con una nota explicando por qué no hay dato
todavía, no se ocultan ni se completan.

## Parte 1 — Backend

Todo nuevo, en un módulo propio para no tocar lo que F-038 ya dejó en `universo.py`.

### `backend/app/instrumentos/__init__.py` + `servicio.py`
Función pura, sin conexión, testeable con fixtures — mismo patrón que `app/universo/segmentacion.py`:

```python
async def ficha_de(conn: Any, ticker: str) -> dict | None:
    """La especie pedida + sus hermanas (las otras monedas de la misma emisión).

    None si el ticker no está en el universo de hoy — no se inventa una ficha vacía, el 404 lo
    dice.
    """
```
Implementación: reusar `sanear_universo(conn)` (mismo import que ya usa `universo.py`) →
`dedup = saneado.emisiones()` → si `ticker not in {e.ticker for e in dedup.vivo()}`: `None`.
Si está: la especie (`como_dict()` + `dato_sano`) más `dedup.hermanas(ticker)` (cada una
`como_dict()` + `dato_sano`) — **usar `dedup.hermanas()` y `dedup.emision_de()` tal como están en
`backend/app/universo/emisiones.py`, no reimplementar el agrupamiento por raíz.**

Forma de retorno:
```jsonc
{
  "ticker": "AL30",
  "especie": { /* EspecieUniverso.como_dict() */, "dato_sano": true },
  "hermanas": [ { /* como_dict() */, "dato_sano": true }, ... ]  // 0, 1 o 2 elementos
}
```

### `GET /instrumentos/{ticker}` en `backend/app/api/v1/instrumentos.py`
```python
@router.get("/{ticker}", responses={404: {...}, 503: {...}})
async def instrumento(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    resultado = await ficha_de(conn, ticker)
    if resultado is None:
        raise HTTPException(404, detail=f"{ticker} no está en el universo de hoy")
    return resultado
```

### `GET /instrumentos/{ticker}/condiciones`
Reusa `app/condiciones/persistencia.py::COLUMNAS` y `TABLA` (los mismos que usa
`backend/app/api/v1/condiciones.py` — **no redefinir la lista de columnas**). Un SQL nuevo, sólo
lectura, con `WHERE ticker = $1` en vez de `WHERE ticker > $1` del listado paginado:
```python
SQL_CONDICIONES_POR_TICKER = (
    f"SELECT {', '.join(COLUMNAS)} FROM public.{TABLA} WHERE ticker = $1"
)
```
Handler: `fila = await conn.fetchrow(SQL, ticker)`; `None` → `{"ticker": ticker, "condiciones": None}`
(no 404: que no haya condiciones curadas es un estado normal y declarado, GWT-2). Si hay fila, la
forma es la misma que ya devuelve `GET /condiciones` — un triplete `campo/campo_origen/campo_fecha`
por cada campo de `CAMPOS` (`ley`, `moneda_pago`, `lamina`, `calificacion`, `sector`,
`underlying`). **No transformar esa forma**: el frontend arma el par (valor, origen, fecha) leyendo
esos tres campos por nombre, igual que tendría que hacerlo si consumiera `/condiciones` directo.

### `GET /instrumentos/{ticker}/cronograma`
Reusa `leer_cashflow(conn)` e `indexar_cronograma(...)` de `app/calendario/cupones.py` — **import
de solo lectura, no se modifica ese archivo**. `indexar_cronograma` agrupa por raíz de emisión; se
busca la raíz de `ticker` (mismo criterio que usa el propio módulo de calendario) y se listan sus
pagos ordenados por fecha:
```jsonc
{
  "ticker": "AL30",
  "pagos": [
    { "fecha": "2026-09-09", "interes": 1.4375, "amortizacion": 0.0, "moneda": "USD" }
  ]
}
```
`interes`/`amortizacion` **por 100 de VN, en la moneda de emisión, tal como están en la tabla** —
sin pasar por paridad ni convertir a fracción: el design system pide exactamente "monto cada 100
VN", no un porcentaje del invertido (eso es lo que hace F-016/F-021, que sí tienen paridad). Sin
cronograma para esa raíz: `"pagos": []`, declarado, no 404 (puede ser legítimamente un instrumento
sin cashflow cargado).

Para resolver moneda de emisión, reusar lo que ya lee `leer_cashflow`/`COLUMNAS_CASHFLOW` de
`app/calendario/lectura.py` si trae la moneda; si no, tomarla de la especie (`EspecieUniverso`)
resuelta en el paso anterior. **No inventar una moneda si ninguna fuente la da** — declararla
`null` en ese caso.

### Tests backend
Archivo nuevo `backend/tests/test_instrumentos_api.py`, offline (mock de conexión, patrón de los
tests de `universo`/`condiciones`/`calendario` ya existentes — leerlos como referencia). Casos:
ticker vivo con 2 hermanas; ticker sin hermanas (`hermanas: []`); ticker fuera del universo → 404;
condiciones presentes con origen/fecha; condiciones ausentes → `condiciones: null`, no 404;
cronograma con pagos; cronograma vacío; 503 sin base (mismo patrón que los demás routers).

## Parte 2 — Frontend (`frontend/src/features/instrumento/`)

### `lib/schema.ts` (nuevo)
Tres zod, uno por endpoint. El de especie: **redefinir localmente** el shape de `EspecieUniverso`
(los mismos 18 campos que ya tipa `features/monitor/lib/schema.ts::esquemaEspecie` — leerlo como
referencia de los nombres exactos, **no importarlo**: `features/monitor/**` está prohibido para
este agente) más `dato_sano: z.boolean()`. El de condiciones: objeto con `ticker` y, por cada uno
de los 6 campos (`ley`, `moneda_pago`, `lamina`, `calificacion`, `sector`, `underlying`), sus tres
claves reales de columna (confirmar contra la fila real que devuelve el backend en el paso
anterior — son `<campo>`, `<campo>_origen`, `<campo>_fecha`), todo nullable. El de cronograma: lista
de `{fecha, interes, amortizacion, moneda}` nullable donde corresponda.

### `hooks/useFichaInstrumento.ts`, `useCondicionesInstrumento.ts`, `useCronogramaInstrumento.ts`
Tres `useQuery` independientes (no un solo hook con Promise.all: así una falla no tumba a las otras
dos — la ficha de precios puede mostrarse aunque el cronograma falle). Claves:
`claves.mercado.instrumento(ticker)`, `claves.referencia.condiciones(ticker)` (las dos ya están
reservadas en `queryKeys.ts` — **no lo edites**, ya tienen la forma correcta), y para cronograma usar
`[...claves.referencia.todas, 'cronograma', ticker] as const` (no hay clave reservada; cuelga de
`referencia` porque el cashflow cambia por ingesta, no por reloj — igual criterio que
`condiciones`). `retry: false` en las tres (el test de rutas falla con cualquier `console.error`
inesperado; un fetch que reintenta y tarda puede disparar warnings de act() en el test).

### `FichaInstrumento.tsx` — deja de ser placeholder
Firma actual: `FichaInstrumento({ ticker }: { ticker: string | undefined })`. Si `ticker` es
`undefined`, mantener el estado vacío tal cual está (no debería pasar en las rutas reales, pero es
el contrato de tipos existente). Con ticker:

- Loading/error de la query principal (`useFichaInstrumento`) con `EstadoCarga`/`EstadoError`
  (patrón ya usado en `ArmadorPage`/`MonitorPage`). 404 → mensaje explícito "no está en el universo
  de hoy", no una pantalla en blanco.
- **Bloque "el mismo papel en las tres monedas"**: una tarjeta por la especie pedida + cada
  hermana. Cada tarjeta: ticker (mono), precio (`fmtMonto` con la moneda de cotización — mono
  alineado a la derecha), volumen (`fmtCompacto`), y dos columnas de punta en `s/d` con un `title`
  fijo: "las puntas no viajan por la fuente hoy". La tarjeta de `ticker` (la pedida) con borde
  `--ac`; las demás borde `--lin`. Nota de una línea: "tres tickers del mismo instrumento; no se
  suman ni se convierten entre sí" (regla 2 del dominio, literal).
- **Grilla de dos columnas** con lo que da la especie: segmento (nombre + `unidadDeNaturaleza` de
  `@/components/SelectorSegmento` — se consume, no se edita), rendimiento (rotulado, `s/d` si
  `null`), duración, paridad, moneda de cotización, volumen, ley, vencimiento (`fmtFecha`). Si
  `clase_activo` indica renta variable: rendimiento y duración muestran **"no aplica"**
  (`NO_APLICA` de `@/lib/fmt`, no `SIN_DATO` — son conceptos distintos y las dos constantes ya
  existen).
- **Condiciones de emisión** (segunda query, independiente): calificación, sector, lámina,
  moneda de pago, ley — cada campo con su valor y, al lado o en `title`, `origen` y `fecha`
  (`fmtFecha`). Sin fila (`condiciones: null`) o campo individual `null`: "no informado" — texto
  distinto de `s/d` porque el matiz es real (GWT-2 dice explícito "no vacío ni inferido de la
  clase del emisor"; usar un texto propio tipo `NO_INFORMADO = 'no informado'` en el módulo, no
  reusar `SIN_DATO` sin criterio — documentarlo en un comentario de una línea).
- **Cronograma** (tercera query): tabla fecha / tipo / monto — dos filas por pago cuando
  `interes > 0` y `amortizacion > 0`, o una fila con el campo que corresponda. Nota: "montos por
  cada 100 de valor nominal; el flujo del cliente depende del nominal que tenga asignado". Vacío:
  "sin cronograma cargado para esta emisión" (declarado, no error).
- **No agregar** botón de "sumar a la cartera": está fuera de esta tanda (contacto con el store de
  F-018, que este agente no toca). Si el design system lo muestra en la maqueta, se omite acá sin
  comentario especial — no hay GWT que lo pida.

### Contrato de test intocable (`app/__tests__/rutas.test.tsx`, YA EXISTE, no se edita)
- El drawer sigue siendo `role="dialog"` `aria-label="Ficha de {ticker}"` con un botón
  `"Cerrar la ficha"` — **no tocar `InstrumentoDrawer.tsx` ni cambiar esos textos**.
  `FichaInstrumento` es lo único que cambia adentro.
- El `h1` de `InstrumentoPage` sigue mostrando el ticker — no tocar `InstrumentoPage.tsx`.
- **Cero `console.error`/`console.warn`**: en el test 2 (drawer sobre `/armador`), el `fetch` stub
  del test sólo devuelve el payload de salud. Cualquier query nueva de esta feature va a fallar
  ahí — eso está bien, tiene que fallar **silenciosamente hacia el estado de error de la UI**, no
  como una excepción no manejada ni un warning de React. Usar `retry: false` en las tres queries y
  manejar `isError` explícito en cada bloque (no un solo error global que tape a los otros dos).

## PROHIBIDO tocar
`features/armador/**` · `features/monitor/**` (sólo lectura de referencia, nunca import) ·
`backend/app/api/v1/universo.py` · `backend/app/api/v1/condiciones.py` · `backend/app/calendario/**`
(salvo import de solo lectura de `cupones.py`) · `backend/app/api/v1/router.py` (ya montado) ·
`frontend/src/app/__tests__/rutas.test.tsx` · `frontend/src/lib/api/queryKeys.ts` ·
`frontend/src/features/instrumento/InstrumentoDrawer.tsx` ·
`frontend/src/features/instrumento/InstrumentoPage.tsx` · `package.json` ·
`backend/requirements.txt` · nada de `git add`/`git commit` · el backend no importa de `tools/`.

## Reglas del dominio que esta pantalla NO puede violar
1. Puntas ausentes → `s/d` con su motivo. Calificación ausente → "no informado", nunca inferida.
2. Las tres especies del mismo bono nunca se suman ni se promedian.
3. Montos del cronograma tal como están en la fuente (por 100 VN, moneda de emisión) — no se
   inventa una conversión que la fuente no da.
4. Todo campo de condiciones trae origen y fecha cuando existe.

## Test Strategy
Backend: pytest offline (ver Parte 1). Frontend (patrón `features/estado-dato/__tests__/`, mock de
`@/lib/supabase` + `vi.stubGlobal('fetch', ...)`): ficha con 2 hermanas renderiza 3 tarjetas y las
puntas en `s/d`; 404 → mensaje explícito; condiciones ausentes → "no informado" en los 6 campos;
un campo de condiciones presente muestra su origen y fecha; renta variable → "no aplica" en
rendimiento/duración; cronograma con pagos → filas correctas separando interés de amortización;
cronograma vacío → mensaje declarado; ninguna de las tres queries en error tumba a las otras dos.

## Comandos de verificación
```
Backend (cd /Users/jeroniki/Documents/Github/10-Swaper/backend):
  source venv/bin/activate
  python -m pytest tests/test_instrumentos_api.py -q
  ruff check app/instrumentos app/api/v1/instrumentos.py
Frontend (cd /Users/jeroniki/Documents/Github/10-Swaper/frontend):
  npx vitest run src/features/instrumento
  npm run lint
  npx tsc --noEmit
```
No correr la suite completa de nada (F-018 trabaja en paralelo); la corre el cierre de tanda.

## Al terminar, reportar
Archivos creados/modificados (backend y frontend por separado), salida real de los comandos, y
cualquier punto donde el plan no cerró contra el código real y qué se hizo (debe ser: frenar esa
parte y reportarla).
