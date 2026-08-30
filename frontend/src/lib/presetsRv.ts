/**
 * Presets temáticos de renta variable — F-078.
 *
 * Un preset no clasifica nada por su cuenta: combina valores que **la fuente ya declaró** y deja
 * su definición a la vista. Vive en `lib/` porque lo comparten el monitor y el armador, que tienen
 * prohibido importarse entre sí (precedente F-017/F-038).
 *
 * **Por qué "metales preciosos" es un preset y no una faceta.** Ninguna fuente declara un campo
 * "esto es metal precioso". Lo que sí hay son tres declaraciones distintas que, unidas, arman la
 * categoría, y cada una se puede señalar con el dedo:
 *
 * 1. `estrategia_etf = 'activo_fisico'` — el fondo tiene el metal, no acciones de empresas. Son
 *    `GLD` (ETF SPDR GOLD TRUST) y `SLV` (iShares SILVER TRUST).
 * 2. `sic_codigo = '1040'` — la SEC lo titula literalmente **Gold and Silver Ores**. Son 25
 *    especies medidas el 28/08/2026: AEM, B (Barrick), CDE, GFI, HMY, KGC, MUX, NEM, NG y PAAS,
 *    con sus hermanas en pesos y en dólares.
 * 3. El nombre oficial que publica BYMA nombra el metal — así entra `GDX` (Van Eck Gold Miners
 *    ETF), que la SEC no clasifica y BYMA declara sólo como sectorial. Leer el nombre es la misma
 *    técnica con la que `app/renta_variable/etfs.py` deriva la estrategia de un fondo: no se
 *    interpreta, se lee.
 *
 * **Lo que queda afuera a propósito, y por qué.** Es la parte que hace honesto al preset:
 *
 * - `sic_codigo = '1000'` (Metal Mining) son metales, pero no preciosos: BHP, FCX, RIO, VALE,
 *   SCCO, LAC, LAR y MP son cobre, hierro, litio y tierras raras. Meterlos haría que "metales
 *   preciosos" devuelva mineras de cobre.
 * - `sic_codigo = '1090'` (Miscellaneous Metal Ores) es uranio: CCJ y NXE.
 * - **`HL` (Hecla Mining) produce plata y aun así no entra por SIC**: la SEC lo clasifica en 1400,
 *   *Mining & Quarrying of Nonmetallic Minerals*. Moverlo de código sería corregir a la fuente, que
 *   es exactamente lo que la regla 11 prohíbe. Entra sólo si su nombre nombra el metal, por el
 *   criterio 3, y si no entra queda declarado acá.
 *
 * La comparación de palabras es **por palabra entera**: `\bgold\b` no matchea "Goldman" (GS), del
 * mismo modo que `etfs.py` aprendió a no leer "ETF" adentro de "NETFLIX".
 */

import type { EspecieRentaVariable } from './rentaVariable'

/** Las dimensiones que un preset puede precargar. Todas opcionales; las declaradas son las que
 *  filtran. Es el espejo exacto de `FiltroRv` del backend (`app/armado/parametros.py`), para que
 *  el mismo preset se pueda mandar al armador sin reinterpretarlo. */
export interface FiltroRv {
  /** Valores exactos de `sic_oficina`, el rubro tal como lo agrupa la SEC. */
  rubros?: string[]
  /** Códigos de major group SIC, dos dígitos (`"73"`), mismo criterio que `sector_codigo` del
   *  backend (F-079). Más fino que `rubros` —que agrupa oficinas ambiguas de la SEC— y más grueso
   *  que `sicCodigos`. */
  sectores?: string[]
  /** Códigos SIC literales, sin normalizar. */
  sicCodigos?: string[]
  /** Claves de `estrategia_etf` (`activo_fisico`, `geografico`, `cripto`…). */
  estrategiasEtf?: string[]
  /** Códigos ISO 3166-1 alfa-2 del país curado. */
  paises?: string[]
  /** Subregiones ONU M49 derivadas del país. */
  regiones?: string[]
  /** Valores de `mercado_origen`, comparados sin distinguir mayúsculas (la fuente escribe el mismo
   *  mercado de dos maneras: "NYSE Arca" en 81 papeles y "NYSE ARCA" en 12). */
  mercados?: string[]
  /** Palabras que el nombre oficial declarado por BYMA tiene que contener, como palabra entera. */
  palabrasEnNombre?: string[]
}

export type ModoFiltroRv = 'interseccion' | 'union'

export interface PresetRv {
  id: string
  etiqueta: string
  filtro: FiltroRv
  /** `interseccion`: toda dimensión declarada tiene que cumplirse. `union`: alcanza con una. */
  modo: ModoFiltroRv
  /** Qué incluye y qué deja afuera. Un preset sin nota es magia: no se agrega ninguno sin esto. */
  nota: string
}

function contienePalabra(texto: string, palabra: string): boolean {
  // Palabra entera y sin distinguir acentos de caja: el nombre viene tanto en mayúsculas
  // ("ETF SPDR GOLD TRUST") como en mixta ("Van Eck Gold Miners ETF/USA").
  const patron = new RegExp(`\\b${palabra.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i')
  return patron.test(texto)
}

/** Las condiciones que el filtro declara, cada una evaluada contra la especie. Una dimensión no
 *  declarada no produce condición; un dato faltante **nunca cumple** una condición activa, que es
 *  como el armador viene tratando el rubro desde F-026: no se acota lo que no se conoce, pero
 *  tampoco se lo cuela adentro de un recorte que el asesor pidió. */
function condiciones(especie: EspecieRentaVariable, filtro: FiltroRv): boolean[] {
  const evaluadas: boolean[] = []
  if (filtro.rubros?.length) evaluadas.push(especie.sic_oficina !== null && filtro.rubros.includes(especie.sic_oficina))
  if (filtro.sectores?.length)
    evaluadas.push(especie.sector_codigo !== null && filtro.sectores.includes(especie.sector_codigo))
  if (filtro.sicCodigos?.length) evaluadas.push(especie.sic_codigo !== null && filtro.sicCodigos.includes(especie.sic_codigo))
  if (filtro.estrategiasEtf?.length)
    evaluadas.push(especie.estrategia_etf !== null && filtro.estrategiasEtf.includes(especie.estrategia_etf))
  if (filtro.mercados?.length) {
    const mercado = especie.mercado_origen?.toLowerCase() ?? null
    evaluadas.push(mercado !== null && filtro.mercados.some((m) => m.toLowerCase() === mercado))
  }
  if (filtro.palabrasEnNombre?.length) {
    const nombre = especie.nombre_largo
    evaluadas.push(nombre !== null && filtro.palabrasEnNombre.some((p) => contienePalabra(nombre, p)))
  }
  return evaluadas
}

/** `true` si la especie cumple el filtro. Un filtro sin ninguna dimensión declarada no filtra nada
 *  —devuelve todo—, que es distinto de no devolver nada: un preset vacío es un preset mal armado,
 *  no un universo vacío. */
export function cumpleFiltroRv(
  especie: EspecieRentaVariable,
  filtro: FiltroRv,
  modo: ModoFiltroRv = 'interseccion',
): boolean {
  const evaluadas = condiciones(especie, filtro)
  if (evaluadas.length === 0) return true
  return modo === 'union' ? evaluadas.some(Boolean) : evaluadas.every(Boolean)
}

export const PRESETS_RV: PresetRv[] = [
  {
    id: 'metales-preciosos',
    etiqueta: 'Metales preciosos',
    modo: 'union',
    filtro: {
      estrategiasEtf: ['activo_fisico'],
      sicCodigos: ['1040'],
      palabrasEnNombre: ['gold', 'silver', 'oro', 'plata'],
    },
    nota:
      'Trae tres cosas que la fuente declara por separado: los fondos que tienen el metal físico ' +
      '(GLD, SLV), las mineras que la SEC titula "Gold and Silver Ores" (código 1040: Barrick, ' +
      'Newmont, Agnico, Pan American y afines) y los fondos cuyo nombre oficial nombra el metal ' +
      '(GDX). Deja afuera la minería metálica genérica —código 1000, que es cobre, hierro y litio: ' +
      'BHP, Rio Tinto, Vale, Freeport— y el uranio (código 1090). Hecla (HL) produce plata pero la ' +
      'SEC la clasifica entre los minerales no metálicos, así que sólo entra si su nombre la nombra.',
  },
  {
    id: 'cripto',
    etiqueta: 'Cripto',
    modo: 'interseccion',
    filtro: { estrategiasEtf: ['cripto'] },
    nota:
      'Fondos cuya estrategia declarada en el nombre es cripto: IBIT (ISHARES BITCOIN TRUST) y ' +
      'ETHA (ISHARES ETHEREUM TR ETF). No hay acciones sueltas en esta categoría: el universo de ' +
      'CEDEARs sólo la ofrece por fondo.',
  },
  // --- F-079: unificación de las píldoras que hasta acá vivían sólo como temáticas del armador,
  // con `rubroRv` inline (`features/armador/lib/tematicas.ts`). Se quedan definidas por
  // `sic_oficina` —la oficina de la SEC— y no se reescriben a `sectores` (major group): una
  // oficina como "Office of Technology" mezcla varios major groups (computadoras 35, electrónica
  // 36, software 73, entre otros) con actividades que no son exclusivamente tecnológicas, así que
  // agruparlas por major group sería una categorización nuestra sin validar. Si el dueño quiere
  // redefinir alguna con major groups específicos, es curado posterior y explícito.
  {
    id: 'financieras',
    etiqueta: 'Financieras',
    modo: 'interseccion',
    filtro: { rubros: ['Office of Finance'] },
    nota:
      'Todo lo que la SEC agrupa bajo Office of Finance: bancos, seguros y servicios financieros. ' +
      'Es la oficina tal como la publica la fuente, no un sector nuestro — incluye las especies ' +
      'que la SEC clasifica en rubros ambiguos como "Office of Finance or Office of Crypto ' +
      'Assets", porque esa especie declara la oficina igual.',
  },
  {
    id: 'tecnologicas',
    etiqueta: 'Tecnológicas',
    modo: 'interseccion',
    filtro: { rubros: ['Office of Technology'] },
    nota:
      'Todo lo que la SEC agrupa bajo Office of Technology. No se reescribe a major groups: ' +
      'computadoras (35), electrónica (36) y software (73) quedan mezclados entre sí y con otras ' +
      'actividades dentro de esos códigos, así que agruparlos sería una categorización nuestra ' +
      'sin validar.',
  },
  {
    id: 'medicina',
    etiqueta: 'Medicina y salud',
    modo: 'interseccion',
    filtro: { rubros: ['Office of Life Sciences'] },
    nota:
      'Todo lo que la SEC agrupa bajo Office of Life Sciences: farmacéuticas, biotecnología y ' +
      'equipamiento médico, tal como la fuente los agrupa.',
  },
]

export function presetRvPorId(id: string | null): PresetRv | null {
  if (id === null) return null
  return PRESETS_RV.find((preset) => preset.id === id) ?? null
}
