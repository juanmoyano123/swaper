/**
 * El contrato de `POST /api/v1/armado` — F-019.
 *
 * Archivo propio y no `lib/schema.ts`, mismo criterio que `schemaConcentracion.ts` (F-020): varias
 * features de esta tanda tocan `lib/schema.ts` en paralelo, y un contrato por archivo evita que dos
 * agentes editen el mismo al mismo tiempo.
 *
 * La forma exacta sale de `backend/app/armado/motor.py::ResultadoArmado.como_dict()`. Las alertas
 * usan el mismo shape que las de calendario/concentración (`Alerta.como_dict()`): se redefinen acá
 * en vez de importarse de otro archivo por la misma razón de coordinación.
 */

import { z } from 'zod'

import type { FiltroRv, ModoFiltroRv } from '@/lib/presetsRv'

export const esquemaAlertaArmado = z.object({
  codigo: z.string(),
  mensaje: z.string(),
  severidad: z.enum(['error', 'advertencia', 'info']),
  /** Siempre `null` en esta feature: informa, no bloquea. */
  accion_requerida: z.string().nullable(),
  detalle: z.record(z.string(), z.unknown()),
})

export const esquemaPosicionArmada = z.object({
  ticker: z.string(),
  /** En puntos porcentuales, post-reponderación. */
  pct_cartera: z.number(),
  monto: z.number(),
  /** Qué lado de la cartera armó esta posición (Tanda 13). El motor sigue eligiendo sólo bonos;
   *  las acciones las elige el endpoint aparte, por liquidez y diversificación sectorial. */
  clase: z.enum(['renta_fija', 'renta_variable']),
})

export const esquemaResultadoArmado = z.object({
  posiciones: z.array(esquemaPosicionArmada),
  mix_aplicado: z.record(z.string(), z.number()),
  origen_mix: z.string(),
  perfil: z.string(),
  sectores: z.object({
    presentes: z.number(),
    minimo: z.number(),
    suficiente: z.boolean(),
  }),
  /** Cuánto del 100% terminó en renta variable. Puede ser menor al pedido —hasta 0— si no hubo
   *  candidatos; en ese caso la alerta `rv_sin_candidatos` lo explica y la renta fija queda
   *  ocupando la cartera entera, sin reescalar. */
  pct_rv_aplicado: z.number(),
  alertas: z.array(esquemaAlertaArmado),
})

export type PosicionArmada = z.infer<typeof esquemaPosicionArmada>
export type ResultadoArmado = z.infer<typeof esquemaResultadoArmado>
export type AlertaArmado = z.infer<typeof esquemaAlertaArmado>

/**
 * Los tres códigos que el armador emite cuando un tope de renta variable interviene — F-078.
 *
 * Se listan acá y no se reconocen por prefijo en cada consumidor porque son un contrato con el
 * backend (`app/armado/renta_variable.py`): un código nuevo tiene que aparecer en esta lista para
 * que la pantalla lo muestre en el bloque de renta variable, y esa es exactamente la revisión que
 * se quiere forzar. El shape de la alerta no cambia — es el mismo `AlertaArmado` de siempre.
 *
 * - `rv_tope_limita_seleccion` — los cupos agotaron los candidatos antes de llenar el bloque.
 * - `rv_tope_excedido` — la verificación post-selección encontró una categoría por encima del
 *   tope. **Declara, no bloquea** (decisión 3 del dueño, 28/08).
 * - `rv_tope_sin_dato_en_eje` — el tope se midió sobre menos posiciones de las que hay, porque a
 *   las otras les falta el dato del eje. No se acota lo que no se conoce (regla 1), y se cuenta.
 */
export const CODIGOS_ALERTA_TOPE_RV = [
  'rv_tope_limita_seleccion',
  'rv_tope_excedido',
  'rv_tope_sin_dato_en_eje',
] as const

export function esAlertaDeTopeRv(alerta: AlertaArmado): boolean {
  return (CODIGOS_ALERTA_TOPE_RV as readonly string[]).includes(alerta.codigo)
}

/** Los cinco ejes sobre los que se puede acotar el bloque de renta variable. Es el mismo orden en
 *  el que se muestran en pantalla y en el que se listan en `TopesRv` del backend. */
export const EJES_TOPE_RV = ['rubro', 'pais', 'region', 'moneda', 'mercado'] as const
export type EjeTopeRv = (typeof EJES_TOPE_RV)[number]

/**
 * Cuánto del bloque de renta variable puede caer en una misma categoría de cada eje — F-078.
 *
 * Espejo de `TopesRv` del backend (`app/armado/parametros.py`). Cinco ejes sueltos y ningún score
 * compuesto: es la regla 7 del dominio aplicada a la renta variable — el riesgo es un vector, y
 * ponderar "país" contra "rubro" para sacar un índice único exigiría un juicio que nadie estableció.
 *
 * `null` en un eje **apaga ese tope**, y es distinto de `topes_rv` entero ausente: lo primero dice
 * "no acotes por país", lo segundo dice "usá los defaults del perfil". El panel manda siempre los
 * cinco campos, así que lo que se ve en pantalla es literalmente lo que se armó.
 *
 * El porcentaje se mide **sobre el bloque de renta variable**, no sobre la cartera entera: mezclar
 * las dos unidades haría que el mismo número signifique dos cosas según `pct_rv`.
 */
export interface TopesRv {
  /** Sobre `sector_codigo` desde F-079 (29/08/2026), no sobre `sic_oficina`: el major group SIC de
   *  dos dígitos (43 valores presentes) es aritmética pura sobre `sic_codigo` y no depende de
   *  ningún curado, mientras que `sic_oficina` —la oficina de la SEC, 12 valores— dejaba 78
   *  especies en oficinas ambiguas ("X or Y", "Multiple Offices") sin poder acotarlas. El nombre
   *  del campo (`max_pct_rubro`) no cambia: es el contrato con el backend
   *  (`app.armado.parametros.TopesRv.max_pct_rubro`); lo que mide, sí. */
  max_pct_rubro: number | null
  /** Sobre `pais`, el país curado en ISO 3166-1 alfa-2. */
  max_pct_pais: number | null
  /** Sobre `region`, la subregión ONU M49 derivada del país. */
  max_pct_region: number | null
  /** Sobre `moneda_cotizacion`, la moneda en la que la especie liquida en BYMA. */
  max_pct_moneda: number | null
  /** Sobre `mercado_origen`, el mercado donde cotiza el subyacente. */
  max_pct_mercado: number | null
}

/** De qué eje es cada campo de `TopesRv`, para no repetir el mapeo en cada consumidor. */
export const CAMPO_TOPE_RV: Record<EjeTopeRv, keyof TopesRv> = {
  rubro: 'max_pct_rubro',
  pais: 'max_pct_pais',
  region: 'max_pct_region',
  moneda: 'max_pct_moneda',
  mercado: 'max_pct_mercado',
}

/**
 * `FiltroRv` de `lib/presetsRv.ts` en la forma que viaja al backend: snake_case y con `modo`
 * adentro — F-078.
 *
 * Son dos tipos y no uno porque cumplen dos roles distintos. `presetsRv.FiltroRv` es el que se
 * evalúa en el navegador (lo comparte el monitor, que no manda nada al armador) y usa camelCase
 * como todo el frontend; éste es el cuerpo del `POST /api/v1/armado`, espejo literal de
 * `app/armado/parametros.py::FiltroRv`. Traducir en un solo lugar —`filtroRvABackend`— es lo que
 * evita que un preset diga una cosa en pantalla y otra en el request.
 */
export interface FiltroRvArmado {
  rubros?: string[]
  /** Códigos de major group SIC de dos dígitos (`sector_codigo`, `"73"`), F-079. Espejo de
   *  `FiltroRv.sectores` de `lib/presetsRv.ts` y de `app.armado.parametros.FiltroRv.sectores` del
   *  backend — más específico que `rubros` (que filtra por `sic_oficina`) y siempre derivable de
   *  `sic_codigos` sin ningún curado adicional. */
  sectores?: string[]
  sic_codigos?: string[]
  estrategias_etf?: string[]
  paises?: string[]
  regiones?: string[]
  mercados?: string[]
  palabras_en_nombre?: string[]
  /** `interseccion`: toda dimensión declarada tiene que cumplirse. `union`: alcanza con una. */
  modo: ModoFiltroRv
}

/** Pasa un `FiltroRv` de preset al shape del request. Las dimensiones no declaradas **no viajan**:
 *  mandar `rubros: []` y no mandar `rubros` significan lo mismo del lado del backend, pero un
 *  cuerpo que sólo lleva lo que el preset declara se lee igual que la definición del preset. */
export function filtroRvABackend(filtro: FiltroRv, modo: ModoFiltroRv): FiltroRvArmado {
  const salida: FiltroRvArmado = { modo }
  if (filtro.rubros?.length) salida.rubros = filtro.rubros
  if (filtro.sectores?.length) salida.sectores = filtro.sectores
  if (filtro.sicCodigos?.length) salida.sic_codigos = filtro.sicCodigos
  if (filtro.estrategiasEtf?.length) salida.estrategias_etf = filtro.estrategiasEtf
  if (filtro.paises?.length) salida.paises = filtro.paises
  if (filtro.regiones?.length) salida.regiones = filtro.regiones
  if (filtro.mercados?.length) salida.mercados = filtro.mercados
  if (filtro.palabrasEnNombre?.length) salida.palabras_en_nombre = filtro.palabrasEnNombre
  return salida
}

/** El mandato del cliente. Espejo de `ParametrosArmado` del backend, recortado a lo que el
 *  formulario expone: sin `mix` manual ni `n_total`, y sin `pago_mensual` —que el backend declara
 *  pero su motor todavía no consume (ver `app/armado/motor.py`: "el desempate por calendario no se
 *  portó"), así que exponerlo prometería un efecto que no ocurre. */
export interface ParametrosArmadoAsistido {
  monto: number
  moneda: 'usd' | 'ars' | 'todas'
  cobertura: 'devaluacion' | 'inflacion' | 'tasa-pesos' | 'mixta'
  perfil: 'conservador' | 'moderado' | 'agresivo'
  horizonte: 'corto' | 'medio' | 'largo'
  /** Qué porcentaje del total va a acciones y CEDEARs. Omitirlo deja que el backend use el
   *  default del perfil (`PCT_RV_PERFIL`). */
  pct_rv?: number
  /** Rubro de la SEC (`sic_oficina`) para acotar la renta variable a una temática.
   *
   *  **Se mantiene por compatibilidad** (F-052): es exactamente `filtro_rv.rubros` con un solo
   *  valor, y el backend lo pliega ahí en `normalizar_filtro_rv`. Mandar los dos diciendo cosas
   *  distintas es 422, no una precedencia silenciosa — así que este panel manda uno u otro, nunca
   *  los dos con valores que se contradigan. */
  rubro_rv?: string | null
  /** Los cinco topes de diversificación del bloque de renta variable. Omitirlo deja que el
   *  backend aplique los defaults del perfil (`TOPES_RV_DEFAULT`); mandarlo con un eje en `null`
   *  apaga ese eje explícitamente. Ver `TopesRv`. */
  topes_rv?: TopesRv
  /** Qué subconjunto del universo de renta variable participa del armado. Sale de un preset de
   *  `lib/presetsRv.ts` pasado por `filtroRvABackend`. */
  filtro_rv?: FiltroRvArmado
  /** Rendimiento mínimo exigido a la renta fija, en puntos porcentuales (`8` = 8%). Va al
   *  `min_rend` del backend, que el motor sí consume como piso al elegir candidatos. Omitirlo es
   *  no exigir piso.
   *
   *  Es el mismo número que `filtros.tirMin` de la grilla, y se mantienen sincronizados a
   *  propósito: que el armado automático proponga un papel que la grilla de al lado esconde por no
   *  llegar al piso sería la pantalla contradiciéndose sola. */
  min_rend?: number
}

/**
 * El default de renta variable por perfil, espejo de `PCT_RV_PERFIL` del backend.
 *
 * Sale del Excel de carteras sugeridas de la mesa: la conservadora no lleva renta variable, la
 * moderada un cuarto, y la audaz la mayor parte. Está acá duplicado —y no pedido al backend— para
 * poder precargar el input antes de que el asesor apriete el botón; el backend sigue siendo el que
 * decide si el campo llega vacío.
 */
export const PCT_RV_PERFIL: Record<ParametrosArmadoAsistido['perfil'], number> = {
  conservador: 0,
  moderado: 25,
  agresivo: 60,
}

/**
 * Los topes de renta variable con los que arranca cada perfil — F-078. Espejo de
 * `TOPES_RV_DEFAULT` del backend (`app/armado/renta_variable.py`).
 *
 * Duplicado a propósito y por la misma razón que `PCT_RV_PERFIL`: el panel tiene que **precargar
 * los números y mostrarlos** antes de que el asesor apriete el botón. Un tope que se aplica pero
 * no se ve obliga a adivinar con qué se armó la cartera, y esta feature existe justamente para que
 * eso no pase. El backend sigue siendo el que decide si el campo llega vacío.
 *
 * De dónde sale cada número. Los cinco ejes **no** se ordenan por importancia —regla 7: el riesgo
 * es un vector, no un score— pero sí tienen entre sí una relación aritmética que no se puede
 * violar:
 *
 * - **rubro** espeja `max_sector` de renta fija (`concentracion/perfiles.py`): es la misma
 *   pregunta —cuánto puede pesar una actividad económica— hecha del otro lado de la cartera. Desde
 *   F-079 (29/08/2026) esa pregunta se mide sobre `sector_codigo` (major group SIC, dos dígitos) y
 *   no sobre `sic_oficina` — mismo motivo que en `TopesRv.max_pct_rubro`: aritmética sin curado
 *   adicional, sin las 78 especies que caían en oficinas ambiguas. Los números no cambian con la
 *   migración.
 * - **país** va más alto que rubro: el panel de CEDEARs es abrumadoramente estadounidense, y un
 *   tope de país por debajo del de rubro dejaría el bloque incumplible por construcción, no por
 *   una cartera mal armada.
 * - **región ≥ país** siempre: una región contiene varios países, así que un tope de región más
 *   chico que el de país sería una contradicción aritmética, no una postura más exigente.
 * - **mercado** acompaña a región: NASDAQ y NYSE cubren casi todo el panel.
 * - **moneda viene apagada (`null`) en los tres perfiles**, y es el único eje así. No es un
 *   descuido: medido el 28/08/2026 sobre los candidatos reales, 379 CEDEARs cotizan en `ARS` y 286
 *   en `USD`, y **276 de esos 286 (96,5%) son la hermana `D`/`C` de un papel que ya cotiza en
 *   pesos**. Con los `n_rv` que el armador usa de verdad (4 en moderado, 9 en agresivo), cualquier
 *   tope por debajo de 100 fuerza al menos una posición no-`ARS`, y con esa proporción esa posición
 *   es casi con seguridad `NVDAD` al lado de `NVDA`: el mismo papel dos veces, comprado para
 *   cumplir una diversificación que no existe. Un CEDEAR de Apple es exposición al dólar se compre
 *   en pesos o en dólares — la moneda de cotización es **forma de liquidación**, no eje de
 *   diversificación. El eje no admite un default laxo: o no hace nada, o hace daño. El input queda
 *   en el panel, vacío, para el asesor que quiera encenderlo a mano.
 *
 * **Mandar el objeto es mandar los cinco ejes.** El backend no hace merge parcial contra el
 * default: `topes_rv` ausente significa "aplicá los del perfil" y `topes_rv` presente significa
 * "exactamente esto", con los ejes no nombrados **apagados**. Por eso `TopesRv` tiene los cinco
 * campos requeridos y no opcionales — omitir uno no puede ser un descuido de tipeo.
 */
export const TOPES_RV_PERFIL: Record<ParametrosArmadoAsistido['perfil'], TopesRv> = {
  conservador: {
    max_pct_rubro: 30,
    max_pct_pais: 40,
    max_pct_region: 60,
    max_pct_moneda: null,
    max_pct_mercado: 60,
  },
  moderado: {
    max_pct_rubro: 40,
    max_pct_pais: 50,
    max_pct_region: 70,
    max_pct_moneda: null,
    max_pct_mercado: 70,
  },
  agresivo: {
    max_pct_rubro: 55,
    max_pct_pais: 60,
    max_pct_region: 85,
    max_pct_moneda: null,
    max_pct_mercado: 85,
  },
}
