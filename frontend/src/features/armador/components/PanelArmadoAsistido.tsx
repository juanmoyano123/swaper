/**
 * El armado asistido: precarga una cartera de arranque a partir del mandato del cliente — F-019.
 *
 * Reemplaza el stub de la base común de la Tanda 10. Formulario chico con los cinco parámetros
 * del mandato (monto, moneda, objetivo de cobertura, perfil, horizonte) — es lo único que
 * `ParametrosArmado` del backend pide como input de esta feature; la sección completa de A1
 * ("Mandato del cliente" con chips de restricciones y "Filtrar universo por mandato") no es esta
 * ficha, y no se construye acá.
 *
 * El botón dispara `useArmadoAsistido`, que en éxito reemplaza la cartera del store entero — es un
 * punto de partida, no un agregado, así que no pide confirmación aunque ya hubiera posiciones
 * cargadas: el asesor sigue pudiendo editar cada una después en `CarteraEditable`.
 */

import { useState, type ReactNode } from 'react'

import { AlertasCalendario } from './AlertasCalendario'
import { useArmadoAsistido } from '../hooks/useArmadoAsistido'
import type { ParametrosArmadoAsistido } from '../lib/schemaArmado'

const MONEDAS: Array<{ valor: ParametrosArmadoAsistido['moneda']; etiqueta: string }> = [
  { valor: 'todas', etiqueta: 'cualquiera' },
  { valor: 'usd', etiqueta: 'dólares' },
  { valor: 'ars', etiqueta: 'pesos' },
]

const COBERTURAS: Array<{ valor: ParametrosArmadoAsistido['cobertura']; etiqueta: string }> = [
  { valor: 'mixta', etiqueta: 'mixta (balanceada)' },
  { valor: 'devaluacion', etiqueta: 'devaluación' },
  { valor: 'inflacion', etiqueta: 'inflación' },
  { valor: 'tasa-pesos', etiqueta: 'tasa en pesos' },
]

const PERFILES: Array<{ valor: ParametrosArmadoAsistido['perfil']; etiqueta: string }> = [
  { valor: 'conservador', etiqueta: 'conservador' },
  { valor: 'moderado', etiqueta: 'moderado' },
  { valor: 'agresivo', etiqueta: 'agresivo' },
]

const HORIZONTES: Array<{ valor: ParametrosArmadoAsistido['horizonte']; etiqueta: string }> = [
  { valor: 'corto', etiqueta: 'corto' },
  { valor: 'medio', etiqueta: 'medio' },
  { valor: 'largo', etiqueta: 'largo' },
]

export function PanelArmadoAsistido() {
  const [monto, setMonto] = useState('')
  const [moneda, setMoneda] = useState<ParametrosArmadoAsistido['moneda']>('todas')
  const [cobertura, setCobertura] = useState<ParametrosArmadoAsistido['cobertura']>('mixta')
  const [perfil, setPerfil] = useState<ParametrosArmadoAsistido['perfil']>('moderado')
  const [horizonte, setHorizonte] = useState<ParametrosArmadoAsistido['horizonte']>('medio')

  const mutacion = useArmadoAsistido()

  const montoNumerico = Number(monto)
  const montoValido = monto !== '' && Number.isFinite(montoNumerico) && montoNumerico > 0

  function armar() {
    if (!montoValido) return
    mutacion.mutate({ monto: montoNumerico, moneda, cobertura, perfil, horizonte })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, margin: '10px 0' }}>
      <div style={estiloFila}>
        <Campo etiqueta="Monto a invertir">
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            style={estiloInput}
          />
        </Campo>

        <Campo etiqueta="Moneda de referencia">
          <select
            value={moneda}
            onChange={(e) => setMoneda(e.target.value as ParametrosArmadoAsistido['moneda'])}
            style={estiloInput}
          >
            {MONEDAS.map((m) => (
              <option key={m.valor} value={m.valor}>
                {m.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="Objetivo de cobertura">
          <select
            value={cobertura}
            onChange={(e) => setCobertura(e.target.value as ParametrosArmadoAsistido['cobertura'])}
            style={estiloInput}
          >
            {COBERTURAS.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="Perfil">
          <select
            value={perfil}
            onChange={(e) => setPerfil(e.target.value as ParametrosArmadoAsistido['perfil'])}
            style={estiloInput}
          >
            {PERFILES.map((p) => (
              <option key={p.valor} value={p.valor}>
                {p.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="Horizonte">
          <select
            value={horizonte}
            onChange={(e) => setHorizonte(e.target.value as ParametrosArmadoAsistido['horizonte'])}
            style={estiloInput}
          >
            {HORIZONTES.map((h) => (
              <option key={h.valor} value={h.valor}>
                {h.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <button
          type="button"
          onClick={armar}
          disabled={!montoValido || mutacion.isPending}
          style={estiloBoton}
        >
          {mutacion.isPending ? 'armando…' : 'Armar cartera asistida'}
        </button>
      </div>

      {mutacion.isError && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--neg)' }}>
          {mutacion.error.message}
        </p>
      )}

      {mutacion.isSuccess && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
          {mutacion.data.posiciones.length} posiciones precargadas · {mutacion.data.origen_mix} ·
          perfil {mutacion.data.perfil} · {mutacion.data.sectores.presentes} de{' '}
          {mutacion.data.sectores.minimo} sectores mínimos
        </p>
      )}

      {mutacion.isSuccess && <AlertasCalendario alertas={mutacion.data.alertas} />}
    </div>
  )
}

function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <label
      style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: 'var(--dim)' }}
    >
      {etiqueta}
      {children}
    </label>
  )
}

const estiloFila = {
  display: 'flex',
  gap: 12,
  alignItems: 'flex-end',
  flexWrap: 'wrap',
} as const

const estiloInput = {
  minWidth: 108,
  font: 'inherit',
  fontSize: 12.5,
  padding: '5px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const

const estiloBoton = {
  font: 'inherit',
  fontSize: 12.5,
  fontWeight: 600,
  padding: '7px 14px',
  borderRadius: 3,
  border: '1px solid var(--ac)',
  background: 'var(--ac)',
  color: 'var(--bg)',
  cursor: 'pointer',
} as const
