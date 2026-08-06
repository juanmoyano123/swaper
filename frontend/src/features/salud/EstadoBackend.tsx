/**
 * Indicador de conexión en la barra superior.
 *
 * Ocupa el lugar donde F-013 va a montar la barra de estado del dato completa —hora del último
 * refresh, demora declarada de la fuente, cobertura de campos—. Hasta entonces informa lo único
 * que F-003 puede saber de verdad: si el backend contesta.
 */

import { useSalud } from './useSalud'

export function EstadoBackend() {
  const { data, isPending, isError } = useSalud()

  const conectado = !isError && data?.status === 'ok'
  const color = isPending ? 'var(--dim)' : conectado ? 'var(--pos)' : 'var(--neg)'
  const texto = isPending ? 'consultando' : conectado ? 'conectado' : 'servicio no disponible'

  return (
    <div
      className="mono"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        border: '1px solid var(--lin)',
        borderRadius: 3,
        padding: '4px 9px',
        fontSize: 11,
        color: 'var(--dim)',
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: color,
          animation: conectado ? 'pulso 1.6s infinite' : undefined,
        }}
      />
      <span style={{ color }}>{texto}</span>
    </div>
  )
}
