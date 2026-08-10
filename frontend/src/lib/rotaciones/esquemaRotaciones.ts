/**
 * El contrato de `POST /api/v1/rotaciones` — F-032, consumido acá por F-033.
 *
 * La forma exacta sale de `backend/app/rotaciones/motor.py` (`Candidata.como_dict()`,
 * `_especie_como_dict()`) y `backend/app/rotaciones/servicio.py` (`ResultadoRotaciones.como_dict()`),
 * leídos directamente en vez de asumidos. Mismo criterio que `esquemaConcentracion.ts`: se valida
 * entero lo que se usa, todo lo demás lo tolera el modo strip por defecto de Zod.
 *
 * **Modo strip a propósito.** Cualquier clave no declarada, en cualquier nivel, se descarta en
 * silencio en vez de romper el contrato. `cupon` sigue sin declararse porque ninguno de los dos
 * modos lo usa todavía.
 *
 * **`costo` se declara desde F-034** (tanda 14). Lo agrega F-035 a cada candidata y viajaba
 * descartado desde entonces: la feature había quedado sin UI, así que el dato llegaba al browser
 * y se tiraba. El bloque es `nullable` y no `optional` porque el backend siempre emite la clave
 * (`motor.py`, `Candidata.como_dict()`) — emite `null` cuando el motor corre sin el servicio que
 * resuelve puntas, no omite el campo.
 */

import { z } from 'zod'

// Mismo shape que `esquemaAlertaConcentracion` de `esquemaConcentracion.ts`: `Alerta.como_dict()`
// del backend (`app/ingesta/alertas.py`) no tiene `origen`, y se redefine acá por la misma razón
// que allá (evitar un import cruzado entre dos contratos que documentan servicios distintos).
export const esquemaAlertaRotacion = z.object({
  codigo: z.string(),
  mensaje: z.string(),
  severidad: z.enum(['error', 'advertencia', 'info']),
  accion_requerida: z.string().nullable(),
  detalle: z.record(z.string(), z.unknown()),
})

/** `_especie_como_dict()`: sólo `ticker` y `emisor` nunca son `null`. */
export const esquemaEspecieRotacion = z.object({
  ticker: z.string(),
  emisor: z.string(),
  rendimiento: z.number().nullable(),
  duracion: z.number().nullable(),
  moneda_cupon: z.string().nullable(),
  ley: z.string().nullable(),
  calificacion: z.string().nullable(),
  lamina: z.number().nullable(),
  frecuencia_cupon: z.string().nullable(),
  volumen_usd: z.number().nullable(),
})

/**
 * `CostoRotacion.como_dict()` de `backend/app/rotaciones/costos.py` — F-035.
 *
 * `verificable` es `false` cuando falta una punta viva en alguna pata; ahí `total_pct`, `elevado`
 * y `payback_meses` viajan `null` en vez de calcularse sobre un supuesto. El arancel sí es siempre
 * un número (es una constante del broker, no un dato de mercado), así que no es nullable: lo único
 * que se puede afirmar sin puntas es ese piso, y se declara como piso.
 */
export const esquemaCostoRotacion = z.object({
  arancel_pct_por_pata: z.number(),
  spread_origen_pct: z.number().nullable(),
  spread_destino_pct: z.number().nullable(),
  total_pct: z.number().nullable(),
  verificable: z.boolean(),
  elevado: z.boolean().nullable(),
  payback_meses: z.number().nullable(),
})

export const esquemaCandidata = z.object({
  tipo: z.enum(['mejora_rendimiento', 'mejora_perfil']),
  segmento: z.string(),
  origen: esquemaEspecieRotacion,
  destino: esquemaEspecieRotacion,
  delta: z.object({
    rendimiento_pp: z.number(),
    duracion: z.number().nullable(),
  }),
  flags: z.object({
    mismo_emisor: z.boolean(),
    pasa_a_cable: z.boolean(),
    mejora_ley: z.boolean(),
    empeora_ley: z.boolean(),
    mejora_volumen: z.boolean(),
    posible_distress: z.boolean(),
  }),
  premio_ley: z
    .object({
      bps: z.number().nullable(),
      vs_mediana_bps: z.number().nullable(),
    })
    .nullable(),
  riesgo_nota: z.string(),
  costo: esquemaCostoRotacion.nullable(),
})

export const esquemaRotaciones = z.object({
  perfil: z.string(),
  candidatas: z.array(esquemaCandidata),
  origenes_evaluados: z.array(z.string()),
  fuera_del_universo: z.array(z.string()),
  sin_rendimiento: z.array(z.string()),
  alertas: z.array(esquemaAlertaRotacion),
})

export type AlertaRotacion = z.infer<typeof esquemaAlertaRotacion>
export type CostoRotacion = z.infer<typeof esquemaCostoRotacion>
export type EspecieRotacion = z.infer<typeof esquemaEspecieRotacion>
export type Candidata = z.infer<typeof esquemaCandidata>
export type ResultadoRotaciones = z.infer<typeof esquemaRotaciones>
