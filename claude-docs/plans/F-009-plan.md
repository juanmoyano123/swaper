# Plan: F-009 — `condiciones_emision`: semilla, herencia entre especies y conflictos

## Contexto

F-009 puebla la tabla que aloja **el dato curado del producto**: ley, moneda de pago, lámina,
calificación, sector y emisor, cada valor con su `origen` y su `fecha` en la misma fila. Es lo que
ninguna fuente de mercado publica —BYMA no trae lámina, IAMC no trae calificación, Docta no trae
sector— y por lo tanto lo que hace posibles las features que dependen de esos campos (F-013, F-020,
F-024, F-025, F-031, F-039).

Reemplaza a `tools/merge_condiciones.py` y `tools/aplicar_sectores.py` conservando su semántica. El
backend no importa de `tools/`: la lógica está portada, con el docstring citando el origen.

La tabla ya existe (`supabase/migrations/20260806151113_mercado.sql:128`) con seis CHECK de
trazabilidad, uno por campo. **No hizo falta ninguna migración nueva.**

## Hallazgo que cambia el alcance, declarado y no resuelto por inferencia

La spec (`claude-docs/planning/plan.md:463-497`) dice sembrar desde tres CSV:
`condiciones_estaticas.csv` (272 tickers), `condiciones_monitor.csv` (526) y el curado de 823.
**Se verificó el árbol entero del repositorio: sólo existe `data/condiciones_emision.csv`** (823
tickers, 7 columnas). Los otros dos no están en ninguna parte.

Es consistente con `CLAUDE.md`: el curado "se rescató del universo consolidado después de que se
borraran los CSV originales" y hay que tratarlo como irrecuperable. La lectura razonable es que ya
los trae fusionados — `merge_condiciones.py` era exactamente lo que los fusionaba.

**Decisión: se siembra desde el único archivo que existe.** No se buscaron los faltantes ni se
generó nada para suplirlos. Queda declarado en el docstring de `app/condiciones/semilla.py`.

Evidencia empírica de que la fusión ya ocurrió: sobre el CSV curado, la herencia entre especies no
completa **ni una sola celda** de ley, moneda de pago, lámina ni calificación, y la detección de
conflictos no encuentra **ninguno**. Es exactamente el estado en que `merge_condiciones.py` deja un
archivo después de correr: propagado a las tres especies y con lo contradictorio ya vaciado.

## Decisiones de diseño

### D1 — El origen nombra al artefacto; la fecha es la del artefacto, no la del dato

El CSV no trae una fecha por valor: no se sabe cuándo fue cierta cada lámina. La base exige por
CHECK que todo valor no nulo traiga origen y fecha, así que hay que poner algo.

- `origen = "condiciones_emision.csv (curado)"` — nombra al artefacto, que no tiene fuente viva.
- `fecha = 2026-08-05`, uniforme para toda la semilla, **declarada como la fecha del artefacto y
  no la del dato**.

Inventar una fecha por valor sería la regla 1 al revés: un dato con fecha falsa parece más preciso
que un rótulo que dice la verdad —"esto es lo que sabíamos a esta fecha"— y por eso es peor.

La fecha es una constante en el código (`FECHA_ARTEFACTO`) y **no se lee del sistema de archivos**:
el mtime de un archivo versionado es la fecha del checkout, así que en un clon nuevo o en el
contenedor daría hoy y cada deploy rejuvenecería la semilla entera sin que nadie tocara un valor.
Un test verifica que la constante no sea futura; reemplazar el CSV obliga a actualizarla en el
mismo commit.

### D2 — El orden entre herencia y conflicto: no se encadenan

La pregunta "¿un valor heredado puede entrar en conflicto con su propia fuente?" **no llega a
existir**, porque las dos operaciones no son dos pasos sino dos ramas de una única resolución por
(emisión, campo). Se juntan los valores **declarados** —los que vinieron del artefacto, nunca los
heredados— y se mira cuántos distintos hay:

| Valores declarados distintos | Qué pasa |
|---|---|
| más de uno | **conflicto**: se vacían todos, se reporta con los valores en pugna, y no se hereda nada |
| exactamente uno | ése es el valor de la emisión: las especies que no lo declaran **lo heredan** |
| ninguno | nada que hacer |

Invertir el orden —heredar primero, buscar conflictos después— obligaría a elegir qué valor
propagar antes de saber si hay uno solo, que es justamente lo que el sistema no hace.

El vocabulario cerrado se aplica **antes** que todo esto, en la lectura: un valor que el proyecto
no maneja no es un valor, no se hereda y no es parte de un conflicto.

### D3 — El sistema no elige. Nunca.

Sin precedencia entre fuentes, sin "gana el más reciente", sin desempate. Ante dos valores en
pugna las dos especies quedan vacías y el conflicto se reporta con ticker y valor de cada parte,
vía el constructor `condiciones_en_conflicto` de `app/ingesta/alertas.py`.

Hay un test por cada forma de elegir que podría colarse: precedencia por orden del archivo, por ser
la raíz de la emisión, o por "el que declara primero". Los tres exigen lo mismo.

Dos grafías del mismo texto ("Soberano" / "soberano") son un conflicto. Unificarlas por mayúsculas
obligaría a elegir cuál grafía se guarda, que es la decisión prohibida.

### D4 — Quién figura como donante, y con qué fecha

`origen = "herencia de AL30"`. El donante es el ticker igual a la raíz si declara el valor, y si no
el primero en orden alfabético entre los que lo declaran. Todos declaran lo mismo —si no, sería
conflicto—, así que la elección no cambia el valor: cambia el rótulo, y el rótulo tiene que nombrar
a alguien que efectivamente lo declare. El donante es estable ante el orden del archivo.

**La fecha del valor heredado es la del donante**, no la de hoy: el heredero no sabe más de lo que
sabía quien se lo prestó.

### D5 — Se hereda por raíz de emisión y por nada más

`aplicar_sectores.py` propagaba el sector **por emisor**. Se midió sobre el CSV real qué aportaría
eso hoy:

| Campo | Celdas que completaría por emisor | Emisores en conflicto por emisor |
|---|---|---|
| `sector` | 0 | 0 |
| `lamina` | 8 | 34 |
| `calificacion` | 38 | 23 |
| `ley` | 1 | 20 |
| `moneda_pago` | 2 | 23 |

Es decir: para `sector` la herencia por emisor no agrega nada que la herencia por raíz no cubra, y
para los demás campos sería **incorrecta** —un emisor tiene varias emisiones y no comparten lámina
ni calificación—, lo cual se ve en la cantidad de conflictos que dispararía. Se hereda por raíz.

Las correcciones de sector hardcodeadas en `aplicar_sectores.py` (Central Puerto → Servicios,
AA2000 → Infraestructura, alias Aluar) **ya están aplicadas en el artefacto curado**: se verificó
ticker por ticker. Re-aplicarlas sería reintroducir una lista escrita a mano que el dato ya
incorporó.

### D6 — El upsert pisa, no completa (al revés que F-007)

`ingesta/consolidacion/persistencia.py` protege cada columna con `COALESCE` para que una corrida
sin IAMC no vacíe la ley del universo. Acá es al revés: **vaciar un valor es una decisión**, no una
ausencia. Un COALESCE resucitaría desde la corrida anterior justo el valor que la detección de
conflictos acaba de declarar inusable. El triplete `valor / origen / fecha` se escribe entero.

Toda la semilla va en **una sola transacción**: media semilla escrita —unas emisiones con el
conflicto ya vaciado y otras no— sería un estado que nadie declaró. Es lo contrario del criterio de
F-007, donde cada bloque tiene su transacción porque las fuentes fallan por separado.

**Una semilla vacía no escribe nada.** Sin ese guardia, un artefacto ilegible sería indistinguible
de uno que no sabe nada: la corrida no tocaría la tabla en ninguno de los dos casos pero cantaría
éxito.

### D7 — La cobertura se mide sobre el universo, abierta por origen

El tercer criterio pide que el conteo se corresponda con los valores efectivamente cargados **y su
origen**, sin ninguna fila completada por inferencia. Se implementa con dos consultas sobre la
**misma población** (`instrumentos ⟕ condiciones_emision`), de modo que la suma de los orígenes de
un campo dé exactamente sus presentes — propiedad verificada por test offline y de integración.

En el reporte agregado los orígenes heredados se agrupan bajo `"herencia entre especies"`: el
donante exacto son doscientas claves de dos filas cada una, ilegible como agregado. El donante con
nombre y apellido sigue en la fila y en el listado del API. No hay un tercer origen posible, y eso
es lo que el test verifica.

### D8 — Los conflictos viajan en la respuesta, no a una tabla

No hay dónde persistirlos —el esquema de F-002 no tiene tabla de conflictos y esta feature no
agrega migraciones—. `merge_condiciones.py` los acumulaba en un CSV aparte porque una vez vaciado
el valor la corrida siguiente ya no lo detectaba; acá eso no pasa, porque la semilla se relee
entera del artefacto en cada corrida. Un conflicto se sigue reportando mientras siga en el CSV.

## Archivos

```
backend/app/condiciones/
├── __init__.py          superficie pública: sembrar, resolver, medir_cobertura_curada
├── semilla.py           CSV → valores con origen y fecha; vocabulario cerrado (puro)
├── resolucion.py        herencia entre especies y conflictos (puro)
├── persistencia.py      upsert, cobertura sobre el universo (sólo SQL)
└── corrida.py           orquestador: leer, resolver, escribir, medir

backend/app/api/v1/condiciones.py    POST /semilla · GET /cobertura · GET (listado paginado)

backend/tests/
├── test_condiciones_semilla.py         lectura, descartes, artefacto real
├── test_condiciones_resolucion.py      GWT-1 y GWT-2
├── test_condiciones_persistencia.py    contrato del SQL y de la cobertura
├── test_condiciones_endpoint.py        corrida completa y los tres endpoints
└── test_condiciones_integration.py     contra Supabase, en transacción que se deshace
```

## Resultado de la siembra sobre el artefacto real

823 especies, cero conflictos, cero alertas. Herencia: **397 sectores y 397 emisores** completados
entre especies de la misma emisión; ley, moneda de pago, lámina y calificación ya venían
propagadas.

| Campo | En la semilla (823) | En el universo (2.894 instrumentos) |
|---|---|---|
| `ley` | 693 · 84,2 % | 674 · 23,3 % |
| `moneda_pago` | 688 · 83,6 % | 669 · 23,1 % |
| `lamina` | 568 · 69,0 % | 558 · 19,3 % |
| `calificacion` | 359 · 43,6 % | 353 · 12,2 % |
| `sector` | 820 · 99,6 % (423 declarados + 397 heredados) | 758 · 26,2 % |
| `underlying` | 773 · 93,9 % (376 declarados + 397 heredados) | 724 · 25,0 % |

62 especies curadas no están en el universo. No se pierden: la tabla no tiene FK a `instrumentos`
justamente para eso.

El denominador es el universo entero a propósito, pero el número engaña si no se abre por clase:
1.417 de los 2.894 instrumentos son CEDEARs y acciones, y para ésos los seis campos no aplican y
quedan en cero. Sobre las **1.477 especies de renta fija**, que son las que el armador mira:

| Clase | Instrumentos | con `ley` | con `lamina` | con `sector` |
|---|---|---|---|---|
| `on_corporativo` | 1.327 | 629 | 558 | 630 |
| `bono_soberano` | 112 | 45 | 0 | 94 |
| `bono_subsoberano` | 38 | 0 | 0 | 34 |
| **renta fija** | **1.477** | **674 · 45,6 %** | **558 · 37,8 %** | **758 · 51,3 %** |
| `cedear` + `accion` | 1.417 | 0 | 0 | 0 |

La lámina de los bonos del Tesoro sigue en cero: el artefacto curado no la trae para ningún
soberano. Es un hueco declarado, no un hueco que F-009 pueda llenar.
