/**
 * Agregado de FCI por tipo de renta — F-067.
 *
 * El AUM nunca se muestra como un total único de la categoría: se rompe por moneda (regla 3), y
 * la participación de cada fondo se calcula contra el AUM de su propia moneda. Expandible por
 * fondo con `<details>`, sin estado propio a mantener.
 */

import { EstadoVacio } from '@/components/EstadoVacio'
import { nombreSegmento } from '@/components/SelectorSegmento'
import { claveTipoRenta } from '@/lib/fci'
import { useCategoriasFci, type CategoriaFci } from '@/lib/fciAgregados'
import { fmtCompacto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

export function TablaCategorias() {
  const categorias = useCategoriasFci()

  if (categorias.isPending) {
    return <p style={{ margin: '14px 0', color: 'var(--dim)', fontSize: 12.5 }}>consultando las categorías…</p>
  }

  if (categorias.isError) {
    return (
      <EstadoVacio
        titulo="No se pudieron traer las categorías de FCI."
        detalle={
          <button
            type="button"
            onClick={() => void categorias.refetch()}
            style={{ color: 'var(--ac)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
          >
            reintentar
          </button>
        }
      />
    )
  }

  const lista = categorias.data?.categorias ?? []

  if (lista.length === 0) {
    return (
      <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
        No hay fondos comunes en la planilla de hoy.
      </p>
    )
  }

  return (
    <div>
      {lista.map((categoria) => (
        <BloqueCategoria key={categoria.tipo_renta} categoria={categoria} />
      ))}
    </div>
  )
}

function BloqueCategoria({ categoria }: { categoria: CategoriaFci }) {
  return (
    <section style={{ margin: '0 0 16px' }}>
      <h3 style={{ font: '600 13px/1.3 inherit', margin: '0 0 6px' }}>
        {nombreSegmento(claveTipoRenta(categoria.tipo_renta))}
        <span style={{ fontWeight: 400, color: 'var(--dim)', marginLeft: 8 }}>
          {fmtNumero(categoria.cantidad_fondos, 0)} fondos
        </span>
      </h3>

      {categoria.por_moneda.map((bloque) => (
        <details key={bloque.moneda} style={{ margin: '0 0 6px' }}>
          <summary
            className="mono"
            style={{ cursor: 'pointer', fontSize: 12, padding: '6px 8px', background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 4 }}
          >
            {bloque.moneda} · AUM {bloque.aum === null ? SIN_DATO : fmtCompacto(bloque.aum)} · {fmtNumero(bloque.cantidad_fondos, 0)} fondos
          </summary>
          <div style={{ padding: '4px 8px 8px' }}>
            {bloque.fondos.map((fondo) => (
              <div
                key={fondo.codigo_cafci}
                style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '4px 0', borderBottom: '1px solid var(--lin)', fontSize: 12 }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{fondo.fondo}</span>
                <span className="mono" style={{ whiteSpace: 'nowrap', color: 'var(--dim)' }}>
                  {fondo.patrimonio === null ? SIN_DATO : fmtCompacto(fondo.patrimonio)}
                  {' · '}
                  {fondo.participacion_pct === null ? SIN_DATO : fmtPct(fondo.participacion_pct)}
                </span>
              </div>
            ))}
          </div>
        </details>
      ))}
    </section>
  )
}
