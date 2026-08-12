/**
 * El contrato de `GET /api/v1/calendario/universo?detalle=true` y de `POST /api/v1/calendario/
 * cartera?detalle=true` — F-015/F-016/F-021. Los dos endpoints comparten el mismo shape de
 * respuesta (`backend/app/calendario/grilla.py`), así que un solo esquema sirve para las dos
 * pantallas que lo consumen.
 *
 * Movido acá en la Tanda 11 desde `features/armador/lib/schema.ts`, para que el diagnóstico de
 * cartera (F-030) lea el mismo contrato que el armador en vez de duplicarlo (riesgo R12).
 *
 * ## Desvío contra el plan original: las alertas no llevan `origen`
 *
 * `Alerta.como_dict()` en `backend/app/ingesta/alertas.py` no serializa `origen` — ese campo lo
 * agrega `backend/app/estado/servicio.py::_serializada`, específico de `/api/v1/estado-del-dato`.
 * `backend/app/calendario/servicio.py` arma las alertas con `Alerta.como_dict()` directo, sin
 * pasar por esa función. Por eso acá hay un esquema de alerta propio, sin `origen`.
 */

import { z } from 'zod'

export const esquemaSeveridadCalendario = z.enum(['error', 'advertencia', 'info'])

/** Una alerta del calendario, con el contrato real de `Alerta.como_dict()` — ver nota del módulo. */
export const esquemaAlertaCalendario = z.object({
  codigo: z.string(),
  mensaje: z.string(),
  severidad: esquemaSeveridadCalendario,
  accion_requerida: z.string().nullable(),
  detalle: z.record(z.string(), z.unknown()),
})

/** Lo que un instrumento paga en un mes de la grilla. */
export const esquemaInstrumentoDelMes = z.object({
  ticker: z.string(),
  emision: z.string(),
  fechas: z.array(z.string()),
  /** Renta del mes como fracción del monto invertido (0,0075 = 0,75%). */
  pct_renta: z.number(),
  pct_amortizacion: z.number(),
  /** Sin montos en la vista universo: siempre `null` en ese caso. */
  renta: z.number().nullable(),
  amortizacion: z.number().nullable(),
  moneda: z.string(),
  /** En la unidad de su segmento (TIR USD, TNA $, tasa real CER...). `null` cuando la fuente no
   *  publicó el número: no se estima, se muestra `s/d`. */
  rendimiento: z.number().nullable(),
  naturaleza: z.string(),
  naturaleza_nombre: z.string(),
  vencimiento: z.string().nullable(),
})

/** Un mes de la grilla, presente aunque no pague nadie. */
export const esquemaMesDelCalendario = z.object({
  anio: z.number(),
  mes: z.number(),
  etiqueta: z.string(),
  nombre: z.string(),
  con_renta: z.number(),
  con_amortizacion: z.number(),
  /** El mes que la grilla existe para encontrar: ningún instrumento del universo paga renta. */
  sin_renta: z.boolean(),
  /** Sin montos no hay totales que sumar entre instrumentos distintos: siempre `null` en ese caso. */
  renta: z.record(z.string(), z.number()).nullable(),
  amortizacion: z.record(z.string(), z.number()).nullable(),
  instrumentos: z.array(esquemaInstrumentoDelMes),
})

const esquemaFlujosResumen = z.object({
  evaluados: z.number(),
  con_flujos: z.number(),
  pagos: z.number(),
  sin_cronograma: z.number(),
  sin_paridad: z.number(),
  sin_paridad_que_cotizan: z.number(),
  vencidos: z.number(),
})

const esquemaResumenCalendario = z.object({
  hoy: z.string(),
  desde: z.string().nullable(),
  hasta: z.string().nullable(),
  con_montos: z.boolean(),
  monedas: z.array(z.string()),
  instrumentos: z.number(),
  meses_sin_renta: z.array(z.string()),
  renta_anual: z.record(z.string(), z.number()).nullable(),
  amortizacion_anual: z.record(z.string(), z.number()).nullable(),
  pendientes_este_mes: z.number(),
  flujos: esquemaFlujosResumen,
})

export const esquemaCalendarioUniverso = z.object({
  resumen: esquemaResumenCalendario,
  /** Siempre 12, sin paginar — ver el docstring de `backend/app/api/v1/calendario.py`. */
  meses: z.array(esquemaMesDelCalendario),
  alertas: z.array(esquemaAlertaCalendario),
})

export type SeveridadCalendario = z.infer<typeof esquemaSeveridadCalendario>
export type AlertaCalendario = z.infer<typeof esquemaAlertaCalendario>
export type InstrumentoDelMes = z.infer<typeof esquemaInstrumentoDelMes>
export type MesDelCalendario = z.infer<typeof esquemaMesDelCalendario>
export type CalendarioUniverso = z.infer<typeof esquemaCalendarioUniverso>
