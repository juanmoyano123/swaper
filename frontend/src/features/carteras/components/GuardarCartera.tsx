/**
 * Guardar una cartera (F-041) — nombre requerido, descripción opcional. El `snapshot` ya viene
 * armado por el llamador (`armarSnapshotCargada` / `armarSnapshotArmador`), congelado al momento
 * del click: siempre inserta una fila nueva, nunca actualiza una guardada antes — el snapshot es
 * inmutable por definición del GWT-1.
 *
 * "Se guardan carteras, no clientes" (GWT-4): el placeholder del nombre lo recuerda en el punto
 * exacto donde el asesor podría, por costumbre, escribir el nombre de su cliente.
 */

import { useState } from 'react'
import { Link } from 'react-router-dom'

import { montoDeCartera, resumenDeCartera } from '../lib/armarSnapshot'
import type { SnapshotCartera } from '../lib/esquemaSnapshot'
import { useGuardarCartera } from '../hooks/useGuardarCartera'
import { Boton } from './Boton'

const campoEstilo = {
  font: 'inherit',
  fontSize: 12.5,
  padding: '6px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const

export function GuardarCartera({ snapshot }: { snapshot: SnapshotCartera }) {
  const [nombre, setNombre] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const guardar = useGuardarCartera()

  if (guardar.isSuccess) {
    return (
      <p style={{ margin: 0, fontSize: 12.5, color: 'var(--pos)' }}>
        Cartera guardada.{' '}
        <Link to={`/carteras/${guardar.data.id}`} style={{ color: 'var(--ac)' }}>
          Verla en Mis carteras
        </Link>
        .
      </p>
    )
  }

  return (
    <form
      aria-label="Guardar cartera"
      onSubmit={(evento) => {
        evento.preventDefault()
        const nombreLimpio = nombre.trim()
        if (nombreLimpio.length === 0) return
        guardar.mutate({
          nombre: nombreLimpio,
          descripcion: descripcion.trim().length > 0 ? descripcion.trim() : null,
          origen: snapshot.origen,
          monedaReferencia: 'usd',
          monto: montoDeCartera(snapshot),
          resumen: resumenDeCartera(snapshot),
          snapshotEn: new Date().toISOString(),
          snapshot,
        })
      }}
      style={{ display: 'grid', gap: 8, maxWidth: 420 }}
    >
      <label style={{ display: 'grid', gap: 4, fontSize: 11.5, color: 'var(--dim)' }}>
        Nombre de la cartera
        <input
          value={nombre}
          onChange={(evento) => setNombre(evento.target.value)}
          required
          placeholder="Ej: Renta USD · perfil moderado"
          style={campoEstilo}
        />
      </label>
      <label style={{ display: 'grid', gap: 4, fontSize: 11.5, color: 'var(--dim)' }}>
        Descripción (opcional)
        <input value={descripcion} onChange={(evento) => setDescripcion(evento.target.value)} style={campoEstilo} />
      </label>
      <div>
        <Boton type="submit" variante="primario" disabled={guardar.isPending || nombre.trim().length === 0}>
          {guardar.isPending ? 'Guardando…' : 'Guardar cartera'}
        </Boton>
      </div>
      {guardar.isError && (
        <p role="alert" style={{ margin: 0, fontSize: 11, color: 'var(--neg)' }}>
          {(guardar.error as Error).message}
        </p>
      )}
    </form>
  )
}
