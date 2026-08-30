# F-079 — Especificidad y UX de los filtros de renta variable

## Contexto

F-078 dejó el mission control de CEDEARs funcionando, y el dueño lo validó con tres mejoras:
(1) la pared de chips ocupa ~400px antes de la tabla y "queda feo" — alguien sin idea de
mercado tiene que poder buscar "oro" o "farmacéuticas" fácil; (2) Rubro (oficina SEC) y
Eslabón (división SIC) dicen casi lo mismo y son gruesos — quiere el rubro del producto
final; (3) un ETF geográfico tiene que decir DÓNDE invierte, no "EAFE".

**Hechos medidos que habilitan esto sin fuentes nuevas:**
- `sic_codigo`/`sic_titulo` (120 rubros finos: "Pharmaceutical Preparations" 42 especies,
  "Semiconductors" 38, "Gold and Silver Ores" 25) ya están persistidos en
  `perfil_renta_variable` y ya viajan al frontend — ningún eje los usa.
- El major group SIC de 2 dígitos (43 presentes) se calcula en
  `backend/app/externos/sic.py:85` y se descarta. Escalera: 8 divisiones → 12 oficinas →
  43 sectores → 120 rubros. 61 de los 120 rubros tienen 1 solo papel ⇒ el nivel fino es
  filtro/etiqueta, el de 43 es el eje de agrupación/topes.
- Redundancia confirmada: 6 de 12 oficinas mapean 1:1 a una división; 78 especies caen en
  oficinas ambiguas ("X or Y", "Multiple Offices").
- El precedente UI ya existe en el repo: RF usa selects para ejes abiertos
  (`FiltrosPerfil.tsx`) y el picker del armador resuelve las mismas dimensiones en ~40px
  con selects + buscador (`BloqueRentaVariable.tsx`). El monitor RV es la única excepción.
- El monitor tiene 2 presets; el armador 9 (incl. "Medicina y salud" = Office of Life
  Sciences). Unificarlos cubre "oro / farmacéuticas" casi literal.

**Decisiones del dueño (29/08, no reabrir):**
- **D1** — Los ~120 títulos SIC se muestran con **traducción curada al ES**, validada por
  él antes de cargarse (SIC es estándar publicado ⇒ leerlo/traducirlo con validación
  respeta la regla 11).
- **D2** — Clasificación sectorial en dos niveles: **Sector** (major group 2 díg., ES
  curado) y **Rubro específico** (título 4 díg., ES curado). Oficina y Eslabón salen de la
  UI (siguen persistidos). El armador topea "rubro" por Sector.
- **D3** — ETFs geográficos: **tabla curada por fondo** (índice que sigue + alcance según
  el emisor del índice + país ISO si es mono-país, fuente y fecha, validada). NO se cura
  composición multi-país (envejece — lección IAMC).
- **D4** — UI: **buscador + píldoras temáticas unificadas + selects compactos** (~90px de
  cromo), patrón del picker del armador.

**Principio rector del diseño**: el valor de faceta/filtro/tope es SIEMPRE el **código**
(`sector_codigo`, `sic_codigo`); la etiqueta ES es presentación. La validación de los CSVs
no cambia selecciones ni agrupaciones, solo mejora rótulos. Sin curado cargado la app corre
entera con fallbacks declarados: rubro → `sic_titulo` EN tal como la SEC lo publica; sector
→ el código de 2 dígitos (un estándar se lee); geografía ETF → token crudo como hoy.

Registro: `claude-docs/plans/F-079-plan.md` (copiar este plan) + `PROGRESS.md`.

## Dónde vive cada curado (argumentado)

- **`data/sic_sectores.csv`** (`major_group,nombre_en,etiqueta_es`, los ~83 del manual
  completo de OSHA para que un CEDEAR nuevo no caiga en hueco) y **`data/sic_rubros.csv`**
  (`sic_codigo,titulo_en,etiqueta_es`, solo los ~120 presentes; un código nuevo cae al
  fallback declarado): **CSV leído a memoria, sin tabla Postgres** — son mapeos por código
  de un estándar cerrado (precedente `regiones.py::REGION_M49`), pero en CSV y no dict
  hardcodeado porque el gate de validación humana necesita un artefacto revisable en
  planilla (patrón `paises_cedears_propuesta.csv`).
- **`data/etfs_geografia.csv`** (`ticker_papel,indice,alcance,pais,fuente,verificado`;
  `alcance` = texto ES ≤~60 chars con la definición del emisor del índice; `pais` ISO solo
  mono-país, validado contra `REGION_M49`): **tabla Postgres `public.etf_geografia` +
  siembra + endpoint jobs**, calcado de `pais_cedear` — es dato por-papel que crece, con
  fuente/fecha por fila.

## Fase 0 — Registro y medición
1. `claude-docs/plans/F-079-plan.md` + entrada en `PROGRESS.md`.
2. Medición read-only (script efímero): distribución de especies y del top-25 de liquidez
   por major group (insumo del docstring de topes); los 120 `sic_codigo+sic_titulo`
   (insumo de `sic_rubros_propuesta.csv`); los 10 papeles con `region_etf` (insumo D3).

## Fase 1 — Backend: sector y rubro derivados (funciona sin CSVs)
3. `backend/app/externos/sic.py`: extraer `major_group_de(sic) -> str | None` (devuelve
   `"28"`, 2 dígitos con cero a la izquierda; hoy se calcula y descarta en la línea 85);
   `division_de` la reusa.
4. **Nuevo** `backend/app/renta_variable/sic_es.py`: lee los dos CSVs (lazy + cache,
   `utf-8-sig`; archivo ausente ⇒ dicts vacíos sin ruido). `sector_de(sic_codigo)` y
   `rubro_de(sic_codigo)` → etiqueta ES o `None`. Docstring: fuentes (OSHA
   osha.gov/data/sic-manual; `sic_titulo` de la SEC) y el gate de validación.
5. `backend/app/renta_variable/especies.py`: `EspecieRentaVariable` + `como_dict()` suman
   `sector_codigo` (siempre derivable de `sic_codigo`), `sector` (ES o None),
   `rubro_especifico` (ES o None). `sic_oficina`/`division_cadena` siguen emitiéndose.
6. Tests: `sic_es` (presente/ausente/malformado), `major_group_de` (ceros, huecos del
   manual), derivación en especies.

## Fase 2 — Backend: geografía curada de ETFs
7. Migración + rollback: `public.etf_geografia (ticker_papel PK, indice NOT NULL, alcance
   NOT NULL, pais NULL, fuente NOT NULL, verificado date NOT NULL, cargado_en)` con
   COMMENT explicando D3. **Recordatorio: aplicarla a la base real, no solo escribirla.**
8. **Nuevo** `backend/app/renta_variable/geografia_etf.py` calcado de `paises.py`:
   `FilaGeografiaEtf` (property `region = region_de(pais)`), `leer_curado`, `persistir`
   (upsert, sin borrar ausentes), `sembrar_geografia_etfs`, `leer_geografia_etfs`.
   Setting `etfs_geografia_csv` en `core/config.py` junto a `paises_cedears_csv`.
9. `api/v1/jobs.py`: `POST /jobs/sembrar-geografia-etfs` (espejo de
   `sembrar-paises-cedears`).
10. `especies.py` + el endpoint que llama `armar_renta_variable`: parámetro
    `geografia_etfs`; campos `etf_indice`, `etf_alcance`, `etf_pais`, `etf_region`
    (derivada), `etf_geo_fuente`, `etf_geo_verificado`.
11. Tests: siembra/lectura/vocabulario, hermanas comparten por papel.

## Fase 3 — Backend: armador sobre el eje sector
12. `armado/renta_variable.py`: `EJES_RV["rubro"] = "sector_codigo"`; greedy primera
    pasada y `rv_sin_perfil_sectorial` sobre `sector_codigo` (gana cobertura y elimina las
    oficinas ambiguas); etiqueta de alertas usa `especie.sector` cuando exista. Docstring
    de `TOPES_RV_DEFAULT` actualizado con la medición de Fase 0 (números 30/40/55 se
    mantienen salvo que la medición muestre algo absurdo — en ese caso se consulta, no se
    decide).
13. `armado/parametros.py`: `FiltroRv.sectores: list[str] | None` (códigos 2 díg.);
    `rubros` (valores de `sic_oficina`) y `rubro_rv` quedan intactos por compat.
14. Ajustar fixtures/tests de `test_armado_renta_variable.py` y `test_armado_endpoint.py`
    (necesitan `sic_codigo` para que el eje funcione).

## Fase 4 — Frontend: zona compartida
15. Schemas zod (`src/lib/rentaVariable.ts`, `features/instrumento/lib/
    schemaRentaVariable.ts`): campos nuevos `.nullable().default(null)`.
16. `src/lib/presetsRv.ts`: `FiltroRv.sectores?` + condición sobre `sector_codigo`.
    **Unificación de píldoras**: sumar `financieras`, `tecnologicas`, `medicina` como
    `PresetRv` con `filtro: {rubros: ['Office of ...']}` (mismo conjunto que hoy, la nota
    declara qué oficina SEC lo define — NO se reescriben a major groups: ese mapeo sería
    una agrupación nuestra sin validar; si el dueño quiere redefinirlos, es curado
    posterior). `features/armador/lib/tematicas.ts`: esas temáticas pasan de `rubroRv` a
    referenciar el preset por id; `PanelArmadoAsistido` manda siempre `filtro_rv` (el
    backend sigue aceptando `rubro_rv`).
17. **Nuevo** `src/components/CampoSelect.tsx`: select compacto con rótulo, absorbe
    `estiloSelectPicker` (`BloqueRentaVariable.tsx:109`) y las copias de `estiloInput`
    (`FiltrosPerfil.tsx:209`, `PanelArmadoAsistido`, `FiltrosGrilla`) — migración mecánica
    sin cambio de comportamiento.

## Fase 5 — Frontend: rediseño del monitor (D4)
18. `features/monitor/lib/filtrosRentaVariable.ts`:
    - `DimensionRv` = `region | pais | mercado | sector | rubroEspecifico | estrategiaEtf`
      (se van `rubro`/`eslabon`). Valores: sector = `sector_codigo`, rubroEspecifico =
      `sic_codigo`; centinelas nuevos. El leave-one-out de `facetar()` resuelve solo la
      jerarquía sector→rubro (mismo mecanismo del rubro⇄eslabón que originó el motor).
    - País: `pais ?? etf_pais` (legítimo: con D3 el país del ETF es dato curado en el
      mismo vocabulario ISO, ya no es traducir). Región: `region ?? etf_region ??
      etf_alcance ?? region_etf` — los tokens crudos sobreviven solo para fondos sin curar.
    - Etiquetas: `Map<codigo, etiquetaES | tituloEN>` armado desde el universo (precedente
      `formasCanonicasDeMercado`); el `title` de cada opción lleva
      `SIC {codigo} — {titulo EN} (SEC)` para conservar visible la fuente.
    - Buscador: `coincideBusquedaRv(especie, texto)` (ticker, nombre_largo, etiquetas ES,
      `sic_titulo`) + `presetsQueCoinciden(texto)` (match sobre etiqueta y
      `palabrasEnNombre` — "oro" encuentra Metales preciosos; **sin sinónimos
      inventados**: solo texto curado o declarado por la fuente). Folding de acentos/caja.
    - Estado: + `busqueda`; `filtrosAlCambiarDeMoneda` conserva preset **y** búsqueda.
19. `FiltrosRentaVariable.tsx` — layout nuevo (~90px): fila 1 = input de búsqueda (patrón
    `SelectorFci`) + píldoras de presets, con sugerencias clickeables cuando la búsqueda
    matchea presets o valores de sector/rubro; fila 2 = hasta 6 `CampoSelect` con conteos
    y "Todos (N)", autoocultado <2 opciones; pie = párrafo de selecciones apagadas. La
    búsqueda filtra la tabla en vivo (entra a `pasaBaseRv` para que los conteos la
    reflejen).
20. `ComposicionUniversoRv.tsx`: ejes Región / País / Sector / Estrategia / Mercado (rubro
    específico con 120 valores no es barra, es filtro); sector = `sector ??
    sector_codigo`; país y región con los fallbacks de arriba.
21. Tests: reescritura de dimensiones + jerarquía sector→rubro, búsqueda "oro"→preset,
    fallback sin curado muestra código/título EN.

## Fase 6 — Frontend: armador
22. `BloqueRentaVariable.tsx`: `DIMENSIONES_PICKER` = Región/País/Sector/Rubro/Estrategia
    (mismos códigos y etiquetas que el monitor); `EJES_COMPOSICION` =
    `['sector','pais','region','moneda','mercado']`; el texto de perfil (línea ~989) pasa
    de `division_cadena` a sector/rubro ES.
23. `PanelArmadoAsistido.tsx`: tope "Rubro" se rotula "Sector"; `coberturaPorEje` sobre
    `sector_codigo`. `schemaArmado.ts`: comentario de `max_pct_rubro` actualizado.
24. `FichaRentaVariable.tsx`: filas Sector y Rubro (ES) arriba de la Actividad
    (`sic_titulo` EN) y el código SIC, que se conservan como llave de auditoría; bloque de
    geografía del ETF (índice, alcance, país, fuente, verificado) cuando exista.

## Fase 7 — Curados y gate de validación humana
25. Generar `data/sic_sectores_propuesta.csv` (83), `data/sic_rubros_propuesta.csv`
    (~120, EN = `sic_titulo` persistido) y `data/etfs_geografia_propuesta.csv` (~10-15,
    URL del emisor del índice por fila).
26. **GATE: el dueño valida los tres.** Recién ahí se renombran a definitivos, se
    commitean y se corre `POST /jobs/sembrar-geografia-etfs`. Hasta entonces todo corre
    con fallbacks declarados (como `pais_cedear` corrió con 0 filas). Nota: sigue
    pendiente de validación previa `data/paises_cedears_propuesta.csv` (F-078).

## Fase 8 — Verificación
27. `pytest` backend (1550+), `vitest` (1190+), `tsc`, `npm run build`.
28. E2E local: monitor RV con y sin CSVs (cromo ≤ ~100px medido); buscar "oro" trae el
    preset Metales; armar con temática Medicina da el mismo conjunto que el `rubro_rv`
    previo (regresión); alertas de tope nombrando el sector.
29. **Pasada visual final invocando el skill `frontend-design`** si está disponible
    (pedido explícito del dueño), contrastando contra `design-system.md`.
30. `PROGRESS.md` + `docs/ESTADO.md` actualizados.

## Riesgos
- Presets migrados podrían cambiar el conjunto de papeles → test de regresión
  antes/después; la migración conserva los filtros por `sic_oficina` dentro del preset.
- `max_pct_rubro` sobre un eje más fino muerde distinto → cambio aceptado (D2),
  documentado; números solo cambian con decisión del dueño.
- Doble valor geográfico (`pais` vs `etf_pais`) → precedencia explícita `pais ?? etf_pais`
  documentada como orden de lectura de dos curados en la práctica excluyentes.
- La búsqueda es tan buena como las etiquetas ES → el gate de validación es también gate
  de UX ("minería de oro" tiene que decir "oro").
- Etiquetas que llegan después del código → neutralizado: los valores son códigos, el ES
  es presentación.
