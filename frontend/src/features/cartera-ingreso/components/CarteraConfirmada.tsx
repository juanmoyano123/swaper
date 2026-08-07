/**
 * El final de F-028 y el enganche con F-029: la lista quedó confirmada y se resuelve.
 *
 * F-028 termina acá y no sabe nada de instrumentos: lo que produce es la lista cruda. Quién es cada
 * ticker lo contesta `ResolucionCartera`, que es F-029 y vive en su propia feature — este
 * componente sólo le pasa las posiciones. La división importa: si la resolución viviera acá, el
 * ingreso de cartera dependería del backend para poder terminar, y hoy no depende de nada.
 */

import { ResolucionCartera } from '@/features/cartera-resolucion/components/ResolucionCartera'

import type { PosicionCruda } from '../types'

import { BotonAccion } from './BotonAccion'

export function CarteraConfirmada({
  posiciones,
  onCargarOtra,
}: {
  posiciones: PosicionCruda[]
  onCargarOtra: () => void
}) {
  const invalidas = posiciones.filter((p) => !p.valida).length

  return (
    <div>
      <p style={{ margin: '0 0 10px', fontSize: 12.5, color: 'var(--dim)' }}>
        Cartera cargada: {posiciones.length} {posiciones.length === 1 ? 'posición' : 'posiciones'}
        {invalidas > 0 && (
          <span style={{ color: 'var(--neg)' }}> ({invalidas} con la fila mal leída)</span>
        )}
        {'.'}
      </p>

      {/* Se mandan también las inválidas: una fila que no se pudo leer sigue siendo plata del
          cliente, y sacarla del pedido la sacaría del diagnóstico de cobertura. */}
      <ResolucionCartera posiciones={posiciones} />

      <div style={{ marginTop: 14 }}>
        <BotonAccion onClick={onCargarOtra}>Cargar otra cartera</BotonAccion>
      </div>
    </div>
  )
}
