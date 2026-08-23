/**
 * El contrato de `GET /renta-variable/{ticker}/ficha` — F-053.
 *
 * Archivo aparte de `schema.ts` a propósito: son dos fichas distintas, no dos variantes de la
 * misma. La de renta fija gira alrededor de la TIR, el cronograma y la paridad; una acción no tiene
 * ninguna de las tres, y meter las dos en un esquema con la mitad de los campos opcionales invitaría
 * exactamente a lo que la regla 2 prohíbe — poner algo en el lugar de una magnitud que no existe.
 *
 * **No hay campo de recomendación, ni de precio objetivo, ni de consenso de analistas.** Son
 * opinión de terceros y el backend no los trae (regla 6); acá tampoco tienen lugar donde entrar. Si
 * el backend algún día los mandara, no viajarían a la pantalla.
 */

import { z } from 'zod'

/**
 * El bloque nuestro: lo que BYMA publica, idéntico a lo que muestra la tabla del monitor, más la
 * clasificación de la SEC y el OHLC del día (13/08/2026). Todo puede faltar: la SEC cubre 74 % de
 * los CEDEARs y 9 % de las acciones argentinas, y `precio_apertura`/`precio_maximo`/
 * `precio_minimo`/`vwap` son `null` en toda fila anterior a la migración que los agrega.
 */
export const esquemaBloquePropio = z.object({
  fuente: z.string(),
  ticker: z.string(),
  clase_activo: z.string(),
  precio: z.number().nullable(),
  moneda_cotizacion: z.string().nullable(),
  cierre_anterior: z.number().nullable(),
  /** Fracción, no puntos: 0.031 es +3,1 %. Multiplicar por 100 recién al formatear. */
  variacion: z.number().nullable(),
  volumen: z.number().nullable(),
  volumen_usd: z.number().nullable(),
  px_bid: z.number().nullable(),
  px_ask: z.number().nullable(),
  operaciones: z.number().nullable(),
  // OHLC de BYMA: siempre de BYMA aunque `fuente` diga data912 (el overlay no los pisa).
  precio_apertura: z.number().nullable(),
  precio_maximo: z.number().nullable(),
  precio_minimo: z.number().nullable(),
  vwap: z.number().nullable(),
  // Perfil de empresa: `nombre_largo` sale de la SEC o de la lista de CEDEARs de BYMA según cuál
  // corrió última (`perfil_fuente` lo dice). El resto es siempre de la SEC.
  nombre_largo: z.string().nullable(),
  perfil_fuente: z.string().nullable(),
  perfil_capturado_en: z.string().nullable(),
  /** Código de actividad de la SEC, sin normalizar: es la llave de auditoría. */
  sic_codigo: z.string().nullable(),
  /** A qué se dedica, en las palabras de la fuente: `Electronic Computers`. */
  sic_titulo: z.string().nullable(),
  /** El rubro, según cómo agrupa la propia SEC: `Office of Energy & Transportation`. */
  sic_oficina: z.string().nullable(),
  /** Eslabón de la cadena productiva (extracción, manufactura, comercio, servicios), derivado de
   *  la división del SIC Manual — nunca una interpretación nuestra. */
  division_cadena: z.string().nullable(),
  /** Qué idea arma el portafolio si es un fondo. `null` = no es un fondo. */
  estrategia_etf: z.string().nullable(),
  /** Cuántos CEDEARs equivalen a una acción del subyacente, como razón (`20:1`). */
  ratio_conversion: z.string().nullable(),
  /** En qué mercado cotiza el subyacente: `NASDAQ`, `NYSE`, `B3`. */
  mercado_origen: z.string().nullable(),
})

export type BloquePropio = z.infer<typeof esquemaBloquePropio>

export const esquemaPuntoHistorico = z.object({
  fecha: z.string(),
  cierre: z.number(),
})

export type PuntoHistorico = z.infer<typeof esquemaPuntoHistorico>

/**
 * El histórico de cierres, de data912. Bloque propio y top-level: es otra fuente, con su propio
 * rótulo, y la regla 11 exige una fuente por bloque. `data912` no declara la moneda de la serie;
 * quien la muestre tiene que decirlo en vez de heredar la de la especie, que podría no ser la
 * misma.
 */
export const esquemaBloqueHistorico = z.object({
  fuente: z.string(),
  disponible: z.boolean(),
  motivo: z.string().nullable(),
  puntos: z.array(esquemaPuntoHistorico),
})

export type BloqueHistorico = z.infer<typeof esquemaBloqueHistorico>

/**
 * Un documento presentado ante la SEC, con el link directo al PDF/HTM real — nunca a una página de
 * resumen nuestra.
 */
export const esquemaFilingSec = z.object({
  form: z.string(),
  fecha: z.string(),
  url_documento: z.string(),
})

export type FilingSec = z.infer<typeof esquemaFilingSec>

/**
 * Un ratio o un monto del paquete SEC. `unidad` es `null` para los seis adimensionales (ROE,
 * márgenes, liquidez, deuda/patrimonio, crecimiento); el EPS es el único que lleva moneda, y por eso
 * `unidad` puede faltar: un ratio adimensional no tiene ninguna.
 */
export const esquemaRatioSec = z.object({
  valor: z.number(),
  unidad: z.string().nullable(),
  periodo: z.string(),
})

export type RatioSec = z.infer<typeof esquemaRatioSec>

export const esquemaRatiosSec = z.object({
  roe: esquemaRatioSec.nullable(),
  margen_operativo: esquemaRatioSec.nullable(),
  crecimiento_ingresos: esquemaRatioSec.nullable(),
  eps: esquemaRatioSec.nullable(),
  deuda_patrimonio: esquemaRatioSec.nullable(),
  liquidez_corriente: esquemaRatioSec.nullable(),
})

export type RatiosSec = z.infer<typeof esquemaRatiosSec>

/**
 * El paquete de estados contables (14/08/2026), sólo para CEDEARs — para una acción argentina
 * `disponible` da `false` con el motivo, sin que la ficha rompa nada. `solo_anual` es `true` para
 * la mayoría de los CEDEARs sudamericanos: la SEC no les publica trimestral consistente porque
 * reportan como emisor privado extranjero, y `nota_solo_anual` lo dice en vez de esconderlo.
 */
export const esquemaBloqueSec = z.object({
  fuente: z.string(),
  disponible: z.boolean(),
  motivo_ausente: z.string().nullable(),
  solo_anual: z.boolean(),
  nota_solo_anual: z.string().nullable(),
  cik: z.string().nullable(),
  filings: z.array(esquemaFilingSec),
  ratios: esquemaRatiosSec.nullable(),
})

export type BloqueSec = z.infer<typeof esquemaBloqueSec>

export const esquemaFichaRentaVariable = z.object({
  ticker: z.string(),
  propio: esquemaBloquePropio,
  historico: esquemaBloqueHistorico,
  // `.optional()`, no obligatorio: un despliegue no atómico puede servir esta pantalla contra un
  // backend anterior al 14/08/2026 que todavía no manda esta clave, y el resto de la ficha tiene
  // que seguir parseando igual.
  sec: esquemaBloqueSec.optional(),
})

export type FichaRentaVariable = z.infer<typeof esquemaFichaRentaVariable>
