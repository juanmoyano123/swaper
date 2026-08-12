/**
 * Carteras guardadas del asesor (F-041) y seguimiento de las ya vendidas (Sección B del diseño
 * Cordillera, fuera de F-041 — esta pantalla sólo trae el listado de guardadas por ahora).
 *
 * "Se guardan carteras, no clientes" (GWT-4): la bajada lo declara porque es la única pantalla
 * donde el asesor podría, por costumbre, buscar el nombre de un cliente.
 */

import { Link } from 'react-router-dom'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'
import { fmtFechaHora, fmtMonto } from '@/lib/fmt'

import { useCarterasGuardadas } from './hooks/useCarterasGuardadas'
import type { FilaListado } from './lib/esquemaSnapshot'

const ROTULO_ORIGEN: Record<string, string> = { cargada: 'Cartera cargada', armador: 'Armador' }

export function CarterasPage() {
  const consulta = useCarterasGuardadas()

  return (
    <Pantalla
      titulo="Mis carteras"
      bajada="Se guardan carteras, no clientes: no hay ningún campo de identificación personal. El aislamiento entre asesores lo aplica Row Level Security adentro de la base."
    >
      <Panel rotulo="Guardadas">
        {consulta.isPending && <EstadoCarga que="las carteras guardadas" />}
        {consulta.isError && <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />}
        {consulta.data && consulta.data.length === 0 && (
          <EstadoVacio
            titulo="Todavía no hay carteras guardadas."
            detalle="Se guardan desde el armador o desde una cartera cargada, una vez valuada."
          />
        )}
        {consulta.data && consulta.data.length > 0 && <TablaCarteras filas={consulta.data} />}
      </Panel>
    </Pantalla>
  )
}

function TablaCarteras({ filas }: { filas: FilaListado[] }) {
  return (
    <div role="table" aria-label="Carteras guardadas" style={{ display: 'grid', gap: 6 }}>
      {filas.map((fila) => (
        <Link
          key={fila.id}
          to={`/carteras/${fila.id}`}
          role="row"
          style={{
            display: 'grid',
            gridTemplateColumns: '1.4fr auto auto',
            gap: 10,
            alignItems: 'baseline',
            background: 'var(--pan2)',
            border: '1px solid var(--lin)',
            borderRadius: 4,
            padding: '10px 12px',
            textDecoration: 'none',
            color: 'inherit',
          }}
        >
          <div>
            <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--tx)' }}>{fila.nombre}</p>
            <p style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--dim)' }}>
              {ROTULO_ORIGEN[fila.origen] ?? fila.origen} · {fila.resumen}
            </p>
          </div>
          <p className="mono" style={{ margin: 0, fontSize: 12.5, color: 'var(--tx)', whiteSpace: 'nowrap' }}>
            {fmtMonto(fila.monto, 'usd')}
          </p>
          <p className="mono" style={{ margin: 0, fontSize: 11, color: 'var(--dim)', whiteSpace: 'nowrap' }}>
            {fmtFechaHora(fila.snapshot_en)}
          </p>
        </Link>
      ))}
    </div>
  )
}
