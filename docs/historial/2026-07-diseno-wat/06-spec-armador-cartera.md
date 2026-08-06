# Spec — Armador de Carteras de Renta Fija (Opportunity C)

`tools/armar_cartera.py` · workflow operativo en `workflows/armar_cartera.md`

## Reto

> ¿Cómo armar una cartera de renta fija a medida del objetivo del cliente, en minutos y sin criterio arbitrario, respetando diversificación y previsibilidad de cobros?

Hoy el asesor arma cada propuesta a mano en Excel, eligiendo instrumento por instrumento y verificando la diversificación con la vista.

## Decisiones de diseño

### 1. El perfil no define el mix; define la calidad exigida

Dos parámetros distintos que se confundían:

- **Mix por segmento** (cuánto hard-dollar, cuánto CER…) sale del **objetivo de cobertura**: contra qué riesgo se quiere proteger el cliente.
- **Perfil** (conservador/moderado/agresivo) define **qué calidad se le exige a cada candidato**: tope de rendimiento, liquidez mínima, concentración máxima.

Un cliente conservador que quiere cubrirse de la devaluación y uno agresivo con el mismo objetivo comparten el mix pero no los instrumentos.

### 2. Sin ratings, se usan proxies observables

La fuente no trae calificación crediticia. En lugar de inventarla:

| Proxy | Lógica |
|---|---|
| **Tope de rendimiento** | Un rendimiento muy por encima de sus pares en USD es *distress*, no oportunidad. Una ON hard-dollar al 245% tiene el precio roto |
| **Percentil de liquidez** | Calculado dentro del propio segmento, no global |
| **Concentración máxima** | Por emisor, y por riesgo soberano agregado |

El análisis crediticio profundo sigue siendo del usuario. La herramienta descarta lo evidentemente roto, no pretende evaluar crédito.

### 3. El riesgo soberano se agrupa aparte

El Tesoro emite bajo muchos prefijos (GD, AE, DIC, TZX, TY3…) y **todos son el mismo riesgo de crédito**. Agrupar por prefijo de ticker dejaba pasar una cartera 100% soberana como si estuviera diversificada.

Se resuelve con una clave de riesgo única (`SOBERANO_AR`) y un tope propio (`max_soberano`), separado del corporativo. Hace falta que sean topes distintos: en el mercado argentino los segmentos en pesos (CER, tasa fija) son casi íntegramente soberanos, así que exigirles el límite corporativo haría inviable cualquier cartera en pesos.

### 4. Los rendimientos no se promedian entre sí

Un promedio único entre una TIR en dólares, una tasa **real** sobre CER y una TNA **nominal** en pesos no tiene significado económico. El resumen los reporta abiertos en 4 naturalezas de tasa. La duration sí se agrega: mide sensibilidad temporal en la misma unidad.

### 5. La continuidad del cobro mensual es criterio de armado

Del Excel real de la mesa (`Propuesta Base 7-26`, hoja "Renta Fija pago mensual") surge que la cartera se arma para que pague **todos los meses**: hay una fila `Mes pago` por bono y totales mensuales donde ningún mes queda en cero.

Implementación: entre candidatos que rinden dentro de **0,5pp** del mejor disponible, gana el que suma un mes de cobro todavía descubierto. Fuera de esa banda manda el rendimiento. El umbral es el mismo con el que la mesa evalúa un swap — por debajo de eso la diferencia de tasa no justifica mover nada.

Medido sobre el universo real: cubre los 12 meses resignando **0,13pp** de renta anual.

## Cómo se traduce un cupón a plata

`lastPrice` del universo viene en **monedas mezcladas**: la misma emisión cotiza en pesos sin sufijo y en dólares con sufijo D/C (AE38 a 127.360 son pesos; PNDCD a 43,77 son dólares). Dividir un monto por ese precio da cualquier cosa.

La normalización pasa por la paridad, que es adimensional:

```
precio sucio (moneda de emisión, c/100 nominales) = paridad × valor técnico
valor técnico  = residual vivo + intereses corridos
cobro / monto  = cash_flow / precio sucio        ← adimensional
```

**Validación**: la fórmula de nominales (`monto / (precio/100)`) reproduce exacto los cuatro casos del Excel real — RUCED, SBC2D, CS47D, LOC5D. Y el cashflow de RUCEO da 7,28% de renta a 12 meses contra un cupón nominal de 7,5%, menor porque cotiza sobre la par: lo que corresponde.

## Stress test

| Escenario | Comportamiento |
|---|---|
| Cobertura inflación | Cartera 100% soberana: el universo CER argentino no permite diversificar crédito. **Sale con alerta explícita** |
| Cobertura tasa-pesos | Badlar sin candidatos en el horizonte medio; se redistribuye y se avisa |
| `--moneda usd` | Descarta CER, dólar linked y tasa fija; reescala el resto a 100% |
| Monto de USD 1.000 | Arma igual, pero alerta que las posiciones quedan en ~USD 62 y sugiere bajar `--n-total` |
| Segmento sin candidatos suficientes | Cada posición conserva el peso validado; el sobrante se redistribuye |
| Sin `cashflow_completo.csv` | Arma sin calendario y avisa |

## Bugs encontrados y corregidos durante la verificación

1. **Emisión duplicada** — MR46O y MR46D son la misma emisión en distinta especie de liquidación. Se colapsan por raíz de ticker, con chequeo de consistencia de duration (>5% de divergencia = no son el mismo bono).
2. **Concentración por segmento en vez de global** — un emisor puede aparecer en varios segmentos; el control tiene que ser global sobre la cartera.
3. **Tope soberano inaplicable** — ver decisión 3.
4. **Peso inflado post-validación** — si entraban menos instrumentos de los buscados, se repartía el peso completo del segmento entre los que quedaron, empujando cada posición por encima del límite que el motor ya había verificado.
5. **Promedio de tasas de distinta naturaleza** — ver decisión 4.
6. **Falso "mes sin renta"** — el mes en curso, con sus cupones ya pagados, contaba como descubierto. La ventana arranca el mes siguiente.

## Fuera de alcance

- Calificación crediticia (no está en la fuente)
- Lámina mínima (los montos no están ajustados a lámina operable)
- Proyección de coeficientes de ajuste: en bonos CER/dólar linked/Badlar/Tamar el calendario usa el coeficiente de hoy
