# Feature Plan: F-004 — Cliente de la API abierta de BYMA

## Overview

- **Source:** `claude-docs/planning/plan.md` (ficha F-004, líneas 260–299) + base común de ingesta
  en `backend/app/ingesta/` + verificación empírica contra la API real (05 y 06/08/2026, ver
  "Hallazgos empíricos" abajo).
- **Complejidad:** M
- **Estimación:** 1–2 días. El cliente HTTP y los reintentos ya existen en la base común; el
  trabajo es la paginación verificada, la detección de forma y la normalización.
- **Depende de:** F-001 (terminada). **Habilita:** F-007 (consolidador), F-012 (contraste de
  índices), F-026.
- **Branch:** `feature/F-004`, un solo commit al cierre (una feature = un commit).
- **Ejecución en paralelo con F-005 y F-006:** este plan NO toca ningún archivo compartido. Todo lo
  nuevo vive en `app/ingesta/byma/` y las rutas van únicamente en `app/api/v1/byma.py`, que ya
  existe, ya está montado en `router.py`, y es propiedad exclusiva de esta feature.

### Hallazgos empíricos que corrigen la spec — LEER ANTES DE IMPLEMENTAR

La ficha de `plan.md` dice que los endpoints devuelven 4.909 / 189 / 2.267 / 189 / 16 filas. **Está
mal en un punto que causaría pérdida silenciosa de datos**: los números de la spec mezclan el
`page_size` por defecto con el total real. Verificado contra la fuente el 05–06/08/2026:

| Endpoint | Forma de la respuesta | Total real | La spec dice |
|---|---|---|---|
| `public-bonds` | objeto paginado (`content` + `data`) | **1106** (189/pág., 6 págs. por defecto) | 189 |
| `general-equity` | objeto paginado | **349** | 189 |
| `index-price` | objeto paginado | 16 (1 pág.) | 16 ✓ |
| `negociable-obligations` | **lista JSON plana**, sin metadatos | ~2181 | 4909 |
| `cedears` | **lista JSON plana**, sin metadatos | ~2107 | 2267 |

Hechos verificados que este plan da por contrato (cualquier desvío en runtime es
`formato_inesperado`, no un supuesto a reinterpretar):

1. **URL y método.** `POST https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free/<endpoint>`
   con `Content-Type: application/json`, sin token ni header de auth.
2. **El payload importa.** `{"excludeZeroPxAndQty": true, "T2": true}` devuelve **cero filas**.
   `{}` devuelve todo. Los endpoints de lista plana **ignoran** los parámetros de paginación
   (verificado: `negociable-obligations` con `{"page_size": 500}` devuelve la lista completa
   igual). Por lo tanto el payload es siempre `{"page_size": 500, "page_number": N}` y nada más.
3. **Objeto paginado:** `{"content": {"page_number", "page_count", "page_size",
   "total_elements_count"}, "data": [...]}`. Con `page_size: 500`, `public-bonds` responde
   `page_count: 3` y `total_elements_count: 1106`.
4. **Campos reales de las filas** (verificados en `public-bonds` y `negociable-obligations`):
   `symbol`, `bidPrice`, `quantityBid`, `offerPrice`, `quantityOffer`, `denominationCcy`,
   `settlementType`, `closingPrice`, `previousClosingPrice`, `openingPrice`, `tradingHighPrice`,
   `tradingLowPrice`, `vwap`, `volume`, `volumeAmount`, `tradeVolume`, `numberOfOrders`,
   `maturityDate`, `daysToMaturity`, `imbalance`, `market`, `securityDesc`, `securitySubType`,
   `securityType`, `trade`, `tradeHour`, `settlementPrice`, `previousSettlementPrice`,
   `openInterest`, `tickDirection`, `description`. En `index-price`: `symbol`, `description`,
   `price`, `previousClosingPrice`, `variation`, `highValue`, `minValue`, `date`, `isRate`,
   `country`.
5. **`denominationCcy` trae tres valores** en las ONs: `ARS`, `USD`, `EXT`. Se conservan tal cual
   vienen: no se traducen, no se interpretan, no se mapean a MEP/CCL (eso sería un juicio que la
   fuente no declara).
6. **TLS verifica bien con httpx + certifi.** El `curl -k` que hizo falta en la exploración era un
   problema del trust store de curl en macOS, no del certificado del servidor: httpx con la
   verificación por defecto respondió 200 en las tres variantes probadas (default, seclevel=1,
   sin verificar). **La verificación TLS queda activada, sin excepciones.** Ver decisión 7.

## Implementation Approach

**Un paquete `app/ingesta/byma/` con tres capas: descarga, normalización, orquestación.** La
descarga (`cliente.py`) sabe de HTTP, paginación y formas de respuesta, y devuelve filas crudas
tal como las publica BYMA. La normalización (`normalizacion.py`) es una función pura de dict crudo
→ fila canónica, sin red y sin estado, que es donde viven las reglas del dominio (moneda desde
`denominationCcy`, faltante = `None`). La orquestación (`ingesta.py`) recorre los cinco endpoints,
aísla los fallos de cada uno, arma el `Snapshot` y mide cobertura. El router (`app/api/v1/byma.py`)
sólo expone la orquestación.

Toda la política HTTP (reintentos 5× con espera 3/6/9/12 s, timeout 90 s, vacío reintentable,
4xx no reintentable) viene de `app.ingesta.http` — **no se reimplementa nada de eso acá**.

**Alternativas descartadas:**

- *Pedir los cinco endpoints con `asyncio.gather`*: se descarta por ahora; la corrida es batch
  (matinal + refresh intradiario de F-008), son ~10 requests en total y la ejecución secuencial
  hace el orden de tramos y de alertas determinístico, que simplifica tests y lectura de logs. Si
  el refresh intradiario de F-008 necesita acortar la corrida, paralelizar es un cambio local a
  `ingerir_rueda()` que no toca el contrato.
- *Confiar en la forma de respuesta por endpoint (hardcodear cuál pagina y cuál no)*: se descarta;
  la forma se **detecta** en cada respuesta (decisión 1). Hoy `public-bonds` pagina y
  `negociable-obligations` no, pero nada garantiza que BYMA no lo cambie, y el modo de fallo sería
  silencioso (leer `data` de una lista plana, o iterar páginas de algo que no pagina).
- *Modelos Pydantic para las filas*: se descarta; las filas normalizadas son `TypedDict` (dicts en
  runtime). `medir_cobertura` consume `Mapping`, la serialización a JSON es directa, y validar
  30 campos opcionales con Pydantic no agrega ninguna garantía que la normalización explícita no
  dé — acá no hay input de usuario, hay una fuente cuyos huecos queremos **conservar** como
  huecos, no rechazar.
- *Reintentar el endpoint que dio 401*: no. `pedir()` lo traduce a `CredencialVencida`
  (no reintentable) y esta feature lo captura por endpoint; BYMA no tiene credencial que renovar,
  así que se alerta como fuente no disponible con el status en el detalle (decisión 4).

## File Structure

### Crear

```
backend/app/ingesta/byma/__init__.py        Exporta ingerir_rueda y ResultadoRueda (la superficie pública del paquete)
backend/app/ingesta/byma/cliente.py         Descarga cruda: detección de forma, paginación hasta agotar, verificación de totales
backend/app/ingesta/byma/normalizacion.py   Dict crudo de BYMA → FilaRueda / FilaIndice (funciones puras, TypedDicts)
backend/app/ingesta/byma/ingesta.py         Orquesta los cinco endpoints, aísla fallos, arma Snapshot + cobertura
backend/tests/test_byma_cliente.py          Paginación, detección de forma, verificación de totales (respx)
backend/tests/test_byma_normalizacion.py    Moneda declarada, faltantes como None, tipos
backend/tests/test_byma_ingesta.py          Los 4 GWT de la spec + aislamiento de fallos por endpoint (respx)
backend/tests/test_byma_integracion.py      Un test marcado integration contra la fuente real
```

### Modificar

```
backend/app/api/v1/byma.py                  Agregar POST /byma/ingesta (el archivo es propiedad de F-004)
```

**Nada más.** No se toca `router.py`, ni `config.py`, ni nada de `app/ingesta/` fuera de `byma/`,
ni `requirements.txt`, ni `pyproject.toml`. Si durante la implementación parece hacer falta tocar
un archivo compartido, eso es una señal de que el enfoque se desvió: parar y reportarlo, no

editarlo.

## Dependency Map

**De la base común (`app/ingesta/`), se usa tal cual — no se redefine nada de esto:**

- `http.crear_cliente()` / `http.pedir()` / `http.con_reintentos()` — todo el tránsito HTTP.
  `dormir` se inyecta en tests para no esperar de verdad.
- `http.ErrorDeFuente` y `http.CredencialVencida` — la traducción de fallos.
- `snapshot.Snapshot` — el tipo de retorno; `registrar_tramo()` por endpoint, `alertar()`,
  `demora_declarada_minutos` desde settings.
- `alertas.fuente_caida()`, `alertas.respuesta_vacia()`, `alertas.formato_inesperado()` — no se
  define ningún modelo de alerta propio. El único código nuevo es `CODIGO_PAGINACION_INCOMPLETA`,
  constante en `byma/cliente.py` siguiendo la convención de `alertas.py` (decisión 3).
- `cobertura.medir_cobertura()` — sobre las filas ya normalizadas.

**De `app/core/config.py` (ya existen, no se agregan):** `byma_base_url`, `byma_demora_minutos`.

**Paquetes (ya instalados):** `httpx`, `respx` (tests). No se agrega ninguna dependencia.

**Precedente de código:** `tools/mercado.py` es el modelo de conducta — cliente de API pública sin
token que acumula fallos por endpoint y nunca corta la corrida. Esa es exactamente la semántica de
`ingerir_rueda()`.

## Edge Cases & Technical Decisions

1. **Detección de forma de respuesta, no supuesto.** En `cliente.py`, sobre el JSON parseado:
   - `list` → lista plana: las filas son la lista entera, no hay más páginas que pedir, el conteo
     es `len()`.
   - `dict` con clave `"data"` (lista) → objeto paginado: filas en `data`, metadatos en
     `content` (`page_count`, `total_elements_count`).
   - `dict` sin `"data"`, o `data` que no es lista, o cualquier otro tipo → `ErrorDeFuente` que la
     orquestación convierte en alerta `formato_inesperado` con el detalle de qué llegó
     (`{"endpoint": ..., "tipo": ...}`). Nunca se intenta "rescatar" filas de una forma no
     reconocida.

2. **Paginación hasta agotar + verificación contra `total_elements_count`.** Payload de todo
   request: `{"page_size": 500, "page_number": N}` empezando en 1 (verificado que los endpoints de
   lista plana lo ignoran, así que el payload es uniforme). Si la primera respuesta es paginada:
   se lee `page_count` y `total_elements_count` de esa primera respuesta y se piden las páginas
   2..`page_count` **con el mismo `page_size`** (cambiarlo a mitad de corrida invalidaría el
   `page_count` leído). Cada página pasa por `con_reintentos` individualmente. Al terminar:
   - si `sum(len(data de cada página)) != total_elements_count` → alerta
     `CODIGO_PAGINACION_INCOMPLETA` (severidad ERROR) con detalle
     `{"endpoint", "esperadas", "obtenidas", "paginas"}`. Las filas obtenidas **se entregan
     igual** (el snapshot queda `completo=False` y lo declara) — descartarlas castigaría el dato
     bueno por el faltante, y el criterio del snapshot es "una corrida incompleta se usa igual,
     pero se declara".
   - una página que en el medio devuelve otra forma (lista plana, dict sin data) → mismo
     tratamiento que 1: el endpoint entero se marca con `formato_inesperado` y se conservan las
     páginas ya bajadas, con la alerta de paginación incompleta.
   - una página vacía (`data: []`) cuando `page_count` decía que había más → cuenta como fallo
     reintentable dentro de `pedir(vacio_es_fallo=...)`; si tras los 5 intentos sigue vacía, el
     faltante lo delata la verificación contra `total_elements_count`.

3. **`CODIGO_PAGINACION_INCOMPLETA = "paginacion_incompleta"`** — constante módulo-local en
   `byma/cliente.py`, con fábrica local `paginacion_incompleta(endpoint, esperadas, obtenidas,
   paginas)` que devuelve `Alerta` usando el modelo compartido. Es el único código nuevo; los demás
   casos usan las fábricas de `alertas.py`.

4. **Un endpoint caído no corta los otros cuatro** (GWT-3). `ingerir_rueda()` envuelve cada
   endpoint en su propio `try/except (ErrorDeFuente)`. `CredencialVencida` es subclase de
   `ErrorDeFuente`, así que un 401 cae en el mismo camino: BYMA no tiene credencial que renovar,
   por lo tanto **no** se emite `credencial_vencida` (cuyo contrato exige una acción humana de
   renovación que acá no existe) sino `fuente_caida("BYMA", motivo, endpoint=..., status=...)`.
   El endpoint fallido registra su tramo con 0 filas — así el conteo por endpoint queda registrado
   para los cinco, que es lo que pide GWT-1 — y los otros cuatro se ingieren y se normalizan
   igual. `respuesta_vacia` se usa cuando el fallo final fue exactamente "cero filas tras N
   intentos".

5. **La moneda de cotización se lee de `denominationCcy` y de ningún otro lado** (GWT-2, regla 1
   del dominio). En `normalizacion.py` el campo `moneda_cotizacion` se asigna con
   `crudo.get("denominationCcy")` — literal, sin mapear, sin mirar el `symbol`. En **ningún**
   punto del paquete se parsea el sufijo del ticker; no existe ninguna función que reciba el
   symbol y devuelva una moneda. `denominationCcy` ausente o vacío → `None`, y el hueco lo cuenta
   la cobertura. Los valores observados (`ARS`, `USD`, `EXT`) viajan tal cual: traducir `EXT` a
   "CCL" sería una interpretación que corresponde discutir en F-007 con la precedencia declarada,
   no acá.

6. **Fila canónica: `TypedDict` con claves en castellano, huecos como `None`.**
   `FilaRueda` (para los cuatro endpoints de especies):

   ```
   ticker (symbol) · descripcion (securityDesc) · subtipo (securitySubType) · mercado (market)
   moneda_cotizacion (denominationCcy) · plazo_liquidacion (settlementType, tal cual: "1"/"2")
   precio_compra (bidPrice) · cantidad_compra (quantityBid)
   precio_venta (offerPrice) · cantidad_venta (quantityOffer)
   precio_ultimo (trade) · precio_cierre (closingPrice) · precio_cierre_anterior (previousClosingPrice)
   precio_apertura (openingPrice) · precio_maximo (tradingHighPrice) · precio_minimo (tradingLowPrice)
   vwap (vwap) · volumen_nominal (tradeVolume) · monto_operado (volumeAmount)
   operaciones (numberOfOrders) · vencimiento (maturityDate) · dias_al_vencimiento (daysToMaturity)
   ```

   `FilaIndice` (para `index-price`): `indice (symbol) · descripcion · valor (price) ·
   cierre_anterior (previousClosingPrice) · variacion · maximo (highValue) · minimo (minValue) ·
   fecha (date) · es_tasa (isRate)`.

   Reglas de la normalización: clave ausente, `None`, o cadena vacía → `None` (nunca 0, nunca un
   default); un `0` numérico de la fuente se conserva como `0.0` (un bono que no operó tiene
   volumen cero — es dato, no hueco; es la misma regla que `cobertura._esta_presente`). Números
   que llegan como número se tipan `float`/`int`; un valor no numérico donde se espera número →
   `None` (no se adivina). Los campos crudos que no están en el mapeo (`openInterest`,
   `tickDirection`, `settlementPrice`, `tradeHour`, etc.) no se descartan a ciegas: `ingerir_rueda`
   los deja fuera de la fila canónica y no viajan — están disponibles en `cliente.py` si F-007 los
   pide, y sumarlos después es un cambio aditivo.

7. **TLS: verificación activada, sin excepciones.** Verificado empíricamente (06/08/2026) que
   httpx con certifi valida el certificado de `open.bymadata.com.ar` sin ninguna configuración
   especial; el `-k` de la exploración con curl era una limitación del trust store de curl en
   macOS. No se pasa `verify=False` ni un contexto degradado en ningún lugar del paquete —
   desactivar la verificación en la fuente de la que salen todos los precios del producto
   permitiría a un intermediario **inventar datos**, que es exactamente la regla 1 del dominio.
   Si en otro entorno de deploy la verificación fallara, eso es un problema de CAs del entorno y
   se resuelve ahí (certifi actualizado), no bajando la guardia del cliente. El test de
   integración es el canario: si el certificado rompe, lo dice ese test, no una corrida muda.

8. **`Snapshot` con la demora como atributo** (GWT-4). `Snapshot(fuente="BYMA",
   demora_declarada_minutos=settings.byma_demora_minutos)` — el 20 sale de config, no se
   hardcodea. `filas_por_tramo` lleva una entrada por endpoint con el nombre del endpoint tal cual
   (`"negociable-obligations"`, …), los cinco siempre presentes (los caídos con 0, ver decisión
   4). `dato_valido_hasta` y `como_dict()` ya vienen de la base — no hay nada que hacer.

9. **Cobertura medida sobre lo que F-007 y las reglas del dominio necesitan ver.** Sobre el
   conjunto de filas normalizadas de especies (los cuatro endpoints juntos):
   `ticker, moneda_cotizacion, plazo_liquidacion, precio_cierre, precio_compra, precio_venta,
   monto_operado, vencimiento`. Sobre `index-price`: `indice, valor`. La elección: moneda y plazo
   son los que habilitan la regla 3 (nada se compara entre monedas sin normalizar — el MEP se
   deriva del cociente entre especies, y para eso la moneda y el plazo tienen que estar
   declarados); puntas y cierre son el corazón del output declarado; vencimiento delata cuándo
   BYMA no publica el dato que F-007 esperaría heredar.

10. **El resultado de la ingesta es un tipo propio del paquete.** `ResultadoRueda` (dataclass
    congelada en `ingesta.py`): `especies: list[FilaRueda]`, `indices: list[FilaIndice]`,
    `snapshot: Snapshot`. F-007 consume esta función directamente (import de
    `app.ingesta.byma`); el endpoint HTTP es la forma de dispararla a mano. No se define en un
    archivo compartido a propósito: unificar los contratos de las tres fuentes es trabajo de
    F-007, con las tres ya construidas a la vista.

11. **Endpoint HTTP: `POST /byma/ingesta`.** POST porque dispara una acción con efectos (consumo
    de red, corrida de ingesta), no una lectura. Responde 200 con
    `{"snapshot": snapshot.como_dict()}` — **sin** las ~3800 filas (el JSON de respuesta es para
    ver el estado de la corrida, no para transportar el universo; cuando exista persistencia, la
    consulta de filas será de F-007+). Devuelve 200 aunque haya endpoints caídos: la semántica de
    "la corrida corrió y esto es lo que declaró" vive en `snapshot.completo` y sus alertas, no en
    el status HTTP. Logging: `logger.info("ingesta_byma_termino", total_filas=...,
    endpoints_caidos=[...], completo=...)` — por nombre de endpoint, **nunca la URL** (convención
    del proyecto; acá no hay token pero la regla es una sola para las tres fuentes).

12. **Sin persistencia en F-004.** Esta feature no escribe a la base: el límite con F-007 es que
    F-004 entrega `ResultadoRueda` en memoria y F-007 es quien persiste con precedencia por campo.
    Cualquier tabla que esta feature quisiera crear sería un contrato inventado antes de tiempo.

## Test Strategy

Convenciones: nombres en castellano como frase completa, docstring de módulo que nombra el
criterio que cubre, `asyncio_mode = "auto"` (sin decorador en los async), `respx` para simular la
fuente, `dormir` inyectado como corrutina nula para que los reintentos no esperen. El marker
`integration` queda excluido por defecto (`addopts` ya lo hace).

### GWT de la spec → verificación

1. **GWT-1** — *cinco endpoints disponibles → cinco respuestas por POST sin token y conteo por
   endpoint en el snapshot*: en `test_byma_ingesta.py`, respx simula los cinco endpoints (dos como
   objeto paginado multi-página, dos como lista plana, `index-price` de una página).
   `test_la_ingesta_registra_el_conteo_de_filas_de_los_cinco_endpoints`: asserta
   `snapshot.filas_por_tramo` con los cinco nombres y los totales exactos, y que cada request
   capturada por respx fue POST con body JSON y **sin** header `Authorization`.

2. **GWT-2** — *moneda por campo declarado, nunca por sufijo*: en `test_byma_normalizacion.py`,
   `test_la_moneda_sale_de_denomination_ccy_y_no_del_sufijo_del_ticker`: una fila cruda con
   `symbol="XXXD"` (sufijo que "parece" dólar) y `denominationCcy="ARS"` normaliza a
   `moneda_cotizacion == "ARS"`; otra con `symbol="PNDC"` sin sufijo D/C y
   `denominationCcy="USD"` normaliza a `"USD"`. Y
   `test_sin_denomination_ccy_la_moneda_queda_vacia_y_cuenta_como_faltante`: `denominationCcy`
   ausente → `None`, y `medir_cobertura` la cuenta faltante — no hay camino de código que la
   complete.

3. **GWT-3** — *un endpoint con 401 → marcado no disponible con su código, los otros cuatro se
   ingieren igual*: respx responde 401 en `public-bonds` y datos válidos en los otros cuatro.
   `test_un_endpoint_caido_no_impide_ingerir_los_otros_cuatro`: el resultado trae las filas de los
   cuatro, `filas_por_tramo["public-bonds"] == 0`, hay exactamente una alerta con
   `codigo == CODIGO_FUENTE_CAIDA` y `detalle` con `endpoint="public-bonds"` y `status=401`,
   `snapshot.completo is False`, y `accion_requerida is None` (nadie tiene que ir a renovar nada).
   Variante `test_un_500_persistente_agota_los_reintentos_y_no_corta_la_corrida` con el contador
   de llamadas de respx en 5.

4. **GWT-4** — *el snapshot expone hora de captura y demora declarada*:
   `test_el_snapshot_declara_la_demora_de_veinte_minutos`: `como_dict()` trae
   `demora_declarada_minutos == 20` (leído de settings) y `dato_valido_hasta ==
   capturado_en - 20 min`.

### Tests de mecánica (no atados a un GWT, cubren los hallazgos empíricos)

- `test_byma_cliente.py`:
  - `test_una_respuesta_paginada_se_pide_hasta_agotar_las_paginas`: 3 páginas de 500/500/106 con
    `total_elements_count=1106` → 3 requests con `page_number` 1, 2, 3 y `page_size` constante;
    1106 filas.
  - `test_si_el_total_ingerido_no_coincide_con_el_declarado_se_alerta`: la página 3 trae menos
    filas que las declaradas → alerta `paginacion_incompleta` con esperadas/obtenidas, y las filas
    obtenidas se entregan igual.
  - `test_una_lista_plana_se_ingiere_entera_sin_pedir_mas_paginas`: respuesta lista → 1 request,
    conteo = len.
  - `test_un_objeto_sin_data_es_formato_inesperado`: `{"content": {...}}` sin `data` → alerta
    `formato_inesperado`, cero filas de ese endpoint.
  - `test_una_respuesta_vacia_se_reintenta_antes_de_declarar_el_fallo`: dos respuestas `[]` y una
    con filas → 3 llamadas (contadas por respx), resultado con filas, sin alerta de error.
- `test_byma_normalizacion.py`: además de GWT-2 — cero se conserva como dato
  (`volumeAmount: 0` → `0.0` presente en cobertura), ausente queda `None`, un string donde iba un
  número queda `None`, `settlementType` viaja tal cual (`"1"`/`"2"`, sin traducir).

### Integración (marcada, excluida por defecto)

- `test_byma_integracion.py` — `@pytest.mark.integration`,
  `test_la_fuente_real_responde_y_el_snapshot_queda_completo`: corre `ingerir_rueda()` contra la
  fuente viva y asserta `total_filas > 3000`, los cinco tramos presentes, `index-price` con 16
  filas, y TLS verificando (ninguna configuración especial en el cliente). Es el canario del
  certificado y del contrato de paginación.

## Verificación end-to-end

Desde `backend/`, con el venv activado:

```bash
ruff check app/ingesta/byma app/api/v1/byma.py tests/test_byma_*.py   # 0 errores
pytest tests/test_byma_cliente.py tests/test_byma_normalizacion.py tests/test_byma_ingesta.py -v
pytest -m integration tests/test_byma_integracion.py -v               # con red; toca la fuente real
pytest                                                                 # la suite entera sigue verde
```

Verificación manual con el backend levantado (`uvicorn app.main:app --reload`):

```bash
curl -s -X POST localhost:8000/api/v1/byma/ingesta | python3 -m json.tool
```

Se espera: `snapshot.fuente == "BYMA"`, `demora_declarada_minutos == 20`, `filas_por_tramo` con
los cinco endpoints y totales del orden de `negociable-obligations ≈ 2180`, `public-bonds ≈ 1106`,
`cedears ≈ 2107`, `general-equity ≈ 349`, `index-price == 16` (los números exactos varían por
rueda), `completo == true` y `alertas == []` en un día normal. En el log: eventos
`ingesta_byma_termino` sin ninguna URL.

Cierre: `/simplify` sobre los archivos modificados, commit único en `feature/F-004`.

## Riesgos

1. **BYMA puede cambiar forma o campos sin aviso** (ya pasó: la spec del 05/08 y la realidad del
   06/08 difieren en conteos). Mitigación: detección de forma + verificación de totales +
   `formato_inesperado` — el cambio se declara, no se absorbe en silencio. El test de integración
   lo detecta en cuanto se corre.
2. **Los totales de lista plana no tienen contra qué verificarse** (la fuente no declara
   metadatos). Se acepta: el conteo queda registrado por tramo y las variaciones grandes entre
   corridas son visibles para F-008/F-013; inventar un "total esperado" hardcodeado sería
   exactamente el tipo de dato inventado que el proyecto prohíbe.
3. **Rate limiting desconocido.** No se observó en las pruebas (~10 requests por corrida). Si
   apareciera un 429, `pedir()` hoy lo trata como 4xx no reintentable → alerta por endpoint; es el
   comportamiento correcto de mínima (declarar en vez de martillar) y ajustarlo sería un cambio en
   la base común, a discutir fuera de esta feature.
4. **`page_count` podría cambiar entre la primera página y las siguientes** si el universo cambia
   intradía durante la corrida. La verificación contra `total_elements_count` de la primera
   respuesta lo convierte en alerta de paginación incompleta en el peor caso; con ~6 s por corrida
   la ventana es mínima.
