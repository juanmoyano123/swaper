/**
 * F-041 — arma el snapshot del mandato armado acá (renta fija + FCI de `useCarteraResuelta`, renta
 * variable de `useRentaVariableResuelta`) y lo pasa al formulario compartido de `features/carteras`.
 * Vive en `armador` y no en `carteras`: necesita los hooks del store del armador, que
 * `features/carteras` no conoce — sólo recibe el snapshot ya armado.
 */

import { useMemo } from 'react'

import { GuardarCartera } from '@/features/carteras/components/GuardarCartera'
import { armarSnapshotArmador } from '@/features/carteras/lib/armarSnapshot'

import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { useRentaVariableResuelta } from '../hooks/useRentaVariableResuelta'
import { useArmador } from '../store/carteraStore'

export function GuardarCarteraArmador() {
  const { pos, montoTotal } = useArmador()
  const carteraResuelta = useCarteraResuelta()
  const rentaVariableResuelta = useRentaVariableResuelta()

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
      ),
    [
      pos,
      carteraResuelta.resueltas,
      carteraResuelta.porTicker,
      carteraResuelta.tipoDeCambio,
      rentaVariableResuelta.resueltas,
      rentaVariableResuelta.porTicker,
      montoTotal,
    ],
  )

  if (pos.length === 0 || montoTotal === 0) {
    return (
      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
        Armá una cartera y cargá el capital objetivo para poder guardarla.
      </p>
    )
  }

  return <GuardarCartera snapshot={snapshot} />
}
