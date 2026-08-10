/**
 * El snapshot que F-041 congela en `carteras.snapshot` (jsonb) al guardar una cartera.
 *
 * Dos formas, unidas por `origen` — la cartera cargada (F-028→F-037) y el armador (F-016→F-018)
 * producen estados distintos y no hay forma honesta de forzarlos a una tabla común sin adivinar
 * columnas (mismo criterio que el comentario original de `propuestas.payload`). `version: 1` deja
 * lugar a migrar la forma del snapshot sin tocar las filas ya guardadas: una fila con una versión
 * que este archivo no sabe leer se declara "no se pudo leer el snapshot" en vez de romper.
 *
 * **`z.strictObject` en todos los niveles propios (GWT-4).** Una cartera guardada no puede llevar
 * ningún campo de identificación de cliente; en vez de confiar en que nadie agregue uno "total, ya
 * que estamos", cualquier clave no declarada acá hace fallar el parseo. `esquemaCandidata` (F-032)
 * es la única excepción —viaja en modo `strip`, documentado y auditado en su propio archivo— y sus
 * campos son enteramente datos de mercado (ticker, rendimiento, ley, emisor): no hay dónde esconder
 * un dato de cliente adentro.
 */

import { z } from 'zod'

import { esquemaCandidata } from '@/lib/rotaciones/esquemaRotaciones'

export const esquemaMoneda = z.enum(['usd', 'ars'])

const esquemaClasePosicion = z.enum(['renta_fija', 'renta_variable', 'fci'])

const esquemaPerfil = z.enum(['conservador', 'moderado', 'agresivo'])

// --- Origen A: cartera cargada -------------------------------------------------------------------

const esquemaPosicionCrudaGuardada = z.strictObject({
  id: z.string(),
  fila: z.number(),
  tickerDeclarado: z.string(),
  nominal: z.number().nullable(),
  monto: z.number().nullable(),
  valida: z.boolean(),
  motivo: z.string().nullable(),
})

const esquemaValuadaGuardada = z.strictObject({
  ticker: z.string(),
  /** `null` cuando la especie no declaraba una moneda de cotización reconocida (regla 1). */
  moneda: esquemaMoneda.nullable(),
  invertido: z.number(),
  invertidoUsd: z.number(),
  pesoReal: z.number(),
})

const esquemaExcluidaGuardada = z.strictObject({
  id: z.string(),
  motivo: z.enum(['no_resuelta', 'sin_nominal', 'sin_precio', 'sin_tipo_de_cambio']),
  montoDeclarado: z.number().nullable(),
})

export const esquemaSnapshotCargada = z.strictObject({
  version: z.literal(1),
  origen: z.literal('cargada'),
  tipoDeCambio: z.number().nullable(),
  perfil: esquemaPerfil,
  /** Lo crudo, inválidas incluidas: es lo que `useCarteraCargadaValuada` necesita para revaluar. */
  posiciones: z.array(esquemaPosicionCrudaGuardada),
  /** La capa de precios, congelada al momento de guardar (GWT-1). */
  valuadas: z.array(esquemaValuadaGuardada),
  excluidas: z.array(esquemaExcluidaGuardada),
  totalInvertidoUsd: z.number(),
  plan: z.strictObject({
    aceptadas: z.array(esquemaCandidata),
    descartadas: z.array(z.string()),
  }),
})

// --- Origen B: armador -------------------------------------------------------------------------

const esquemaResueltaGuardada = z.strictObject({
  ticker: z.string(),
  clase: esquemaClasePosicion,
  peso: z.number(),
  moneda: esquemaMoneda.nullable(),
  /** El precio del momento: es lo que permite reproducir la propuesta tal como se presentó. */
  precio: z.number().nullable(),
  /** Renta fija y FCI. `null` en renta variable. */
  vn: z.number().nullable(),
  /** Renta variable, unidades enteras. `null` en renta fija y FCI. */
  cantidad: z.number().nullable(),
  invertido: z.number().nullable(),
  invertidoUsd: z.number().nullable(),
})

export const esquemaSnapshotArmador = z.strictObject({
  version: z.literal(1),
  origen: z.literal('armador'),
  tipoDeCambio: z.number().nullable(),
  /** El capital objetivo que el asesor cargó (`useArmador().montoTotal`), no lo efectivamente
   *  invertido — la lámina y las posiciones sin precio pueden dejarlos distintos. */
  montoTotalUsd: z.number(),
  /** El mandato: lo que hace falta para reabrir en el armador con `cargarCartera`. */
  posiciones: z.array(
    z.strictObject({ ticker: z.string(), peso: z.number(), clase: esquemaClasePosicion }),
  ),
  /** La foto valuada, congelada al momento de guardar. */
  resueltas: z.array(esquemaResueltaGuardada),
  totalInvertidoUsd: z.number(),
})

export const esquemaSnapshotCartera = z.discriminatedUnion('origen', [
  esquemaSnapshotCargada,
  esquemaSnapshotArmador,
])

export type SnapshotCargada = z.infer<typeof esquemaSnapshotCargada>
export type SnapshotArmador = z.infer<typeof esquemaSnapshotArmador>
export type SnapshotCartera = z.infer<typeof esquemaSnapshotCartera>
export type ValuadaGuardada = z.infer<typeof esquemaValuadaGuardada>
export type ExcluidaGuardada = z.infer<typeof esquemaExcluidaGuardada>
export type ResueltaGuardada = z.infer<typeof esquemaResueltaGuardada>

// --- Filas de la tabla `carteras` ----------------------------------------------------------------

const esquemaOrigen = z.enum(['cargada', 'armador'])

/** Las columnas denormalizadas que alimentan el listado — nunca baja `snapshot` (regla del
 *  índice `carteras_user_id_snapshot_en_idx`: el listado se ordena y se muestra sin él). */
export const esquemaFilaListado = z.object({
  id: z.string(),
  nombre: z.string(),
  descripcion: z.string().nullable(),
  origen: esquemaOrigen,
  moneda_referencia: z.string(),
  monto: z.number(),
  resumen: z.string(),
  snapshot_en: z.string(),
})

/** La fila completa, para el detalle. `snapshot` se valida aparte con `safeParse`: una versión
 *  futura o un dato corrupto se declara sin romper la carga de la fila entera. */
export const esquemaFilaDetalle = esquemaFilaListado.extend({
  snapshot: z.unknown(),
})

export type FilaListado = z.infer<typeof esquemaFilaListado>
export type FilaDetalle = z.infer<typeof esquemaFilaDetalle>
