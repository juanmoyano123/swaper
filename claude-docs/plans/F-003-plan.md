# Feature Plan: F-003 — Esqueleto de aplicación frontend

## Overview

- **Source:** `claude-docs/planning/plan.md` (ficha F-003, líneas 221–252) + `claude-docs/planning/design-system.md` (handoff Cordillera v2) + contrato de API de F-001 (`backend/app/core/errors.py`, `backend/app/core/pagination.py`, `backend/app/api/v1/`).
- **Complejidad:** M
- **Estimación:** 2–3 días. Es scaffolding con decisiones, no lógica de negocio: el costo está en dejar convenciones correctas, no en la cantidad de código.
- **Depende de:** F-001 (terminada). **Habilita:** F-013, F-014, F-016, F-038 y transitivamente toda la UI.
- **Branch:** `feature/F-003`, un solo commit al cierre (regla del proyecto: una feature = un commit).

### Las seis pantallas — mapa de rutas aprobado

Había una contradicción entre la spec y el diseño: el criterio de aceptación de F-003
(`plan.md:241-243`) y `product-definition.md:529-539` piden seis pantallas navegables, mientras que
`design-system.md:41` describe una sola ruta con toggle Armado/Seguimiento más drawer. **El usuario
ya decidió: seis rutas.** Este mapa está aprobado y no se replantea:

| # | Pantalla | Ruta | Qué carga cada feature posterior |
|---|---|---|---|
| 1 | Login | `/login` | F-014 (auth por invitación) |
| 2 | Armador | `/armador` | Diseño Cordillera sección A completo (A1–A9), F-016/F-017/F-018 |
| 3 | Optimizador | `/optimizador` | F-028 (ingreso de cartera), F-030+ |
| 4 | Monitor de mercado | `/monitor` (y `/` redirige acá) | F-038 |
| 5 | Mis carteras | `/carteras` | Mis carteras (F-041) **más la sección B "Seguimiento" de Cordillera** |
| 6 | Detalle de instrumento | `/instrumento/:ticker` | F-039 — el drawer de ficha, con URL propia |

`/monitor` es el índice porque es "la pantalla de entrada diaria" (ficha F-038). En F-003 cada
pantalla es un esqueleto: layout, título y `EstadoVacio` que declara qué feature la construye —
navegable, sin errores de consola, sin funcionalidad simulada. La sección B "Seguimiento" del
prototipo vive bajo `/carteras`, no dentro de `/armador`; el placeholder de `/carteras` lo dice.

El detalle de instrumento tiene URL propia para poder compartir el link, pero **sigue viéndose como
drawer/overlay sobre la ruta de fondo** cuando se abre navegando desde adentro de la app. F-003
implementa esa mecánica de router (background location, ver decisión 15); F-039 llena el contenido.

## Implementation Approach

**Patrón: SPA por features con capa `lib/` compartida.** Tres capas:

1. `app/` — bootstrap: providers (QueryClient, ErrorBoundary), router, layout global con barra
   superior. Es lo único que conoce a todas las features.
2. `lib/` — infraestructura sin UI: cliente de API tipado, esquemas Zod del contrato, query keys,
   hook de paginación, formateadores es-AR, tema. Ninguna feature reimplementa nada de esto.
3. `features/<nombre>/` — una carpeta por feature de producto, con la estructura interna que ya usa
   el sub-agente `feature-builder` (`components/`, `hooks/`, `services/`, `types/`, `__tests__/`).
   En F-003 cada feature tiene solo su página; las subcarpetas se crean cuando se necesitan.
4. `components/` — UI compartida entre features (estados de carga/error/vacío, panel base). Regla:
   un componente nace en su feature y se promueve a `components/` recién cuando lo usa una segunda
   feature. Las excepciones de F-003 (`EstadoCarga`, `EstadoError`, `EstadoVacio`, `Panel`) nacen
   compartidas porque su razón de ser es ser la convención global.

**Alternativas descartadas:**

- *Estructura por tipo* (`pages/`, `hooks/`, `services/` en la raíz): con 20+ features de UI por
  delante, agrupar por tipo dispersa cada feature en cuatro directorios y hace imposible saber qué
  se puede borrar. Por features escala y coincide con la convención del agente que las construye.
- *Axios / ky / openapi-fetch como cliente HTTP*: `fetch` nativo + Zod alcanza. El contrato de F-001
  es chico y estable (error uniforme + `Page[T]`); generar tipos desde OpenAPI se puede evaluar
  cuando haya más de ~10 endpoints, no ahora.
- *`createBrowserRouter` (data router de React Router 7)*: se usa `BrowserRouter` + `<Routes>`
  declarativas. El patrón de background location para el drawer de instrumento (decisión 15) se
  implementa naturalmente con `<Routes location={fondo ?? location}>`, que es el mecanismo
  documentado de React Router para modales con URL; con el data router ese patrón es más forzado. Y
  los loaders/actions del data router no aportan acá: los datos los maneja TanStack Query.
- *Zustand ahora*: F-003 no tiene estado de cliente global más allá del tema. El estado del armador
  (F-016/F-018) decidirá su store cuando exista; instalarlo hoy sería elegir a ciegas.
- *react-error-boundary como dependencia*: el boundary necesario son ~30 líneas de componente de
  clase. No se agrega dependencia por eso.
- *MSW para tests*: para F-003 alcanza con stubear `fetch` (`vi.stubGlobal`). MSW entra cuando haya
  endpoints de datos reales con flujos de varias requests.

## File Structure

### Crear

```
frontend/src/app/App.tsx                    Providers (QueryClientProvider, ErrorBoundary) + BrowserRouter
frontend/src/app/router.tsx                 <AppRoutes/>: las seis rutas + redirect de / + background location del drawer
frontend/src/app/AppLayout.tsx              Topbar sticky de 52 px + slot de barra de estado + <Outlet/>
frontend/src/app/BarraSuperior.tsx          Marca, nav de secciones, EstadoBackend, botón de tema ☾/☀
frontend/src/app/ErrorBoundary.tsx          Boundary de clase: panel con mensaje y botón "Recargar"
frontend/src/app/queryClient.ts             QueryClient con defaults + tiempos por tipo de dato (exportados)
frontend/src/lib/api/client.ts              apiFetch<T> tipado: base URL, parseo Zod, mapeo a ApiError
frontend/src/lib/api/errors.ts              ApiError y ErrorDeRed, con mensajeParaUsuario()
frontend/src/lib/api/schemas.ts             esquemaError (contrato F-001), esquemaSalud, esquemaPagina(T)
frontend/src/lib/api/queryKeys.ts           Factory jerárquica de query keys (claves.salud, claves.mercado…)
frontend/src/lib/api/usePaginaQuery.ts      Wrapper de useInfiniteQuery para Page[T] con cursor opaco
frontend/src/lib/fmt.ts                     Formateadores es-AR + constantes SIN_DATO ('s/d') y NO_APLICA
frontend/src/lib/theme.ts                   TEMA_STORAGE_KEY, leerTema, aplicarTema, hook useTema
frontend/src/components/Panel.tsx           Panel base: fondo --pan, borde 1px --lin, radio 4px, padding 12–16
frontend/src/components/EstadoCarga.tsx     Convención única de "cargando" (texto mono 11px --dim + pulso)
frontend/src/components/EstadoError.tsx     Convención única de fetch fallido: mensaje + code + request_id + reintentar
frontend/src/components/EstadoVacio.tsx     Convención única de "acá no hay nada" con explicación del porqué
frontend/src/features/salud/useSalud.ts     useQuery de GET /api/v1/health con refetchInterval
frontend/src/features/salud/EstadoBackend.tsx  Chip en topbar: ● conectado / servicio no disponible
frontend/src/features/auth/LoginPage.tsx    Placeholder (F-014), fuera del AppLayout
frontend/src/features/auth/RequiereSesion.tsx  Guard placeholder: hoy passthrough, F-014 lo enchufa (decisión 16)
frontend/src/features/monitor/MonitorPage.tsx      Placeholder (F-038)
frontend/src/features/armador/ArmadorPage.tsx      Placeholder; acá vive Cordillera sección A (F-016+)
frontend/src/features/optimizador/OptimizadorPage.tsx  Placeholder (F-028+)
frontend/src/features/carteras/CarterasPage.tsx    Placeholder: Mis carteras + sección B Seguimiento (F-041)
frontend/src/features/instrumento/InstrumentoPage.tsx  Placeholder (F-039); página completa al entrar por URL directa
frontend/src/features/instrumento/InstrumentoDrawer.tsx  Overlay de 430 px sobre la ruta de fondo (mismo placeholder adentro)
frontend/src/features/instrumento/useAbrirInstrumento.ts  navigate('/instrumento/:t', { state: { fondo } }) — la única forma de abrir la ficha desde adentro
frontend/src/test/setup.ts                  jest-dom + limpieza de localStorage entre tests
frontend/src/lib/api/__tests__/client.test.ts        Contrato de error, ErrorDeRed, parseo Zod
frontend/src/lib/api/__tests__/usePaginaQuery.test.tsx  Encadenado de next_cursor y fin de páginas
frontend/src/lib/__tests__/fmt.test.ts               es-AR, s/d vs 0, no aplica
frontend/src/lib/__tests__/theme.test.ts             Persistencia y default oscuro
frontend/src/app/__tests__/router.test.tsx           GWT-1: seis rutas sin console.error
frontend/src/components/__tests__/EstadoError.test.tsx  GWT-2: mensaje del contrato + request_id visibles
```

### Modificar

```
frontend/index.html          lang="es", script inline anti-flash de tema (ver decisión 5)
frontend/src/index.css       Quitar @media prefers-color-scheme y el bloque [data-theme="dark"] redundante;
                             agregar color-scheme por tema y utilidades mínimas (ver decisión 5)
frontend/src/main.tsx        Importar App desde app/App.tsx
frontend/vite.config.ts      Proxy /api → http://localhost:8000, alias @ → src, bloque test de Vitest
frontend/tsconfig.app.json   Agregar "strict": true y paths para @/*  ← hoy TS corre SIN strict; se corrige acá
frontend/tsconfig.node.json  Agregar "strict": true
frontend/package.json        Scripts test/test:watch; devDependencies de test
frontend/.oxlintrc.json      Agregar plugin "vitest" para los archivos de test
```

### Eliminar

```
frontend/src/App.tsx         Reemplazado por app/App.tsx (el placeholder actual muere acá)
```

`frontend/src/types/database.types.ts` **no se toca** (ver decisión 2).

## Dependency Map

- **Depende de:** contrato de F-001 (solo lectura; el backend no se modifica). El único endpoint
  consumido de verdad en F-003 es `GET /api/v1/health`.
- **Comparte hacia adelante:** todo `lib/`, `components/` y `app/` son las utilidades que heredan
  F-013, F-014, F-016, F-028, F-038 y el resto de la UI.
- **Paquetes ya instalados que se usan:** `react@19`, `react-router-dom@7`,
  `@tanstack/react-query@5`, `zod@4`, `tailwindcss@4` (vía `@tailwindcss/postcss`). No se usan
  todavía (quedan para sus features): `@tanstack/react-table` (F-038), `recharts` (F-016+).
- **Paquetes nuevos (devDependencies, última estable al instalar):**
  - `vitest` (^4)
  - `@vitest/coverage-v8` (^4)
  - `@testing-library/react` (^16 — compatible React 19)
  - `@testing-library/jest-dom` (^6)
  - `@testing-library/user-event` (^14)
  - `jsdom` (^27)

  Instalar con `npm install -D` sin pin exacto; el lockfile fija la versión.

## Edge Cases & Technical Decisions

1. **Cliente de API: `fetch` + Zod en el borde, errores como clases.**
   `apiFetch<T>(ruta, esquema, init?)` en `lib/api/client.ts`: antepone la base
   (`import.meta.env.VITE_API_URL ?? ''` — vacío en dev porque el proxy de Vite resuelve `/api`),
   hace la request, y:
   - **2xx** → parsea el body con el esquema Zod recibido. Si el parseo falla, lanza `ApiError` con
     `code: 'contract_mismatch'`: una respuesta que no cumple el contrato es un bug que se quiere
     ver en desarrollo, no un dato que se muestra a medias (regla 1 de CLAUDE.md aplicada al borde).
   - **no-2xx** → intenta parsear `{"error": {code, message, details, request_id}}` (contrato de
     `errors.py`). Si matchea, lanza `ApiError` con esos campos. Si no matchea (caso real: el 503 de
     `/health` devuelve `HealthResponse`, no el shape de error), lanza `ApiError` con el `code`
     derivado del status (`service_unavailable`, etc.) y mensaje genérico.
   - **fetch rechazado** (backend caído, sin red) → lanza `ErrorDeRed`. Es una clase distinta a
     propósito: "el servicio no responde" y "el servicio respondió con un error" son estados
     diferentes para el usuario y para el retry.
   - `request_id` **sí se expone al usuario**, en letra chica mono dentro de `EstadoError`
     ("código de soporte: `abc123`"): es exactamente para qué existe según `errors.py` — que un
     error reportado por un asesor se rastree en el log sin adivinar.

2. **`database.types.ts` NO se usa en el cliente de API.** Ese archivo tipa el acceso directo a
   Supabase (PostgREST) y es el contrato de F-014 en adelante, cuando entre `supabase-js`. El
   cliente HTTP de F-003 tipa contra lo que expone FastAPI, que no son las tablas: son modelos
   Pydantic (`Page[T]`, `HealthResponse`, vistas calculadas). Acoplar los dos contratos obligaría a
   que cada endpoint devuelva filas crudas. Se deja constancia en un comentario en
   `lib/api/schemas.ts`: "los tipos de tablas viven en `types/database.types.ts` y se usan solo con
   el cliente de Supabase".

3. **TanStack Query: defaults conservadores + tiempos por tipo de dato + invalidación por prefijo.**
   En `app/queryClient.ts`:
   - Defaults globales: `refetchOnWindowFocus: false` (el dato de mercado tiene demora declarada de
     20 minutos — refetchear al foco de ventana simula una frescura que la fuente no tiene),
     `staleTime: 60_000`, `retry` como función: nunca reintentar `ApiError` 4xx (es determinístico),
     hasta 2 reintentos para `ErrorDeRed` y 5xx.
   - Constantes exportadas por tipo de dato, que las features futuras importan en sus hooks:
     `TIEMPOS.mercado = { staleTime: 5 min }` (el refresh explícito invalida, no el reloj),
     `TIEMPOS.referencia = { staleTime: Infinity }` (condiciones de emisión: cambian por ingesta,
     no por tiempo), `TIEMPOS.salud = { staleTime: 0, refetchInterval: 60_000 }`.
   - **Política de invalidación:** las query keys son jerárquicas por dominio via factory en
     `lib/api/queryKeys.ts` — `claves.salud`, `claves.mercado.todas`, `claves.mercado.universo(seg)`,
     `claves.referencia.todas`, `claves.carteras.todas`. El contrato para el refresh de precios
     (F-008/F-013 en adelante) queda escrito en ese archivo: *un refresh exitoso ejecuta
     `queryClient.invalidateQueries({ queryKey: claves.mercado.todas })` y nada más*. Invalidar por
     prefijo es lo que hace que ninguna feature tenga que enumerar qué queries dependen del precio.

4. **Paginación por cursor: `usePaginaQuery`.** Wrapper fino de `useInfiniteQuery`:
   recibe query key, ruta y esquema Zod del ítem; arma `esquemaPagina(item)` (`{ items: T[],
   next_cursor: string | null }` — espejo de `Page[T]` de `pagination.py`), pasa
   `initialPageParam: null` y `getNextPageParam: (ultima) => ultima.next_cursor` (que devuelve
   `null` al final, cortando solo). El cursor viaja como query param `?cursor=` tal cual llegó:
   **opaco, nunca se decodifica en el cliente** — ese es el contrato de F-001. Expone
   `{ items aplanados, cargarMas, hayMas, ...estados }`. F-038 lo consume para las ~1.700 filas.

5. **Tema: default oscuro determinístico, `data-theme` en `<html>`, script inline anti-flash.**
   - La preferencia vive en `localStorage` bajo `swaper-tema`, valores `'dark' | 'light'`.
   - `index.html` lleva un script inline de 3 líneas **antes** del bundle: lee la clave y setea
     `document.documentElement.dataset.theme`; sin clave guardada, `'dark'`. Como corre antes de la
     primera pintura, no hay flash de tema incorrecto. Es la única forma: cualquier solución dentro
     de React llega después del primer frame.
   - La spec dice "oscuro por defecto", no "seguir al sistema": se elimina de `index.css` el bloque
     `@media (prefers-color-scheme: light)` — con él, un asesor con el SO en claro vería claro por
     defecto, que es exactamente lo que la spec no pide. También se elimina el bloque
     `:root[data-theme="dark"]` (duplica los tokens de `:root`); quedan `:root` (oscuro,
     `color-scheme: dark`) y `:root[data-theme="light"]` (claro, `color-scheme: light`).
   - `lib/theme.ts` exporta el hook `useTema()` → `{ tema, alternar }`: alterna el atributo y
     persiste. El botón ☾/☀ vive en `BarraSuperior`, como en el prototipo.

6. **Manejo global de errores: dos niveles, ninguno en blanco.**
   - **Errores de render** (bugs): `ErrorBoundary` propio en `app/`, montado alrededor del router.
     Muestra un `Panel` con "Algo se rompió en la interfaz" y botón "Recargar". No intenta
     recuperación parcial: es una herramienta interna, recargar es aceptable.
   - **Errores de datos** (fetch fallido): **no** se usa `throwOnError` — cada vista renderiza
     `<EstadoError error={...} onRetry={refetch} />` en el lugar donde iban los datos. `EstadoError`
     es la traducción única del contrato: muestra `mensajeParaUsuario()` (el `message` del contrato
     para `ApiError`; "No hay conexión con el servicio" para `ErrorDeRed`), el `code`, el
     `request_id` como código de soporte, y el botón reintentar. Ninguna feature posterior escribe
     su propio estado de error.
   - **Backend caído** (caso real y esperable, health devuelve 503): `EstadoBackend` en la topbar lo
     muestra permanentemente — punto `--pos` con "conectado" o texto `--neg` "servicio no
     disponible", alimentado por `useSalud`. Ese chip es además el placeholder del slot donde F-013
     monta la barra de estado del dato completa; `AppLayout` deja el slot ya previsto.

7. **"Sin dato" y "cero" no se ven iguales.** En `lib/fmt.ts`:
   - Formateadores es-AR con `Intl.NumberFormat('es-AR')`: `fmtMonto` (`US$ 5.264,50`), `fmtNumero`,
     `fmtPct` (`7,27%`), `fmtCompacto` (`12,9 MM`), según la sección "Formato de números" del
     design system.
   - Todo formateador acepta `null | undefined` y devuelve la constante `SIN_DATO = 's/d'` — nunca
     `'0'`, nunca cadena vacía, nunca un guión mudo. `NO_APLICA = 'no aplica'` es una constante
     separada que la feature elige explícitamente (una acción no tiene TIR: eso no es un faltante).
     La distinción visual (s/d en `--dim`) queda documentada en el propio archivo.
   - Los formateadores **no reciben unidad implícita**: `fmtPct` formatea el número; el rótulo de la
     naturaleza de la tasa ("TIR USD", "CER + n%", "TNA") lo pone la feature al lado, siempre. Así
     la convención de formato no puede violar la regla 2 de CLAUDE.md (unidades que no se mezclan).

8. **Tests: Vitest + Testing Library se instalan ahora.** Justificación: los 3 GWT de F-003 son
   verificables por test, y el sub-agente `feature-builder` que construye todas las features
   posteriores tiene como regla "cada función con al menos 1 test" — sin runner instalado, esa regla
   es letra muerta desde la primera feature de UI. Configuración dentro de `vite.config.ts` (bloque
   `test`, `environment: 'jsdom'`, `setupFiles: ['src/test/setup.ts']`, sin `globals`: se importa
   `describe/it/expect` de `vitest`, que es lo que TS strict resuelve sin config extra).

9. **`strict: true` se enciende en F-003.** Hoy ningún tsconfig del frontend tiene `strict` — todo
   el TypeScript corre sin chequeo de nulls ni de `any` implícito. Encenderlo con 4 archivos es
   gratis; encenderlo con 40 features encima es una migración. Va en `tsconfig.app.json` y
   `tsconfig.node.json`.

10. **Alias `@/` → `src/`.** En `vite.config.ts` (`resolve.alias`) y `tsconfig.app.json`
    (`baseUrl` + `paths`). Con tres niveles de carpetas y 20+ features, los imports relativos
    `../../../lib/api/client` son ruido y se rompen al mover archivos.

11. **Proxy de Vite en dev.** `server.proxy: { '/api': 'http://localhost:8000' }`. Evita CORS sin
    tocar el backend y hace que el frontend hable siempre con rutas relativas `/api/v1/...`; en
    producción `VITE_API_URL` (variable de build) cubre el caso de dominios distintos. No se
    configura CORS en FastAPI: no hace falta con proxy y es una superficie menos.

12. **oxlint.** Ya está configurado (`.oxlintrc.json` con plugins react/typescript/oxc y
    `rules-of-hooks` en error) y el script `lint` existe. Único cambio: agregar `"vitest"` a
    `plugins` para que los archivos de test tengan sus reglas (`no-focused-tests`, etc.). No se
    agrega ESLint ni Prettier: una sola herramienta de lint, la que el proyecto ya eligió.

13. **Rutas placeholder honestas.** Cada página placeholder usa `EstadoVacio` con el texto "Esta
    pantalla la construye F-0XX" — nada de datos de ejemplo ni UI simulada. Los datos ficticios del
    prototipo Cordillera **no se copian**: mostrar una rueda ficticia en la app real viola la regla
    de no inventar datos, aunque sea decorativa. `InstrumentoPage` lee `:ticker` con `useParams` y
    lo muestra en el título (mono), para que la ruta parametrizada quede demostrada.

14. **El drawer de instrumento se resuelve con background location — decidido, se implementa en
    F-003.** Mecánica en `app/router.tsx`:
    - `<AppRoutes/>` lee `const fondo = location.state?.fondo` y renderiza el árbol principal con
      `<Routes location={fondo ?? location}>`. Si hay `fondo`, renderiza además un segundo
      `<Routes>` con solo `/instrumento/:ticker` → `<InstrumentoDrawer/>`, superpuesto.
    - **Abrir desde adentro** (armador, monitor, etc.): siempre via `useAbrirInstrumento()`, que
      hace `navigate(`/instrumento/${ticker}`, { state: { fondo: location } })`. La pantalla de
      fondo sigue montada con su estado y su scroll intactos; la URL de la barra es compartible.
    - **Entrar directo por URL** (link compartido, recarga): no hay `state.fondo`, así que el árbol
      principal matchea `/instrumento/:ticker` y renderiza `InstrumentoPage` como página completa
      dentro del `AppLayout`. Las dos vistas comparten el mismo componente de contenido; cambia el
      contenedor (drawer vs. página).
    - **Cerrar el drawer**: `navigate(-1)` si se llegó navegando (vuelve al fondo); el botón ✕ de
      la página completa navega a `/monitor`.
    - El drawer en F-003 es el contenedor con los estilos del design system (fijo a la derecha,
      `top: 52px`, 430 px, borde izquierdo `--ac`, sombra `-16px 0 40px rgba(0,0,0,.35)`,
      `z-index: 50`) con el placeholder adentro; F-039 pone la ficha real sin tocar el ruteo.
    - `location.state` no sobrevive a un hard reload con historial limpio ni a abrir en pestaña
      nueva: en esos casos se cae al modo página completa, que es exactamente el comportamiento
      deseado.

15. **Login queda con el enchufe de F-014 puesto pero sin auth.** `/login` renderiza fuera del
    `AppLayout` (no tiene topbar ni chip de salud). Las rutas de la app cuelgan de
    `<RequiereSesion>`, un componente en `features/auth/` que hoy devuelve `children` tal cual, con
    el comentario de contrato: F-014 lo reemplaza por la verificación de sesión + redirect a
    `/login`. No se implementa ninguna guarda funcional en F-003 — solo existe el punto único donde
    F-014 la va a enchufar sin tocar el resto del router.

16. **La topbar se construye con lo que F-003 puede sostener.** Del prototipo se toman: altura
    52 px sticky, fondo `--pan`, borde inferior `--lin`, marca "10-Swaper" (17 px / 700 /
    -0.01em), y el botón de tema. La navegación entre secciones es con `NavLink` (activo: fondo
    `--ac`, texto `--bg`, como el toggle del prototipo). **No** se incluyen todavía: selector de
    cliente, monto, conmutador de moneda, indicador "EN VIVO" — pertenecen al armador (F-016+) y
    ponerlos sin función sería UI muerta.

## Test Strategy

Runner: `npm run test` (Vitest, `vitest run`). Todos los tests en `__tests__/` junto a lo que prueban.

### Acceptance checks (GWT de la spec → verificación)

1. **GWT-1** — *seis rutas renderizan su layout sin errores de consola*:
   `app/__tests__/router.test.tsx` renderiza `<AppRoutes/>` dentro de `MemoryRouter` (con
   `initialEntries`) y los providers, y para cada una de las seis rutas (`/login`, `/armador`,
   `/optimizador`, `/monitor`, `/carteras`, `/instrumento/AL30D`) asserta con spies sobre
   `console.error` y `console.warn`: (a) el título de la pantalla está en el documento, (b) los
   spies no fueron llamados. Casos extra: `/` redirige a `/monitor`; una ruta inexistente muestra
   el NotFound (no pantalla en blanco); y el doble modo de la ficha — entrada con
   `initialEntries: ['/instrumento/AL30D']` renderiza la página completa dentro del layout,
   mientras que una entrada con `state: { fondo }` (simula la navegación interna via
   `useAbrirInstrumento`) renderiza el drawer **y** la pantalla de fondo sigue en el documento.
   Verificación manual complementaria en la sección end-to-end (la consola real del browser).

2. **GWT-2** — *endpoint con error → estado de error global con el mensaje del contrato, no
   pantalla en blanco*: dos tests.
   - `lib/api/__tests__/client.test.ts`: con `fetch` stubeado devolviendo 422 y el body exacto del
     contrato de `errors.py`, `apiFetch` lanza `ApiError` con `code`, `message`, `details` y
     `requestId` poblados; con `fetch` rechazando, lanza `ErrorDeRed`; con 503 y body que no cumple
     el shape de error (caso `/health`), lanza `ApiError` con `code: 'service_unavailable'`; con
     2xx y body que no cumple el esquema, lanza `contract_mismatch`.
   - `components/__tests__/EstadoError.test.tsx`: renderizado con un `ApiError` muestra el
     `message` del contrato y el `request_id`, y el botón reintentar dispara el callback; con un
     `ErrorDeRed` muestra "No hay conexión con el servicio".

3. **GWT-3** — *tema oscuro por defecto, alternar a claro persiste entre recargas*:
   `lib/__tests__/theme.test.ts`: sin nada en `localStorage`, `leerTema()` devuelve `'dark'`;
   `alternar` deja `data-theme="light"` en `<html>` y `'light'` en `localStorage['swaper-tema']`;
   una nueva lectura (simula la recarga) devuelve `'light'`. La ausencia de flash se verifica
   manualmente (es un script inline pre-bundle, fuera del alcance de jsdom).

### Tests de infraestructura (no atados a un GWT)

- `usePaginaQuery.test.tsx`: con `fetch` stubeado devolviendo dos páginas (`next_cursor: "abc"` →
  `next_cursor: null`), el hook encadena el cursor tal cual (se asserta la URL de la segunda
  request con `?cursor=abc`), aplana los ítems y reporta `hayMas: false` al final.
- `fmt.test.ts`: `fmtMonto(5264.5)` → `"US$ 5.264,50"` (coma decimal, punto de miles);
  `fmtPct(null)` → `"s/d"` y `fmtPct(0)` → `"0,0%"` (la distinción sin-dato/cero); `NO_APLICA`
  distinta de `SIN_DATO`.

## Verificación end-to-end

Desde `frontend/`, en este orden; todos tienen que pasar antes del commit:

```bash
npm install                  # instala las devDependencies nuevas; el lockfile queda commiteado
npm run lint                 # oxlint, 0 errores
npx tsc -b                   # typecheck estricto, 0 errores (primera corrida con strict: true)
npm run test                 # vitest run, toda la suite verde
npm run build                # tsc -b && vite build, el bundle se genera
```

Verificación manual con los dos servicios levantados
(`backend`: `source venv/bin/activate && uvicorn app.main:app --reload`; `frontend`: `npm run dev`):

1. Abrir `http://localhost:5173` → redirige a `/monitor`, consola del browser sin errores ni
   warnings. Navegar a las seis rutas desde la topbar: cada una muestra su layout y su placeholder
   honesto. `/login` se ve sin topbar (fuera del AppLayout).
2. Doble modo de la ficha: pegar `http://localhost:5173/instrumento/AL30D` en la barra → página
   completa dentro del layout. Desde `/armador`, disparar `useAbrirInstrumento` (el placeholder
   incluye un link de prueba) → el drawer se superpone, el armador sigue visible detrás con su
   scroll, y la URL de la barra es `/instrumento/AL30D`; cerrar con ✕ vuelve a `/armador`.
3. El chip de la topbar muestra "conectado" (el proxy `/api` → `:8000` funciona y `useSalud` lee
   `/api/v1/health`).
4. **Matar el backend** y esperar el próximo `refetchInterval` (≤60 s) o recargar: el chip pasa a
   "servicio no disponible". Ninguna pantalla queda en blanco.
5. Alternar el tema a claro → recargar la página → sigue claro y **sin flash oscuro** en la primera
   pintura (mirar con recarga dura, Cmd+Shift+R). Volver a oscuro → recargar → sigue oscuro.
6. `curl -s localhost:5173/api/v1/health | python3 -m json.tool` → responde el JSON del backend a
   través del proxy.

Cierre: correr el quality gate del agente (`/simplify` sobre los archivos modificados según su
regla pre-PR), commit único en `feature/F-003` y actualización de
`claude-docs/progress/PROGRESS.md` si el flujo del proyecto lo pide.
