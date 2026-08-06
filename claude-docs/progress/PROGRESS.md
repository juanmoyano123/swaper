# Progreso — 10-Swaper

Generado desde `claude-docs/planning/plan.md` (Fase 2) al correr `/init-project`.
Estado inicial: las 50 features arrancan en **pendiente**. Este archivo se actualiza a mano o
desde `/build-feature` a medida que cada una se implementa.

## Ciclo 1 — Cimientos e ingesta (12 features · ~9,5 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-001 | Esqueleto de servicio backend | Foundation | 400,0 | completada |
| F-002 | Esquema de datos y migraciones | Foundation | 300,0 | completada |
| F-003 | Esqueleto de aplicación frontend | Foundation | 400,0 | completada |
| F-004 | Cliente de la API abierta de BYMA | Stage 1 | 300,0 | completada |
| F-005 | Parser del informe diario de IAMC | Stage 1 | 50,0 | completada |
| F-006 | Cliente del feed de cashflow de Docta | Stage 1 | 240,0 | completada |
| F-007 | Consolidador multi-fuente | Stage 1 | 160,0 | pendiente |
| F-008 | Job programado de ingesta | Stage 1 | 266,7 | pendiente |
| F-009 | condiciones_emision: semilla y herencia | Stage 1 | 200,0 | pendiente |
| F-010 | Sanidad del dato en dos capas | Stage 1 | 400,0 | pendiente |
| F-011 | Deduplicación de especies | Stage 1 | 400,0 | pendiente |
| F-012 | Tipo de cambio implícito y normalización | Stage 1 | 266,7 | pendiente |

> Milestone 1 — "El universo existe y es confiable."

## Ciclo 2 — Armador completo (12 features · ~11 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-013 | Barra de estado del dato | Stage 1 | 200,0 | pendiente |
| F-014 | Autenticación y aislamiento por asesor | Stage 1 | 200,0 | pendiente |
| F-015 | API del calendario de doce meses | Stage 1 | 285,0 | pendiente |
| F-016 | Grilla-selector de doce meses | Stage 1 | 114,0 | pendiente |
| F-017 | Filtros de la grilla | Stage 1 | 112,0 | pendiente |
| F-018 | Cartera editable y ponderación | Stage 1 | 140,0 | pendiente |
| F-019 | Armado asistido | Stage 1 | 100,0 | pendiente |
| F-020 | Límites de concentración en vivo | Stage 1 | 233,3 | pendiente |
| F-021 | Panel de renta y renta anual | Stage 1 | 285,0 | pendiente |
| F-022 | Rendimientos por naturaleza y plazo | Stage 1 | 175,0 | pendiente |
| F-023 | Composición y curva TIR/duración | Stage 1 | 48,0 | pendiente |
| F-024 | Redondeo por lámina y diferencia | Stage 1 | 200,0 | pendiente |

> Milestone 2 — "Un asesor arma una cartera desde el calendario y se lleva el número a la
> reunión." Depende de `claude-docs/planning/design-system.md` (Fase 3, ya bajado).

## Ciclo 3 — Renta variable, carga y diagnóstico (9 features · ~8 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-025 | Carga asistida de lámina | Stage 1 | 53,3 | pendiente |
| F-026 | Bloque de renta variable | Stage 1 | 96,0 | pendiente |
| F-027 | Calendario de balances | Stage 1 | 16,7 | pendiente |
| F-028 | Ingreso de cartera por tres vías | Stage 1 | 96,0 | pendiente |
| F-029 | Resolución de tickers | Stage 1 | 106,7 | pendiente |
| F-030 | Valuación y diagnóstico de cartera | Stage 1 | 150,0 | pendiente |
| F-031 | Vector de riesgo de seis ejes | Stage 1 | 100,0 | pendiente |
| F-032 | Motor de rotaciones intra-segmento | Stage 1 | 100,0 | pendiente |
| F-035 | Costo real de rotar y cupón próximo | Stage 1 | 180,0 | pendiente |

> Milestone 3 — "El diagnóstico de una cartera ajena tarda minutos y no horas."

## Ciclo 4 — Optimizador, monitor y persistencia (9 features · ~8,5 semanas)

| ID | Feature | Etiqueta | RICE | Estado |
|---|---|---|---|---|
| F-033 | Modo bajar riesgo | Stage 1 | 57,6 | pendiente |
| F-034 | Modo subir TIR con contrapartida | Stage 1 | 86,4 | pendiente |
| F-036 | Aceptación rotación por rotación | Stage 1 | 57,6 | pendiente |
| F-037 | Comparación original contra propuesta | Stage 1 | 72,0 | pendiente |
| F-038 | Monitor de mercado | Stage 1 | 106,7 | pendiente |
| F-039 | Ficha de instrumento | Stage 1 | 112,0 | pendiente |
| F-040 | Sensibilidad por repricing completo | Stage 1 | 66,7 | pendiente |
| F-041 | Guardar, listar, reabrir y revaluar | Stage 1 | 180,0 | pendiente |
| F-042 | Exportación a Excel y PDF | Stage 1 | 100,0 | pendiente |

> Milestone 4 — "Stage 1 completo: los tres flujos cierran."

## Stage 2 — se activa después de validar con usuarios reales (8 features · ~14,5 semanas)

| ID | Feature | RICE | Estado |
|---|---|---|---|
| F-043 | Gestión de clientes y CRM | 20,0 | pendiente |
| F-044 | Historial de propuestas | 25,0 | pendiente |
| F-045 | Colocaciones primarias | 15,0 | pendiente |
| F-046 | FCI con fuente | 8,3 | pendiente |
| F-047 | Opciones | 4,0 | pendiente |
| F-048 | Alertas y notificaciones | 40,0 | pendiente |
| F-049 | Comparación de carteras entre sí | 40,0 | pendiente |
| F-050 | API Market Data oficial de BYMA | 80,0 | pendiente |

## Totales

| Ciclo | Features | Person-days | Semanas (est.) | Acumulado |
|---|---|---|---|---|
| 1 — Cimientos e ingesta | 12 | 47 | ~9,5 | ~9,5 |
| 2 — Armador completo | 12 | 55 | ~11 | ~20,5 |
| 3 — RV, carga y diagnóstico | 9 | 41 | ~8 | ~28,5 |
| 4 — Optimizador y persistencia | 9 | 42 | ~8,5 | ~37 |
| **Stage 1** | **42** | **185** | **~37 semanas** | |
| Stage 2 | 8 | 72 | ~14,5 | |

Siguiente paso: **F-007** (consolidador multi-fuente), que une lo que traen F-004, F-005 y F-006 en
las tablas de mercado con precedencia declarada por campo. Es lo que finalmente puebla la base y
destraba el resto del Ciclo 1. En paralelo se pueden tomar `F-014` (auth) y `F-028` (ingreso de
cartera), que dependen solo del frontend.
