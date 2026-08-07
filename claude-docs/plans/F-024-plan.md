# Feature Plan: F-024 — Redondeo por lámina y diferencia entre pedido y real

## Overview
- **Source**: spec en `claude-docs/planning/plan.md` (sección "#### F-024", líneas ~1194–1228) ·
  diseño A8 en `claude-docs/planning/design-system.md` · orden de tandas en
  `claude-docs/planning/plan-ejecucion-tandas.md` (tanda 8b)
- **Complexity**: S–M — el motor de redondeo ya existe y está testeado (F-018); lo que falta es
  cablear la lámina real, el total ajustado y el resumen de cobertura
- **Modo**: plan prescriptivo. Si algo no cierra contra la realidad del código, **FRENAR y
  reportar**, no improvisar.

## Qué es

Cuando la lámina está informada, el armador redondea el valor nominal al múltiplo correspondiente
y muestra la diferencia entre la ponderación pedida y la real — que es justamente lo que hace que
difieran: una posición pedida al 16,5 % puede terminar en 17,6 % real, y eso se ve. Cuando **no**
está informada, no redondea y **no asume 1, ni 1.000, ni ningún default de mercado**: marca la
posición como *lámina no informada*, la excluye del total ajustado, y el resumen dice cuántas
posiciones y qué porcentaje de la cartera quedaron sin ajustar. Un default de lámina produciría
nominales que parecen correctos y no lo son, en la pantalla que el asesor lleva a la reunión.

El motor puro ya sabe hacer todo el redondeo (`resolver.ts`, F-018, con `Math.floor` a propósito:
nunca se compra de más). El bloqueo real es **una línea**: `CarteraEditable.tsx` le pasa
`lamina: null` siempre porque hasta esta feature el dato no viajaba. Esta feature lo hace viajar y
lo declara cuando falta.

## GWT (criterios de aceptación, literales del plan)

```
GIVEN una posición pedida al 16,5 % con lámina informada
WHEN se calcula el nominal
THEN se redondea al múltiplo de la lámina y la pantalla muestra el 16,5 % pedido y el porcentaje real
     resultante, los dos a la vista

GIVEN una posición cuya emisión no tiene lámina informada
WHEN se calcula el nominal
THEN no se redondea, la posición se marca como "lámina no informada", y no se asume ningún valor por
     defecto

GIVEN una cartera con dos de siete posiciones sin lámina
WHEN se muestra el resumen
THEN declara cuántas posiciones y qué porcentaje de la cartera quedaron fuera del total ajustado
```

## De dónde sale la lámina — y por dónde NO

**Hallazgo verificado contra el código**: `instrumentos.lamina` está **NULL para todo el
universo**. `backend/app/ingesta/consolidacion/armado.py` (~línea 398) escribe literalmente
`"lamina": None` y nada propaga `condiciones_emision.lamina → instrumentos.lamina`. Leer `lamina`
de la vista `resumen` o de `instrumentos` devolvería NULL siempre. La única fuente viva es la
tabla `public.condiciones_emision` (823 filas, 568 con lámina = 69 % de cobertura; su origen es el
CSV curado `data/condiciones_emision.csv`, que es irrecuperable — ver CLAUDE.md).

**PROHIBIDO ABSOLUTO — con todas las letras**: NO propagar la lámina a `instrumentos.lamina`
tocando `backend/app/ingesta/consolidacion/armado.py` ni nada de `backend/app/ingesta/**`. Ese
archivo lo modifican F-051 (métricas propias) y F-052 en esta misma secuencia de tandas: tocarlo
desde acá genera un conflicto de merge y rompe la tanda. La vía correcta es el LEFT JOIN a
`condiciones_emision` en `backend/app/universo/lectura.py`, **que ya hizo la base común de la
tanda 8b antes de soltar esta feature** (ver `plan-ejecucion-tandas.md`, fila 8b: "JOIN a
`condiciones_emision` en `universo/lectura.py` + campos `lamina` y `sector` en `EspecieUniverso`").

**Endpoint: no hace falta uno nuevo.** `GET /api/v1/universo/emisiones/especies` — que el armador
ya consume entero vía `traerUniversoEntero()` en
`frontend/src/features/armador/lib/especies.ts` — trae `lamina` sola una vez que está en
`EspecieUniverso.como_dict()`. **Alternativa descartada**: `GET /api/v1/instrumentos/{ticker}/condiciones`
(F-039) devuelve el triplete `lamina`/`lamina_origen`/`lamina_fecha`, pero es 1 request por
ticker: una cartera de 10 posiciones haría 10 requests para un dato que ya viaja en la lista que
la pantalla tiene cacheada, y duplicaría la fuente de verdad del componente. No usarlo acá.

**Trazabilidad — decisión tomada**: la fila de la cartera muestra la lámina pero **no** el
origen/fecha. El triplete no viaja por `/especies` (la base común sólo sube `lamina`), y traerlo
exigiría o ampliar un archivo compartido de la tanda (prohibido) o el request por ticker recién
descartado. El origen ya se consulta a un clic: la ficha del instrumento (F-039,
`frontend/src/features/instrumento/FichaInstrumento.tsx`, `BloqueCondiciones`/`campoDeCondicion`)
muestra "Lámina" con tooltip `origen · fecha`. No reinventar ese criterio acá.

## Parte 0 — Verificación de la base común (ANTES de escribir una línea)

La base común de la tanda 8b se hace a mano antes de soltar los agentes. Verificar que existe:

1. `backend/app/universo/segmentacion.py` → `EspecieUniverso` tiene el campo
   `lamina: float | None` (y `sector: str | None`) **y** la clave `"lamina"` en `como_dict()`.
2. `backend/app/universo/lectura.py` → el SQL tiene un LEFT JOIN a `public.condiciones_emision`.
3. `curl` mental equivalente: el item de `/api/v1/universo/emisiones/especies` incluye `lamina`.

**Si cualquiera de los tres falta: FRENAR y reportar. NO implementarlo por cuenta propia** —
`lectura.py` y `segmentacion.py` son archivos compartidos de la tanda (F-052 también los consume)
y agregarles el campo desde este agente es exactamente el conflicto que la base común existe para
evitar. Al 07/08/2026, fecha de este plan, la base común **todavía no está en el repo** (verificado:
`segmentacion.py` no tiene `lamina` y `lectura.py` no tiene el JOIN); el plan asume que va a estar
cuando esta feature arranque, y por eso la verificación es obligatoria, no decorativa.

Ojo al detalle: `condiciones_emision.lamina` es `numeric` en Postgres y asyncpg la devuelve como
`Decimal` (está documentado en `backend/app/condiciones/persistencia.py`). Si la base común la
dejó sin convertir a `float`, el test backend de la Parte 1 lo va a mostrar — reportarlo, no
parcharlo en archivos compartidos.

## Parte 1 — Backend: sólo un test (condicional)

**Archivo**: `backend/tests/test_universo_emisiones_api.py`. Tiene la factory
`fila(ticker, *, duration, completa)` con las claves crudas de la vista (hoy: `ticker`,
`clase_activo`, `tipo_tasa`, `tir`, `tna`, `duration`, `maturity`, `law`, `couponCurrency`,
`underlying`).

- **Verificar primero si la base común ya dejó cubierto** que `lamina` viaja por
  `GET /api/v1/universo/emisiones/especies` (buscar `lamina` en `backend/tests/`). Si sí,
  declararlo en el reporte y no duplicar el test.
- Si no: agregar la clave `lamina` a la factory `fila(...)` como parámetro opcional con default
  `None` (verificar el nombre exacto de la clave que la base común usó en `COLUMNAS`/el JOIN de
  `lectura.py` y usar ése), y un test nuevo:
  - una fila con `lamina=100.0` → el item de la vista viva (`/especies`) trae `"lamina": 100.0`
    (número, no string: acá se cae el `Decimal` sin convertir);
  - una fila sin lámina → `"lamina": None`. No se estima, no se rellena.
- No tocar ningún otro test ni módulo del backend.

## Parte 2 — `frontend/src/features/armador/lib/schema.ts`

En `esquemaEspecie` (línea ~116), agregar el campo:

```ts
/** Lámina mínima de la emisión, de `condiciones_emision` vía la base común de la tanda 8b.
 *  `null` = no informada: no se redondea y se declara (F-024, regla 1 del proyecto). */
lamina: z.number().nullable(),
```

Nada más de este archivo cambia. (El zod del monitor en `features/monitor/lib/schema.ts` no usa
`.strict()`, así que el campo nuevo del backend no lo rompe — verificado; igual está prohibido
tocarlo.)

## Parte 3 — `frontend/src/features/armador/lib/resolver.ts`

El núcleo no se toca: `vn = Math.floor(objetivo / (precio / 100) / lamina) * lamina` ya está y ya
está testeado ("redondea siempre hacia abajo, nunca hacia arriba"). Lo que falta es el **total
ajustado que excluye las posiciones sin lámina** y el conteo/porcentaje de cobertura del GWT-3.
Para no romper el contrato de F-018 (`resolver` devuelve `PosicionResuelta[]` y sus tests
destructuran el array), se agrega una función pura aparte, no se cambia el retorno de `resolver`:

1. **`PosicionResuelta` gana un campo passthrough**:
   ```ts
   /** Una lámina faltante en un FCI no es un dato faltante: a un FCI no le corresponde lámina.
    *  El resumen de ajuste lo necesita para no contarlo como "lámina no informada". */
   esFci: boolean
   ```
   Poblarlo en `sinResolver` (`esFci: entrada.esFci`) y en el map principal de `resolver`.

2. **Nuevo export en el mismo archivo**:
   ```ts
   export interface ResumenAjuste {
     /** Posiciones a las que una lámina les corresponde (excluye FCI). */
     ajustables: number
     /** De esas, cuántas quedaron sin lámina informada. */
     sinLamina: number
     /** Σ invertidoUsd de las posiciones con lámina informada y resueltas.
      *  `null` cuando ninguna posición ajustable tiene lámina: un total que no existe no es 0. */
     totalAjustadoUsd: number | null
     /** Σ pesoReal de las posiciones sin lámina: el % de la cartera fuera del total ajustado.
      *  `null` cuando ninguna posición está resuelta (no hay cartera medible sobre la que
      *  declarar un porcentaje). Una posición sin lámina y además sin resolver (sin precio o sin
      *  TC) cuenta en `sinLamina` pero no puede aportar al porcentaje: su pesoReal es null y no
      *  se le inventa uno. */
     pctSinAjustar: number | null
   }

   export function resumenAjuste(resueltas: PosicionResuelta[]): ResumenAjuste
   ```
   Semántica exacta:
   - `ajustables` = posiciones con `!esFci`.
   - `sinLamina` = de las ajustables, las que tienen `laminaConocida === false`.
   - `totalAjustadoUsd` = suma de `invertidoUsd` de las ajustables con `laminaConocida === true`
     e `invertidoUsd !== null`; si no hay ninguna con lámina, `null`.
   - `pctSinAjustar` = suma de `pesoReal` (ignorando `null`) de las `sinLamina`; si ninguna
     posición de la cartera tiene `pesoReal` (nada resuelto), `null`; si hay resueltas y las
     sin-lámina son cero, es `0` — un cero real, no un faltante.
   - Notar que `pesoReal` ya usa el denominador Σ`invertidoUsd`, así que el porcentaje declarado
     es consistente con lo que las filas muestran, sin un segundo criterio de reparto.

3. Actualizar el docstring del módulo: una línea que diga que F-024 cablea la lámina real desde
   `condiciones_emision` (vía `/especies`) y que el resumen de ajuste vive acá para testearse puro.

## Parte 4 — `frontend/src/features/armador/components/CarteraEditable.tsx`

1. **La línea que desbloquea todo** (línea ~68). Reemplazar:
   ```ts
   lamina: null, // F-024 (tanda 8) todavía no cablea la lámina real: nunca se inventa una acá.
   ```
   por:
   ```ts
   // F-024: la lámina real, de condiciones_emision vía /especies. `null` = no informada: el
   // resolver no redondea y la fila lo declara. Jamás un default (regla 1 del proyecto).
   lamina: p.esFci ? null : (especie?.lamina ?? null),
   ```
   Y actualizar el párrafo del docstring del módulo que dice "La lámina real todavía no está
   cableada (la trae F-024, tanda 8)": ya no es cierto.

2. **Cabecera — el resumen de cobertura (GWT-3)**. Después del `useMemo` de `resueltas`, calcular
   `const ajuste = useMemo(() => resumenAjuste(resueltas), [resueltas])`. En el `<header>`,
   después del Campo "Invertido", agregar:
   - `<Campo etiqueta="Invertido ajustado">` con
     `ajuste.totalAjustadoUsd !== null ? fmtMonto(ajuste.totalAjustadoUsd, 'usd') : SIN_DATO`
     (mono, `var(--tx)`).
   - Debajo de la fila de Campos (o al final del header, ancho completo: `flexBasis: '100%'`),
     una leyenda en `fontSize: 11, color: 'var(--dim)'` cuyo texto **explica también los ceros**
     — la casa exige explicar un cero, no aceptarlo:
     - `ajuste.sinLamina > 0` →
       `"{sinLamina} de {ajustables} posiciones sin lámina informada — {fmtPct(pctSinAjustar)} de la cartera fuera del total ajustado"`;
       si `pctSinAjustar === null`, cerrar con `"— porcentaje sin calcular: posiciones sin resolver"`.
     - `ajuste.sinLamina === 0 && ajuste.ajustables > 0` →
       `"todas las posiciones con lámina informada: el total ajustado cubre la cartera"`.
     - `ajuste.ajustables === 0 && pos.length > 0` →
       `"sólo FCI en la cartera: no hay nominales que redondear"`.
     - `pos.length === 0` → no se muestra leyenda (ya está el estado vacío).
3. **La fila**. En `FilaCartera`, en el renglón mono de 10 px que hoy dice
   `VN {…} · {invertido}`:
   - con `resuelta?.laminaConocida === true` y la especie con `lamina` numérica, agregar al final
     `· lám. {fmtNumero(especie.lamina, 0)}`;
   - con lámina no informada y `!posicion.esFci`, agregar al final un `<span>` con el texto
     literal `lámina no informada` en `color: 'var(--ac2)'` (GWT-2: la marca es visible en la
     fila, no sólo un tooltip).
   - El pedido y el real ya están los dos a la vista (input de peso + columna `pesoReal`): GWT-1
     no necesita elementos nuevos, sólo que la lámina de verdad llegue. No duplicar columnas.
   - En `motivoDiferencia`, cambiar el literal `'sin lámina conocida'` por
     `'lámina no informada'` para usar el mismo vocabulario que la ficha (F-039) y que la marca
     de la fila.
4. **Contrato interno para F-020 (tanda 9)** — la duda de solape 2 de `plan-ejecucion-tandas.md`
   dice que F-020 también agrega elementos a esta tabla. Dejar documentada la forma de la fila
   para que F-020 la **extienda en vez de duplicarla**: junto a la constante `GRID_FILA`, un
   comentario que enumere las columnas en orden (ticker+moneda · emisor+VN/invertido/lámina ·
   peso pedido · peso real · minicalendario · quitar) y diga explícitamente:
   `// F-020 (tanda 9): para agregar columnas, extender GRID_FILA y FilaCartera acá — no crear otra fila.`

## PROHIBIDO tocar

- `backend/app/ingesta/**` — en particular `backend/app/ingesta/consolidacion/armado.py`
  (lo modifican F-051/F-052; el porqué está arriba, en "De dónde sale la lámina").
- `backend/app/universo/lectura.py` y `backend/app/universo/segmentacion.py` — son la base común
  de la tanda 8b, se **verifican** (Parte 0), no se editan. Si les falta algo: FRENAR.
- `backend/app/api/v1/**` — no hace falta ningún endpoint nuevo ni cambio de router.
- `frontend/src/features/monitor/**` — el armador no importa nada de ahí (ya está declarado en
  `especies.ts` y en `schema.ts`).
- `frontend/src/lib/api/queryKeys.ts`.
- `frontend/src/features/armador/store/carteraStore.tsx`, `ArmadorPage.tsx` y cualquier barra de
  filtros nueva — **F-017 corre en paralelo en esta misma tanda sobre esos archivos**. F-024 y
  F-017 comparten carpeta pero no archivos; cruzarse ahí rompe la tanda.
- `frontend/src/features/instrumento/**` — la ficha (F-039) se mira como referencia, no se edita.
- `package.json` / dependencias nuevas — no hacen falta.
- Nada de `git add` / `git commit`: el cierre de tanda lo hace otro.

## Reglas del dominio que esto NO puede violar

1. **Regla 1 — nunca inventar un dato — es LA regla de esta feature.** Sin lámina informada no
   hay redondeo, no hay default de 1 ni de 1.000 ni "el estándar del mercado", y la posición se
   excluye del total ajustado declarándolo. Un default de lámina produce nominales que parecen
   correctos y no lo son, en la pantalla que el asesor lleva a la reunión. Textual de la ficha.
2. **Nunca redondear hacia arriba.** `Math.floor` en el resolver es a propósito: comprar de más
   que lo pedido no es una aproximación, es plata puesta sin que el asesor la haya pedido.
3. **Regla 3 — nada se compara entre monedas sin normalizar.** El total ajustado suma
   `invertidoUsd`, ya normalizado por el TC implícito del propio universo; sin TC la posición en
   ARS queda sin resolver y así se declara. No tocar esa lógica.
4. **Lo excluido se declara con nombre y número**: cuántas posiciones y qué % de la cartera
   quedaron fuera del total ajustado — y un cero también se explica (cero sin lámina = cobertura
   total declarada; cero con lámina = total ajustado inexistente, `null`, no un 0 que parezca
   plata).
5. La pantalla no "hace coincidir" pedido y real: si la lámina obliga a redondear, la diferencia
   se ve, no se maquilla (docstring de `CarteraEditable`, F-018).

## Test Strategy

### `frontend/src/features/armador/__tests__/resolver.test.ts` (motor puro, factory `entrada(extra)`)
- **GWT-1**: posición al 16,5 % con `lamina: 100` y monto que no dé redondo → `vn` es múltiplo
  exacto de 100, redondeado hacia abajo, y `peso` (16,5) y `pesoReal` viajan los dos y difieren.
- **GWT-2**: `lamina: null` → `vn` sin redondear (ya existe el test "no pisa a ningún múltiplo";
  extenderlo o sumarle uno que aserte además `resumenAjuste`: `sinLamina: 1` y
  `totalAjustadoUsd: null`).
- **GWT-3**: cartera de **siete** posiciones, **dos** sin lámina → `resumenAjuste` da
  `ajustables: 7`, `sinLamina: 2`, `totalAjustadoUsd` = suma exacta de las cinco con lámina, y
  `pctSinAjustar` = suma de los `pesoReal` de las dos sin lámina.
- **El caso real de los 255 tickers sin lámina** (823 curados − 568 con lámina): una cartera
  donde **ninguna** posición trae lámina — que es lo que la pantalla muestra hoy para cualquier
  ticker sin fila curada → nada se redondea, `sinLamina === ajustables`,
  `totalAjustadoUsd === null` (no 0) y `pctSinAjustar ≈ 100`.
- **Cero explicado, las dos puntas**: (a) todas con lámina → `sinLamina: 0` y `pctSinAjustar: 0`
  (cero real, no null); (b) FCI solo en la cartera → `ajustables: 0`, `sinLamina: 0`,
  `totalAjustadoUsd: null` — el FCI no cuenta como "lámina no informada".
- Posición sin lámina y además sin resolver (precio null): cuenta en `sinLamina`, no aporta a
  `pctSinAjustar`.

### `frontend/src/features/armador/__tests__/CarteraEditable.test.tsx` (factory `especie(extra)`, mock de fetch por URL)
- **Primero**: agregar `lamina: null` al default de la factory `especie()` — sin eso el zod nuevo
  hace fallar todos los tests existentes del archivo (el esquema valida entero a propósito).
- **GWT-1 por la UI**: especie con `lamina: 100`, monto 10.000, peso 50 → la fila muestra un VN
  múltiplo de 100 y el peso pedido (input) y el real (columna) a la vista, distintos.
- **GWT-2 por la UI**: especie con `lamina: null` → la fila muestra el texto `lámina no
  informada` y el VN es el de F-018 sin redondear (no aparece ningún múltiplo inventado).
- **GWT-3 por la UI**: dos especies, una con lámina y una sin → la cabecera muestra "1 de 2
  posiciones sin lámina informada" con el porcentaje, y el Campo "Invertido ajustado" suma sólo
  la que tiene lámina.
- Cobertura total: todas con lámina → la leyenda dice que el total ajustado cubre la cartera.

### Backend
- Ver Parte 1: `lamina` numérica viaja por `/especies` y `None` cuando falta — **sólo si la base
  común no lo dejó ya cubierto**; si lo cubrió, declararlo en el reporte en lugar de duplicar.

## Comandos de verificación

```
Frontend (cd /Users/jeroniki/Documents/Github/10-Swaper/frontend):
  npx vitest run src/features/armador
  npm run lint

Backend (cd /Users/jeroniki/Documents/Github/10-Swaper/backend):
  source venv/bin/activate
  python -m pytest tests/ -x -q
  ruff check . && ruff format --check .
```

El marcador real de integración en `backend/pyproject.toml` es `integration`, y `addopts` ya trae
`-m 'not integration'`: el `pytest` pelado de arriba corre offline solo, no hace falta filtrar a
mano. No correr la suite entera del frontend (F-017 trabaja en paralelo en la misma carpeta con
otros archivos); la corre el cierre de la tanda.

## Al terminar, reportar

- El resultado de la Parte 0 (la base común estaba o no; si no estaba, acá terminó todo y el
  reporte lo dice).
- Si el test backend de `lamina` ya venía cubierto por la base común o hubo que escribirlo.
- Archivos creados/modificados y el resultado textual de los comandos.
- Cuántas posiciones de una cartera de prueba real quedaron "lámina no informada" (el universo
  hoy cubre 568 de 823 emisiones curadas: el estado normal es que haya faltantes, y verlos
  declarados es la feature funcionando, no un bug).
- Cualquier punto donde el plan no cerró contra la realidad del código y qué se hizo — que debe
  ser: frenar esa parte y reportarla, no improvisar.
