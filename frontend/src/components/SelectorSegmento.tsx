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

/** Orden de pestañas del design system; los segmentos que no figuren van al final, en su orden. */
const ORDEN = ['usd_hard', 'cer', 'tasa_fija', 'dollar_linked', 'badlar', 'tamar']

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
