/**
 * El bloque separado de renta variable — F-026, mockup A4 del design system.
 *
 * Acciones (69 verificadas) y CEDEARs (683 verificados), con subtotal propio, que suma al monto
 * total de la cartera y **queda afuera de todo cálculo de renta fija**: sin TIR, sin duración, sin
 * cupón, sin participar de ninguno de los cuatro rendimientos por naturaleza de tasa (regla 2 del
 * dominio). `posicionesRentaFija` (store, base común de la Tanda 9) ya excluye estas posiciones del
 * resolver de bonos y del calendario de cupones — este componente no repite esa frontera, la usa.
 *
 * ## Dos ausencias deliberadas contra el mockup, no dos olvidos
 *
 * 1. **Sin distribución por país ni por rubro.** El mockup A4 y la spec (F-026) piden esas dos
 *    distribuciones, pero `EspecieRentaVariable` (backend, F-052) sólo trae ticker, precio, moneda,
 *    cierre anterior, variación, volumen, puntas y operaciones — ni país, ni rubro, ni el nombre de
 *    la empresa. Construir la distribución hoy sería una pantalla con "país no informado" en el
 *    100% de las especies (regla 1: nunca inventar un dato, ni derivarlo del ticker). Queda para
 *    F-053, que trae la ficha de instrumento con esos datos recopilados aparte. Anotado en
 *    `claude-docs/planning/plan-ejecucion-tandas.md`, duda de solape 6.
 *
 *    La misma ausencia de datos deja sin "nombre/emisor" a la tarjeta del mockup: donde el diseño
 *    pide el emisor, acá va la clase (`Acción` / `CEDEAR`), que es el único dato descriptivo que
 *    existe hoy — no se inventa un nombre a partir del ticker.
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

import { useAbrirInstrumento } from '@/features/instrumento/useAbrirInstrumento'
import { fmtFecha, fmtMonto, fmtPct, SIN_DATO } from '@/lib/fmt'
import { type EspecieRentaVariable, useRentaVariable } from '@/lib/rentaVariable'

import { BadgeClase } from './BadgeClase'
import { PatronBalances } from './PatronBalances'
import { agruparEnPapeles, papelCoincide, type PapelRentaVariable } from '../lib/papelesRentaVariable'
import { type CalendarioBalances } from '../lib/esquemaBalances'
import { useCalendarioBalances } from '../hooks/useCalendarioBalances'
import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { useRentaVariableResuelta } from '../hooks/useRentaVariableResuelta'
import { sumaPesos } from '../lib/mix'
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

const estiloSelectPicker = {
  minWidth: 140,
  font: 'inherit',
  fontSize: 12,
  padding: '4px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const

export function BloqueRentaVariable() {
  const { pos, tematicaId } = useArmador()
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
  // Rubro y eslabón salen de la clasificación de la SEC (13/08/2026), no del perfil de Yahoo: ese
  // job quedó bloqueado y la tabla nunca tuvo un solo sector cargado, así que los dos selects
  // estaban siempre vacíos. Ver `app/renta_variable/clasificacion.py`.
  const [rubroFiltro, setRubroFiltro] = useState<string | null>(null)
  const [eslabonFiltro, setEslabonFiltro] = useState<string | null>(null)

  // Un preset temático (Tanda 13) filtra los dos lados a la vez: la grilla de bonos por su sector
  // y este bloque por el rubro equivalente de la SEC. El rubro del preset se aplica al cambiar de
  // temática y después queda editable — el chip es un punto de partida, no un modo.
  const [tematicaAplicada, setTematicaAplicada] = useState<string | null>(null)
  if (tematicaId !== tematicaAplicada) {
    setTematicaAplicada(tematicaId)
    setRubroFiltro(presetPorId(tematicaId)?.rubroRv ?? null)
    setEslabonFiltro(null)
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

  const yaEnCartera = new Set(posicionesRv.map((p) => p.ticker))
  const listaPicker = cedears.data ?? []
  const cargandoPicker = cedears.isPending
  const erroresPicker = cedears.isError

  // Opciones del filtro: sólo las que de verdad aparecen en esta clase, ordenadas alfabéticamente
  // (orden de presentación — rubro y eslabón no tienen jerarquía propia que ordenar por otro
  // criterio). Los nombres van tal como los publica la fuente: `Office of Finance` no se traduce
  // (regla 11), y la SEC hasta publica rubros ambiguos como `Office of Finance or Office of Crypto
  // Assets`, que se muestran así porque así vienen.
  //
  // Facetado bidireccional (14/08/2026): las opciones de cada select se calculan sobre la lista
  // filtrada por EL OTRO filtro, no por ambos — así el select propio siempre puede pivotar, y
  // ninguna opción visible produce una lista vacía. Se usa el filtro crudo, no el efectivo de
  // abajo: si una selección quedó inválida, su faceta se comporta como "todos" y las opciones del
  // otro select vuelven a abrirse solas.
  const rubrosPicker = [
    ...new Set(
      listaPicker
        .filter((e) => eslabonFiltro === null || e.division_cadena === eslabonFiltro)
        .map((e) => e.sic_oficina)
        .filter((s): s is string => s !== null),
    ),
  ].sort()
  const eslabonesPicker = [
    ...new Set(
      listaPicker
        .filter((e) => rubroFiltro === null || e.sic_oficina === rubroFiltro)
        .map((e) => e.division_cadena)
        .filter((d): d is string => d !== null),
    ),
  ].sort()

  // Una selección que el facetado dejó sin opciones no se aplica ni se muestra: se cae a "todos".
  // Derivado, no sincronizado: setState en cascada entre dos selects es una carrera perdida.
  const rubroEfectivo = rubroFiltro !== null && rubrosPicker.includes(rubroFiltro) ? rubroFiltro : null
  const eslabonEfectivo =
    eslabonFiltro !== null && eslabonesPicker.includes(eslabonFiltro) ? eslabonFiltro : null

  /**
   * Saca una sugerencia y deja al asesor eligiendo con qué cambiarla.
   *
   * Es composición de lo que ya existe —quitar la posición y usar el buscador—, no un flujo nuevo:
   * el reemplazo no es una operación atómica del dominio, es "esta no me sirve, dame otra". Se
   * pre-filtra por el rubro de la que se saca cuando el dato existe, que es el caso de uso real
   * ("otro banco, no este"); sin clasificación no se filtra nada en vez de inventar una
   * equivalencia.
   */
  function reemplazar(ticker: string) {
    const rubro = porTicker.get(ticker)?.sic_oficina ?? null
    alternarRentaVariable(ticker)
    if (rubro !== null) {
      setRubroFiltro(rubro)
      // Mismo reset que el sync de temática: setear el rubro con un eslabón viejo activo dejaría
      // a los dos filtros invalidándose mutuamente por el facetado (cada uno queda fuera de las
      // opciones del otro) y los dos caerían a "todos" — perdiendo justo el rubro que este flujo
      // vino a poner.
      setEslabonFiltro(null)
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
  const filtradaPicker = listaPicker.filter((e) => {
    if (rubroEfectivo !== null && e.sic_oficina !== rubroEfectivo) return false
    if (eslabonEfectivo !== null && e.division_cadena !== eslabonEfectivo) return false
    return true
  })
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

      {/* Rubro y eslabón: de la clasificación de la SEC. Una clase sin ningún papel clasificado
          deja los selects con la única opción "todos" y no estorban — el aviso de abajo lo dice. */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        {/* "(SEC)" en la etiqueta visible, no sólo en el aria-label: el filtro de sector de la
            grilla de renta fija (más arriba en la misma página) ya se llama "Sector" a secas —
            dos selects con el mismo texto visible confundirían tanto a la vista como a un lector
            de pantalla. Y nombrar la fuente en la etiqueta es lo que evita que se lean como la
            misma taxonomía, que no lo son. */}
        <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: 'var(--dim)' }}>
          Rubro (SEC)
          <select
            value={rubroEfectivo ?? ''}
            onChange={(evento) => setRubroFiltro(evento.target.value === '' ? null : evento.target.value)}
            style={estiloSelectPicker}
          >
            <option value="">todos</option>
            {rubrosPicker.map((rubro) => (
              <option key={rubro} value={rubro}>
                {rubro}
              </option>
            ))}
          </select>
        </label>
        {/* El eslabón sale de la división del SIC Manual: en qué parte de la cadena productiva
            está la empresa (extracción, manufactura, comercio, servicios). */}
        <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: 'var(--dim)' }}>
          Eslabón productivo
          <select
            value={eslabonEfectivo ?? ''}
            onChange={(evento) => setEslabonFiltro(evento.target.value === '' ? null : evento.target.value)}
            style={estiloSelectPicker}
          >
            <option value="">todos</option>
            {eslabonesPicker.map((eslabon) => (
              <option key={eslabon} value={eslabon}>
                {eslabon}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Sin clasificación, los dos selects quedan con una sola opción y filtrar por rubro no
          devuelve nada. Decirlo evita que una lista vacía se lea como "no hay papeles de este
          rubro" cuando en realidad es que el dato todavía no se trajo (regla 1). */}
      {!cargandoPicker && !erroresPicker && rubrosPicker.length === 0 && listaPicker.length > 0 && (
        <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--ac2)' }}>{SIN_PERFILES_DE_EMPRESA}</p>
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
            especie?.nombre_corto
              ? `Empresa según Yahoo Finance · capturado ${fmtFecha(especie.perfil_capturado_en)}`
              : undefined
          }
        >
          {/* Sin perfil de empresa el espacio va vacío: el job de enriquecimiento todavía no pasó
              por este ticker y no hay nombre que mostrar (regla 1). */}
          {especie?.nombre_corto ?? SIN_DATO}
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
 * Qué es este papel, en una línea: nombre, a qué se dedica y en qué eslabón de la cadena está.
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
  const nombre = especie.nombre_largo ?? especie.nombre_corto
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
            {especie.division_cadena && ` · ${especie.division_cadena}`}
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
