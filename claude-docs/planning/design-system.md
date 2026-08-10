---
Fase: 3 — Design System
Fuente: Claude Design, proyecto "Cinco alternativas de visualización de cartera"
Proyecto ID: 19678bf3-12bb-43cf-bcef-fcc5e519c1a2
Archivo origen: design_handoff_cordillera/README.md
Diseño elegido: 1 Cordillera v2
Bajado: 2026-08-05
---

# Handoff: Cordillera — armado y seguimiento de carteras (ALyC)

## Overview

Herramienta interna para asesores financieros de un ALyC argentino. Resuelve dos trabajos:

1. **Armar una cartera nueva** a partir del mandato del cliente (objetivo, riesgos a cubrir, horizonte, moneda, monto), moviendo instrumentos y viendo en vivo cómo cambia el resultado.
2. **Seguir una cartera ya vendida**: qué se cobró, qué falta cobrar, cómo se comporta contra el mandato firmado.

El concepto central es **la cuponera**: elegir bonos de forma que los cupones caigan repartidos a lo largo del año. La tesis de esta interfaz es que *el asesor no elige papeles: esculpe la forma del año, y la cartera es el subproducto*. Por eso el calendario de cobros no es un reporte final sino el criterio de armado, y se dibuja como una cordillera de doce columnas cuya altura es plata real.

El número que cierra la venta —**renta anual sobre lo invertido, sólo cupones**— está siempre visible y se recalcula con cada cambio.

## About the Design Files

Los archivos de este bundle son **referencias de diseño hechas en HTML**: prototipos funcionales que muestran el aspecto y el comportamiento buscados, **no código de producción para copiar**. Están escritos en un runtime propio (`support.js` + plantillas `.dc.html`) que no debe portarse.

La tarea es **recrear estos diseños en el entorno del codebase destino** (React, Vue, Angular, lo que exista) usando sus patrones y librerías establecidas. Si todavía no hay entorno, elegir el framework más apropiado e implementarlos ahí. Lo único que conviene portar casi tal cual es la **lógica de cálculo** descrita más abajo (y presente en `datos.js`), porque son reglas de negocio, no diseño.

Cómo abrir los prototipos: servir la carpeta con cualquier servidor estático (`npx serve .`) y abrir `1 Cordillera v2.dc.html`. Requiere que `datos.js` y `support.js` estén en la misma carpeta (los `.dc.html` de `referencia/` esperan `datos.js` un nivel arriba: si querés abrirlos, copiá `datos.js` y `support.js` dentro de `referencia/`).

## Fidelity

**Alta (hifi).** Colores, tipografía, espaciados, densidad y estados son definitivos y están declarados abajo con valores exactos. Recrear la UI fielmente con las librerías del codebase. Si el codebase ya tiene design system, mapear los tokens de acá a los suyos manteniendo la jerarquía y la densidad (es una pantalla de trabajo: la densidad alta es intencional).

Los datos de mercado son **de ejemplo** (rueda ficticia del 05/08/2026) con tickers y órdenes de magnitud argentinos plausibles. Deben reemplazarse por el feed real.

---

## Screens / Views

La aplicación tiene **una sola ruta** con dos secciones conmutadas por un toggle en la barra superior: `Armado` y `Seguimiento`. Más un **drawer lateral de ficha de instrumento** que puede abrirse desde cualquiera de las dos.

### Barra superior (fija, común a las dos secciones)

- Altura 52 px, `background: --pan`, borde inferior 1 px `--lin`, `position: sticky; top: 0; z-index: 40`.
- Contenido, de izquierda a derecha, con `gap: 16px` y padding lateral 18 px:
  - Marca "Cordillera" 17 px / peso 700 / `letter-spacing: -0.01em`, más "v2" 10 px mayúsculas `letter-spacing: 0.14em` en `--dim`.
  - Toggle de sección: dos botones de 6×14 px de padding, 12 px, radio 3 px. Activo: fondo `--ac`, texto `--bg`, borde `--ac`. Inactivo: fondo transparente, texto `--dim`, borde `--lin`.
  - Indicador de vivo: caja con borde 1 px `--lin`, radio 3 px, tipografía mono 11 px. Punto de 6 px `--pos` con `animation: pulso 1.6s infinite` (opacidad 1 → .25 → 1). Texto "EN VIVO" en `--pos` y "refresco en Ns" en `--dim`, con cuenta regresiva de 8 segundos en bucle.
  - A la derecha: selector de cliente (`select`), campo de monto (mono, alineado a la derecha, 94 px), conmutador de moneda de operación (Pesos / MEP / Cable — segmentado, activo con fondo `--ac` y texto `--bg`), y botón de tema (☾ / ☀).

### Sección A — Armado

Estructura vertical dentro de un contenedor de padding 14/18 px:

**A1. Mandato del cliente** (panel colapsable, ancho completo) — **no implementado.** Es alcance
de producto nuevo sin feature en `plan.md` (modelo de mandato, guardado, validación contra
cartera). El patrón de plegado de la Etapa 2 del rediseño del armador (09/08/2026,
`SeccionDeArmador`) es el mismo que pide este panel — implementarlo es la base ya lista, falta el
resto.
- Cabecera clickeable: rótulo "MANDATO DEL CLIENTE" 10 px mayúsculas `letter-spacing: 0.13em` en `--ac`; resumen en una línea (`nombre · perfil · horizonte · piso US$ X/mes · cubrir …`) 12,5 px; a la derecha "guardado dd/mm hh:mm" o "sin guardar" en mono 11 px `--dim`; chevron ▲/▼.
- Cuerpo abierto: grilla `1.3fr 1fr 1fr`, `gap: 20px`.
  - Columna 1: textarea "Qué busca" (2 filas, 12,5 px, `line-height: 1.5`), input "Piso mensual (US$)" (mono 14 px, texto `--ac`, 96 px), selects "Horizonte" (2/5/8 años) y "Perfil" (Conservador / Moderado / Agresivo declarado).
  - Columna 2: chips "Contra qué se quiere cubrir" — Devaluación, Inflación local, Riesgo soberano, Suba de tasas, Iliquidez. Chip activo: fondo `--ac`, texto `--bg`. Inactivo: transparente, texto `--dim`, borde `--lin`. Radio 12 px, padding 5×11 px, 11,5 px.
  - Columna 3: chips de restricciones — Sin ley Argentina, Sin provinciales, Máx. 30% renta variable, Duración mínima 2 años. **Activo en `--neg`** (son prohibiciones). Debajo, botones "Guardar mandato" (primario) y "Filtrar universo por mandato" (secundario), y una línea de aviso: si la cartera viola el mandato el texto va en `--neg`, si no en `--dim`.

**A2. Cordillera en dólares** (panel principal)
- Cabecera: rótulo + bajada "Tocá un mes para abrirlo y comparar los papeles que pagan ahí.". A la derecha: segmentado de modo de renta variable (Rombos / Dividendos / Panel aparte), botones "Leer cartera del cliente", "Silueta original" y copiar panel (⧉).
- Gráfico: alto 290 px, doce columnas `flex: 1`, `gap: 8px`, alineadas abajo.
  - Cada columna es una barra apilada: un tramo por papel que paga ese mes, altura proporcional al monto, color `--ac`, separador `border-top: 1px solid rgba(0,0,0,.35)`. Radio superior 4 px.
  - Encima de la barra, el monto del mes en mono 11,5 px: `--tx` si supera el piso, `--ac2` si está por debajo, `--neg` si es cero (muestra "—").
  - Línea de piso: `border-top: 1px dashed --ac2` posicionada a `piso / pico * 100%`, con etiqueta "piso US$ N" en mono 10,5 px `--ac2` sobre fondo `--pan`.
  - Silueta original (cuando se leyó la cartera del cliente): rectángulo `border: 1px dashed --sd` sin borde inferior, a la altura del mes en la cartera original.
  - Mes seleccionado: fondo de la columna `rgba(94,227,154,.10)` en oscuro / `rgba(14,138,85,.08)` en claro, borde superior de la etiqueta 2 px `--ac`, nombre del mes en `--ac` y peso 700.
- Debajo del gráfico, fila de etiquetas de mes (12,5 px) y rombos de 7 px rotados 45°: `--ac2` para amortizaciones, `--sd` para balances trimestrales (sólo en modo Rombos).
- Leyenda inferior 10,5 px `--dim`: renta (cupón) en dólares · amortización · balance/dividendo según modo · cartera original.

**A3. Cordillera en pesos** (panel secundario, alto 118 px)
- Misma mecánica, color de barra `--ac2`, montos compactados ("12,9 MM").
- **Escala y unidad propias.** Nota fija: los cobros en pesos nunca se suman a los dólares ni se convierten para el total, y la TIR de esta parte no se promedia con la del segmento dólar hard.
- Si no hay posiciones en pesos, muestra el estado vacío explicándolo.

**A4. Panel aparte de renta variable** (sólo en modo "Panel aparte")
- Grilla de tarjetas `repeat(auto-fill, minmax(268px, 1fr))`, `gap: 10px`, fondo `--pan2`.
- Cada tarjeta: ticker (mono 14 px, subrayado sutil, abre la ficha), emisor, variación del día a la derecha (`--pos`/`--neg`/`--ac2` si es s/d); tres métricas (Peso, Invertido, Div. est.); calendario de doce celdas de 16 px de alto — `--sd` balance, `--ac2` dividendo estimado, transparente con borde `--lin` si no hay nada; nota con industria, tipo y rendimiento por dividendos anualizado.
- Total del año en dividendos estimados, siempre rotulado como **no garantizado** y separado de la renta por cupones.

**A5. Detalle del mes** (aparece al tocar una columna)
- Panel con borde `--ac`. Título "Marzo · US$ 425 de renta" 15 px 600 en `--ac`, bajada con cuántos papeles del universo pagan ese mes.
- Grilla de tarjetas comparables `repeat(auto-fill, minmax(232px, 1fr))`: ticker + emisor, tres métricas grandes (TIR / Cupón / Frecuencia), línea de detalle (tipo, ley, estructura, vencimiento, duración, lámina, meses en que paga), mini-calendario de 12 celdas, botón "sumar al 10%" y el aporte calculado ("+US$ 158 en Ene") en `--pos`.

**A6. Rotaciones propuestas · con el efecto medido**
- Una fila por rotación: grilla `150px 1fr 200px 92px`.
  - Columna 1: "– TICKER" en `--neg` sobre "+ TICKER" en `--pos`, mono 12,5 px.
  - Columna 2: motivo en prosa (mes flojo vs. mes saturado, TIR y duración de los dos papeles).
  - Columna 3: efecto medido en cuatro pares rótulo/valor — aporte al mes flojo, renta anual antes→después, parejo antes→después, TIR ponderada antes→después. Verde si mejora, `--ac2`/rojo si empeora.
  - Columna 4: botón "Aplicar".
- **Sólo se muestran rotaciones que mejoran de verdad** (ver reglas abajo). Si no hay ninguna, el panel lo dice explícitamente en vez de proponer algo malo.

**A7. Universo** (columna izquierda de la última fila)
- Cabecera con conteo y filtro de mes activo.
- Barra de segmentos: Dólar hard / CER / Tasa fija $ / Dólar linked / Badlar / Tamar / Acciones y CEDEARs. **Nunca dos segmentos a la vez**; el activo lleva borde inferior 2 px `--ac`.
- Barra de filtros numéricos: rendimiento mín/máx (el rótulo cambia con la unidad del segmento), duración máxima, botón limpiar.
- Filas: `minmax(70px,88px) 1fr 56px 46px 92px 24px` → ticker + ley / emisor + subtítulo / rendimiento con su rótulo de unidad / cupón en `--ac2` / mini-calendario de 12 celdas / botón + o ✓.
- Alto máximo 352 px con scroll.

**A8. Cartera** (columna derecha)
- Cabecera: Σ de ponderación pedida (en `--ac2` si no suma 100), invertido, botones Equiponderar y Vaciar.
- Filas: `minmax(70px,86px) 1fr 52px 62px 52px 22px` → ticker + moneda de cobro / emisor + VN e invertido / input de ponderación pedida (mono, texto `--ac`) / **ponderación real** con tooltip explicando el redondeo a lámina / mini-calendario / ×.
- La diferencia entre pedido y real se muestra en `--ac2` cuando supera 0,6 pp. Nunca se esconde.

**A9. Columna derecha fija** (252 px, `position: sticky; top: 66px`)
- Tarjeta grande: "Renta anual en dólares", número en mono 36 px `--ac`, y la cuenta expuesta: `US$ 5.264,50 / US$ 72.460,50 = 7,27%`.
- Cuatro KPIs en grilla 2×2: Meses cubiertos (n/12), Parejo (%), TIR ponderada USD (sólo dólar hard), Duración + mix RF/RV.
- "Lo que falta": lista de avisos accionables (mes bajo el piso → abre ese mes; renta variable por debajo del rango → abre el segmento).
- Flujo mes por mes en mono 10,5 px, total anual y botón "Descargar propuesta".

**Implementado en la Etapa 6 del rediseño del armador (`ColumnaKpis.tsx`, 09/08/2026)**: la
tarjeta de renta anual y los cuatro KPIs, tal como los describe esta sección (número en `--pos`,
no `--ac` — ver la disciplina `--ac`/`--pos` de la Etapa 1). "Lo que falta" sólo trae avisos
derivables de datos existentes (meses sin cobertura, posiciones sin resolver): "mes bajo el piso"
y "renta variable por debajo del rango" necesitan A1 (mandato), que no existe todavía. El flujo
mes por mes y "Descargar propuesta" quedan para cuando F-042 (export) esté en plan.

### Sección B — Seguimiento

- **Cinco KPIs** en tarjetas: Valuación hoy (con costo debajo), Resultado por precio (sin contar cupones), Renta cobrada (ene–jul, acreditada), Renta por cobrar (ago–dic, proyectada), Renta anual sobre lo invertido.
- **Año en curso**: doce columnas de 210 px de alto. Los meses pasados son barras **llenas** `--ac` con borde sólido y rótulo "cobrado"; los futuros son barras **vacías con borde punteado** `--ac` y rótulo "proyectado". La distinción visual entre lo real y lo proyectado es obligatoria.
- **Posiciones vendidas al cliente**: tabla `minmax(72px,88px) 1fr 64px 64px 58px 74px 74px` → ticker (abre ficha) / emisor + fecha y tipo / precio de compra / precio de hoy / variación (`--pos`/`--neg`) / cobrado a la fecha / próximo cobro.
- **Alertas de la cartera viva**: meses que quedan sin cobro en lo que resta del año (lleva a Armado con ese mes abierto y la cartera cargada), amortizaciones próximas a reinvertir, papeles con datos de mercado incompletos.
- **Contra el mandato firmado**: tres chequeos con ✓/✗ — piso mensual, mix declarado, riesgos que el cliente pidió cubrir.

### Drawer — Ficha del instrumento

- Panel fijo a la derecha: `top: 52px; right: 0; bottom: 0; width: 430px`, borde izquierdo 1 px `--ac`, `box-shadow: -16px 0 40px rgba(0,0,0,.35)`, scroll propio, `z-index: 50`.
- Cabecera sticky con ticker (mono 20 px), emisor y botón ✕.
- **"El mismo papel en las tres monedas"**: tres tarjetas (Pesos / Dólar MEP / Dólar cable) con el ticker de cada especie, su precio y **sus propias puntas**. La moneda activa lleva borde `--ac`. Donde la especie no cotiza: "no cotiza" y puntas "s/d". Nota explicando que son tres tickers del mismo instrumento y que nunca se suman.
- **Ficha**: grilla de dos columnas con tipo, ley, estructura, cupón y frecuencia, TIR, duración modificada, convexidad, vida promedio, paridad, valor técnico, valor residual, lámina mínima, moneda de pago, volumen, variación y vencimiento. Para renta variable: TIR y duración dicen **"no aplica"** (no "s/d"), y aparecen apertura, máximo, mínimo, cierre anterior, órdenes, dividendo y rendimiento por dividendos.
- **Cronograma** de los próximos doce meses: fecha, tipo (renta / amortización / balance / dividendo estimado) y monto cada 100 VN. Nota aclarando que el flujo en dólares del cliente sale del nominal asignado.
- Botones: sumar/sacar de la cartera y copiar panel.

---

## Interactions & Behavior

- **Tocar una columna del calendario** alterna el mes seleccionado: filtra el universo a los papeles que pagan ese mes y abre el panel de detalle. Volver a tocarla lo cierra.
- **Tocar un papel** en universo, comparables o cartera lo agrega o lo saca. Al agregar, el peso inicial es `100 / (n+1)` redondeado a un decimal; el resto de los pesos no se toca (por eso Σ puede no dar 100 y se muestra).
- **Editar la ponderación** recalcula todo en vivo: nominales, invertido, flujo mensual, renta anual, KPIs.
- **Equiponderar** reparte `100 / n` entre todas las posiciones. **Vaciar** limpia cartera y silueta.
- **Leer cartera del cliente** carga las posiciones y fija la silueta punteada de referencia; "Silueta original" la muestra u oculta.
- **Aplicar rotación** reemplaza la posición saliente por la entrante conservando su peso.
- **Guardar mandato** sella fecha y hora; cualquier cambio en chips o campos vuelve el estado a "sin guardar".
- **Cambio de moneda de operación** (Pesos/MEP/Cable) cambia el ticker y el precio con que se compran los instrumentos en dólares; los instrumentos en pesos siempre operan en pesos.
- **Refresco en vivo**: cuenta regresiva de 8 s en bucle. En producción debe disparar el refetch de precios y recalcular sin perder foco de inputs ni scroll.
- **Tema claro/oscuro** conmuta la paleta completa; ambos temas son de primera clase.
- Sin animaciones más allá del pulso del indicador de vivo. Las transiciones de altura de barras pueden hacerse en 150–200 ms `ease-out`, opcional.
- **Responsive**: pensado para 1440–1920 px. Las grillas de tarjetas usan `auto-fill/minmax`; las columnas fijas (252 px derecha, 430 px drawer) deberían pasar a overlay por debajo de 1280 px.

---

## State Management

Estado de la sección de armado:

| Variable | Tipo | Qué hace |
|---|---|---|
| `sec` | `'armar' \| 'seguimiento'` | Sección activa |
| `clienteId` | string | Cliente elegido; al cambiar resetea monto, piso, objetivo, perfil, horizonte y riesgos |
| `monto` | number | Capital a invertir, en dólares |
| `mon` | `'ars' \| 'mep' \| 'cable'` | Moneda de operación |
| `pos` | `{id, peso}[]` | Cartera en construcción (peso = ponderación **pedida**, en %) |
| `ghost` | `{id, peso}[] \| null` | Cartera original del cliente, para la silueta |
| `verGhost` | boolean | Muestra u oculta la silueta |
| `seg` | id de segmento | Segmento activo del universo |
| `selMes` | 1–12 \| null | Mes abierto |
| `sel` | id de instrumento \| null | Ficha abierta en el drawer |
| `rvModo` | `'rombos' \| 'dividendos' \| 'panel'` | Cómo entra la renta variable |
| `obj` | number | Piso mensual en dólares |
| `objetivoTxt`, `horizonte`, `perfil`, `riesgos[]`, `restr[]`, `guardado` | — | Mandato del cliente |
| `tirMin`, `tirMax`, `dmMax` | string | Filtros numéricos del universo |
| `tema` | `'oscuro' \| 'claro'` | Paleta |
| `tick` | number | Segundos hasta el próximo refresco |

**Datos que hay que traer del backend**: universo de instrumentos con ficha y calendario de pagos; precios en vivo por especie (las tres monedas por instrumento); mandato y cartera guardados por cliente; cartera vendida con precio y fecha de compra; cupones ya acreditados.

---

## Reglas del dominio (no negociables)

Una implementación que las viole está mal aunque se vea bien.

1. **Los rendimientos de distinta naturaleza nunca comparten eje ni se promedian.** Seis segmentos con seis unidades: dólar hard (TIR en USD), CER (tasa real), tasa fija en pesos (TNA), dólar linked, Badlar y Tamar (márgenes). Un gráfico = un segmento, con la unidad declarada. La TIR y la duración ponderadas de la cartera se calculan **sólo sobre el segmento dólar hard**; si hay posiciones de otros segmentos se informan aparte.
2. **El mismo bono cotiza en tres monedas** (AL30 / AL30D / AL30C): son tres tickers con **su propio book de puntas**. Se muestran juntos para comparar, nunca se suman ni se convierten entre sí.
3. **Los cobros en pesos y en dólares no se suman.** Dos cordilleras, dos escalas, dos totales de renta.
4. **Cuando falta un dato se muestra "s/d".** Nunca se estima ni se rellena ni se deja la celda muda. Distinto de "no aplica" (una acción no tiene TIR: eso no es un dato faltante).
5. **La ponderación pedida y la real conviven en pantalla.** El nominal se redondea **hacia abajo** al múltiplo de la lámina mínima, así que un 16,5% pedido puede quedar en 17,6% real. Se muestran las dos y la diferencia se marca.
6. **La renta anual sobre lo invertido es sólo cupones**, con la cuenta a la vista, y separada de cualquier ganancia de capital. Los dividendos estimados nunca entran ahí.
7. **La interfaz no empuja al riesgo.** El perfil del inversor argentino tiende a la conservación aun cuando el cliente se declare arriesgado.

---

## Lógica de cálculo (portar tal cual)

Implementada en `datos.js` (`resolver`, `puntasDe`) y en el método `resolverMix` del prototipo. En pseudocódigo:

```
resolver(posiciones, monto, monedaOperación):
  tc = cotización MEP o cable según la moneda de operación
  para cada posición:
    esUSD        = instrumento.segmento == 'hard' o es renta variable
    monedaCompra = esUSD ? monedaOperación (o 'mep' si no cotiza ahí) : 'ars'
    precio       = instrumento.precios[monedaCompra]          // cada 100 VN
    objetivo     = monto * peso/100 * (monedaCompra=='ars' ? tc : 1)
    VN           = floor(objetivo / (precio/100) / lámina) * lámina   // SIEMPRE hacia abajo
    invertidoLocal = VN * precio / 100
    invertidoUSD   = monedaCompra=='ars' ? invertidoLocal / tc : invertidoLocal
  pesoReal = invertidoUSD / suma(invertidoUSD) * 100

  para cada mes 1..12 y cada posición de renta fija:
    si el mes está en instrumento.meses:
      cupón = VN * (cupónAnual/100) / cantidadDePagos * (valorResidual/100)
      va al balde USD si el segmento es 'hard', al balde ARS si no
    amortizaciones: VN * porcentaje/100 en su mes
  renta variable: sólo marca balances y, si hay historia, dividendo estimado
                  = invertidoUSD * rendDiv/100 repartido entre sus meses (NO es renta)

  rentaAnualUSD  = suma de cupones USD
  rentaPct       = rentaAnualUSD / invertido en posiciones que cobran en USD
  cubiertos      = meses con cobro > 0
  parejo         = 1 - ( Σ|renta_mes - promedio| / (2*rentaAnual) * (12/11) )   // 100% = perfecto
  TIR ponderada  = Σ(TIR_i * invertido_i) / Σ invertido_i   sólo segmento 'hard'
  remanente      = monto - invertido
```

**Motor de rotaciones** (A6): para cada uno de los dos meses más flojos, tomar los 5 mejores candidatos que pagan ahí (ordenados por cupón y luego TIR) y las 4 posiciones más prescindibles del mes más saturado (menor cupón, y que no paguen en el mes flojo); simular las 20 combinaciones; puntuar `Δparejo + Δrentaanual*8 + Δmesescubiertos*6`; descartar la rotación si no sube la renta del mes flojo o si baja la renta anual más de 0,05 pp; quedarse con la mejor. **Si ninguna pasa el filtro, decirlo en vez de proponer algo malo.**

**Puntas por especie** (`puntasDe`): si el precio de esa moneda coincide con el último operado, devolver el book real; si no, derivarlo con un spread por liquidez (0,40% en pesos, 0,45% MEP, 0,70% cable). Si la especie no cotiza, `null` → "s/d". En producción esto lo reemplaza el book real del feed; **jamás reusar el book de otra especie**.

---

## Design Tokens

### Colores — tema oscuro (default)

| Token | Hex | Uso |
|---|---|---|
| `--bg` | `#0a0e13` | Fondo de la app |
| `--pan` | `#111820` | Paneles y tarjetas |
| `--pan2` | `#0d141b` | Cabeceras de tabla, inputs, tarjetas anidadas |
| `--lin` | `#1d2833` | Bordes y separadores |
| `--tx` | `#dce6f0` | Texto principal |
| `--dim` | `#7e91a5` | Texto secundario y rótulos |
| `--ac` | `#5ee39a` | Acento: renta, primario, foco |
| `--ac2` | `#f2b13c` | Atención: amortizaciones, desvíos, dividendos estimados |
| `--neg` | `#ff6b6b` | Negativo, prohibiciones, meses sin cobro |
| `--pos` | `#5ee39a` | Positivo |
| `--sd` | `#516373` | Silueta, balances, elementos apagados |

### Colores — tema claro

`--bg #f2f4f7` · `--pan #ffffff` · `--pan2 #eef1f5` · `--lin #d5dce4` · `--tx #182430` · `--dim #61717f` · `--ac #0e8a55` · `--ac2 #a86a06` · `--neg #c0392b` · `--pos #0e8a55` · `--sd #94a4b4`

Fondos de selección: oscuro `rgba(94,227,154,.07–.10)`, claro `rgba(14,138,85,.06–.08)`.

### Desviación aprobada — paleta categórica (Etapa 1 del rediseño del armador, 09/08/2026)

Esta spec no define una paleta para distinguir tramos entre sí dentro de una misma distribución
(sector, clase, calificación...): en la implementación original todos compartían `--ac`, y con
seis-más distribuciones en pantalla el verde dejó de significar nada. Se agregaron seis tokens
más, sin tocar la semántica de los once de arriba:

| Token | Oscuro | Claro | Uso |
|---|---|---|---|
| `--cat1` | `#5c9de5` | `#2e6db4` | Distribución categórica, tramo 1 (azul) |
| `--cat2` | `#46c2b4` | `#0e8177` | tramo 2 (teal) |
| `--cat3` | `#a08df0` | `#6d4fc4` | tramo 3 (violeta) |
| `--cat4` | `#7e93a8` | `#566b7e` | tramo 4 (acero) |
| `--cat5` | `#7379e8` | `#4550b4` | tramo 5 (índigo) |
| `--cat6` | `#b98bd6` | `#8a4fa8` | tramo 6 (malva) |
| `--medida` | `= --cat1` | `= --cat1` | Barra que mide contra una escala (no reparte una composición) — duración, percentiles, topes |

`--ac`/`--pos` quedan reservados a renta, positivo y selección/interacción; `--ac2` a advertencia;
`--neg` a excedido/prohibición. `.rotulo` pasó de `--ac` a `--dim` — el rótulo de un panel no es
ninguna de las cuatro cosas de arriba, y con acento en cada título el verde no distinguía nada.

### Tipografía

- **Texto**: `ui-sans-serif, system-ui, "Helvetica Neue", sans-serif`, `-webkit-font-smoothing: antialiased`. Si el codebase tiene una grotesca propia, usarla.
- **Números, tickers y montos**: `ui-monospace, "SF Mono", Menlo, Consolas, monospace`. **Todo dato numérico va en mono y alineado a la derecha** — es lo que hace legible una tabla densa.
- Escala: 9 px rótulos micro · 10 px rótulos mayúsculas (`letter-spacing: .10–.13em`) · 10,5–11 px metadatos · 11,5–12,5 px texto de tabla · 13,5 px base · 14–15 px títulos de panel · 17 px marca · 21 px KPI chico · 25–28 px KPI de seguimiento · 36 px renta anual.
- `text-wrap: pretty` en todo texto en prosa.

### Espaciado, radios, sombras

- Escala de espaciado: 2 · 3 · 4 · 5 · 6 · 7 · 8 · 9 · 10 · 11 · 12 · 14 · 16 · 18 · 20 px.
- Padding de panel: 12–16 px. Padding de fila de tabla: 6–8 px vertical, 12–13 px horizontal. `gap` entre paneles: 10–14 px.
- Radios: 2 px (chips de calendario), 3 px (botones, inputs, tarjetas anidadas), 4 px (paneles), 12 px (chips de mandato), 50% (punto de vivo).
- Sombras: sólo el drawer (`-16px 0 40px rgba(0,0,0,.35)`). El resto se separa por color de fondo y borde de 1 px.
- Bordes: siempre 1 px `--lin`. Acento: borde izquierdo de 3 px en paneles destacados, borde inferior de 2 px en pestañas activas.

### Formato de números (es-AR)

Coma decimal y punto de miles. `US$ 5.264,50` · `$ 88.400` · `7,27%` · `12,9 MM` para volúmenes. Montos de flujo mensual sin decimales; precios con dos; porcentajes con uno o dos según el campo. Datos faltantes: `s/d`. No aplicables: `no aplica`.

## Assets

Ninguno. No hay imágenes, iconos ni fuentes externas: los prototipos son autocontenidos y usan caracteres tipográficos (`☾ ☀ ✓ ✗ ✕ ⧉ ▲ ▼ ● Σ ×`) y formas CSS (rombos = cuadrados rotados 45°). Si el codebase tiene set de iconos, reemplazarlos por los equivalentes.

## Files

| Archivo | Qué es |
|---|---|
| `1 Cordillera v2.dc.html` | **Diseño principal.** Armado + Seguimiento + drawer de ficha |
| `datos.js` | Universo de instrumentos de ejemplo, motor de cálculo (`resolver`), `puntasDe`, formateadores es-AR, clientes y carteras de ejemplo |
| `support.js` | Runtime del prototipo. **No portar** |
| `referencia/1 Cordillera v1.dc.html` | Primera versión, sin mandato ni seguimiento. Sólo referencia |
| `referencia/0 Comparación y recomendación.dc.html` | Las cinco direcciones de diseño exploradas y por qué se eligió esta |

Para abrir los archivos de `referencia/` hay que copiar ahí `datos.js` y `support.js`.

Los prototipos completos (`.dc.html`, `datos.js`, `support.js`) quedaron en
`referencia/diseno-cordillera/` de este repo.
