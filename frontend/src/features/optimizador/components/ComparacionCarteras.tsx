/**
 * F-037 — la cartera original contra la propuesta, lado a lado, con la misma vara.
 *
 * "Misma vara" (GWT-1) no es una promesa, es una consecuencia de la implementación: las dos
 * columnas llaman a las mismas funciones puras (`rendimientosPorNaturaleza`, `vectorDeRiesgo`,
 * `calcularRentaAnualPorMoneda`) con las posiciones de cada lado — nunca hay una segunda fórmula
 * que pueda divergir de la primera.
 *
 * El costo total (F-035) no se suma en porcentaje: `costoAcumulado` lo lleva a plata sobre el
 * monto encadenado de cada pata y lo normaliza a USD (regla 3) — sumar `total_pct` de bases
 * distintas sería inventar un número. Lo no verificable o no convertible se declara con el ticker,
 * nunca se omite (regla 1).
 *
 * Los meses que cambian de cobertura (GWT-2) se marcan en la cordillera de la columna propuesta
 * vía `Cordillera`'s prop `marcas`, moneda por moneda — nunca se suma entre monedas para decidir
 * si "se llena" (regla 3), mismo criterio que el diff de F-036 (`diffCalendarioCarteras`).
 *
 * Reemplaza el calendario y el vector de riesgo que `PlanDeRotacion` mostraba de la cartera
 * propuesta sola (F-036): mostrarlos ahí y acá sería el mismo dato dos veces. `PlanDeRotacion`
 * quedó con su identidad real — la lista de aceptadas y Deshacer.
 */

import { useMemo } from 'react'

import { Cordillera } from '@/components/Cordillera'
import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { VectorDeRiesgo } from '@/components/VectorDeRiesgo'
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import type { Especie } from '@/lib/cartera/esquemaEspecie'
import { useCalendarioCartera } from '@/lib/cartera/hooks/useCalendarioCartera'
import { useConcentracion } from '@/lib/cartera/hooks/useConcentracion'
import { useEspeciesUniverso } from '@/lib/cartera/hooks/useEspeciesUniverso'
import {
  rendimientosPorNaturaleza,
  type PosicionPonderada,
  type RendimientoPorNaturaleza,
} from '@/lib/cartera/metricas'
import {
  calcularRentaAnualPorMoneda,
  columnasDeCordillera,
  invertidoPorMoneda,
  type RentaAnualPorMoneda,
} from '@/lib/cartera/renta'
import { vectorDeRiesgo, type EjeDeRiesgo, type PosicionConPeso } from '@/lib/cartera/riesgo'
import { fmtCompacto, fmtMonto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'
import { diffCalendarioCarteras, type EfectoCalendario } from '@/lib/rotaciones/efectoCalendario'
import { costoAcumulado, type CostoAcumulado, type PosicionConMonto } from '@/lib/rotaciones/plan'

import { formatoValor } from './compartidos'
import { usePlanRotacion } from '../store/planRotacionStore'

// --- helpers puros locales -------------------------------------------------------------------

function aPosicionPonderada(posiciones: PosicionConPeso[]): PosicionPonderada[] {
  return posiciones.map((p) => ({ ticker: p.ticker, peso: p.peso, pesoReal: null }))
}

/** Tickers cuyo monto difiere entre las dos carteras — los únicos que le importan a
 *  `diffCalendarioCarteras` para decidir si una falta de cronograma tumba el diff (ver su
 *  docstring: un ticker sin cronograma que está igual en las dos carteras no es un problema de
 *  la comparación). */
function tickersConMontoDistinto(a: PosicionConMonto[], b: PosicionConMonto[]): string[] {
  const montosA = new Map(a.map((p) => [p.ticker, p.monto]))
  const montosB = new Map(b.map((p) => [p.ticker, p.monto]))
  const tickers = new Set([...montosA.keys(), ...montosB.keys()])
  const distintos: string[] = []
  for (const ticker of tickers) {
    if ((montosA.get(ticker) ?? 0) !== (montosB.get(ticker) ?? 0)) distintos.push(ticker)
  }
  return distintos
}

/** `PosicionConMonto.monto` viaja en la moneda de cotización (ver `plan.ts`); `invertidoPorMoneda`
 *  necesita el monto normalizado a dólares para no mezclar cotización con moneda de cobro (regla
 *  3, mismo criterio que `costoAcumulado` de `plan.ts`). Sin moneda declarada o sin tipo de
 *  cambio para una posición en pesos, esa posición no aporta — no se le adivina nada. */
function aInvertidoUsd(
  posiciones: PosicionConMonto[],
  monedaDe: (ticker: string) => 'usd' | 'ars' | null,
  tipoDeCambio: number | null,
): { ticker: string; invertidoUsd: number | null }[] {
  return posiciones.map((p) => {
    const moneda = monedaDe(p.ticker)
    const invertidoUsd =
      moneda === 'usd' ? p.monto : moneda === 'ars' && tipoDeCambio !== null ? p.monto / tipoDeCambio : null
    return { ticker: p.ticker, invertidoUsd }
  })
}

function fmtMontoMoneda(valor: number, moneda: string): string {
  if (moneda === 'usd' || moneda === 'ars') return fmtMonto(valor, moneda)
  return `${moneda.toUpperCase()} ${fmtNumero(valor)}`
}

const ROTULO_MONEDA: Record<string, string> = { usd: 'dólares', ars: 'pesos' }

function marcasPorMoneda(
  efecto: EfectoCalendario | null,
  moneda: string,
): ReadonlyMap<string, 'se_llena' | 'se_vacia'> {
  const mapa = new Map<string, 'se_llena' | 'se_vacia'>()
  if (!efecto || !efecto.calculable) return mapa
  for (const mes of efecto.seLlenan) if (mes.moneda === moneda) mapa.set(mes.etiqueta, 'se_llena')
  for (const mes of efecto.seVacian) if (mes.moneda === moneda) mapa.set(mes.etiqueta, 'se_vacia')
  return mapa
}

// --- componente principal ----------------------------------------------------------------------

export function ComparacionCarteras({
  montosOriginales,
  montos,
  monedaDe,
  tipoDeCambio,
  perfil,
}: {
  montosOriginales: PosicionConMonto[]
  /** La cartera propuesta en plata — `propuesta.montos` de `useCarteraPropuesta`. */
  montos: PosicionConMonto[]
  monedaDe: (ticker: string) => 'usd' | 'ars' | null
  tipoDeCambio: number | null
  perfil: NombreDePerfil
}) {
  const plan = usePlanRotacion()
  const especiesUniverso = useEspeciesUniverso()
  const calendarioOriginal = useCalendarioCartera(montosOriginales)
  const calendarioPropuesto = useCalendarioCartera(montos)
  const concentracionOriginal = useConcentracion(plan.posicionesOriginales, perfil)
  const concentracionPropuesta = useConcentracion(plan.posicionesAcumuladas, perfil)

  // `Especie` trae todos los campos que piden `rendimientosPorNaturaleza` (naturaleza, duración,
  // rendimiento) y `vectorDeRiesgo` (clase de activo, ley, calificación...) a la vez — un solo mapa
  // sirve para las dos, mismo criterio estructural que `useCarteraCargadaValuada.ts`.
  const porTicker = useMemo(() => {
    const mapa = new Map<string, Especie>()
    for (const especie of especiesUniverso.data ?? []) mapa.set(especie.ticker, especie)
    return mapa
  }, [especiesUniverso.data])

  const rendimientosOriginal = useMemo(
    () => rendimientosPorNaturaleza(aPosicionPonderada(plan.posicionesOriginales), porTicker),
    [plan.posicionesOriginales, porTicker],
  )
  const rendimientosPropuesta = useMemo(
    () => rendimientosPorNaturaleza(aPosicionPonderada(plan.posicionesAcumuladas), porTicker),
    [plan.posicionesAcumuladas, porTicker],
  )

  const ejesOriginal = useMemo(
    () => vectorDeRiesgo(plan.posicionesOriginales, porTicker, concentracionOriginal.data ?? null),
    [plan.posicionesOriginales, porTicker, concentracionOriginal.data],
  )
  const ejesPropuesta = useMemo(
    () => vectorDeRiesgo(plan.posicionesAcumuladas, porTicker, concentracionPropuesta.data ?? null),
    [plan.posicionesAcumuladas, porTicker, concentracionPropuesta.data],
  )

  const rentaOriginal = useMemo(() => {
    if (!calendarioOriginal.data) return []
    const { meses, resumen } = calendarioOriginal.data
    const invertidoMapa = invertidoPorMoneda(meses, aInvertidoUsd(montosOriginales, monedaDe, tipoDeCambio), tipoDeCambio)
    return calcularRentaAnualPorMoneda(meses, resumen.renta_anual ?? {}, invertidoMapa)
  }, [calendarioOriginal.data, montosOriginales, monedaDe, tipoDeCambio])

  const rentaPropuesta = useMemo(() => {
    if (!calendarioPropuesto.data) return []
    const { meses, resumen } = calendarioPropuesto.data
    const invertidoMapa = invertidoPorMoneda(meses, aInvertidoUsd(montos, monedaDe, tipoDeCambio), tipoDeCambio)
    return calcularRentaAnualPorMoneda(meses, resumen.renta_anual ?? {}, invertidoMapa)
  }, [calendarioPropuesto.data, montos, monedaDe, tipoDeCambio])

  const costo = useMemo(
    () => costoAcumulado(montosOriginales, plan.aceptadas, monedaDe, tipoDeCambio),
    [montosOriginales, plan.aceptadas, monedaDe, tipoDeCambio],
  )

  const tickersQueCambian = useMemo(
    () => tickersConMontoDistinto(montosOriginales, montos),
    [montosOriginales, montos],
  )

  const efecto = useMemo(() => {
    if (!calendarioOriginal.data || !calendarioPropuesto.data) return null
    return diffCalendarioCarteras(calendarioOriginal.data, calendarioPropuesto.data, tickersQueCambian)
  }, [calendarioOriginal.data, calendarioPropuesto.data, tickersQueCambian])

  // GWT-3 de F-036 conserva su forma acá: sin aceptadas no hay propuesta que comparar.
  if (plan.aceptadas.length === 0) return null

  return (
    <section
      style={{ marginTop: 16, display: 'grid', gap: 16 }}
      aria-label="Comparación de la cartera original contra la propuesta"
    >
      <header>
        <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
          Original contra propuesta
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 16 }}>
        <ColumnaCartera
          titulo="Cartera original"
          calendario={calendarioOriginal}
          renta={rentaOriginal}
          rendimientos={rendimientosOriginal}
          ejes={ejesOriginal}
        />
        <ColumnaCartera
          titulo="Cartera propuesta"
          calendario={calendarioPropuesto}
          renta={rentaPropuesta}
          rendimientos={rendimientosPropuesta}
          ejes={ejesPropuesta}
          efecto={efecto}
        />
      </div>

      <DeltaEjes ejesOriginal={ejesOriginal} ejesPropuesta={ejesPropuesta} />

      <ResultadoNeto
        costo={costo}
        rendimientosOriginal={rendimientosOriginal}
        rendimientosPropuesta={rendimientosPropuesta}
        rentaOriginal={rentaOriginal}
        rentaPropuesta={rentaPropuesta}
        efecto={efecto}
      />
    </section>
  )
}

// --- una columna ---------------------------------------------------------------------------------

function ColumnaCartera({
  titulo,
  calendario,
  renta,
  rendimientos,
  ejes,
  efecto,
}: {
  titulo: string
  calendario: ReturnType<typeof useCalendarioCartera>
  renta: RentaAnualPorMoneda[]
  rendimientos: RendimientoPorNaturaleza[]
  ejes: EjeDeRiesgo[]
  /** Sólo la columna propuesta recibe el efecto: es la que se marca (GWT-2). */
  efecto?: EfectoCalendario | null
}) {
  return (
    <div
      style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px', display: 'grid', gap: 14 }}
      aria-label={titulo}
    >
      <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
        {titulo}
      </div>

      {calendario.isPending && <EstadoCarga que="el calendario" />}
      {calendario.isError && <EstadoError error={calendario.error} onRetry={() => void calendario.refetch()} />}
      {calendario.data && <CalendarioColumna calendario={calendario.data} efecto={efecto ?? null} renta={renta} />}

      <SeccionRendimientosColumna rendimientos={rendimientos} />

      <VectorDeRiesgo ejes={ejes} />
    </div>
  )
}

function CalendarioColumna({
  calendario,
  efecto,
  renta,
}: {
  calendario: NonNullable<ReturnType<typeof useCalendarioCartera>['data']>
  efecto: EfectoCalendario | null
  renta: RentaAnualPorMoneda[]
}) {
  const { meses, alertas, resumen } = calendario
  const columnasUsd = columnasDeCordillera(meses, 'usd')
  const columnasArs = columnasDeCordillera(meses, 'ars')
  const hayPosicionesEnPesos = resumen.monedas.includes('ars')

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <Cordillera
        titulo="Renta mensual en dólares"
        columnas={columnasUsd}
        alto={90}
        colorBarra="var(--ac)"
        formatoMonto={(v) => fmtMonto(v, 'usd', 0)}
        leyenda="Los meses sin cobertura muestran 0 explícito."
        marcas={marcasPorMoneda(efecto, 'usd')}
      />

      {hayPosicionesEnPesos && (
        <Cordillera
          titulo="Renta mensual en pesos"
          columnas={columnasArs}
          alto={60}
          colorBarra="var(--ac2)"
          formatoMonto={(v) => `$ ${fmtCompacto(v)}`}
          leyenda="Escala propia, en pesos. Nunca se suma a los dólares."
          marcas={marcasPorMoneda(efecto, 'ars')}
        />
      )}

      <RentaAnualColumna datos={renta} />

      {alertas.length > 0 && (
        <div role="list" aria-label="Alertas del calendario" style={{ display: 'grid', gap: 4 }}>
          {alertas.map((alerta, indice) => (
            <p
              role="listitem"
              key={`${alerta.codigo}:${indice}`}
              style={{ margin: 0, fontSize: 10, color: alerta.severidad === 'error' ? 'var(--neg)' : 'var(--ac2)', textWrap: 'pretty' }}
            >
              {alerta.mensaje}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}

function RentaAnualColumna({ datos }: { datos: RentaAnualPorMoneda[] }) {
  if (datos.length === 0) {
    return <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>Sin cupones que calcular en ninguna moneda.</p>
  }
  return (
    <div style={{ display: 'grid', gap: 4 }}>
      {datos.map((d) => (
        <p key={d.moneda} className="mono" style={{ margin: 0, fontSize: 11, color: 'var(--sd)' }}>
          Renta anual en {ROTULO_MONEDA[d.moneda] ?? d.moneda}: {fmtMontoMoneda(d.rentaAnual, d.moneda)}
          {' · '}
          {d.mesesCubiertos}/12 meses cubiertos
        </p>
      ))}
    </div>
  )
}

function SeccionRendimientosColumna({ rendimientos }: { rendimientos: RendimientoPorNaturaleza[] }) {
  return (
    <div style={{ display: 'grid', gap: 4 }}>
      {rendimientos.map((r) => (
        <p key={r.naturaleza} className="mono" style={{ margin: 0, fontSize: 11, color: 'var(--sd)' }}>
          {r.nombre}: {r.rendimientoPond !== null ? fmtPct(r.rendimientoPond * 100) : SIN_DATO}
          {' · '}
          {fmtPct(r.pctCartera, 1)} de la cartera
        </p>
      ))}
    </div>
  )
}

// --- delta de los seis ejes -----------------------------------------------------------------------

/**
 * A diferencia de la renta y el rendimiento, "mejora" no tiene una única dirección para los seis
 * ejes (mayor percentil de liquidez es mejor, mayor concentración por crédito es peor, duración no
 * es buena ni mala por sí sola) — pintar un delta de eje en verde/rojo inventaría un juicio que la
 * regla 7 prohíbe. El delta se declara en su unidad, sin color de mejora.
 */
function DeltaEjes({ ejesOriginal, ejesPropuesta }: { ejesOriginal: EjeDeRiesgo[]; ejesPropuesta: EjeDeRiesgo[] }) {
  return (
    <div
      role="list"
      aria-label="Delta de los seis ejes de riesgo"
      style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px', display: 'grid', gap: 4 }}
    >
      <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase', marginBottom: 6 }}>
        Riesgo — original → propuesta
      </div>
      {ejesPropuesta.map((eje, indice) => {
        const antes = ejesOriginal[indice]
        const delta = antes.valor !== null && eje.valor !== null ? eje.valor - antes.valor : null
        return (
          <p role="listitem" key={eje.id} className="mono" style={{ margin: 0, fontSize: 11, color: 'var(--sd)' }}>
            {eje.nombre}: {formatoValor(antes.valor, antes.unidad)} → {formatoValor(eje.valor, eje.unidad)}
            {delta !== null && ` (Δ ${delta > 0 ? '+' : ''}${fmtNumero(delta, 1)})`}
          </p>
        )
      })}
    </div>
  )
}

// --- resultado neto: costo + deltas de renta y rendimiento ---------------------------------------

function CostoTotal({ costo }: { costo: CostoAcumulado }) {
  const faltantes = [...costo.sinCostoVerificable, ...costo.noConvertibles]
  const esParcial = costo.totalUsd !== null && faltantes.length > 0

  return (
    <div style={{ display: 'grid', gap: 2 }}>
      <p className="mono" style={{ margin: 0, fontSize: 13, fontWeight: 600, color: costo.totalUsd !== null ? 'var(--tx)' : 'var(--sd)' }}>
        Costo total de rotación acumulado: {costo.totalUsd !== null ? fmtMonto(costo.totalUsd, 'usd') : SIN_DATO}
        {esParcial && ' (parcial)'}
      </p>
      {faltantes.length > 0 && (
        <p style={{ margin: 0, fontSize: 10.5, color: 'var(--ac2)' }}>No entran al total: {faltantes.join(', ')}.</p>
      )}
    </div>
  )
}

function ResultadoNeto({
  costo,
  rendimientosOriginal,
  rendimientosPropuesta,
  rentaOriginal,
  rentaPropuesta,
  efecto,
}: {
  costo: CostoAcumulado
  rendimientosOriginal: RendimientoPorNaturaleza[]
  rendimientosPropuesta: RendimientoPorNaturaleza[]
  rentaOriginal: RentaAnualPorMoneda[]
  rentaPropuesta: RentaAnualPorMoneda[]
  efecto: EfectoCalendario | null
}) {
  const rendimientosOriginalPorNaturaleza = new Map(rendimientosOriginal.map((r) => [r.naturaleza, r]))
  const rentaOriginalPorMoneda = new Map(rentaOriginal.map((d) => [d.moneda, d]))
  const rentaPropuestaPorMoneda = new Map(rentaPropuesta.map((d) => [d.moneda, d]))
  const monedas = [...new Set([...rentaOriginalPorMoneda.keys(), ...rentaPropuestaPorMoneda.keys()])]

  return (
    <div
      style={{ background: 'var(--pan)', border: '1px solid var(--ac)', borderRadius: 4, padding: '12px 16px', display: 'grid', gap: 10 }}
      aria-label="Resultado neto"
    >
      <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
        Resultado neto
      </div>

      <CostoTotal costo={costo} />

      <div style={{ display: 'grid', gap: 4 }}>
        {monedas.map((moneda) => {
          const antes = rentaOriginalPorMoneda.get(moneda) ?? null
          const despues = rentaPropuestaPorMoneda.get(moneda) ?? null
          const antesPct = antes?.pct ?? null
          const despuesPct = despues?.pct ?? null
          const delta = antesPct !== null && despuesPct !== null ? despuesPct - antesPct : null
          const color = delta === null ? 'var(--sd)' : delta > 0 ? 'var(--pos)' : delta < 0 ? 'var(--neg)' : 'var(--sd)'
          return (
            <p key={moneda} className="mono" style={{ margin: 0, fontSize: 11.5, color }}>
              Renta anual en {ROTULO_MONEDA[moneda] ?? moneda}: {antesPct !== null ? fmtPct(antesPct) : SIN_DATO} →{' '}
              {despuesPct !== null ? fmtPct(despuesPct) : SIN_DATO}
              {delta !== null && ` (${delta > 0 ? '+' : ''}${fmtPct(delta)})`}
              {' · '}
              {antes !== null ? `${antes.mesesCubiertos}/12` : SIN_DATO} →{' '}
              {despues !== null ? `${despues.mesesCubiertos}/12` : SIN_DATO} meses cubiertos
            </p>
          )
        })}
      </div>

      <div style={{ display: 'grid', gap: 4 }}>
        {rendimientosPropuesta.map((prop) => {
          const antes = rendimientosOriginalPorNaturaleza.get(prop.naturaleza) ?? null
          const antesValor = antes?.rendimientoPond ?? null
          const despuesValor = prop.rendimientoPond
          const delta = antesValor !== null && despuesValor !== null ? (despuesValor - antesValor) * 100 : null
          if (antesValor === null && despuesValor === null) return null
          const color = delta === null ? 'var(--sd)' : delta > 0 ? 'var(--pos)' : delta < 0 ? 'var(--neg)' : 'var(--sd)'
          return (
            <p key={prop.naturaleza} className="mono" style={{ margin: 0, fontSize: 11.5, color }}>
              {prop.nombre}: {antesValor !== null ? fmtPct(antesValor * 100) : SIN_DATO} →{' '}
              {despuesValor !== null ? fmtPct(despuesValor * 100) : SIN_DATO}
              {delta !== null && ` (${delta > 0 ? '+' : ''}${fmtPct(delta)})`}
            </p>
          )
        })}
      </div>

      <EfectoResumen efecto={efecto} />
    </div>
  )
}

function EfectoResumen({ efecto }: { efecto: EfectoCalendario | null }) {
  if (!efecto) return null

  if (!efecto.calculable) {
    return (
      <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--sd)' }}>
        {efecto.motivoNoCalculable}
      </p>
    )
  }

  const partes = [
    ...efecto.seLlenan.map((m) => `se llena ${m.nombre} (${m.moneda.toUpperCase()})`),
    ...efecto.seVacian.map((m) => `se vacía ${m.nombre} (${m.moneda.toUpperCase()})`),
  ]

  if (partes.length === 0) {
    return (
      <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)' }}>
        {efecto.mesesQueCambian > 0
          ? `No cambia qué meses cobran renta (cambia el monto en ${efecto.mesesQueCambian} ${efecto.mesesQueCambian === 1 ? 'mes' : 'meses'}).`
          : 'No cambia qué meses cobran renta.'}
      </p>
    )
  }

  return (
    <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)' }}>
      Meses que cambian de cobertura: {partes.join(' · ')}.
    </p>
  )
}
