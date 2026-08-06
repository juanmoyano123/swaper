# 10-Swaper — Armador y Optimizador de Carteras

Herramienta web para asesores financieros de una ALyC argentina: arman carteras de renta
fija y variable a medida del objetivo del cliente, y optimizan las que el cliente ya trae.

**El calendario de cupones es el selector, no el reporte.** El asesor ve los doce meses del
año con los papeles que pagan en cada uno y elige desde el mes que necesita cubrir. Mientras
arma, ve en vivo la renta mes a mes en plata real y el total anual de cupones sobre lo
invertido — el número que lleva a la reunión. Esa mecánica es la razón de ser del producto.

## Estado

El producto está en diseño. El **motor de cálculo financiero ya está construido y
verificado**; lo que falta es la aplicación alrededor.

| Fase | Qué produce | Estado |
|---|---|---|
| −1 `/shape-idea` | `claude-docs/planning/idea-brief.md` | Hecha |
| 1A `/define-product` | `claude-docs/planning/product-definition.md` | Hecha |
| 2 `/create-prd` | `claude-docs/planning/plan.md` — features con RICE | Siguiente |
| 3 Claude Design | `claude-docs/planning/design-system.md` | Prompt listo |
| 4 `/init-project` | Estructura del repo | Pendiente |
| 5 `/build-feature` | Código | Pendiente |

**Empezá por `claude-docs/planning/product-definition.md`**: tiene las 13 features del MVP,
el stack, los flujos y qué se reusa del motor existente.

## Alcance

Renta fija argentina —soberanos, subsoberanos y obligaciones negociables, en los seis
segmentos de tasa— **y renta variable**: acciones locales y CEDEARs, con el calendario de
presentación de balances como equivalente del cupón.

Las dos familias conviven pero **no se mezclan**: una acción no tiene TIR, ni duración, ni
cashflow, así que no es comparable con un bono. Los FCI y las opciones quedan fuera.

La gestión de clientes (CRM) es una segunda etapa. Se guardan carteras, no clientes.

## Estructura

```
claude-docs/planning/   El pipeline de producto. No renombrar: los comandos lo tienen fijo
docs/                   ESTADO.md — qué se verificó y contra qué
docs/historial/         El diseño WAT de julio, congelado. Explica el porqué de cada regla
tools/                  El motor de cálculo, 8 módulos Python
workflows/              SOPs operativos de cada herramienta
data/                   condiciones_emision.csv (curado) + output/ (regenerable)
referencia/             Los entregables de la mesa que sirven de molde, y el monitor actual
fuentes/                Muestras de los informes que alimentan el universo
```

## El motor hoy

Corre por línea de comandos y sigue siendo la única forma de producir carteras:

```bash
python3 tools/armar_cartera.py --monto 100000
python3 tools/detectar_swaps.py
```

**No corras `tools/consolidar_universo.py`.** Fusiona condiciones desde un CSV que ya no
existe, así que sobrescribiría `data/output/universo_consolidado.xlsx` dejando vacías las
columnas de ley, moneda de pago, lámina, calificación y sector. El ingestor se reescribe
contra BYMA e IAMC; hasta entonces, ese archivo se deja quieto.

## De dónde salen los datos

Tres fuentes que se complementan sin superponerse, y se unen por la raíz del ticker —porque
ley, moneda de pago y estructura son atributos de la emisión, no de la especie:

- **BYMA**, API abierta sin token (`open.bymadata.com.ar`): precios, puntas bid/ask con
  cantidad, volumen, moneda de cotización declarada, las tres especies y los dos plazos de
  liquidación. 20 minutos de demora; el tiempo real se pide a `marketdata@byma.com.ar`.
- **IAMC**, informe diario de deuda corporativa: emisor, ley, moneda de pago, estructura del
  cupón, TIR, duración modificada, convexidad, próximos pagos.
- **Docta** (doctacapital), sólo el cronograma completo de pagos: es el único que lo publica,
  con 97% de cobertura, y sin él la grilla de doce meses no existe.

## Reglas del dominio

Están en `CLAUDE.md` y no se revierten. Las dos que más se rompen sin querer:

1. **Los rendimientos de distinta naturaleza no se promedian ni comparten eje.** Una TIR en
   dólares, una tasa real sobre CER y una TNA en pesos son unidades distintas.
2. **Cuando falta un dato, se muestra que falta.** Nunca se estima ni se infiere.
