/**
 * Composición de la cartera y curva TIR/duración del segmento activo — F-023.
 *
 * `PanelConcentracion` (F-020) ya muestra distribución por sector, ley y naturaleza desde
 * `/concentracion`: este panel no la repite (sería una segunda fuente del mismo hecho, riesgo R12
 * de `plan.md:2774`) y agrega lo que ese panel no cubre — clase de activo, segmento y emisor —
 * más la curva. Sin mockup en el design system (igual que F-020 y F-022): mismo estilo de panel
 * compacto ya establecido en esta carpeta.
 *
 * ## Qué pestaña de la curva arranca activa, y por qué no sale de `composicionPorSegmento`
 *
 * `composicionPorSegmento` agrupa por el segmento crudo (`especie.segmento`, p.ej. `usd_hard`) —
 * es la composición que se muestra en la barra "Segmento", sin partir por crédito. La curva, en
 * cambio, tiene que abrir `usd_hard` en sus tres pestañas de crédito (soberano/subsoberano/ON,
 * regla 4) para no mezclar tres créditos distintos en la misma nube — mismo criterio que el
 * monitor (`MonitorPage.tsx`, `SEGMENTO_POR_CREDITO`). Por eso la pestaña por defecto se calcula
 * acá con su propia clave expandida, y no leyendo `[0]` del corte por segmento: ese corte no
 * expone la clave de crédito, sólo el nombre ya traducido para mostrar.
 *
 * ## Moneda de la nube (decisión de implementación, no bloqueante en el plan)
 *
 * Una emisión con hermanas cotiza en más de una moneda (`especie.hermanas`); sin elegir una sola,
 * la nube mostraría 2-3 puntos por la misma emisión. Se sigue el precedente del monitor: se elige
 * la moneda con más especies dentro del segmento/clase activo (`monedaInicial`/`contarPorMoneda`),
 * sin agregar un segundo selector visible — el panel ya tiene uno (el de segmento) y agregar otro
 * competiría por atención con la curva, que es el foco de esta ficha. Las posiciones de la
 * cartera **no** se filtran por esa moneda: lo que el asesor tiene es lo que se marca, sea cual
 * sea su moneda de cotización.
 */

import { useMemo, useState } from 'react'

import { DistribucionBarras } from '@/components/DistribucionBarras'
import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { SIN_MONEDA_DECLARADA, contarPorMoneda, monedaInicial } from '@/components/SelectorMoneda'
import {
  SEGMENTO_POR_CREDITO,
  SelectorSegmento,
  claseDeClave,
  claveDeCredito,
  expandirSegmentos,
  segmentoDeClave,
} from '@/components/SelectorSegmento'

import { CurvaTirDuracion } from './CurvaTirDuracion'
import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { useEspeciesUniverso } from '../hooks/useEspeciesUniverso'
import {
  composicionPorClase,
  composicionPorEmisor,
  composicionPorSegmento,
  leyendaDelPeso,
} from '../lib/composicion'
import type { PosicionResuelta } from '../lib/resolver'
import type { Especie } from '../lib/schema'

/** La clave de crédito de una especie (`usd_hard/bono_soberano`), o su segmento tal cual cuando
 *  el segmento no se abre por crédito. */
function claveDeCurva(especie: Especie): string {
  return SEGMENTO_POR_CREDITO[especie.segmento]
    ? claveDeCredito(especie.segmento, especie.clase_activo)
    : especie.segmento
}

export function PanelComposicion() {
  const { resueltas, porTicker } = useCarteraResuelta()
  const universo = useEspeciesUniverso()
  const [segmentoElegido, setSegmentoElegido] = useState<string | null>(null)

  const conEspecie = useMemo(() => {
    const salida: Array<{ resuelta: PosicionResuelta; especie: Especie }> = []
    for (const resuelta of resueltas) {
      const especie = porTicker.get(resuelta.ticker)
      if (especie) salida.push({ resuelta, especie })
    }
    return salida
  }, [resueltas, porTicker])

  const pestanias = useMemo(() => {
    const segmentosPresentes = [...new Set(conEspecie.map(({ especie }) => especie.segmento))]
    return expandirSegmentos(segmentosPresentes)
  }, [conEspecie])

  const pestaniaDeMayorPeso = useMemo(() => {
    const pesos = new Map<string, number>()
    for (const { resuelta, especie } of conEspecie) {
      const clave = claveDeCurva(especie)
      const peso = resuelta.pesoReal ?? resuelta.peso
      pesos.set(clave, (pesos.get(clave) ?? 0) + peso)
    }
    let mejor: string | null = null
    let mejorPeso = -Infinity
    for (const [clave, peso] of pesos) {
      if (peso > mejorPeso) {
        mejor = clave
        mejorPeso = peso
      }
    }
    return mejor
  }, [conEspecie])

  const activa = segmentoElegido ?? pestaniaDeMayorPeso ?? pestanias[0] ?? null
  const segmentoActivo = activa !== null ? segmentoDeClave(activa) : null
  const claseActiva = activa !== null ? claseDeClave(activa) : null

  const deLaClase = useMemo(() => {
    if (segmentoActivo === null) return []
    const filasDelSegmento = (universo.data ?? []).filter((e) => e.segmento === segmentoActivo)
    return claseActiva === null
      ? filasDelSegmento
      : filasDelSegmento.filter((e) => e.clase_activo === claseActiva)
  }, [universo.data, segmentoActivo, claseActiva])

  const monedaDominante = useMemo(
    () => monedaInicial(contarPorMoneda(deLaClase), ''),
    [deLaClase],
  )

  const candidatos = useMemo(
    () =>
      monedaDominante === null
        ? deLaClase
        : deLaClase.filter((e) => (e.moneda_cotizacion ?? SIN_MONEDA_DECLARADA) === monedaDominante),
    [deLaClase, monedaDominante],
  )

  const carteraDelSegmento = useMemo(() => {
    if (segmentoActivo === null) return []
    return conEspecie
      .filter(
        ({ especie }) =>
          especie.segmento === segmentoActivo && (claseActiva === null || especie.clase_activo === claseActiva),
      )
      .map(({ especie }) => especie)
  }, [conEspecie, segmentoActivo, claseActiva])

  const naturaleza = deLaClase[0]?.naturaleza ?? ''

  if (resueltas.length === 0) {
    return (
      <div
        style={{
          marginTop: 16,
          padding: '10px 12px',
          border: '1px dashed var(--lin)',
          borderRadius: 4,
          fontSize: 12,
          color: 'var(--dim)',
        }}
      >
        Sin posiciones de renta fija todavía: agregá papeles para ver la composición de la cartera
        y la curva TIR/duración.
      </div>
    )
  }

  const porClase = composicionPorClase(resueltas, porTicker)
  const porSegmento = composicionPorSegmento(resueltas, porTicker)
  const porEmisor = composicionPorEmisor(resueltas, porTicker)
  const conPesoReal = resueltas.filter((r) => r.pesoReal !== null).length

  return (
    <section
      aria-label="Composición"
      style={{
        marginTop: 16,
        background: 'var(--pan)',
        border: '1px solid var(--lin)',
        borderRadius: 4,
        padding: '12px 16px',
        display: 'grid',
        gap: 14,
      }}
    >
      <header>
        <div className="rotulo">Composición</div>
        <h2 style={{ font: '600 15px/1.3 inherit', margin: '2px 0 0' }}>
          Por clase, segmento y emisor
        </h2>
      </header>

      <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>
        {leyendaDelPeso(conPesoReal, resueltas.length)}
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14 }}>
        <DistribucionBarras titulo="Clase de activo" tramos={porClase} />
        <DistribucionBarras titulo="Segmento" tramos={porSegmento} />
        <DistribucionBarras titulo="Emisor" tramos={porEmisor} />
      </div>

      <div style={{ borderTop: '1px solid var(--lin)', paddingTop: 12 }}>
        <h3
          style={{
            margin: '0 0 8px',
            fontSize: 10,
            color: 'var(--dim)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          Curva TIR/duración
        </h3>

        {activa === null ? (
          <p style={{ margin: 0, fontSize: 12.5, color: 'var(--dim)' }}>
            Ninguna posición de la cartera tiene segmento conocido: no hay curva para elegir.
          </p>
        ) : (
          <>
            <SelectorSegmento segmentos={pestanias} activo={activa} onCambio={setSegmentoElegido} />
            <div style={{ marginTop: 10 }}>
              {universo.isPending && <EstadoCarga que="el universo del segmento" />}
              {universo.isError && (
                <EstadoError error={universo.error} onRetry={() => void universo.refetch()} />
              )}
              {universo.data && (
                <CurvaTirDuracion candidatos={candidatos} cartera={carteraDelSegmento} naturaleza={naturaleza} />
              )}
            </div>
          </>
        )}
      </div>
    </section>
  )
}
