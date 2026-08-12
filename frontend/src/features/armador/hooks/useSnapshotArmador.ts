/**
 * F-042 — arma el snapshot congelado del mandato del armador, con los atributos de mercado que el
 * export necesita (naturaleza, lámina, vector de seis ejes, calendario de cupones, fuente del
 * dato) además de lo que F-041 ya congelaba. Lo consumen `GuardarCarteraArmador` (al guardar) y el
 * botón "Descargar propuesta" de `ColumnaKpis` (al exportar en curso) — un solo armado, para que
 * ninguno de los dos duplique pedidos ni diverja del otro.
 *
 * **El perfil de concentración queda fijo en `moderado` y declarado en `perfilConcentracion`.** El
 * armador no tiene, hoy, un selector de perfil para el vector de riesgo al momento de guardar (sólo
 * lo tiene `PanelRiesgo` como estado local de esa pantalla); en vez de adivinar cuál usó el asesor,
 * se fija uno y se declara cuál — nunca implícito.
 */

import { useMemo } from 'react'

import { armarMercadoCongelado, armarSnapshotArmador } from '@/features/carteras/lib/armarSnapshot'
import type { SnapshotArmador } from '@/features/carteras/lib/esquemaSnapshot'
import { useEstadoDelDato } from '@/features/estado-dato/hooks/useEstadoDelDato'
import { useCalendarioCartera } from '@/lib/cartera/hooks/useCalendarioCartera'
import { useConcentracion } from '@/lib/cartera/hooks/useConcentracion'
import { especieDeRiesgo, vectorDeRiesgo, type EspecieRiesgo } from '@/lib/cartera/riesgo'
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'

import { useCarteraResuelta } from './useCarteraResuelta'
import { useRentaVariableResuelta } from './useRentaVariableResuelta'
import { useArmador } from '../store/carteraStore'

const PERFIL_CONCENTRACION_ARMADOR: NombreDePerfil = 'moderado'

export function useSnapshotArmador(): SnapshotArmador | null {
  const { pos, montoTotal } = useArmador()
  const carteraResuelta = useCarteraResuelta()
  const rentaVariableResuelta = useRentaVariableResuelta()
  const estadoDelDato = useEstadoDelDato()

  const posicionesConPeso = useMemo(
    () => carteraResuelta.resueltas.map((r) => ({ ticker: r.ticker, peso: r.pesoReal ?? r.peso })),
    [carteraResuelta.resueltas],
  )
  const concentracion = useConcentracion(posicionesConPeso, PERFIL_CONCENTRACION_ARMADOR)
  const calendario = useCalendarioCartera(carteraResuelta.posicionesParaCalendario)

  const porTickerRiesgo = useMemo(() => {
    const mapa = new Map<string, EspecieRiesgo>()
    for (const especie of carteraResuelta.porTicker.values()) mapa.set(especie.ticker, especieDeRiesgo(especie))
    return mapa
  }, [carteraResuelta.porTicker])

  const vector = useMemo(
    () =>
      posicionesConPeso.length > 0
        ? vectorDeRiesgo(posicionesConPeso, porTickerRiesgo, concentracion.data ?? null)
        : null,
    [posicionesConPeso, porTickerRiesgo, concentracion.data],
  )

  const tickers = useMemo(() => pos.map((p) => p.ticker), [pos])

  const mercado = useMemo(
    () =>
      armarMercadoCongelado({
        tickers,
        porTickerRentaFija: carteraResuelta.porTicker,
        porTickerRentaVariable: rentaVariableResuelta.porTicker,
        vector,
        perfilConcentracion: PERFIL_CONCENTRACION_ARMADOR,
        calendario: calendario.data ?? null,
        estadoDelDato: estadoDelDato.data ?? null,
      }),
    [
      tickers,
      carteraResuelta.porTicker,
      rentaVariableResuelta.porTicker,
      vector,
      calendario.data,
      estadoDelDato.data,
    ],
  )

  const snapshot = useMemo(
    () =>
      armarSnapshotArmador(
        pos,
        carteraResuelta.resueltas,
        carteraResuelta.porTicker,
        rentaVariableResuelta.resueltas,
        rentaVariableResuelta.porTicker,
        carteraResuelta.tipoDeCambio,
        montoTotal,
        mercado,
      ),
    [
      pos,
      carteraResuelta.resueltas,
      carteraResuelta.porTicker,
      carteraResuelta.tipoDeCambio,
      rentaVariableResuelta.resueltas,
      rentaVariableResuelta.porTicker,
      montoTotal,
      mercado,
    ],
  )

  return pos.length === 0 || montoTotal === 0 ? null : snapshot
}
