# Feature Plan: F-010 — Sanidad del dato en dos capas

## Contexto

- **Source:** `claude-docs/planning/plan.md` (ficha F-010) + `tools/segmentos.py:133-279`, que es
  la lógica original ya verificada contra el universo real.
- **Depende de:** F-007 (consolidador). **Habilita:** F-011, F-012, F-013, F-015, F-038.
- **Complejidad:** S. La lógica ya estaba resuelta; el trabajo es portarla sin traicionarla y darle
  al paquete `universo/` la forma que F-011 y F-012 van a heredar.

La feature envuelve como servicio lo que el motor Python ya hacía, y existe por las reglas 2 y 3 del
dominio: los rendimientos de distinta naturaleza no comparten eje, y nada se compara entre monedas
sin normalizar.

**Capa 1 — coherencia entre especies del mismo bono.** Un bono tiene UNA TIR: sus especies de
liquidación (O/D/C) tienen que declarar la misma. Cuando una se despega de las otras por más de
100 pp, esa especie tiene el precio mal escalado. El umbral es 100 pp y no menos porque hay
discordancias legítimas: DICPD rinde 51 pp más que DICP y son datos válidos.

**Capa 2 — techo de lo posible, por segmento y en la unidad de cada segmento.** hard-dollar y
dólar-linked 300 %, CER 100 % de tasa *real*, tasa fija/Badlar/Tamar 500 % de TNA *nominal*. Los
topes son holgados a propósito: SNSBO al 245 % en dólares es dato correcto —bono a 80 días cotizando
al 78 % de su valor técnico— y un umbral ajustado lo mataría junto con la basura.

Nada se corrige y nada se estima: el instrumento descartado sigue en el universo para poder
auditarlo, pero no se propone.

## Decisiones de diseño

### 1. La segmentación entra en el alcance, y por eso el paquete se llama `universo` y no `sanidad`

La capa 2 necesita el segmento de cada instrumento para elegir el tope, y el segmento hoy sólo lo
calcula `tools/segmentos.py`. El backend no importa de `tools/`, así que F-010 porta también la
segmentación. Eso convierte al paquete en "el universo como servicio" y no en "la sanidad como
servicio", que es la forma correcta: F-011 y F-012 también parten del universo segmentado.

### 2. Los umbrales no son configuración

No se agregó nada a `config.py`. Son criterio de dominio verificado caso por caso; hacerlos
ajustables por entorno invitaría a subirlos cuando descarten algo molesto, que es exactamente cuando
hay que mirarlos.

### 3. Python puro, no pandas

El motor usa pandas porque lee un Excel. El backend lee filas de asyncpg, así que la sanidad se
escribió como funciones puras sobre dataclasses, igual que `armado.py` en F-007. Además de ser el
patrón del backend, evita la trampa que el port sí tuvo (ver "Lo que encontró el test de paridad").

### 4. El descartado no sale del universo

`UniversoSaneado.especies` incluye a los descartados; `operables()` es el corte para quien necesita
la lista corta. Si el descartado desapareciera, nadie podría contestar por qué VSCQD no está.

### 5. Un instrumento se lista una sola vez, y gana la capa 1

Una especie con el precio mal escalado viola además cualquier techo. Contarla en las dos capas
duplicaría el mismo problema haciendo creer que hay dos. Gana la capa 1 porque explica mejor qué
pasó: nombra la especie hermana que sí tiene el precio bien.

### 6. Dos endpoints y no uno

`/universo/sanidad` contesta "¿sirve el universo de hoy?" y es lo que mira una corrida.
`/universo/sanidad/descartes` contesta "¿por qué no está VSCQD?" y es una colección paginada por
cursor. Juntos obligarían a devolver la colección entera en cada chequeo.

### 7. El piso de una emisión es el mínimo, no el promedio

Un valor de 34 millones por ciento arrastraría cualquier promedio y dejaría de detectarse a sí
mismo. Y se mira sólo hacia arriba: el error que la capa 1 ataca —un precio mal escalado— siempre
infla la TIR; una especie que rinde de menos está diciendo que cotiza más cara, que es un dato
posible y no un error de escala.

## Archivos

| Archivo | Qué es |
|---|---|
| `backend/app/universo/__init__.py` | superficie pública + el mapa del paquete y dónde se engancha lo que falta |
| `backend/app/universo/lectura.py` | la vista `resumen` → filas crudas. Sólo SQL |
| `backend/app/universo/segmentacion.py` | segmento, unidad de tasa y `EspecieUniverso` |
| `backend/app/universo/sanidad.py` | las dos capas. Funciones puras, sin base ni reloj |
| `backend/app/universo/servicio.py` | la corrida: leer, segmentar, sanear → `UniversoSaneado` |
| `backend/app/api/v1/universo.py` | `GET /universo/sanidad` y `GET /universo/sanidad/descartes` |
| `backend/tests/test_universo_segmentacion.py` | la segmentación y las unidades |
| `backend/tests/test_universo_sanidad.py` | los cuatro GWT y sus bordes |
| `backend/tests/test_universo_servicio.py` | la orquestación y el resumen |
| `backend/tests/test_universo_api.py` | el contrato HTTP y la paginación |
| `backend/tests/test_universo_paridad_motor.py` | el port contra `tools/segmentos.py` |
| `backend/tests/test_universo_integration.py` | contra la base real, marcado `integration` |

## Qué le toca a F-011 y a F-012

`EspecieUniverso` es el tipo que atraviesa el paquete y es donde crece lo que falta:

- **F-011 (dedup)** le suma lo que decide el representante de una emisión: `duration`, la
  completitud de datos (`maturity`, `law`, `couponCurrency`, `underlying`) y el volumen. La clave de
  emisión ya está en el tipo (`raiz`), en las dos vistas.
- **F-012 (tipo de cambio implícito)** le suma las dos puntas del cociente: `lastPrice` y la moneda
  de cotización, más `effectiveVolume` para normalizar.

Las columnas se agregan en `lectura.COLUMNAS` y en el dataclass; el resto del paquete no se entera.

Las dos parten del `UniversoSaneado` y no de la lectura cruda: elegir como representante de una
emisión a la especie con el precio mal escalado, o derivar el tipo de cambio de ese mismo precio,
sería propagar el error en vez de contenerlo.

## Lo que encontró el test de paridad

El port se comparó contra `tools/segmentos.py` sobre el mismo input —el consolidado histórico, que
sí tiene los casos rotos— y la primera corrida no coincidió: el motor descartaba 4 instrumentos y el
backend 367.

**Causa:** pandas escribe `NaN` donde no hay dato. `NaN <= tope` es `False`, y la condición de la
capa 2 estaba escrita como la negación de "conservar lo que no supera el techo", así que cada
faltante caía del lado del descarte. El motor no tenía el problema porque pandas filtra los `NaN`
antes de comparar. Era un caso de la regla 1 disfrazado: el sistema estaba condenando por roto lo
que simplemente no sabía.

**Arreglo, con dos cinturones:** `_numero()` traduce `NaN` a `None` al segmentar, y la comparación
de la capa 2 se escribió en positivo —"descartar lo que supera el techo"— para que un valor
incomparable caiga del lado de conservar. Después del arreglo los dos veredictos coinciden exacto:
los mismos 4 tickers, en las mismas capas.

## Estado del universo real (06/08/2026)

Sobre las 2.894 filas de la vista `resumen`: **las dos capas descartan cero**, y la razón no es que
el port esté roto.

| | |
|---|---|
| Leídas | 2.894 |
| Renta variable (acciones + CEDEARs) | 1.417 |
| Sin segmento (renta fija sin `tipo_tasa`) | 535 |
| Evaluadas | 942 |
| Con rendimiento publicado | 217 |
| Descartadas por capa 1 | 0 |
| Descartadas por capa 2 | 0 |

- **La capa 1 no tiene con qué comparar.** De las 217 emisiones con TIR, **ninguna tiene dos
  especies con TIR a la vez**. Es consecuencia directa de F-007: las métricas de IAMC se escriben
  sólo en el ticker que el informe nombra, y las demás especies quedan con el campo vacío. Hasta que
  otra fuente publique TIR por especie, esta capa no puede disparar.
- **La capa 2 no encuentra nada fuera de rango.** El máximo entre las especies segmentadas es BPCSO
  con 275 % en dólares, por debajo del tope de 300 %. **SNSBO figura hoy con 242,5 % y se conserva**,
  que es el GWT-2 verificado contra dato real.
- **`tna` está en cero filas**, así que ningún instrumento de tasa fija tiene rendimiento y el tope
  de 500 % de TNA nominal no puede dispararse todavía. F-007 ya lo alerta.
- **VE32P declara 614 % de TIR y no se evalúa** porque no tiene `tipo_tasa`: sin segmento no hay
  unidad, y comparar sin unidad sería justamente lo que la feature existe para impedir. Aparece
  contado en `sin_segmento`, que es donde tiene que estar.

## Riesgos

- **La cobertura de TIR es el techo de la feature.** Con 217 de 2.894 instrumentos con rendimiento,
  la sanidad opina sobre el 7 % del universo. No es un problema de F-010 sino de qué publica IAMC,
  pero conviene no leer "cero descartes" como "universo sano".
- **El port puede divergir del motor.** Mitigado con `test_universo_paridad_motor.py`, que los corre
  a los dos sobre el mismo Excel y exige el mismo veredicto.
