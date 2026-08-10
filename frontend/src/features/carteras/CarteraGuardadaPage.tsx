/**
 * El detalle de una cartera guardada (F-041) — `/carteras/:id`. Página completa y no drawer: dos
 * valuaciones lado a lado (la congelada y "hoy") necesitan el ancho de una pantalla, y F-042
 * (export) va a partir de esta vista.
 *
 * Por defecto muestra sólo lo congelado (GWT-1): `VistaCongelada` no dispara ningún pedido de
 * mercado. "Revaluar a hoy" es la única puerta a precios de hoy, y el asesor la abre a propósito.
 */

import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'
import { fmtFechaHora, fmtMonto } from '@/lib/fmt'

import { Boton } from './components/Boton'
import { Revaluacion } from './components/Revaluacion'
import { VistaCongelada } from './components/VistaCongelada'
import { useBorrarCartera } from './hooks/useBorrarCartera'
import { useCarteraGuardada } from './hooks/useCarteraGuardada'
import { mandatoDesdeSnapshotArmador } from './lib/revaluacion'

export function CarteraGuardadaPage() {
  const { id } = useParams<{ id: string }>()
  const consulta = useCarteraGuardada(id ?? '')
  const borrar = useBorrarCartera()
  const navigate = useNavigate()
  const [confirmandoBorrado, setConfirmandoBorrado] = useState(false)

  return (
    <Pantalla
      titulo={consulta.data?.nombre ?? 'Cartera guardada'}
      bajada="Se muestra tal como se guardó. «Revaluar a hoy» compara contra los precios de ahora, con la fecha de cada punta."
    >
      {consulta.isPending && <EstadoCarga que="la cartera guardada" />}
      {consulta.isError && <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />}

      {consulta.data && (
        <div style={{ display: 'grid', gap: 16 }}>
          <Panel>
            <p className="mono" style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
              Guardada el {fmtFechaHora(consulta.data.snapshotEn)} · Monto: {fmtMonto(consulta.data.monto, 'usd')}
            </p>
            {consulta.data.descripcion && (
              <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--sd)', textWrap: 'pretty' }}>
                {consulta.data.descripcion}
              </p>
            )}
            <p style={{ margin: '4px 0 0', fontSize: 11.5, color: 'var(--dim)' }}>{consulta.data.resumen}</p>
          </Panel>

          {consulta.data.snapshot ? (
            <Panel rotulo="Detalle" ariaLabel="Detalle de la cartera guardada">
              <VistaCongelada snapshot={consulta.data.snapshot} />
              <div style={{ marginTop: 14 }}>
                <Revaluacion snapshot={consulta.data.snapshot} snapshotEn={consulta.data.snapshotEn} />
              </div>
            </Panel>
          ) : (
            <Panel ariaLabel="Detalle de la cartera guardada">
              <p style={{ margin: 0, fontSize: 12.5, color: 'var(--neg)' }}>
                No se pudo leer el snapshot de esta cartera.
              </p>
            </Panel>
          )}

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            {consulta.data.snapshot?.origen === 'armador' && (
              <Boton
                onClick={() => {
                  const snapshot = consulta.data.snapshot
                  if (!snapshot || snapshot.origen !== 'armador') return
                  navigate('/armador', {
                    state: {
                      carteraGuardada: {
                        posiciones: mandatoDesdeSnapshotArmador(snapshot),
                        montoTotalUsd: snapshot.montoTotalUsd,
                      },
                    },
                  })
                }}
              >
                Abrir en el armador
              </Boton>
            )}

            {confirmandoBorrado ? (
              <>
                <span style={{ fontSize: 11.5, color: 'var(--dim)' }}>¿Borrar esta cartera guardada?</span>
                <Boton
                  variante="peligro"
                  disabled={borrar.isPending}
                  onClick={() => {
                    if (!id) return
                    borrar.mutate(id, { onSuccess: () => navigate('/carteras') })
                  }}
                >
                  {borrar.isPending ? 'Borrando…' : 'Confirmar'}
                </Boton>
                <Boton onClick={() => setConfirmandoBorrado(false)}>Cancelar</Boton>
              </>
            ) : (
              <Boton variante="peligro" onClick={() => setConfirmandoBorrado(true)}>
                Borrar
              </Boton>
            )}
          </div>

          {borrar.isError && (
            <p role="alert" style={{ margin: 0, fontSize: 11, color: 'var(--neg)' }}>
              {(borrar.error as Error).message}
            </p>
          )}
        </div>
      )}
    </Pantalla>
  )
}
