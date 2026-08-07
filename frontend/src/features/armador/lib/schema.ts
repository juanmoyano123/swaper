/**
 * El contrato de GET /api/v1/calendario/universo?detalle=true — F-015/F-016.
 *
 * Se valida entero, como todo lo que entra por `apiFetch`: si el backend deja de mandar un campo,
 * esto falla fuerte en vez de dibujar una grilla a medias. La forma exacta sale de
 * `backend/app/calendario/grilla.py` (`Calendario.como_dict`, `MesDelCalendario.como_dict`,
 * `InstrumentoDelMes.como_dict`).
 *
 * ## Desvío contra el plan: las alertas no llevan `origen`
 *
 * El plan de esta feature copió el shape de alerta de F-013 (`estado-dato/lib/schema.ts`), que
 * incluye `origen`. Contra el código real no cierra: `Alerta.como_dict()` en
 * `backend/app/ingesta/alertas.py` **no** serializa `origen` — ese campo lo agrega
 * `backend/app/estado/servicio.py::_serializada`, y es específico de `/api/v1/estado-del-dato`.
 * `backend/app/calendario/servicio.py` arma las alertas del calendario con `Alerta.como_dict()`
 * directo, sin pasar por esa función. Por eso acá se define un esquema de alerta propio, sin
 * `origen`, en vez de reusar el de `estado-dato`.
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
  /** Sin montos en la vista universo: siempre `null` acá. Se deja tipado por si F-021/F-036
   *  reusan este esquema con `con_montos: true`. */
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
  /** Sin montos no hay totales que sumar entre instrumentos distintos: siempre `null` acá. */
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

/**
 * Contratos de F-018, agregados acá — no se importa el esquema de `features/monitor/`, que está
 * prohibido para este agente y además es un contrato ajeno a esta feature.
 */

/**
 * Una especie de `/api/v1/universo/emisiones/especies`, con el mismo shape que ya usa el monitor
 * (F-038) — es el mismo endpoint, no un contrato nuevo. Redefinido acá en vez de importado.
 */
export const esquemaEspecie = z.object({
  ticker: z.string(),
  emision: z.string(),
  sufijo_liquidacion: z.string().nullable(),
  clase_activo: z.string(),
  segmento: z.string(),
  naturaleza: z.string(),
  naturaleza_nombre: z.string(),
  rendimiento: z.number().nullable(),
  duracion: z.number().nullable(),
  vencimiento: z.string().nullable(),
  ley: z.string().nullable(),
  moneda_cupon: z.string().nullable(),
  emisor: z.string().nullable(),
  precio: z.number().nullable(),
  moneda_cotizacion: z.string().nullable(),
  volumen: z.number().nullable(),
  volumen_usd: z.number().nullable(),
  paridad: z.number().nullable(),
  /** Lámina mínima de la emisión, de `condiciones_emision` vía la base común de la tanda 8b.
   *  `null` = no informada: no se redondea y se declara (F-024, regla 1 del proyecto). */
  lamina: z.number().nullable(),
  /** Sector del emisor, del dato curado de F-009 vía la base común de la tanda 8b. `null` = no
   *  informado y agrupa aparte: no se le asigna uno por parecido con otro emisor (F-017). */
  sector: z.string().nullable(),
  dato_sano: z.boolean(),
  hermanas: z.array(z.string()),
})

export type Especie = z.infer<typeof esquemaEspecie>

/**
 * El tramo que este panel necesita de `GET /api/v1/universo/tipo-de-cambio` — sólo `valor` y
 * `disponible`. El backend manda más campos (dispersión, contraste, muestras de descarte); no
 * hace falta tipar los que esta pantalla no usa, mismo criterio que `estado-dato/lib/schema.ts`.
 */
export const esquemaTipoDeCambio = z.object({
  tipo_de_cambio: z.object({
    valor: z.number().nullable(),
    disponible: z.boolean(),
  }),
})

export type RespuestaTipoDeCambio = z.infer<typeof esquemaTipoDeCambio>
