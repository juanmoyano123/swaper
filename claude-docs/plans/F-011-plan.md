# Feature Plan: F-011 — Deduplicación de especies de liquidación

## Contexto

- **Source:** `claude-docs/planning/plan.md` (ficha F-011) + `tools/segmentos.py:399-444`
  (`deduplicar_emisiones`), que es la lógica original ya verificada contra el universo real.
- **Depende de:** F-010. **Habilita:** F-015, F-020, F-032, F-039.
- **Complejidad:** S. El criterio ya estaba resuelto; el trabajo es portarlo sin traicionarlo,
  declarar el criterio que todavía no se puede portar, y darle al paquete la forma que F-012 hereda.

MR46O, MR46D y MR46C son el mismo bono. Comprar dos es comprar el mismo bono creyendo que se
diversifica, y un límite de concentración que cuente tres posiciones donde hay una mide mal el
riesgo (regla 4 del dominio, aplicada a la emisión en vez de al emisor).

**La deduplicación no es un descarte, es una doble vista.** Colapsada para el armador y para el
cómputo de concentración; viva para el optimizador, porque los swaps de perfil rotan justamente
entre especies de la misma emisión (MEP → Cable). Las dos llevan la clave de emisión explícita.

## Decisiones de diseño

### 1. El desempate por volumen queda como hueco declarado, no como desempate crudo

El motor desempata por `volumen_usd` —volumen **normalizado a dólares**, que produce F-012— y su
propio comentario dice por qué: *"El desempate va en NOMINALES: con el volumen crudo siempre ganaba
la especie en pesos por el tipo de cambio, no por liquidez."*

Usar `effectiveVolume` crudo reintroduciría ese error y violaría la regla 3 del dominio. Así que
esa columna **no se lee en absoluto**: no está en `lectura.COLUMNAS` ni en `EspecieUniverso`. En su
lugar desempata el ticker alfabético: arbitrario, pero estable y reproducible.

El punto de enganche es `emisiones._prioridad`, documentado en su docstring: F-012 mete el volumen
normalizado entre la completitud y el ticker, y no hay que tocar nada más.

### 2. Se porta el chequeo del 5 % de duración antes que cualquier otra cosa

La misma emisión tiene la misma duración. Si las duraciones del grupo difieren más de un 5 %, no son
la misma emisión: comparten raíz y nada más, y el grupo **no se colapsa**. Fusionar dos bonos
distintos en una fila es peor que duplicar uno. Se portó con su piso de división (`1e-9`) incluido:
con duraciones que no son duraciones, el grupo cae del lado de no fusionar.

Con menos de dos duraciones publicadas no hay dispersión y el grupo colapsa: no saber no es saber
que son distintos. Sin esto, las emisiones sin `duration` —que hoy son casi todas— se partirían.

### 3. Las dos vistas son dos recursos y no un `?colapsado=`

Quien pide la colapsada y quien pide la viva no preguntan lo mismo. Un flag las haría parecer la
misma pregunta con un ajuste, y su default sería una decisión silenciosa sobre cuál de los dos
clientes se rompe. Es la misma razón por la que `dedup` es obligatorio y sin default en el motor.

### 4. La advertencia de duplicado es servicio, no interfaz

GWT-3 lo pide desde el armador, que es F-018 y no existe. Lo que se construyó es la respuesta:
`UniversoDeduplicado.advertencia_de_duplicado(ticker, cartera)` y su endpoint. Si la decisión de qué
es la misma emisión viviera en la pantalla, la pantalla tendría que volver a cortar tickers.

**No advierte sobre un grupo que no se colapsó**: el chequeo de duración ya dijo que esas especies
son emisiones distintas, y llamarlas duplicado sería tan falso como el error que la feature ataca.

### 5. Las alertas de la deduplicación viven en `universo/emisiones.py`

No se tocó `app/ingesta/alertas.py`: sus alertas hablan de una corrida de ingesta —una fuente que
falló, un campo sin cobertura— y éstas hablan de cómo quedó armado el universo. Se construye
`Alerta` directamente, con sus códigos exportados para quien las agrupe.

### 6. `por_raiz` es la única estructura, y todo lo demás se deriva

La vista colapsada, la viva y el listado ordenado salen del mismo diccionario. Un índice y una lista
con lo mismo adentro se desincronizan el día que alguien filtre uno de los dos.

## Archivos

| Archivo | Qué es |
|---|---|
| `backend/app/universo/emisiones.py` | la doble vista y el criterio de representante. Funciones puras |
| `backend/app/universo/lectura.py` | +5 columnas: `duration`, `maturity`, `law`, `couponCurrency`, `underlying` |
| `backend/app/universo/segmentacion.py` | `EspecieUniverso` +5 campos, `sufijo_liquidacion`, `como_dict` |
| `backend/app/universo/servicio.py` | `UniversoSaneado.emisiones()`: el enganche desde el universo saneado |
| `backend/app/api/v1/universo.py` | `/universo/emisiones`, `/colapsada`, `/especies`, `/duplicado` |
| `backend/tests/test_universo_emisiones.py` | los tres GWT y los bordes del criterio |
| `backend/tests/test_universo_emisiones_api.py` | el contrato HTTP de las dos vistas y la paginación |
| `backend/tests/test_universo_emisiones_paridad.py` | el port contra `tools/segmentos.py` |
| `backend/tests/test_universo_emisiones_integration.py` | contra la base real, marcado `integration` |

Los identificadores del SELECT se entrecomillan porque `couponCurrency` viene en camelCase de la
fuente original; sin comillas PostgreSQL lo plegaría a minúsculas. Se entrecomillan todos: una regla
que aplica a veces es una regla que alguien va a olvidar en la siguiente columna.

## Lo que dijo el test de paridad

Sobre el consolidado histórico, contra `cargar_universo(alertas, dedup=True)` corrido tal cual:

| | |
|---|---|
| Emisiones (claves) | idénticas |
| Grupos no colapsados por duración | idénticos: **DICP y MR43** |
| Filas de la vista colapsada | 468 en los dos |
| Representante coincidente | **279 / 279** emisiones multiespecie |

Los criterios 1-3 no divergieron, y el desempate faltante no cambió ninguna elección sobre ese
universo. El test además exige que el representante del backend nunca sea *peor* que el del motor
—ni menos sano ni menos completo— que es la parte que tiene que seguir valiendo aunque el desempate
elija otra especie.

## Estado del universo real (06/08/2026)

Sobre las 2.894 filas de `resumen` → 942 especies segmentadas:

| | |
|---|---|
| Emisiones | 431 |
| Filas de la vista colapsada | 431 |
| Especies colapsadas | 511 |
| Emisiones con más de una especie | 299 (máximo 3) |
| Grupos no colapsados por duración | **0** |
| Emisiones que pierden el rendimiento al colapsar | **199** |

- **MR46** —el caso de la spec— tiene sus tres especies, colapsa a una fila y la advertencia de
  duplicado contra una cartera con MR46D funciona sobre la base real.
- **Los 0 grupos no colapsados no son un chequeo roto**: sólo 217 de 942 especies publican
  `duration`, y **ningún** grupo multiespecie tiene dos duraciones a la vez, así que el chequeo no
  tiene con qué disparar. Es el mismo fenómeno que dejó la capa 1 de F-010 sin material: IAMC
  escribe sus métricas sólo en el ticker que su informe nombra. Sobre el consolidado histórico, que
  sí tiene duraciones, dispara en DICP y MR43.
- **199 emisiones quedan sin rendimiento en la fila colapsada.** Ver abajo: es la consecuencia
  medible del desempate pendiente y la decisión abierta de la feature.

## La decisión que queda abierta

Como los cuatro campos de completitud son de la emisión, las hermanas empatan en las 299 emisiones
multiespecie y **el desempate decide todas**. Eso solo no sería grave. Lo que sí importa es que IAMC
publica la TIR únicamente en la especie que su informe nombra, y cuando ésa no gana el desempate la
fila colapsada queda sin rendimiento: **de 217 instrumentos operables, sólo 18 sobreviven a la vista
colapsada**.

No se corrigió acá. Preferir a la especie que publica rendimiento sería un cuarto criterio que el
motor no tiene, y agregarlo por cuenta propia sería cambiar el criterio de armado sin que nadie lo
haya decidido. Lo que se hizo es contarlo y alertarlo en cada corrida
(`rendimiento_perdido_al_colapsar`, con los tickers), para que la decisión se tome mirando el número
y no cuando el armador muestre una lista corta sin explicación.

Las dos salidas posibles: que el volumen normalizado de F-012 elija naturalmente la especie más
operada —que suele ser la que IAMC nombra— o, si con eso persiste, un criterio explícito. La
segunda es decisión de dominio y no de esta feature.

## Riesgos

- **El desempate arbitrario decide todo hoy.** Mitigado por el alerta y por el test de paridad, que
  mide la coincidencia con el motor y tiene que llegar al 100 % cuando F-012 cierre el hueco.
- **El chequeo del 5 % no puede disparar sobre la base actual.** No es un problema de F-011 sino de
  la cobertura de `duration`, pero conviene no leer "cero grupos partidos" como "todo verificado".
- **El port puede divergir del motor.** Mitigado con `test_universo_emisiones_paridad.py`, que los
  corre a los dos sobre el mismo Excel.
