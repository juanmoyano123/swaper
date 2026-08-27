/**
 * Barra de pestañas de segmento: un segmento activo por vez, nunca dos.
 *
 * Es la regla 2 del dominio hecha componente: los rendimientos de distinta naturaleza no comparten
 * eje ni columna, y la forma de garantizarlo en pantalla es que sólo pueda haber un segmento a la
 * vista. Base común de la tanda 6: la usan el monitor (F-038, con las claves de tipo de tasa sin
 * partir desde el 14/08/2026), los filtros del armador (F-017, ídem) y, partidas por crédito, la
 * curva del armador (`PanelComposicion.tsx`, F-023) — si cada pantalla tuviera su propia barra,
 * alguna terminaría permitiendo dos.
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
  // Los tipos de renta de FCI (23/08/2026, F-057), con prefijo `fci_` para no colisionar nunca con
  // una clave de renta fija — espejan `tipo_renta` del backend (`app/ingesta/cafci/secciones.py`).
  // Tienen entrada en UNIDAD_NATURALEZA (más abajo): a diferencia de una acción, un FCI sí tiene
  // rendimiento — variación de cuotaparte —, sólo que de una naturaleza que no comparte eje con
  // ninguna TIR.
  fci_renta_variable: 'FCI renta variable',
  fci_renta_fija: 'FCI renta fija',
  fci_renta_mixta: 'FCI renta mixta',
  fci_pymes: 'FCI PyMEs',
  fci_infraestructura: 'FCI infraestructura',
  fci_retorno_total: 'FCI retorno total',
  fci_asg: 'FCI ASG',
  fci_rg900: 'FCI RG900',
  fci_mercado_dinero: 'FCI mercado de dinero',
  fci_fondos_cerrados: 'FCI fondos cerrados',
  fci_en_liquidacion: 'FCI en liquidación',
}

/** Las pestañas que no son de renta fija: quien las active muestra columnas propias, sin TIR.
 *
 *  Sólo `cedear` desde el 14/08/2026: las acciones argentinas dejaron de ser descubribles desde
 *  cualquier picker (pedido del dueño del producto — la pestaña quedaba mayormente `s/d`, casi
 *  ninguna opera). El dato sigue existiendo: `FichaInstrumento.tsx` reconoce `accion` aparte para
 *  que una posición vieja o un link directo a `/instrumento/GGAL` sigan resolviendo. */
export const CLAVES_RENTA_VARIABLE = ['cedear'] as const

/**
 * Los segmentos que se muestran abiertos por crédito, con las clases de activo que los componen.
 *
 * **Desde el 14/08/2026 el Monitor ya no usa esto.** La reorganización en jerarquía (familia →
 * segmento → chip de crédito, ver el header de `features/monitor/MonitorPage.tsx`) reemplazó las
 * pestañas de crédito por `SelectorCredito`, un chip que generaliza la partición a los seis
 * segmentos en vez de sólo al dólar hard. Este diccionario y los cuatro helpers de abajo
 * (`claveDeCredito`, `segmentoDeClave`, `claseDeClave`, `expandirSegmentos`) quedan **exclusivamente
 * para `PanelComposicion.tsx`** del armador (la curva TIR/duración de la cartera, F-023), que sigue
 * mostrando Soberanos/Subsoberanos/ONs como pestañas propias — es otra superficie, con su propio
 * criterio de cuándo conviene partir. No se borran ni cambian de firma para no tocarla sin pedido.
 *
 * El dólar hard es el 81 % de la renta fija segmentada (764 de 942) y mete al Tesoro, a las
 * provincias y a las ONs en una sola lista de 764 filas. Todas comparten naturaleza de tasa, así
 * que la regla 2 no obliga a separarlas; lo que las separa es el crédito, que es el eje que importa
 * cuando la unidad ya es la misma — y es la regla 4 del dominio, que exige que el riesgo soberano
 * se agrupe aparte.
 *
 * **La partición es de presentación y no toca el backend.** `/segmentos` sigue devolviendo
 * `usd_hard` y la grilla sigue pidiendo `?segmento=usd_hard`: las pestañas de `PanelComposicion`
 * leen la misma query ya cacheada y filtran por `clase_activo`, que es un dato declarado. Cambiar
 * de pestaña no dispara un pedido.
 *
 * Los valores de `clase_activo` son los cinco de `SUBMARKET_MAP` (backend
 * `ingesta/consolidacion/clasificacion.py`); dos son renta variable y los otros tres están acá. **No
 * existe una clase "letra"**: una LECAP llega como `bono_soberano`, así que no hay pestaña que
 * inventarle.
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
  // Tanda 2 (26/08/2026): `tasa_fija` dejó de compartir naturaleza con badlar y tamar. Su rótulo
  // dice TIR y el de ellos TNA porque son unidades distintas, y la columna declara la suya.
  tir_ea_ars: 'TIR EA $',
  tna_nominal_ars: 'TNA $',
  // F-057: espeja `NATURALEZA_FCI` de `app/fci/fondos.py`.
  variacion_cuotaparte: 'Var. VCP %',
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
 * `usd_hard` es el que usa el Monitor desde el 14/08/2026 (claves sin partir). Las tres claves
 * compuestas `usd_hard/bono_*` siguen en la lista sólo por `PanelComposicion.tsx`, que todavía las
 * pide partidas; el Monitor no las usa más.
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
  'fci_renta_variable',
  'fci_renta_fija',
  'fci_renta_mixta',
  'fci_pymes',
  'fci_infraestructura',
  'fci_retorno_total',
  'fci_asg',
  'fci_rg900',
  'fci_mercado_dinero',
  'fci_fondos_cerrados',
  'fci_en_liquidacion',
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
