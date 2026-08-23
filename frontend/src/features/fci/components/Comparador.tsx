/**
 * Comparador de 2 a 4 fondos comunes de inversión, lado a lado — F-067.
 *
 * Sin endpoint propio: usa `useFondosFci(null)` (todos los fondos) filtrando por nombre en el
 * cliente. Fondos de distinta moneda se comparan tal cual, sin convertir ni calcular una
 * diferencia entre monedas (regla 3) — el asesor lee dos columnas con unidades distintas, no un
 * spread inventado.
 */

import { useMemo, useState } from 'react'

import { EstadoVacio } from '@/components/EstadoVacio'
import { useFondosFci, type FondoFci } from '@/lib/fci'
import { fmtCompacto, fmtFecha, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

const MIN_FONDOS = 2
const MAX_FONDOS = 4
const LARGO_MINIMO_BUSQUEDA = 2
const TOPE_COINCIDENCIAS = 20

export function Comparador() {
  const fondos = useFondosFci(null)
  const [busqueda, setBusqueda] = useState('')
  const [seleccionados, setSeleccionados] = useState<string[]>([])

  const coincidencias = useMemo(() => {
    if (busqueda.trim().length < LARGO_MINIMO_BUSQUEDA) return []
    const texto = busqueda.trim().toLowerCase()
    return (fondos.data ?? [])
      .filter((f) => !seleccionados.includes(f.codigo_cafci) && f.fondo.toLowerCase().includes(texto))
      .slice(0, TOPE_COINCIDENCIAS)
  }, [fondos.data, busqueda, seleccionados])

  const fondosSeleccionados = useMemo(() => {
    const porCodigo = new Map((fondos.data ?? []).map((f) => [f.codigo_cafci, f]))
    return seleccionados.map((c) => porCodigo.get(c)).filter((f): f is FondoFci => f !== undefined)
  }, [fondos.data, seleccionados])

  function agregar(codigoCafci: string) {
    if (seleccionados.length >= MAX_FONDOS) return
    setSeleccionados((actual) => [...actual, codigoCafci])
    setBusqueda('')
  }

  function quitar(codigoCafci: string) {
    setSeleccionados((actual) => actual.filter((c) => c !== codigoCafci))
  }

  if (fondos.isPending) {
    return <p style={{ margin: '14px 0', color: 'var(--dim)', fontSize: 12.5 }}>consultando los fondos…</p>
  }

  if (fondos.isError) {
    return (
      <EstadoVacio
        titulo="No se pudieron traer los fondos."
        detalle={
          <button
            type="button"
            onClick={() => void fondos.refetch()}
            style={{ color: 'var(--ac)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
          >
            reintentar
          </button>
        }
      />
    )
  }

  return (
    <div>
      <p style={{ margin: '0 0 8px', fontSize: 12, color: 'var(--dim)' }}>
        Elegí entre {MIN_FONDOS} y {MAX_FONDOS} fondos. Fondos de distinta moneda se muestran tal cual, sin convertir.
      </p>

      <input
        type="text"
        value={busqueda}
        onChange={(e) => setBusqueda(e.target.value)}
        placeholder={seleccionados.length >= MAX_FONDOS ? `Ya elegiste ${MAX_FONDOS} fondos` : 'Buscar fondo por nombre…'}
        disabled={seleccionados.length >= MAX_FONDOS}
        style={{
          width: '100%',
          maxWidth: 420,
          padding: '6px 8px',
          fontSize: 12.5,
          background: 'var(--pan2)',
          border: '1px solid var(--lin)',
          borderRadius: 4,
          color: 'var(--tx)',
        }}
      />

      {coincidencias.length > 0 && (
        <ul style={{ listStyle: 'none', margin: '4px 0 0', padding: 0, maxWidth: 420, border: '1px solid var(--lin)', borderRadius: 4, overflow: 'hidden' }}>
          {coincidencias.map((f) => (
            <li key={f.codigo_cafci}>
              <button
                type="button"
                onClick={() => agregar(f.codigo_cafci)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: '6px 8px',
                  fontSize: 12,
                  background: 'none',
                  border: 'none',
                  borderBottom: '1px solid var(--lin)',
                  cursor: 'pointer',
                  color: 'var(--tx)',
                }}
              >
                {f.fondo} <span className="mono" style={{ color: 'var(--dim)' }}>· {f.moneda}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {fondosSeleccionados.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '10px 0' }}>
          {fondosSeleccionados.map((f) => (
            <span
              key={f.codigo_cafci}
              className="mono"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, padding: '4px 8px', background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 12 }}
            >
              {f.fondo}
              <button
                type="button"
                onClick={() => quitar(f.codigo_cafci)}
                aria-label={`Quitar ${f.fondo} de la comparación`}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--dim)', font: 'inherit' }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {fondosSeleccionados.length < MIN_FONDOS ? (
        <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
          Elegí al menos {MIN_FONDOS} fondos para ver la comparación.
        </p>
      ) : (
        <TablaComparacion fondos={fondosSeleccionados} />
      )}
    </div>
  )
}

const FILAS: { etiqueta: string; valor: (f: FondoFci) => string }[] = [
  { etiqueta: 'Moneda', valor: (f) => f.moneda },
  {
    etiqueta: 'VCP (por mil)',
    valor: (f) => `${fmtNumero(f.vcp)}${f.fecha_vcp ? ` (al ${fmtFecha(f.fecha_vcp)})` : ''}`,
  },
  { etiqueta: 'Variación diaria', valor: (f) => fmtPct(f.var_diaria_pct) },
  { etiqueta: 'Variación mensual', valor: (f) => fmtPct(f.var_mes_pct) },
  { etiqueta: 'Variación anual', valor: (f) => fmtPct(f.var_anio_pct) },
  { etiqueta: 'Variación 12 meses', valor: (f) => fmtPct(f.var_12m_pct) },
  { etiqueta: 'Patrimonio', valor: (f) => fmtCompacto(f.patrimonio) },
  {
    etiqueta: 'Plazo de rescate (días)',
    valor: (f) => (f.dias_para_rescatar === null ? SIN_DATO : fmtNumero(f.dias_para_rescatar, 0)),
  },
  { etiqueta: 'Calificación', valor: (f) => f.calificacion ?? 'no informada' },
  { etiqueta: 'Sociedad gerente', valor: (f) => f.gerente ?? SIN_DATO },
  { etiqueta: 'Sociedad depositaria', valor: (f) => f.depositaria ?? SIN_DATO },
  { etiqueta: 'Comisión de ingreso', valor: (f) => (f.comision_ingreso === null ? SIN_DATO : fmtPct(f.comision_ingreso)) },
  { etiqueta: 'Honorarios adm. sociedad gerente', valor: (f) => (f.honorarios_adm_sg === null ? SIN_DATO : fmtPct(f.honorarios_adm_sg)) },
  { etiqueta: 'Gastos ordinarios de gestión', valor: (f) => (f.gastos_ord_gestion === null ? SIN_DATO : fmtPct(f.gastos_ord_gestion)) },
  { etiqueta: 'Comisión de rescate', valor: (f) => (f.comision_rescate === null ? SIN_DATO : fmtPct(f.comision_rescate)) },
]

function TablaComparacion({ fondos }: { fondos: FondoFci[] }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12 }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '6px 8px', borderBottom: '1px solid var(--lin)' }} />
            {fondos.map((f) => (
              <th
                key={f.codigo_cafci}
                style={{ textAlign: 'left', padding: '6px 8px', borderBottom: '1px solid var(--lin)', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap' }}
              >
                {f.fondo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {FILAS.map((fila) => (
            <tr key={fila.etiqueta}>
              <td style={{ padding: '5px 8px', color: 'var(--dim)', borderBottom: '1px solid var(--lin)', whiteSpace: 'nowrap' }}>
                {fila.etiqueta}
              </td>
              {fondos.map((f) => (
                <td key={f.codigo_cafci} className="mono" style={{ padding: '5px 8px', borderBottom: '1px solid var(--lin)', whiteSpace: 'nowrap' }}>
                  {fila.valor(f)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
