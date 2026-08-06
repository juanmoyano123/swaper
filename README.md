# 10-Swaper — Herramienta de Renta Fija

Herramienta de análisis y automatización enfocada **exclusivamente en renta fija** (bonos soberanos, subsoberanos y Obligaciones Negociables del mercado argentino). Acciones, CEDEARs, FCI y opciones están fuera de alcance.

Construida con el framework WAT (Workflows/Agents/Tools) — ver `CLAUDE.md`.

**Para retomar el trabajo en una sesión nueva: leer `ESTADO.md`** — tiene el estado completo, las decisiones tomadas y los pendientes.

## Dos pilares

### 1. Armador de Carteras
Construye una propuesta de cartera de renta fija según el perfil/objetivo del cliente (monto, moneda, horizonte, apetito de riesgo o necesidad de cobertura específica), **priorizando la continuidad del cobro mensual de cupones**.

`tools/armar_cartera.py` — construido y verificado sobre el universo real.

### 2. Buscador de Swaps
Detecta bonos con TIR baja o negativa y propone rotaciones hacia alternativas de mejor rendimiento a igual o menor riesgo (mismo emisor, mejor moneda de pago, mejor ley), **avisando si el bono a vender cobra cupón pronto**.

`tools/detectar_swaps.py` — construido y validado.

## Base de datos común

Ambos pilares se alimentan del mismo universo consolidado:

```
tools/consolidar_universo.py  →  data/output/universo_consolidado.xlsx
```

Ingesta 100% vía API de Docta (`.env`), sin descarga manual. Ver `workflows/consolidar_universo.md`.

## Análisis de cupones (integrado)

`tools/cupones.py` — módulo compartido por ambos pilares. La previsibilidad del cashflow es la base de la inversión en renta fija, así que el calendario de cobros no es un reporte posterior sino criterio de armado.

- **Armador de Carteras**: prioriza cubrir los 12 meses (desempata candidatos de rendimiento parejo por mes de cobro descubierto, dentro de una banda de 0,5pp). Hoja `Calendario` con renta y amortización mes a mes. Se desactiva con `--sin-pago-mensual`.
- **Buscador de Swaps**: avisa si el bono a vender cobra cupón dentro de los próximos N días (`--dias-cupon`, default 45) y cuánto del capital se resigna. No bloquea el swap, lo señala.

**Cómo se calcula**: `lastPrice` del universo viene en monedas mezcladas (la misma emisión cotiza en pesos sin sufijo y en dólares con sufijo D/C), así que el cobro se normaliza contra paridad y valor técnico — `cobro/monto = cash_flow / (paridad × valor_técnico)` — que es adimensional. Validado contra `cartera de inversion/Propuesta Base 7-26.xlsx`: reproduce exacto los nominales de RUCED, SBC2D, CS47D y LOC5D.

**Limitación**: en bonos ajustables (CER, dólar linked, Badlar, Tamar) el calendario proyecta con el coeficiente de ajuste de hoy; el monto nominal futuro va a diferir.

## Historial de diseño

`procesos-en-diseño/2026-07-busqueda-instrumentos-swap-carteras/` — mapeo del proceso, priorización y specs de cada pieza, siguiendo el skill `automation-design-skill`.
