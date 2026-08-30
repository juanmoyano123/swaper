# Instrucciones para el Agente

Este proyecto construye **10-Swaper**: una aplicación web para que asesores financieros de
una ALyC argentina armen carteras de renta fija y variable, y optimicen las que sus clientes
ya tienen. Leé `README.md` para el estado y `claude-docs/planning/product-definition.md` para
qué se está construyendo.

## Cómo se trabaja acá

El proyecto sigue un **pipeline de producto por fases**, y cada fase deja un archivo que la
siguiente consume. Los archivos viven en `claude-docs/` — **ese nombre no se cambia**, porque
los comandos `/create-prd`, `/build-feature`, `/init-project` y `/status` lo tienen fijo.

```
-1  /shape-idea       → planning/idea-brief.md
 0  /research-market  → planning/market-research.md        (opcional)
1A  /define-product   → planning/product-definition.md
1B  /validate-idea    → planning/validacion.md             (alternativa a 1A)
 2  /create-prd       → planning/plan.md                   features con RICE
 3  Claude Design     → planning/design-system.md          fuera de la terminal
 4  /init-project     → estructura del repo + progress/PROGRESS.md
 5  /build-feature    → plans/F-XXX-plan.md → código
```

No saltear fases ni adelantarse: cada comando valida que exista el output de la anterior.

Hasta la Fase 4 el motor sigue siendo Python de línea de comandos en `tools/`. Después pasa a
ser el backend de la aplicación. Qué se reusa, qué se envuelve y qué se reescribe está
definido en `product-definition.md`, sección "Rol del motor existente".

## Reglas del dominio — no se revierten

Son restricciones del negocio, no preferencias. Salieron de errores reales; el porqué de cada
una está en `docs/ESTADO.md` y en `docs/historial/`.

1. **Nunca inventar un dato.** Si falta, se deja vacío y se alerta con nombre y apellido. No
   se estima, no se infiere del ticker, no se completa por analogía. *Antecedente: una vez
   traduje un código de la fuente como "Ley Inglesa" —categoría que no existe— y otra vez
   derivé 121 tickers inexistentes cortando strings. Las dos veces hubo que revertir.*

2. **Los rendimientos de distinta naturaleza no se promedian ni comparten eje.** Una TIR en
   dólares, una tasa real sobre CER y una TNA nominal en pesos son unidades distintas. Se
   reportan abiertos por naturaleza de tasa, siempre.

3. **Nada se compara entre monedas sin normalizar.** Precio y volumen vienen en la moneda de
   cotización de cada especie. El tipo de cambio se deriva del propio universo —la misma
   emisión cotiza en pesos y en dólares, y ese cociente es el MEP—, nunca de una fuente
   externa. BYMA publica su Índice Dólar: sirve de contraste, no de fuente.

4. **El riesgo soberano se agrupa aparte.** El Tesoro emite bajo muchos prefijos (GD, AE, DIC,
   TZX, TY3) y todos son el mismo crédito: clave única `SOBERANO_AR` con tope propio. Sin
   esto una cartera 100% soberana pasaba como diversificada.

5. **El calendario de cupones es criterio de armado, no reporte.** *"La predecibilidad del
   cashflow es la piedra fundamental sobre la que fomentamos la inversión en bonos."*

6. **La lógica de análisis es determinística, sin IA.** *"No busco algo que razone, sino que
   analice datos y me devuelva un análisis de datos duros."*

7. **El riesgo no es un número, es un vector de seis ejes** —duración, crédito, legislación,
   liquidez, concentración y moneda—. No se construye un score compuesto: exigiría ponderar
   años contra una calificación que sólo existe para el 39% del universo, y eso sería un
   juicio inventado presentado como dato.

8. **Nunca se propone una mejora de TIR sin nombrar qué riesgo se asume a cambio.**

9. **No se filtra por disponibilidad en Balanz.** Se da por sentado que todo lo negociable
   está. No reintroducir esa whitelist.

10. **El proyecto no se conecta al monitor de mesa** (`mesaifa.netlify.app`) ni a su base de
    datos, en ninguna forma. Se usa como referencia visual y para contrastar números
    publicados contra los nuestros, nada más.

11. **No se supone ni se infiere nada en la representación de datos.** Todo lo que se muestra
    sale de una fuente oficial, tal como la fuente lo declara. Si un dato existe pero no
    estamos seguros de cómo interpretarlo, **el espacio va en blanco** y el faltante se
    declara. Nunca se muestra la interpretación en lugar del dato. Aplica a toda
    representación de datos —monitor, armador, ficha, exportes, informes—, no sólo al monitor.

    La línea práctica: un código estándar se lee (`USD` y `ARS` son ISO 4217 y significan lo
    que significan); un **código propietario de la fuente no se traduce sin una fuente que lo
    confirme**. `denominationCcy` de BYMA vale `ARS`, `USD` y `EXT`, y BYMA no publica en ningún
    lado qué es `EXT`. Medir una coincidencia de precio no es tener una fuente — pero una
    confirmación del dueño del producto sí lo es: **30/08/2026, confirmado, `USD` es liquidación
    MEP y `EXT` es liquidación cable**, la misma distinción que ya usa renta variable con el
    sufijo del ticker (`D`=MEP, `C`=cable). Desde esa fecha `EXT` se sigue mostrando como `EXT`
    en pantalla (regla 11 sigue vigente: no se traduce el código), pero los cálculos
    determinísticos que sólo necesitaban saber "esto es dólares" —como la TIR de un bono
    hard-dollar contra su propio precio— ya pueden usar una fila `EXT` igual que usan una `USD`,
    sin mezclar el precio de una especie con el de su hermana. Cualquier interpretación de `EXT`
    que no sea "dólares por cable" sigue sin fuente y sigue yendo vacía.

    Un cálculo determinístico sobre datos duros **no es una inferencia**: la TIR que sale de
    resolver el cronograma contractual contra el precio publicado es aritmética, y se muestra.
    Lo que la regla prohíbe es rellenar el hueco entre lo que la fuente dice y lo que
    necesitamos que diga.

## Sobre datos y archivos

- **Los secretos van en `.env`**, nunca en otro lado.
- **`data/condiciones_emision.csv` es dato curado**: 823 tickers con ley, moneda de pago,
  lámina, calificación, sector y emisor. No tiene fuente de origen viva — se rescató del
  universo consolidado después de que se borraran los CSV originales. Tratarlo como
  irrecuperable.
- **`data/output/` es regenerable**, salvo `universo_consolidado.xlsx` y
  `cashflow_completo.csv`, que están versionados a propósito.
- **El cronograma de pagos no tiene fuente viva y no se regenera.** Docta era la única fuente
  que lo publicaba y se dio de baja el 12/08/2026 porque es paga. El flujo contractual sale de
  la tabla `public.cashflow`, que quedó persistida, y de `data/output/cashflow_completo.csv`.
  Un cronograma es contractual y no envejece, así que reusarlo no es mostrar un dato viejo como
  nuevo — pero **el conjunto está cerrado**: una emisión que empiece a cotizar de ahora en más
  entra sin cronograma, sin `tipo_tasa` y sin métricas propias, y eso se declara faltante. No se
  proyecta el calendario desde la estructura del cupón de IAMC: funcionaría para los bullets de
  cupón fijo y fallaría en los amortizing con escalera, que son mayoría entre las ONs locales.
  **Nunca vaciar ni truncar esas dos fuentes de cronograma.**
- **No correr `tools/consolidar_universo.py`** hasta que el ingestor se reescriba: hoy
  sobrescribiría el universo dejando vacías las columnas de condiciones.
- **El consumo de IAMC está pausado desde el 13/08/2026** (`IAMC_HABILITADO`, default `false`). El
  informe llegaba por subida manual y envejecía sin que nada lo declarara —el cargado en producción
  tenía ocho días—, así que el universo mostraba una TIR vieja al lado de un precio de hoy. La
  pausa corta dos cosas: la lectura del informe **y el arrastre de las métricas ya guardadas**; sin
  lo segundo la TIR vieja se seguiría publicando y la pausa no serviría de nada. **El código quedó
  entero** —parser, almacén y `POST /iamc/informe`— y prender la variable devuelve el
  comportamiento anterior. Se retoma en Stage 2 con descarga automática, ya verificada viable
  contra `iamc.com.ar`. Lo que se pierde: 35 emisiones con rendimiento (de 283 a 248), la
  convexidad y el valor residual. Lo que **no** se pierde: ley, moneda de pago, emisor y estructura
  de cupón ya escritos, porque el upsert los protege con COALESCE y son atributos de la emisión que
  no envejecen.
- **Datos de clientes reales nunca entran al repositorio.** Van a `~/Documents/IFA-confidencial/`.

## Estructura del repo (desde Fase 4)

```
10-Swaper/
├── frontend/           React 19 + Vite + TypeScript + Tailwind v4
├── backend/            FastAPI + Python 3.12, venv local en backend/venv
├── tools/              motor Python de línea de comandos (pre-Fase 4)
├── data/                condiciones_emision.csv (curado) + output/ (regenerable)
├── claude-docs/         pipeline de producto: planning, plans, progress, qa, deploys
├── referencia/           incluye diseno-cordillera/ (prototipos de Fase 3, no producción)
├── docs/                ESTADO.md + historial de decisiones
└── workflows/            SOPs operativos del motor de línea de comandos
```

## Comandos útiles

```
# Frontend
cd frontend && npm run dev      # http://localhost:5173
cd frontend && npm run build

# Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload   # http://localhost:8000/api/v1/health

# Motor (pre-Fase 4, sigue vigente)
python3 tools/armar_cartera.py --monto 100000
```

## Antes de escalar de modelo

Avisar antes de pasar a Fable u Opus.
