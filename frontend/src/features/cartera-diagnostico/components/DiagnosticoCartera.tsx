/**
 * F-030 — valuación y diagnóstico de la cartera cargada: la descripción de la cartera tal como
 * está, a precios de hoy.
 *
 * Reusa exactamente los mismos servicios que el armador (`@/lib/cartera/*`, base común de la
 * Tanda 11): la renta mes a mes, los rendimientos por naturaleza de tasa, el plazo promedio y la
 * concentración se calculan con las mismas funciones puras y los mismos endpoints que
 * `features/armador`. El criterio de aceptación (riesgo R12) es que la misma composición cargada
 * acá y armada a mano en `/armador` dé los mismos números — ver `__tests__/paridad.test.ts`.
 *
 * La barra de estado del dato (F-013, hora del snapshot y demora) no se re-declara: ya está
 * montada globalmente en `AppLayout.tsx` y cubre toda la app, esta pantalla incluida.
 *
 * Lo que no resolvió F-029, y lo que F-029 resolvió pero no se pudo valuar (sin nominal, sin
 * precio, sin tipo de cambio) queda fuera de renta/rendimientos/concentración y se declara en la
 * sección de excluidas — nunca se esconde ni se completa con un valor inventado (reglas 1 y 11).
 */

import { useMemo, useState } from 'react'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { DistribucionBarras, type TramoDistribucion } from '@/components/DistribucionBarras'
import { fmtCompacto, fmtMonto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

import type { PosicionCruda } from '@/features/cartera-ingreso/types'

import {
  PERFILES,
  type AlertaConcentracion,
  type Concentracion,
  type EstadoDeTope,
  type NombreDePerfil,
  type TipoDeTope,
  type TramoConcentracion,
} from '@/lib/cartera/esquemaConcentracion'
import { useCalendarioCartera } from '@/lib/cartera/hooks/useCalendarioCartera'
import { useConcentracion } from '@/lib/cartera/hooks/useConcentracion'
import { plazoPromedio, rendimientosPorNaturaleza, type RendimientoPorNaturaleza } from '@/lib/cartera/metricas'
import {
  calcularRentaAnualPorMoneda,
  columnasDeCordillera,
  invertidoPorMoneda,
  picoDeColumnas,
  type ColumnaCordillera,
  type RentaAnualPorMoneda,
} from '@/lib/cartera/renta'

import { useCarteraCargadaValuada } from '../hooks/useCarteraCargadaValuada'
import type { MotivoExclusionValuacion, PosicionExcluidaValuacion, PosicionValuada } from '../lib/valuacion'

const MOTIVO_LABEL: Record<MotivoExclusionValuacion, string> = {
  no_resuelta: 'no resueltas contra el universo — detalle arriba, en la resolución de la cartera',
  sin_nominal: 'resueltas pero sin nominal declarado (sólo monto, en una moneda no declarada)',
  sin_precio: 'sin precio de mercado o sin moneda de cotización conocida',
  sin_tipo_de_cambio: 'cotizan en pesos y no hay tipo de cambio implícito para llevarlas a dólares',
}

export function DiagnosticoCartera({ posiciones }: { posiciones: PosicionCruda[] }) {
  const { resolucion, valuacion, porTicker, cargando, error } = useCarteraCargadaValuada(posiciones)

  // `useMemo` y no `?? []` suelto: sin memoizar, el fallback crea un array nuevo en cada render y
  // los `useMemo` de abajo, que dependen de esta referencia, se recalculan siempre.
  const valuadas = useMemo(() => valuacion?.valuadas ?? [], [valuacion])
  const excluidas = useMemo(() => valuacion?.excluidas ?? [], [valuacion])

  const posicionesParaCalendario = useMemo(
    () => valuadas.map((v) => ({ ticker: v.ticker, monto: v.invertido })),
    [valuadas],
  )
  const posicionesConPeso = useMemo(
    () => valuadas.map((v) => ({ ticker: v.ticker, peso: v.pesoReal })),
    [valuadas],
  )

  const [perfil, setPerfil] = useState<NombreDePerfil>('moderado')

  // Se llaman siempre, aunque `valuadas` esté vacío: los dos hooks tienen `enabled: length > 0` y
  // no pegan al backend con una lista vacía (mismo criterio que `PanelRenta`/`PanelConcentracion`
  // del armador). Los hooks de React no pueden colgar de un `return` condicional de más arriba.
  const calendario = useCalendarioCartera(posicionesParaCalendario)
  const concentracion = useConcentracion(posicionesConPeso, perfil)

  // Sin posiciones no hay nada que resolver ni que valuar — mismo criterio que `ResolucionCartera`.
  if (posiciones.length === 0) return null

  if (cargando) return <EstadoCarga que="la valuación de la cartera" />
  if (error) return <EstadoError error={error} onRetry={() => void resolucion.refetch()} />
  if (!valuacion) return null

  if (valuadas.length === 0) {
    return (
      <section style={{ marginTop: 16 }} aria-label="Diagnóstico de la cartera">
        <div
          style={{
            border: '1px dashed var(--lin)',
            borderRadius: 4,
            padding: '12px 16px',
            fontSize: 12,
            color: 'var(--dim)',
          }}
        >
          Cartera no valuable: ninguna posición tiene nominal, precio y tipo de cambio a la vez.
        </div>
        <ExcluidasDetalle excluidas={excluidas} soloDetalle />
      </section>
    )
  }

  const rendimientos = rendimientosPorNaturaleza(valuadas, porTicker)
  const plazo = plazoPromedio(valuadas, porTicker)

  return (
    <section style={{ marginTop: 16, display: 'grid', gap: 16 }} aria-label="Diagnóstico de la cartera">
      <header>
        <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
          Diagnóstico de la cartera
        </div>
        <p style={{ margin: '2px 0 0', fontSize: 11.5, color: 'var(--dim)' }}>
          {valuadas.length} {valuadas.length === 1 ? 'posición valuada' : 'posiciones valuadas'} de{' '}
          {posiciones.length} cargadas, a precios de hoy.
        </p>
      </header>

      <SeccionRendimientosYPlazo rendimientos={rendimientos} plazo={plazo} />

      <SeccionRenta calendario={calendario} valuadas={valuadas} />

      <SeccionConcentracion perfil={perfil} onPerfil={setPerfil} posiciones={posicionesConPeso} consulta={concentracion} />

      <ExcluidasDetalle excluidas={excluidas} />
    </section>
  )
}

// --- Rendimientos por naturaleza y plazo promedio -------------------------------------------------

function SeccionRendimientosYPlazo({
  rendimientos,
  plazo,
}: {
  rendimientos: RendimientoPorNaturaleza[]
  plazo: { anios: number | null; posicionesExcluidas: number }
}) {
  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
        {rendimientos.map((r) => (
          <TarjetaRendimiento key={r.naturaleza} datos={r} />
        ))}
      </div>
      <p className="mono" style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>
        Plazo promedio: {plazo.anios !== null ? `${fmtNumero(plazo.anios, 1)} años` : SIN_DATO}
        {plazo.posicionesExcluidas > 0 && (
          <span style={{ color: 'var(--ac2)' }}>
            {' · '}
            {plazo.posicionesExcluidas} sin duración informada, fuera del promedio
          </span>
        )}
      </p>
    </div>
  )
}

function TarjetaRendimiento({ datos }: { datos: RendimientoPorNaturaleza }) {
  return (
    <div style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '10px 12px' }}>
      <div style={{ fontSize: 10.5, color: 'var(--dim)', textWrap: 'pretty' }}>{datos.nombre}</div>
      <div className="mono" style={{ fontSize: 22, fontWeight: 600, color: 'var(--ac)', marginTop: 2 }}>
        {datos.rendimientoPond !== null ? fmtPct(datos.rendimientoPond * 100) : SIN_DATO}
      </div>
      <p className="mono" style={{ margin: '3px 0 0', fontSize: 10.5, color: 'var(--sd)' }}>
        {fmtPct(datos.pctCartera, 1)} de la cartera · {datos.posiciones} posición
        {datos.posiciones === 1 ? '' : 'es'}
        {datos.posicionesExcluidas > 0 && (
          <span style={{ color: 'var(--ac2)' }}>
            {' '}
            ({datos.posicionesExcluidas} sin rendimiento informado)
          </span>
        )}
      </p>
    </div>
  )
}

// --- Renta mes a mes -------------------------------------------------------------------------------

function SeccionRenta({
  calendario,
  valuadas,
}: {
  calendario: ReturnType<typeof useCalendarioCartera>
  valuadas: PosicionValuada[]
}) {
  if (calendario.isPending) return <EstadoCarga que="el calendario de la cartera" />
  if (calendario.isError) {
    return <EstadoError error={calendario.error} onRetry={() => void calendario.refetch()} />
  }
  if (!calendario.data) return null

  const { meses, resumen } = calendario.data
  const rentaAnual = resumen.renta_anual ?? {}
  const resueltasParaInvertido = valuadas.map((v) => ({ ticker: v.ticker, invertido: v.invertido }))
  const invertidoMapa = invertidoPorMoneda(meses, resueltasParaInvertido)
  const porMoneda = calcularRentaAnualPorMoneda(meses, rentaAnual, invertidoMapa)

  const columnasUsd = columnasDeCordillera(meses, 'usd')
  const columnasArs = columnasDeCordillera(meses, 'ars')
  const hayPosicionesEnPesos = resumen.monedas.includes('ars')

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <Cordillera
        titulo="Renta mensual en dólares"
        columnas={columnasUsd}
        alto={140}
        colorBarra="var(--ac)"
        formatoMonto={(v) => fmtMonto(v, 'usd', 0)}
        leyenda="Renta (cupón) en dólares. Los meses sin cobertura muestran 0 explícito."
      />

      {hayPosicionesEnPesos && (
        <Cordillera
          titulo="Renta mensual en pesos"
          columnas={columnasArs}
          alto={90}
          colorBarra="var(--ac2)"
          formatoMonto={(v) => `$ ${fmtCompacto(v)}`}
          leyenda="Escala propia, en pesos. Nunca se suma a los dólares ni se convierte para el total."
        />
      )}

      <RentaAnual datos={porMoneda} />
    </div>
  )
}

function Cordillera({
  titulo,
  columnas,
  alto,
  colorBarra,
  formatoMonto,
  leyenda,
}: {
  titulo: string
  columnas: ColumnaCordillera[]
  alto: number
  colorBarra: string
  formatoMonto: (valor: number) => string
  leyenda: string
}) {
  const pico = picoDeColumnas(columnas)

  return (
    <div style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px' }}>
      <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase', marginBottom: 10 }}>
        {titulo}
      </div>

      <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end', height: alto }}>
        {columnas.map((columna) => (
          <div
            key={columna.etiqueta}
            title={`${columna.nombre}: ${formatoMonto(columna.total)}`}
            style={{ flex: 1, minWidth: 0, height: alto, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}
          >
            <span className="mono" style={{ fontSize: 9.5, textAlign: 'center', color: columna.total === 0 ? 'var(--neg)' : 'var(--dim)', marginBottom: 3 }}>
              {columna.total === 0 ? '0' : formatoMonto(columna.total)}
            </span>
            <span
              style={{
                display: 'block',
                height: pico > 0 ? (columna.total / pico) * (alto - 22) : 0,
                background: colorBarra,
                borderRadius: '2px 2px 0 0',
              }}
            />
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
        {columnas.map((columna) => (
          <div key={columna.etiqueta} className="mono" style={{ flex: 1, minWidth: 0, textAlign: 'center', fontSize: 9, color: 'var(--dim)' }}>
            {columna.etiqueta}
          </div>
        ))}
      </div>

      <p style={{ margin: '8px 0 0', fontSize: 10.5, color: 'var(--dim)' }}>{leyenda}</p>
    </div>
  )
}

function fmtMontoMoneda(valor: number, moneda: string): string {
  if (moneda === 'usd' || moneda === 'ars') return fmtMonto(valor, moneda)
  return `${moneda.toUpperCase()} ${fmtNumero(valor)}`
}

const ROTULO_MONEDA: Record<string, string> = { usd: 'dólares', ars: 'pesos' }

function RentaAnual({ datos }: { datos: RentaAnualPorMoneda[] }) {
  if (datos.length === 0) {
    return (
      <div style={{ border: '1px dashed var(--lin)', borderRadius: 4, padding: '10px 12px', fontSize: 11.5, color: 'var(--dim)' }}>
        Sin cupones que calcular en ninguna moneda: la cartera valuada no tiene posiciones con
        cronograma de pagos.
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
      {datos.map((d) => (
        <div key={d.moneda} style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '10px 12px' }}>
          <div style={{ fontSize: 10, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Renta anual en {ROTULO_MONEDA[d.moneda] ?? d.moneda}
          </div>
          <div className="mono" style={{ fontSize: 26, fontWeight: 600, color: 'var(--ac)', marginTop: 2 }}>
            {d.pct !== null ? fmtPct(d.pct) : SIN_DATO}
          </div>
          <p className="mono" style={{ margin: '2px 0 0', fontSize: 10.5, color: 'var(--sd)' }}>
            {fmtMontoMoneda(d.rentaAnual, d.moneda)} /{' '}
            {d.invertido !== null ? fmtMontoMoneda(d.invertido, d.moneda) : SIN_DATO}
          </p>
          <p className="mono" style={{ margin: '4px 0 0', fontSize: 10, color: 'var(--dim)' }}>
            {d.mesesCubiertos}/12 meses cubiertos
          </p>
        </div>
      ))}
    </div>
  )
}

// --- Concentración -----------------------------------------------------------------------------

const TITULO_TOPE: Record<TipoDeTope, string> = {
  soberano: 'Riesgo soberano',
  emisor: 'Por emisor',
  sector: 'Por sector',
}

function SeccionConcentracion({
  perfil,
  onPerfil,
  posiciones,
  consulta,
}: {
  perfil: NombreDePerfil
  onPerfil: (perfil: NombreDePerfil) => void
  posiciones: { ticker: string; peso: number }[]
  consulta: ReturnType<typeof useConcentracion>
}) {
  return (
    <section
      style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px' }}
      aria-label="Concentración de la cartera cargada"
    >
      <header style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 10 }}>
        <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
          Concentración
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--dim)' }}>
          Perfil
          <select
            value={perfil}
            onChange={(evento) => onPerfil(evento.target.value as NombreDePerfil)}
            style={{ font: 'inherit', fontSize: 12, color: 'var(--tx)', background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 3, padding: '3px 6px' }}
          >
            {PERFILES.map((nombre) => (
              <option key={nombre} value={nombre}>
                {nombre}
              </option>
            ))}
          </select>
        </label>
      </header>

      {posiciones.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--sd)' }}>Sin posiciones valuadas para medir.</p>
      ) : (
        <>
          {consulta.isPending && <EstadoCarga que="los límites de concentración" />}
          {consulta.isError && <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />}
          {consulta.data && <VeredictoConcentracion datos={consulta.data} />}
        </>
      )}
    </section>
  )
}

function VeredictoConcentracion({ datos }: { datos: Concentracion }) {
  const porTipo = (tipo: TipoDeTope) => datos.topes.filter((t) => t.tipo === tipo)

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
        {(['soberano', 'emisor', 'sector'] as const).map((tipo) => (
          <BloqueDeTopes key={tipo} tipo={tipo} topes={porTipo(tipo)} />
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
        <DistribucionBarras titulo="Sector" tramos={aTramos(datos.distribucion.sector)} />
        <DistribucionBarras titulo="Legislación" tramos={aTramos(datos.distribucion.ley)} />
        <DistribucionBarras titulo="Naturaleza de tasa" tramos={aTramos(datos.distribucion.naturaleza)} />
      </div>

      <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--sd)' }}>
        Σ declarada {fmtPct(datos.peso.declarado, 1)} · medida {fmtPct(datos.peso.medido, 1)}
        {datos.fuera_del_universo.length > 0 && (
          <> · {datos.fuera_del_universo.length} posición(es) fuera del universo</>
        )}
      </p>

      <Advertencias alertas={datos.alertas} />
    </div>
  )
}

function aTramos(tramos: TramoConcentracion[]): TramoDistribucion[] {
  return tramos.map((t) => ({ nombre: t.nombre, peso: t.peso, sinDato: t.sin_dato }))
}

function BloqueDeTopes({ tipo, topes }: { tipo: TipoDeTope; topes: EstadoDeTope[] }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <h4 style={{ margin: 0, fontSize: 10, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {TITULO_TOPE[tipo]}
      </h4>
      {topes.length === 0 ? (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--sd)' }}>Sin posiciones de este tipo.</p>
      ) : (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 5 }}>
          {topes.map((tope) => (
            <li key={`${tope.tipo}:${tope.clave}`} style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11.5 }}>
              <span style={{ color: tope.excedido ? 'var(--neg)' : 'var(--tx)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={tope.nombre}>
                {tope.nombre}
              </span>
              <span className="mono" style={{ color: tope.excedido ? 'var(--neg)' : 'var(--ac)', whiteSpace: 'nowrap' }}>
                {fmtPct(tope.peso, 1)} / {fmtPct(tope.tope, 0)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Advertencias({ alertas }: { alertas: AlertaConcentracion[] }) {
  if (alertas.length === 0) {
    return <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>Sin advertencias de concentración.</p>
  }

  return (
    <div role="list" aria-label="Advertencias de concentración" style={{ display: 'grid', gap: 6 }}>
      {alertas.map((alerta, indice) => (
        <div
          role="listitem"
          key={`${alerta.codigo}:${indice}`}
          style={{ borderLeft: `2px solid ${alerta.severidad === 'error' ? 'var(--neg)' : 'var(--ac2)'}`, background: 'var(--pan2)', borderRadius: '0 3px 3px 0', padding: '7px 10px' }}
        >
          <p style={{ margin: 0, fontSize: 12, color: 'var(--tx)', textWrap: 'pretty' }}>{alerta.mensaje}</p>
        </div>
      ))}
    </div>
  )
}

// --- Excluidas -----------------------------------------------------------------------------------

function ExcluidasDetalle({
  excluidas,
  soloDetalle = false,
}: {
  excluidas: PosicionExcluidaValuacion[]
  soloDetalle?: boolean
}) {
  if (excluidas.length === 0) {
    if (soloDetalle) return null
    return (
      <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>
        Todas las posiciones cargadas se pudieron valuar.
      </p>
    )
  }

  const porMotivo = new Map<MotivoExclusionValuacion, number>()
  for (const e of excluidas) porMotivo.set(e.motivo, (porMotivo.get(e.motivo) ?? 0) + 1)

  const montoDeclaradoExcluido = excluidas.reduce(
    (acumulado, e) => acumulado + (e.montoDeclarado ?? 0),
    0,
  )

  return (
    <div style={{ marginTop: soloDetalle ? 10 : 0, display: 'grid', gap: 4 }}>
      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
        {excluidas.length} {excluidas.length === 1 ? 'posición excluida' : 'posiciones excluidas'} de
        renta, rendimientos y concentración:
      </p>
      <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: 11, color: 'var(--dim)' }}>
        {(Object.keys(MOTIVO_LABEL) as MotivoExclusionValuacion[])
          .filter((motivo) => (porMotivo.get(motivo) ?? 0) > 0)
          .map((motivo) => (
            <li key={motivo}>
              {porMotivo.get(motivo)} {MOTIVO_LABEL[motivo]}
            </li>
          ))}
      </ul>
      <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--sd)' }}>
        monto declarado excluido {fmtNumero(montoDeclaradoExcluido)} (en la moneda en que vino el
        resumen, que no se declara)
      </p>
    </div>
  )
}
