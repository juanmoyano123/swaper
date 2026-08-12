/**
 * F-041/F-042 — arma el snapshot del mandato armado (renta fija + FCI, renta variable, y desde
 * F-042 los atributos de mercado para exportar) y lo pasa al formulario compartido de
 * `features/carteras`. Vive en `armador` y no en `carteras`: necesita los hooks del store del
 * armador, que `features/carteras` no conoce — sólo recibe el snapshot ya armado.
 *
 * El armado en sí vive en `useSnapshotArmador`, compartido con el botón "Descargar propuesta" de
 * `ColumnaKpis` — un solo cálculo, sin duplicar pedidos ni poder divergir entre los dos.
 */

import { GuardarCartera } from '@/features/carteras/components/GuardarCartera'

import { useSnapshotArmador } from '../hooks/useSnapshotArmador'

export function GuardarCarteraArmador() {
  const snapshot = useSnapshotArmador()

  if (!snapshot) {
    return (
      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
        Armá una cartera y cargá el capital objetivo para poder guardarla.
      </p>
    )
  }

  return <GuardarCartera snapshot={snapshot} />
}
