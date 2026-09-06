/**
 * El bloque separado de renta variable — F-026, mockup A4 del design system.
 *
 * Acciones (69 verificadas) y CEDEARs (683 verificados), con subtotal propio, que suma al monto
 * total de la cartera y **queda afuera de todo cálculo de renta fija**: sin TIR, sin duración, sin
 * cupón, sin participar de ninguno de los cuatro rendimientos por naturaleza de tasa (regla 2 del
 * dominio). `posicionesRentaFija` (store, base común de la Tanda 9) ya excluye estas posiciones del
 * resolver de bonos y del calendario de cupones — este componente no repite esa frontera, la usa.
 *
 * ## La composición para el cliente, y lo que todavía le falta
 *
 * **Hasta F-078 este bloque declaraba que la distribución por país y por rubro no existía**, y era
 * cierto: `EspecieRentaVariable` traía sólo precio, moneda, volumen y puntas — ni país, ni rubro,
 * ni el nombre de la empresa. Construir la distribución entonces habría sido una pantalla con
 * "país no informado" en el 100% de las especies.
 *
 * Ahora hay fuente para los cinco ejes, y las barras se dibujan (`composicionRentaVariable.ts`,
 * pesadas por plata invertida): **sector** y **mercado** salen de la clasificación de la SEC y de la
 * tabla de CEDEARs de BYMA; **moneda** de BYMA, cruda; **país** del curado manual papel por papel
 * de F-078 (ISO 3166-1 alfa-2, con fuente y fecha por fila) unificado desde F-079 con el país curado
 * de los ETFs mono-país; **región** de varios lados a la vez — la subregión ONU M49 derivada del
 * país para las empresas y para los ETFs mono-país, el alcance curado del índice cuando no hay país
 * único, y el nombre oficial del fondo para los ETFs geográficos sin curar, que se muestra como
 * tramo distinto porque mapearlo al resto sería traducir (regla 11).
 *
 * **Lo que sigue faltando aparece como tramo "sin dato", nunca repartido**, y es bastante: los
 * papeles que el curado de país todavía no cubrió —al escribirse esto, todos, hasta que corra la
 * siembra—, y los 112 CEDEARs sin CIK ni código SIC, que no tienen rubro y no van a tenerlo por
 * esta vía. Que el eje de país sea un solo tramo "país no informado" es el contrato del sistema
 * funcionando, no una pantalla rota.
 *
 * Los topes que el asesor configura en `PanelArmadoAsistido` gobiernan exactamente estos cinco
 * ejes, y las alertas que el armador devuelve cuando un tope interviene se muestran acá y no allá:
 * es donde se ve la consecuencia.
 *
 * ## Dos cosas que el mockup pide y siguen sin fuente
 *
 * 1. **El emisor de la tarjeta.** Donde el diseño pide el emisor, acá va la clase (`Acción` /
 *    `CEDEAR`) y, si el perfil de empresa ya se trajo, el nombre largo tal como lo publica la
 *    fuente. No se inventa un nombre a partir del ticker.
 *
 * 2. **"Div. est." siempre en `SIN_DATO`.** No hay fuente de dividendos en el universo consolidado.
 *    Mostrar un estimado sería inventar un dato (regla 1); se declara `s/d` con una nota, siempre.
 *    El calendario de doce celdas del mockup sí se dibuja desde F-027 (16/08/2026) — pero es sólo
 *    de **balances**, vía SEC EDGAR: un patrón histórico de presentación, no una fecha confirmada
 *    ni un cobro. Sigue sin dividendos, que es un dato distinto y sigue sin fuente.
 *
 * ## Selección de peso
 *
 * `PosicionArmador.peso` es el pedido sobre la cartera **entera** (store, `alternarRentaVariable`),
 * el mismo eje que usa la renta fija — así el 100% es del total y no de cada bloque. Acá se muestra
 * además el **peso real dentro del bloque** (`resolverRentaVariable`, distinto de `pesoReal` de
 * `resolver.ts`, que reparte sobre el total de la cartera): es la cifra que importa para juzgar el
 * bloque de renta variable en sí mismo.
 *
 * **Etapa 3 del rediseño**: hasta acá el peso pedido de una acción sólo se podía cambiar con
 * "Equiponderar" o agregando/sacando papeles — `fijarPeso` del store ya era agnóstico de clase,
 * pero `CarteraEditable` (su único llamador) filtra la renta variable, así que nunca llegaba un
 * input. La tarjeta gana su propio "% pedido", con el mismo trato visual que el de
 * `CarteraEditable.tsx` (mono, `--ac`, resaltado si difiere del real más de
 * `TOLERANCIA_DIFERENCIA_FILA`). La cabecera suma el mix pedido y el mix real (sobre lo
 * efectivamente invertido) — dos cuentas distintas que pueden no coincidir, y las dos se muestran.
 */

import { type ReactNode, useMemo, useRef, useState } from 'react'

import { CampoSelect } from '@/components/CampoSelect'
import { DistribucionBarras } from '@/components/DistribucionBarras'
import { useAbrirInstrumento } from '@/features/instrumento/useAbrirInstrumento'
import { facetar, type Faceta } from '@/lib/facetado'
import { fmtFecha, fmtMonto, fmtPct, SIN_DATO } from '@/lib/fmt'
import { cumpleFiltroRv } from '@/lib/presetsRv'
import { type EspecieRentaVariable, useRentaVariable } from '@/lib/rentaVariable'

import { AlertasCalendario } from './AlertasCalendario'
import { BadgeClase } from './BadgeClase'
import { PatronBalances } from './PatronBalances'
import { agruparEnPapeles, papelCoincide, type PapelRentaVariable } from '../lib/papelesRentaVariable'
import {
  categoriaRvDe,
  composicionRvPor,
  cuantasSeMidieron,
  leyendaDelMontoRv,
  tituloDelEje,
  type EjeComposicionRv,
} from '../lib/composicionRentaVariable'
import { type CalendarioBalances } from '../lib/esquemaBalances'
import { useCalendarioBalances } from '../hooks/useCalendarioBalances'
import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { useRentaVariableResuelta } from '../hooks/useRentaVariableResuelta'
import { sumaPesos } from '../lib/mix'
import { esAlertaDeTopeRv } from '../lib/schemaArmado'
import { presetPorId, SIN_PERFILES_DE_EMPRESA } from '../lib/tematicas'
import { type PosicionRvResuelta } from '../lib/resolverRentaVariable'
import {
  useArmador,
  useArmadorAcciones,
  type PosicionArmador,
} from '../store/carteraStore'

/** El papel que la SEC conoce para una especie: `emision` si está resuelta, si no el ticker —
 *  mismo criterio que usa la ficha de F-053 (`bloque_sec`) para buscar por papel, no por especie. */
function papelSecDe(especie: EspecieRentaVariable): string {
  return (especie.emision || especie.ticker).toUpperCase()
}

/** Mismo umbral que `CarteraEditable.tsx` (design system, sección A8): a partir de acá la
 *  diferencia entre pedido y real se marca, no antes. */
const TOLERANCIA_DIFERENCIA_FILA = 0.6

/**
 * Una dimensión del picker de papeles.
 *
 * `valorDe` devuelve **el valor de filtro** de esta dimensión: lo que arma la jerarquía y lo que se
 * compara en `coincide`. Para región, país y estrategia coincide con lo que se ve en el select — los
 * tres ejes que también son ejes de composición lo sacan de `categoriaRvDe` (su `.nombre`) para que
 * la barra y el filtro lean la fuente igual: si la barra dice `Brazil (fondo)` y el filtro ofreciera
 * `Brazil`, el asesor tendría que traducir de una pantalla a la otra. **Sector y Rubro específico son
 * la excepción — F-079**: ahí `valorDe` es el código (`sector_codigo`, `sic_codigo`), y `null` = a la
 * especie le falta el dato, y entonces no aporta opción ni cumple ningún valor de esta dimensión —
 * nunca se puede afirmar que un papel sin sector pertenece al sector que se pidió (regla 1).
 */
type DimensionPicker = 'region' | 'pais' | 'sector' | 'rubroEspecifico' | 'estrategia'

interface DimensionDelPicker {
  id: DimensionPicker
  etiqueta: string
  valorDe: (especie: EspecieRentaVariable) => string | null
  /** `true` para las que se muestran aunque no tengan ninguna opción. Ver el comentario del JSX. */
  siempreVisible?: boolean
}

/**
 * El orden **es** el orden de validación de `facetar()`, de lo general a lo específico: cuando dos
 * selecciones son incompatibles gana la primera y la otra queda apagada y declarada, en vez de
 * apagarse las dos. Región contiene país, país contiene empresas de cualquier sector, y el rubro
 * específico es una subdivisión del sector (el código SIC de cuatro dígitos, dentro del major group
 * de dos); la estrategia de ETF va al final porque sólo aplica a los fondos, que son una minoría
 * del panel.
 */
const DIMENSIONES_PICKER: DimensionDelPicker[] = [
  { id: 'region', etiqueta: 'Región', valorDe: (e) => categoriaRvDe(e, 'region')?.nombre ?? null },
  { id: 'pais', etiqueta: 'País (ISO)', valorDe: (e) => categoriaRvDe(e, 'pais')?.nombre ?? null },
  // Sector: value=`sector_codigo` (F-079), el major group SIC de dos dígitos — mismo criterio que
  // el monitor. El texto visible no es el código sino `especie.sector` (etiqueta ES curada) cuando
  // existe, resuelto por `textoDeOpcion` más abajo porque acá `valorDe` sólo puede devolver un
  // string por especie y necesita quedar como el código para que la jerarquía con Rubro específico
  // funcione sobre un valor estable.
  //
  // "(SIC)" en la etiqueta visible, no sólo en el aria-label: el filtro de sector de la grilla de
  // renta fija (más arriba en la misma página, `FiltrosGrilla.tsx`) ya se llama "Sector" a secas —
  // dos selects con el mismo texto visible confundirían tanto a la vista como a un lector de
  // pantalla (mismo motivo que ya evitaba la colisión con "Rubro (SEC)" antes de F-079).
  {
    id: 'sector',
    etiqueta: 'Sector (SIC)',
    valorDe: (e) => e.sector_codigo,
    siempreVisible: true,
  },
  // Rubro específico: value=`sic_codigo`, el código de cuatro dígitos tal como lo escribe la SEC.
  // Acotado por Sector arriba en la cascada de `facetar()`: elegir un sector deja sólo los rubros
  // específicos de empresas de ese sector.
  {
    id: 'rubroEspecifico',
    etiqueta: 'Rubro específico',
    valorDe: (e) => e.sic_codigo,
    siempreVisible: true,
  },
  // Qué idea arma el portafolio del fondo. Se muestra traducida al castellano porque `estrategia_etf`
  // **no es un código de la fuente**: es una clave nuestra que `app/renta_variable/etfs.py` deriva
  // leyendo el nombre, y `ETIQUETA_ESTRATEGIA` es su único texto de pantalla desde F-052.
  {
    id: 'estrategia',
    etiqueta: 'Estrategia (ETF)',
    valorDe: (e) =>
      e.estrategia_etf === null ? null : (ETIQUETA_ESTRATEGIA[e.estrategia_etf] ?? e.estrategia_etf),
  },
]

const SELECCION_VACIA: Record<DimensionPicker, string | null> = {
  region: null,
  pais: null,
  sector: null,
  rubroEspecifico: null,
  estrategia: null,
}

function etiquetaDimension(id: string): string {
  return DIMENSIONES_PICKER.find((dimension) => dimension.id === id)?.etiqueta ?? id
}

/** Los cinco ejes de la composición, en el mismo orden en que `PanelArmadoAsistido` ofrece sus
 *  topes: el asesor configura un tope y ve abajo la barra que ese tope gobierna. `'sector'` desde
 *  F-079, no `'rubro'` — ver el comentario de `EjeComposicionRv`. */
const EJES_COMPOSICION: EjeComposicionRv[] = ['sector', 'pais', 'region', 'moneda', 'mercado']

export function BloqueRentaVariable() {
  const { pos, tematicaId, alertasArmado } = useArmador()
  const { alternarRentaVariable, fijarPeso } = useArmadorAcciones()
  const abrirInstrumento = useAbrirInstrumento()

  // Sólo CEDEARs desde el 14/08/2026 (pedido del dueño del producto): las acciones argentinas
  // dejaron de ser descubribles desde este picker — la mayoría no opera nunca, y el armado
  // automático (backend) tampoco puede sugerirlas. El dato de `accion` sigue existiendo en el
  // universo; sólo se dejó de pedir acá. `FichaInstrumento.tsx` sigue reconociendo `accion` para
  // que una posición vieja o un link directo a `/instrumento/GGAL` sigan resolviendo.
  const cedears = useRentaVariable('cedear')
  // Sólo lectura: F-021/F-020 ya extrajeron este hook para no repetir el pipeline. Se usa acá
  // únicamente para declarar cómo se compone el monto total (GWT-4) — este bloque no recalcula
  // nada de renta fija.
  const {
    totalInvertidoUsd: subtotalRfUsd,
    hayAlgunaResuelta: hayRfResuelta,
    resueltas: resueltasRf,
  } = useCarteraResuelta()

  const [busqueda, setBusqueda] = useState('')
  // Para que "reemplazar" deje el cursor donde se elige el sustituto: sacar la posición y dejar al
  // asesor buscando dónde estaba el scroll sería la mitad del trabajo.
  const refBuscador = useRef<HTMLInputElement>(null)
  // Las cinco dimensiones del picker, cada una en su propio estado. Se guardan crudas —lo que el
  // asesor eligió— y `facetar()` decide después cuáles tienen respaldo; derivar en vez de
  // sincronizar es lo que evita la carrera entre cinco selects corrigiéndose por efectos.
  const [seleccion, setSeleccion] = useState<Record<DimensionPicker, string | null>>(
    SELECCION_VACIA,
  )
  function fijarDimension(dimension: DimensionPicker, valor: string | null) {
    setSeleccion((previa) => ({ ...previa, [dimension]: valor }))
  }

  // Un preset temático (Tanda 13) filtra los dos lados a la vez: la grilla de bonos por su sector
  // y este bloque por el rubro equivalente de la SEC. El rubro del preset se aplica al cambiar de
  // temática y después queda editable — el chip es un punto de partida, no un modo.
  const [tematicaAplicada, setTematicaAplicada] = useState<string | null>(null)
  const preset = presetPorId(tematicaId)
  if (tematicaId !== tematicaAplicada) {
    setTematicaAplicada(tematicaId)
    // Las cinco dimensiones se limpian: un país o un rubro específico que quedó de la temática
    // anterior seguiría filtrando invisible sobre una temática nueva.
    //
    // `preset.rubroRv` (`sic_oficina`) ya no tiene una dimensión del picker a la que
    // sincronizarse: Sector filtra por `sector_codigo`, un vocabulario distinto (F-079), y los
    // ocho presets vigentes lo tienen en `null` —migrados a `filtroRv`—, que sigue aplicándose
    // como `pasaBase` de `facetar()` más abajo sin pasar por ningún select. Si algún preset futuro
    // volviera a declarar `rubroRv`, su filtro seguiría acotando la lista igual mientras el
    // picker muestra "todos" en Sector: la selección visible no tiene por qué coincidir con una
    // oficina de la SEC que no es lo que Sector mide.
    setSeleccion(SELECCION_VACIA)
  }

  // El cruce contra el universo y la resolución a unidades enteras viven en el hook desde la
  // Tanda 13: `CarteraEditable` muestra las mismas posiciones en su bloque de renta variable y los
  // dos paneles tienen que dar el mismo número.
  const {
    posiciones: posicionesRv,
    resueltas,
    porTicker,
    subtotalUsd: subtotalRvUsd,
    hayAlgunaResuelta: hayAlgunaRvResuelta,
  } = useRentaVariableResuelta()

  // F-027: sólo se pide a la SEC por los CEDEARs de la cartera (las acciones heredadas de una
  // cartera vieja quedan fuera — el endpoint no las reconoce, `sec_calendario.py` sólo cubre
  // CEDEARs). Se deriva de `posicionesRv`/`porTicker`, no de un estado propio: la lista de papeles
  // a pedir es la misma cartera, así que no hay nada que sincronizar.
  const papelesCedear = useMemo(
    () =>
      posicionesRv
        .map((p) => porTicker.get(p.ticker))
        .filter((e): e is EspecieRentaVariable => e !== undefined && e.clase_activo === 'cedear')
        .map(papelSecDe),
    [posicionesRv, porTicker],
  )
  const balances = useCalendarioBalances(papelesCedear)

  // GWT-4: el monto total incluye las dos porciones, cada una con su subtotal identificado. Sin
  // ninguna de las dos resuelta no hay total que declarar — no es 0, es sin dato.
  //
  // Un lado sin resolver sólo aporta 0 si genuinely no tiene posiciones: con posiciones pendientes
  // de resolver, foldearlo a 0 inflaría el mix del otro lado al 100% (bug detectado en el
  // relevamiento de confiabilidad de datos del 16/08/2026) — acá se propaga `null` en su lugar.
  const contribucionRf = hayRfResuelta ? subtotalRfUsd : resueltasRf.length === 0 ? 0 : null
  const contribucionRv = subtotalRvUsd !== null ? subtotalRvUsd : posicionesRv.length === 0 ? 0 : null
  const totalUsd =
    hayRfResuelta || hayAlgunaRvResuelta
      ? contribucionRf !== null && contribucionRv !== null
        ? contribucionRf + contribucionRv
        : null
      : null

  // Mix pedido: sobre `peso` (puntos porcentuales sobre la cartera entera), sin pasar por precio
  // ni tipo de cambio — siempre calculable si hay posiciones.
  const pesoRvPedido = sumaPesos(posicionesRv)
  const pesoRfPedido = sumaPesos(pos) - pesoRvPedido

  // Mix real: sobre lo efectivamente invertido en dólares. Es otra cuenta — puede no coincidir
  // con el mix pedido si falta precio, tipo de cambio o si el redondeo por lámina movió algo — y
  // sin `totalUsd` no hay de qué ser un porcentaje.
  const mixRealRf = totalUsd !== null && totalUsd > 0 && hayRfResuelta ? (subtotalRfUsd / totalUsd) * 100 : null
  const mixRealRv =
    totalUsd !== null && totalUsd > 0 && subtotalRvUsd !== null ? (subtotalRvUsd / totalUsd) * 100 : null

  // Cuántas de las posiciones aportaron plata al reparto. Es el numerador de la leyenda: decir
  // sobre qué se midió va antes de mostrar cualquier número (mismo criterio que `leyendaDelPeso`).
  const medidas = cuantasSeMidieron(resueltas, porTicker)
  const alertasDeTope = alertasArmado.filter(esAlertaDeTopeRv)

  const yaEnCartera = new Set(posicionesRv.map((p) => p.ticker))
  const listaPicker = cedears.data ?? []
  const cargandoPicker = cedears.isPending
  const erroresPicker = cedears.isError

  // El texto de cada opción de Sector y Rubro específico — F-079. `valorDe` de esas dos dimensiones
  // es el código (`sector_codigo`, `sic_codigo`) para que la jerarquía y la comparación de
  // `facetar()` corran sobre un valor estable; el texto que ve el asesor es la etiqueta ES cuando
  // el curado la tiene, y si no el nombre oficial del major group (SIC Manual de OSHA,
  // `sector_titulo`, 30/08/2026) — nunca vacío mientras haya `sector_codigo` reconocido, mismo
  // fallback que ya usa `rubroEspecifico` con `sic_titulo` y que usa el backend en `especies.py`.
  const etiquetaSector = useMemo(() => {
    const mapa = new Map<string, string>()
    for (const e of listaPicker) {
      if (e.sector_codigo === null || mapa.has(e.sector_codigo)) continue
      mapa.set(e.sector_codigo, e.sector ?? e.sector_titulo ?? e.sector_codigo)
    }
    return mapa
  }, [listaPicker])
  const etiquetaRubroEspecifico = useMemo(() => {
    const mapa = new Map<string, string>()
    for (const e of listaPicker) {
      if (e.sic_codigo === null || mapa.has(e.sic_codigo)) continue
      // `rubro_especifico` (ES, curado) primero; si no hay fila en el curado, `sic_titulo` (inglés,
      // tal como lo publica la SEC) — nunca vacío mientras haya `sic_codigo`, mismo fallback
      // declarado que usa el backend en `especies.py`.
      mapa.set(e.sic_codigo, e.rubro_especifico ?? e.sic_titulo ?? e.sic_codigo)
    }
    return mapa
  }, [listaPicker])
  function textoDeOpcion(id: string, valor: string): string {
    if (id === 'sector') return etiquetaSector.get(valor) ?? valor
    if (id === 'rubroEspecifico') return etiquetaRubroEspecifico.get(valor) ?? valor
    return valor
  }

  // El facetado del picker, sobre el motor genérico `facetar()` de `lib/facetado.ts` — F-078.
  //
  // Hasta acá eran dos selects (rubro ⇄ eslabón) con la cascada escrita a mano: cada uno calculaba
  // sus opciones sobre la lista filtrada por el otro, y cada selección se validaba contra las
  // opciones del propio. Con dos dimensiones eso se tolera; con cinco son veinte pares que
  // mantener a mano, y el mismo motor ya está portado tres veces (barra de la cordillera, monitor
  // de renta variable). La semántica que aporta —leave-one-out para que cada select pueda pivotar,
  // orden de validación de lo general a lo específico para que dos selecciones incompatibles no se
  // apaguen las dos— es exactamente la que el código a mano venía imitando.
  //
  // **Sin centinelas de "sin dato"**, a diferencia del mismo facetado en el monitor. Allá "mostrame
  // los papeles sin rubro" es una pregunta legítima sobre la cobertura del universo; acá el picker
  // sirve para elegir qué comprar, y "los que no sabemos qué son" no es un criterio de compra. Lo
  // faltante se declara igual: en los tramos "sin dato" de las barras de composición de arriba.
  //
  // El preset temático entra como `pasaBase` y no como faceta: es una elección explícita y visible
  // —el chip está prendido— que no se apaga sola, y encima "metales preciosos" no es un valor de
  // ninguna dimensión sino la unión de tres declaraciones de fuentes distintas (`lib/presetsRv.ts`).
  const facetas: Array<Faceta<EspecieRentaVariable>> = DIMENSIONES_PICKER.map((dimension) => ({
    id: dimension.id,
    seleccion: seleccion[dimension.id] === null ? [] : [seleccion[dimension.id] as string],
    coincide: (especie, valor) => dimension.valorDe(especie) === valor,
    valores: (especie) => {
      const valor = dimension.valorDe(especie)
      return valor === null ? [] : [valor]
    },
  }))
  const facetado = facetar(listaPicker, facetas, (especie) =>
    preset?.filtroRv === undefined
      ? true
      : cumpleFiltroRv(especie, preset.filtroRv, preset.modoFiltroRv ?? 'interseccion'),
  )

  /** Los valores ofrecibles de una dimensión, ordenados. El orden es de presentación y nada más:
   *  ninguna de estas dimensiones tiene jerarquía propia. Para Región, País y Estrategia son los
   *  nombres tal como los publica la fuente (`Office of Finance` no se traduce). Para Sector y
   *  Rubro específico son códigos de ancho fijo (dos y cuatro dígitos), así que ordenar el string
   *  también los ordena numéricamente. */
  function opcionesDe(id: string): string[] {
    return [...(facetado.opciones.get(id) ?? [])].sort((a, b) => a.localeCompare(b, 'es-AR'))
  }
  /** Lo que esa dimensión de verdad está filtrando: una selección sin respaldo bajo las demás se
   *  cae a "todos" y `facetar` la declara en `apagadas`. */
  function efectivaDe(id: string): string {
    return facetado.efectivas.get(id)?.[0] ?? ''
  }

  /**
   * Saca una sugerencia y deja al asesor eligiendo con qué cambiarla.
   *
   * Es composición de lo que ya existe —quitar la posición y usar el buscador—, no un flujo nuevo:
   * el reemplazo no es una operación atómica del dominio, es "esta no me sirve, dame otra". Se
   * pre-filtra por el sector de la que se saca cuando el dato existe, que es el caso de uso real
   * ("otro banco, no este"); sin clasificación no se filtra nada en vez de inventar una
   * equivalencia.
   */
  function reemplazar(ticker: string) {
    const sector = porTicker.get(ticker)?.sector_codigo ?? null
    alternarRentaVariable(ticker)
    if (sector !== null) {
      // Las otras cuatro dimensiones se limpian junto con el sector nuevo. Con `facetar()` una
      // selección incompatible ya no invalida a las demás —gana la más general y la otra queda
      // declarada en `apagadas`—, pero el resultado seguiría siendo un picker acotado por un
      // rubro específico que el asesor eligió para otra búsqueda. Este flujo es "otro banco, no
      // este": lo único que se conserva es el sector.
      setSeleccion({ ...SELECCION_VACIA, sector })
    }
    setBusqueda('')
    refBuscador.current?.focus()
  }

  // El buscador ofrece **papeles, no especies**: AAPL, AAPLC y AAPLD son el mismo CEDEAR en
  // pesos, cable y MEP, y listarlos como tres opciones distintas obligaba al asesor a reconocerlos
  // de memoria. El agrupamiento viene del backend, ya contrastado contra el tipo de cambio del
  // universo (`app/renta_variable/agrupamiento.py`).
  //
  // Los filtros de rubro y eslabón se aplican **antes** de agrupar, sobre cada especie: son
  // atributos de la empresa, así que las hermanas los comparten y filtrar antes o después da lo
  // mismo — salvo que una hermana no tenga la clasificación cargada, y en ese caso lo correcto es
  // que no arrastre al papel entero.
  const filtradaPicker = listaPicker.filter((especie) =>
    facetas.every((faceta) => {
      const efectiva = facetado.efectivas.get(faceta.id) ?? []
      return efectiva.length === 0 || efectiva.some((valor) => faceta.coincide(especie, valor))
    }),
  ).filter((especie) =>
    preset?.filtroRv === undefined
      ? true
      : cumpleFiltroRv(especie, preset.filtroRv, preset.modoFiltroRv ?? 'interseccion'),
  )
  const papelesFiltrados = agruparEnPapeles(filtradaPicker).filter((papel) =>
    papelCoincide(papel, busqueda),
  )

  return (
    <div>
      <header style={{ marginBottom: 8 }}>
        <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>
          CEDEARs — y, si venían de una cartera anterior, acciones ya cargadas. Fuera del cálculo
          de renta fija, de la TIR, la duración y los cuatro rendimientos por naturaleza de tasa.
        </p>
      </header>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginBottom: 12 }}>
        <Campo etiqueta="Renta fija (USD)">{hayRfResuelta ? fmtMonto(subtotalRfUsd, 'usd') : SIN_DATO}</Campo>
        <Campo etiqueta="Renta variable (USD)">{subtotalRvUsd !== null ? fmtMonto(subtotalRvUsd, 'usd') : SIN_DATO}</Campo>
        <Campo etiqueta="Total de la cartera (USD)">{totalUsd !== null ? fmtMonto(totalUsd, 'usd') : SIN_DATO}</Campo>
        <Campo etiqueta="Σ pedido RV">{pos.length > 0 ? fmtPct(pesoRvPedido, 1) : SIN_DATO}</Campo>
        <Campo etiqueta="Mix pedido RF/RV">
          {pos.length > 0 ? `${fmtPct(pesoRfPedido, 1)} / ${fmtPct(pesoRvPedido, 1)}` : SIN_DATO}
        </Campo>
        <Campo etiqueta="Mix real RF/RV (sobre invertido)">
          {mixRealRf !== null && mixRealRv !== null ? `${fmtPct(mixRealRf, 1)} / ${fmtPct(mixRealRv, 1)}` : SIN_DATO}
        </Campo>
      </div>

      {posicionesRv.length === 0 ? (
        <p style={{ margin: '0 0 12px', fontSize: 12, color: 'var(--sd)' }}>
          Sin acciones ni CEDEARs en la cartera. Buscá un ticker abajo para sumarlo.
        </p>
      ) : (
        <div
          role="list"
          aria-label="Renta variable en la cartera"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(268px, 1fr))',
            gap: 10,
            background: 'var(--pan2)',
            padding: 10,
            borderRadius: 4,
            marginBottom: 14,
          }}
        >
          {posicionesRv.map((posicion) => {
            const especie = porTicker.get(posicion.ticker) ?? null
            const esCedear = especie?.clase_activo === 'cedear'
            return (
              <TarjetaRentaVariable
                key={posicion.ticker}
                posicion={posicion}
                especie={especie}
                resuelta={resueltas.find((r) => r.ticker === posicion.ticker) ?? null}
                onAbrir={() => abrirInstrumento(posicion.ticker)}
                onQuitar={() => alternarRentaVariable(posicion.ticker)}
                onReemplazar={() => reemplazar(posicion.ticker)}
                onFijarPeso={(peso) => fijarPeso(posicion.ticker, peso)}
                calendarioBalances={
                  esCedear && especie ? balances.porPapel.get(papelSecDe(especie)) : undefined
                }
                cargandoBalances={esCedear && balances.isPending}
              />
            )
          })}
        </div>
      )}

      {/* La composición que se le muestra al cliente: en qué quedó su plata, por los mismos cinco
          ejes que el armador acota con sus topes. Pesada por monto invertido y no por cantidad de
          papeles — es una cartera, no un universo—, y con el faltante como tramo propio. */}
      {posicionesRv.length > 0 && (
        <section aria-label="Composición de la renta variable" style={{ marginBottom: 14 }}>
          <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>
            {leyendaDelMontoRv(medidas, posicionesRv.length)} Lo que no declara el dato de un eje va
            a su propio tramo, nunca repartido entre los demás.
          </p>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
              gap: 14,
              background: 'var(--pan2)',
              padding: 10,
              borderRadius: 4,
            }}
          >
            {EJES_COMPOSICION.map((eje) => (
              <DistribucionBarras
                key={eje}
                titulo={tituloDelEje(eje)}
                tramos={composicionRvPor(resueltas, porTicker, eje)}
                vacio="Ninguna posición se pudo valuar: no hay monto que repartir."
              />
            ))}
          </div>
        </section>
      )}

      {/* Las alertas de tope se muestran acá y no en el panel del formulario: es donde el asesor
          está mirando la cartera que el tope produjo. Son del **último armado asistido** —nada del
          frontend puede recalcularlas, son la explicación de una decisión del motor—, así que se
          dice, para que editar posiciones a mano no las haga leer como un diagnóstico de la cartera
          de este instante. */}
      {alertasDeTope.length > 0 && (
        <section aria-label="Alertas de los topes de renta variable" style={{ marginBottom: 14 }}>
          <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>
            Topes de diversificación, del último armado asistido:
          </p>
          <AlertasCalendario alertas={alertasDeTope} />
        </section>
      )}

      {/* Una sola leyenda a nivel bloque: cada tarjeta sólo marca sus doce celdas, la explicación
          del criterio va acá una vez. Sólo aparece si hay al menos un CEDEAR — sin CEDEARs no se
          le pidió nada a la SEC (ver `papelesCedear`). */}
      {papelesCedear.length > 0 && (
        <p style={{ margin: '0 0 12px', fontSize: 10.5, color: 'var(--dim)' }}>
          Balances: patrón histórico de presentaciones ante la SEC (SEC EDGAR) — no es fecha
          confirmada. Los emisores privados extranjeros sólo muestran patrón anual.
        </p>
      )}

      <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
        <input
          ref={refBuscador}
          type="text"
          value={busqueda}
          onChange={(evento) => setBusqueda(evento.target.value)}
          placeholder="Buscar ticker o nombre…"
          aria-label="Buscar CEDEAR por ticker o nombre"
          className="mono"
          style={{
            marginLeft: 8,
            flex: 1,
            minWidth: 120,
            fontSize: 12,
            color: 'var(--tx)',
            background: 'var(--pan2)',
            border: '1px solid var(--lin)',
            borderRadius: 3,
            padding: '4px 8px',
          }}
        />
      </div>

      {/* Los cinco ejes por los que se busca un papel. Sector y Rubro específico se muestran
          siempre —son la pareja histórica de rubro⇄eslabón y su vacío ya está explicado por el
          aviso de abajo—; los otros tres aparecen sólo cuando tienen algo que ofrecer: un select
          con la única opción "todos" no es un filtro, es ruido. Que país y región no aparezcan
          hasta que corra la siembra del curado es el estado esperado, y las barras de composición
          de arriba lo declaran con su tramo "sin dato". */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        {DIMENSIONES_PICKER.map((dimension) => {
          const opciones = opcionesDe(dimension.id)
          if (opciones.length === 0 && !dimension.siempreVisible) return null
          return (
            <CampoSelect
              key={dimension.id}
              etiqueta={dimension.etiqueta}
              valor={efectivaDe(dimension.id)}
              onChange={(valor) => fijarDimension(dimension.id, valor === '' ? null : valor)}
              opciones={[
                { valor: '', texto: 'todos' },
                ...opciones.map((opcion) => ({
                  valor: opcion,
                  texto: textoDeOpcion(dimension.id, opcion),
                })),
              ]}
            />
          )
        })}
      </div>

      {/* Sin clasificación, los dos selects quedan con una sola opción y filtrar por sector no
          devuelve nada. Decirlo evita que una lista vacía se lea como "no hay papeles de este
          sector" cuando en realidad es que el dato todavía no se trajo (regla 1). */}
      {!cargandoPicker && !erroresPicker && opcionesDe('sector').length === 0 && listaPicker.length > 0 && (
        <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--ac2)' }}>{SIN_PERFILES_DE_EMPRESA}</p>
      )}

      {/* Lo que se pidió y no tiene respaldo bajo el resto de las selecciones. `facetar()` lo apaga
          para no dejar la lista vacía, y acá se dice: un filtro que dejó de aplicarse en silencio
          hace que el asesor lea la lista como si todavía estuviera acotada. */}
      {facetado.apagadas.length > 0 && (
        <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--ac2)' }}>
          Sin efecto sobre esta búsqueda:{' '}
          {facetado.apagadas
            .map(
              ({ dimension, valor }) =>
                `${etiquetaDimension(dimension)} "${textoDeOpcion(dimension, valor)}"`,
            )
            .join(', ')}
          . Ningún papel cumple eso junto con el resto de lo elegido.
        </p>
      )}

      {cargandoPicker && <p style={{ fontSize: 11.5, color: 'var(--dim)' }}>Cargando especies…</p>}
      {erroresPicker && <p style={{ fontSize: 11.5, color: 'var(--neg)' }}>No se pudo traer el universo de renta variable.</p>}
      {!cargandoPicker && !erroresPicker && (
        <div
          role="list"
          aria-label="Resultados de CEDEARs"
          style={{ maxHeight: 176, overflowY: 'auto', border: '1px solid var(--lin)', borderRadius: 4 }}
        >
          {papelesFiltrados.length === 0 ? (
            <p style={{ margin: 0, padding: '8px 10px', fontSize: 11.5, color: 'var(--dim)' }}>
              Ningún ticker coincide con la búsqueda.
            </p>
          ) : (
            papelesFiltrados.map((papel) => (
              <FilaPicker
                key={papel.id}
                papel={papel}
                enCartera={yaEnCartera}
                onAbrir={(ticker) => abrirInstrumento(ticker)}
                onAlternar={(ticker) => alternarRentaVariable(ticker)}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <span style={{ fontSize: 10, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {etiqueta}
      </span>
      <span className="mono" style={{ fontSize: 14, color: 'var(--tx)' }}>
        {children}
      </span>
    </div>
  )
}

/**
 * Un papel en el buscador, con sus monedas de liquidación al lado.
 *
 * Antes había una fila por especie: `AAPL`, `AAPLC` y `AAPLD` eran tres opciones. Ahora es una
 * fila por papel y un botón por moneda — el asesor elige Apple y después en qué dólar lo quiere,
 * que es el orden en que lo piensa.
 *
 * **La moneda que no operó no se ofrece.** Sin precio no hay con qué resolver nominales
 * (`lib/resolverRentaVariable.ts`), así que se muestra apagada y sin acción en vez de dejar
 * agregar algo que después no se puede valuar.
 */
function FilaPicker({
  papel,
  enCartera,
  onAbrir,
  onAlternar,
}: {
  papel: PapelRentaVariable
  enCartera: Set<string>
  onAbrir: (ticker: string) => void
  onAlternar: (ticker: string) => void
}) {
  const { representante } = papel
  return (
    <div
      role="listitem"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '5px 8px',
        borderBottom: '1px solid var(--lin)',
      }}
    >
      <button
        type="button"
        onClick={() => onAbrir(representante.ticker)}
        className="mono"
        style={{
          font: 'inherit',
          fontSize: 12,
          color: 'var(--tx)',
          background: 'transparent',
          border: 'none',
          textDecoration: 'underline',
          textUnderlineOffset: 2,
          cursor: 'pointer',
          padding: 0,
        }}
      >
        {papel.emision}
      </button>
      <BadgeClase claseActivo={representante.clase_activo} />

      {/* La fuente no explica qué es esta especie: se declara en vez de esconderla o de inventarle
          una categoría (regla 1). */}
      {papel.noIdentificado && (
        <span
          title="BYMA publica esta especie pero no documenta qué es; nunca registró operaciones"
          style={{
            fontSize: 9.5,
            color: 'var(--ac2)',
            border: '1px solid var(--ac2)',
            borderRadius: 3,
            padding: '0 4px',
            cursor: 'help',
          }}
        >
          n/n
        </span>
      )}

      <FichaDelPapel especie={representante} />

      <div style={{ display: 'flex', gap: 4, marginLeft: 'auto', alignItems: 'center' }}>
        {papel.especies.map(({ especie, rotulo, opera }) => {
          const dentro = enCartera.has(especie.ticker)
          return (
            <button
              key={especie.ticker}
              type="button"
              onClick={() => onAlternar(especie.ticker)}
              disabled={!opera && !dentro}
              title={
                opera
                  ? `${especie.ticker} · ${especie.precio}`
                  : `${especie.ticker} no operó: sin precio no se puede valuar`
              }
              aria-label={
                dentro
                  ? `sacar ${especie.ticker} de la cartera`
                  : `agregar ${especie.ticker} a la cartera`
              }
              style={{
                font: 'inherit',
                fontSize: 10.5,
                color: dentro ? 'var(--ac)' : opera ? 'var(--tx)' : 'var(--sd)',
                background: dentro ? 'var(--sel)' : 'transparent',
                border: `1px solid ${dentro ? 'var(--ac)' : 'var(--lin)'}`,
                borderRadius: 3,
                padding: '2px 6px',
                cursor: opera || dentro ? 'pointer' : 'default',
              }}
            >
              {dentro ? '✓ ' : ''}
              {rotulo}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function TarjetaRentaVariable({
  posicion,
  especie,
  resuelta,
  onAbrir,
  onQuitar,
  onReemplazar,
  onFijarPeso,
  calendarioBalances,
  cargandoBalances,
}: {
  posicion: PosicionArmador
  especie: EspecieRentaVariable | null
  resuelta: PosicionRvResuelta | null
  onAbrir: () => void
  onQuitar: () => void
  /** Saca esta posición y deja el buscador listo para elegir la que la reemplaza. */
  onReemplazar: () => void
  onFijarPeso: (peso: number) => void
  /** `undefined`: no es CEDEAR, o el pedido todavía no trajo este papel. */
  calendarioBalances: CalendarioBalances | undefined
  cargandoBalances: boolean
}) {
  const variacionPct = especie?.variacion == null ? null : especie.variacion * 100
  const colorVariacion =
    variacionPct === null ? 'var(--ac2)' : variacionPct > 0 ? 'var(--pos)' : variacionPct < 0 ? 'var(--neg)' : 'var(--tx)'
  const textoVariacion = variacionPct === null ? SIN_DATO : `${variacionPct > 0 ? '+' : ''}${fmtPct(variacionPct)}`
  const ticker = especie?.ticker ?? resuelta?.ticker ?? posicion.ticker

  const pesoReal = resuelta?.pesoReal ?? null
  const difiere = pesoReal !== null && Math.abs(pesoReal - posicion.peso) > TOLERANCIA_DIFERENCIA_FILA

  return (
    <article
      aria-label={ticker}
      style={{
        background: 'var(--pan)',
        border: '1px solid var(--lin)',
        borderRadius: 4,
        padding: '8px 10px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <button
          type="button"
          onClick={onAbrir}
          className="mono"
          style={{
            font: '600 14px inherit',
            color: 'var(--tx)',
            background: 'transparent',
            border: 'none',
            textDecoration: 'underline',
            textUnderlineOffset: 2,
            cursor: 'pointer',
            padding: 0,
          }}
        >
          {ticker}
        </button>
        {/* La clase sale del badge y no de un ternario "si no es acción, es CEDEAR": ese descarte
            etiquetaba mal cualquier valor nuevo que apareciera. Acá al lado queda el nombre de la
            empresa, que es el otro dato que identifica al papel. */}
        <BadgeClase claseActivo={especie?.clase_activo} />
        <span
          style={{
            fontSize: 10.5,
            color: 'var(--dim)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            minWidth: 0,
          }}
          title={
            especie?.nombre_largo
              ? `Empresa según ${especie.perfil_fuente ?? 'una corrida anterior'} · capturado ${fmtFecha(especie.perfil_capturado_en)}`
              : undefined
          }
        >
          {/* Sin perfil de empresa el espacio va vacío: el job de clasificación todavía no pasó
              por este ticker y no hay nombre que mostrar (regla 1). */}
          {especie?.nombre_largo ?? SIN_DATO}
        </span>
        <span className="mono" style={{ marginLeft: 'auto', fontSize: 12, color: colorVariacion }}>
          {textoVariacion}
        </span>
        <button
          type="button"
          onClick={onReemplazar}
          aria-label={`reemplazar ${ticker} por otro activo`}
          title="sacarlo y buscar otro en su lugar"
          style={{ font: 'inherit', fontSize: 10.5, border: '1px solid var(--lin)', borderRadius: 3, padding: '2px 6px', background: 'transparent', color: 'var(--dim)', cursor: 'pointer' }}
        >
          cambiar
        </button>
        <button
          type="button"
          onClick={onQuitar}
          aria-label={`sacar ${ticker} de la cartera`}
          style={{ font: 'inherit', fontSize: 13, border: 'none', background: 'transparent', color: 'var(--dim)', cursor: 'pointer' }}
        >
          ×
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6, marginTop: 8 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ fontSize: 9.5, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            % pedido
          </span>
          <input
            type="number"
            className="mono"
            value={posicion.peso}
            step={0.1}
            onChange={(evento) => onFijarPeso(Number(evento.target.value) || 0)}
            aria-label={`ponderación pedida de ${ticker}`}
            style={{
              width: '100%',
              textAlign: 'right',
              font: 'inherit',
              fontSize: 12,
              color: 'var(--ac)',
              background: 'var(--pan2)',
              border: '1px solid var(--lin)',
              borderRadius: 3,
              padding: '2px 4px',
            }}
          />
        </div>
        <Metrica etiqueta="% real" nota="Ponderación efectiva dentro del bloque de renta variable, sobre lo invertido.">
          <span style={{ color: difiere ? 'var(--ac2)' : 'var(--tx)' }}>
            {pesoReal !== null ? fmtPct(pesoReal) : SIN_DATO}
          </span>
        </Metrica>
        <Metrica etiqueta="Invertido">
          {resuelta?.invertidoUsd !== null && resuelta?.invertidoUsd !== undefined ? fmtMonto(resuelta.invertidoUsd, 'usd') : SIN_DATO}
        </Metrica>
        {/* Siempre s/d: no hay fuente de dividendos en el universo consolidado. Nunca se estima
            (regla 1 del dominio) — ver comentario del módulo. */}
        <Metrica etiqueta="Div. est." nota="Sin fuente de dividendos: nunca se estima.">
          {SIN_DATO}
        </Metrica>
      </div>

      {/* F-027, sólo CEDEARs — una acción heredada de una cartera vieja no tiene celdas: el
          calendario no le pide nada a la SEC (`papelesCedear` la excluye río arriba). */}
      {especie?.clase_activo === 'cedear' && (
        <div style={{ marginTop: 8 }}>
          <span
            style={{
              fontSize: 9.5,
              color: 'var(--dim)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            Balances
          </span>
          <div style={{ marginTop: 2 }}>
            <PatronBalances calendario={calendarioBalances} cargando={cargandoBalances} />
          </div>
        </div>
      )}
    </article>
  )
}

function Metrica({ etiqueta, nota, children }: { etiqueta: string; nota?: string; children: ReactNode }) {
  return (
    <div title={nota} style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <span style={{ fontSize: 9.5, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {etiqueta}
      </span>
      <span className="mono" style={{ fontSize: 12, color: 'var(--tx)' }}>
        {children}
      </span>
    </div>
  )
}

/**
 * Qué es este papel, en una línea: nombre, a qué se dedica y en qué sector está.
 *
 * Todo sale de fuente y nada se completa: la SEC cubre el 74 % de los CEDEARs y el 9 % de las
 * acciones argentinas, así que la mayoría de los papeles locales va a mostrar sólo el ticker hasta
 * que la CNV entre como fuente (F-054). Un papel sin clasificar **no muestra nada** en vez de
 * mostrar el sector de otra empresa parecida.
 *
 * El `title` lleva el detalle largo —el código SIC, el rubro de la SEC, el ratio— porque son datos
 * de auditoría: hacen falta cuando alguien pregunta de dónde salió, no mientras se arma.
 */
function FichaDelPapel({ especie }: { especie: EspecieRentaVariable }) {
  const nombre = especie.nombre_largo
  const esFondo = especie.estrategia_etf !== null

  const detalle = [
    especie.sic_codigo && `SIC ${especie.sic_codigo}`,
    especie.sic_oficina,
    especie.ratio_conversion && `ratio ${especie.ratio_conversion}`,
    especie.mercado_origen,
  ]
    .filter(Boolean)
    .join(' · ')

  if (!nombre && !especie.sic_titulo && !esFondo) return null

  return (
    <span
      style={{ display: 'flex', gap: 6, alignItems: 'baseline', minWidth: 0, overflow: 'hidden' }}
      title={detalle || undefined}
    >
      {nombre && (
        <span
          style={{
            fontSize: 11,
            color: 'var(--tx)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {nombre}
        </span>
      )}
      {esFondo ? (
        <span style={{ fontSize: 9.5, color: 'var(--dim)', whiteSpace: 'nowrap' }}>
          fondo · {ETIQUETA_ESTRATEGIA[especie.estrategia_etf ?? ''] ?? especie.estrategia_etf}
        </span>
      ) : (
        especie.sic_titulo && (
          <span
            style={{
              fontSize: 9.5,
              color: 'var(--dim)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {especie.sic_titulo}
            {/* Sector en ES (F-079) y no el eslabón productivo: es la dimensión que reemplaza al
                eslabón como agrupador visible al lado del rubro específico en inglés de la SEC. */}
            {especie.sector && ` · ${especie.sector}`}
          </span>
        )
      )}
    </span>
  )
}

/** Cómo se lee cada estrategia en pantalla. Espejo de las claves de `app/renta_variable/etfs.py`. */
const ETIQUETA_ESTRATEGIA: Record<string, string> = {
  indice_amplio: 'índice amplio',
  equiponderado: 'equiponderado',
  factor: 'por factor',
  geografico: 'geográfico',
  sectorial: 'sectorial',
  activo_fisico: 'activo físico',
  cripto: 'cripto',
  esg: 'ESG',
  sin_clasificar: 'sin clasificar',
}
