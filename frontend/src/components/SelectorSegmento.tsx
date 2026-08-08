/**
 * Barra de pestañas de segmento: un segmento activo por vez, nunca dos.
 *
 * Es la regla 2 del dominio hecha componente: los rendimientos de distinta naturaleza no comparten
 * eje ni columna, y la forma de garantizarlo en pantalla es que sólo pueda haber un segmento a la
 * vista. Base común de la tanda 6: la usan el monitor (F-038) y, más adelante, los filtros del
 * armador (F-017); si cada pantalla tuviera su propia barra, alguna terminaría permitiendo dos.
 *
 * La lista de segmentos viene del dato (los que el universo del día realmente tiene), no de una
 * constante: un segmento sin especies hoy no se muestra. Lo único que este archivo fija son los
 * NOMBRES de display y el rótulo corto de la unidad, que son diseño (A7 del design system) y
 * espejan los diccionarios del backend (`app/universo/segmentacion.py`). Un segmento cuya clave
 * no esté acá se muestra con su clave cruda: preferible feo a invisible.
 */

/** Espeja `DESC_SEGMENTO` del backend, en la forma corta de pestaña del design system (A7). */
export const NOMBRE_SEGMENTO: Record<string, string> = {
  usd_hard: 'Dólar hard',
  cer: 'CER',
  tasa_fija: 'Tasa fija $',
  dollar_linked: 'Dólar linked',
  badlar: 'Badlar',
  tamar: 'Tamar',
  // Base común de la tanda 8b, para F-052. No son segmentos de renta fija y por eso no tienen
  // entrada en UNIDAD_NATURALEZA: una acción no tiene rendimiento que rotular, y quien las muestre
  // no debe ponerle una columna de rendimiento ni nada en su lugar. Van al final del orden.
  accion: 'Acciones',
  cedear: 'CEDEARs',
  // Las tres pestañas en que se abre el dólar hard (08/08/2026). Ver `SEGMENTO_POR_CREDITO`.
  'usd_hard/bono_soberano': 'Soberanos',
  'usd_hard/bono_subsoberano': 'Subsoberanos',
  'usd_hard/on_corporativo': 'ONs',
}

/** Las pestañas que no son de renta fija: quien las active muestra columnas propias, sin TIR. */
export const CLAVES_RENTA_VARIABLE = ['accion', 'cedear'] as const

/**
 * Los segmentos que se muestran abiertos por crédito, con las clases de activo que los componen.
 *
 * El dólar hard es el 81 % de la renta fija segmentada (764 de 942) y mete al Tesoro, a las
 * provincias y a las ONs en una sola lista de 764 filas. Todas comparten naturaleza de tasa, así
 * que la regla 2 no obliga a separarlas; lo que las separa es el crédito, que es el eje que importa
 * cuando la unidad ya es la misma — y es la regla 4 del dominio, que exige que el riesgo soberano
 * se agrupe aparte. Es también cómo lo presentan el monitor de mesa y Balanz, cada uno a su manera.
 *
 * **La partición es de presentación y no toca el backend.** `/segmentos` sigue devolviendo
 * `usd_hard` y la grilla sigue pidiendo `?segmento=usd_hard`: las tres pestañas leen la misma query
 * ya cacheada y filtran por `clase_activo`, que es un dato declarado. Cambiar de pestaña no dispara
 * un pedido.
 *
 * Los valores de `clase_activo` son los cinco de `SUBMARKET_MAP` (backend
 * `ingesta/consolidacion/clasificacion.py`); dos son renta variable y los otros tres están acá. **No
 * existe una clase "letra"**: una LECAP llega como `bono_soberano`, así que no hay pestaña que
 * inventarle. Si apareciera una clase nueva, sus especies no entrarían en ninguna de las tres y el
 * conteo de la pestaña lo delataría — por eso el monitor cuenta lo que reparte.
 */
export const SEGMENTO_POR_CREDITO: Record<string, readonly string[]> = {
  usd_hard: ['bono_soberano', 'bono_subsoberano', 'on_corporativo'],
}

const SEPARADOR_CREDITO = '/'

/** La clave visible de una pestaña de crédito. `usd_hard` + `bono_soberano` → `usd_hard/bono_soberano`. */
export function claveDeCredito(segmento: string, clase: string): string {
  return `${segmento}${SEPARADOR_CREDITO}${clase}`
}

/**
 * El segmento real de una clave visible, para pedirle el dato al backend y para buscar su
 * naturaleza en `/segmentos`. Una clave sin partir se devuelve tal cual.
 */
export function segmentoDeClave(clave: string): string {
  const corte = clave.indexOf(SEPARADOR_CREDITO)
  return corte === -1 ? clave : clave.slice(0, corte)
}

/** La clase de activo por la que filtra una pestaña de crédito, o `null` si la pestaña no filtra. */
export function claseDeClave(clave: string): string | null {
  const corte = clave.indexOf(SEPARADOR_CREDITO)
  return corte === -1 ? null : clave.slice(corte + SEPARADOR_CREDITO.length)
}

/**
 * Las claves visibles de la barra: los segmentos del dato, con los que se abren por crédito
 * reemplazados por sus pestañas. Un segmento sin partición pasa entero.
 */
export function expandirSegmentos(claves: readonly string[]): string[] {
  return claves.flatMap((clave) => {
    const clases = SEGMENTO_POR_CREDITO[clave]
    return clases ? clases.map((clase) => claveDeCredito(clave, clase)) : [clave]
  })
}

/**
 * Rótulo corto de la unidad de rendimiento, por naturaleza (`NATURALEZA_TASA` del backend).
 * Va en la cabecera de la columna de rendimiento y en los filtros: la columna declara su unidad,
 * siempre. Sin entrada conocida no se rotula "TIR" por defecto — se muestra la clave cruda.
 */
export const UNIDAD_NATURALEZA: Record<string, string> = {
  tir_usd: 'TIR USD',
  tir_dolar_linked: 'TIR DL',
  tasa_real_cer: 'Tasa real CER',
  tna_nominal_ars: 'TNA $',
}

export function nombreSegmento(clave: string): string {
  return NOMBRE_SEGMENTO[clave] ?? clave
}

export function unidadDeNaturaleza(naturaleza: string): string {
  return UNIDAD_NATURALEZA[naturaleza] ?? naturaleza
}

/**
 * Orden de pestañas del design system; los segmentos que no figuren van al final, en su orden.
 *
 * `usd_hard` sigue en la lista aunque el monitor lo muestre abierto: el armador (F-017) pasa la
 * clave sin partir y tiene que seguir ordenándose donde siempre estuvo. Las tres pestañas de
 * crédito ocupan su lugar, delante del resto.
 */
const ORDEN = [
  'usd_hard',
  'usd_hard/bono_soberano',
  'usd_hard/bono_subsoberano',
  'usd_hard/on_corporativo',
  'cer',
  'tasa_fija',
  'dollar_linked',
  'badlar',
  'tamar',
  'accion',
  'cedear',
]

export function ordenarSegmentos(claves: readonly string[]): string[] {
  return [...claves].sort((a, b) => {
    const ia = ORDEN.indexOf(a)
    const ib = ORDEN.indexOf(b)
    return (ia === -1 ? ORDEN.length : ia) - (ib === -1 ? ORDEN.length : ib)
  })
}

export function SelectorSegmento({
  segmentos,
  activo,
  onCambio,
}: {
  /** Claves de segmento presentes en el dato, sin ordenar (este componente las ordena). */
  segmentos: readonly string[]
  activo: string
  onCambio: (segmento: string) => void
}) {
  return (
    <nav
      aria-label="Segmento"
      style={{
        display: 'flex',
        gap: 2,
        borderBottom: '1px solid var(--lin)',
        overflowX: 'auto',
      }}
    >
      {ordenarSegmentos(segmentos).map((clave) => {
        const esActivo = clave === activo
        return (
          <button
            key={clave}
            type="button"
            onClick={() => onCambio(clave)}
            aria-current={esActivo ? 'true' : undefined}
            style={{
              font: `${esActivo ? 600 : 400} 12.5px/1 inherit`,
              color: esActivo ? 'var(--tx)' : 'var(--dim)',
              background: 'none',
              border: 'none',
              borderBottom: esActivo ? '2px solid var(--ac)' : '2px solid transparent',
              padding: '8px 12px 7px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {nombreSegmento(clave)}
          </button>
        )
      })}
    </nav>
  )
}
