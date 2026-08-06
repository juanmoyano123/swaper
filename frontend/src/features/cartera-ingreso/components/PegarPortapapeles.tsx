/**
 * La vía más usada: pegar el resumen de cuenta tal como sale de la plataforma de origen.
 *
 * No se interpreta al vuelo con cada tecla — recién al apretar "Interpretar", porque un pegado a
 * medio escribir no es un dato, es ruido, y parsearlo en cada cambio solo produciría errores
 * intermedios que no le sirven a nadie.
 */

import { useState } from 'react'

import { BotonAccion } from './BotonAccion'

export function PegarPortapapeles({
  textoInicial,
  onInterpretar,
  onVolver,
}: {
  textoInicial: string
  onInterpretar: (texto: string) => void
  onVolver: () => void
}) {
  const [texto, setTexto] = useState(textoInicial)

  return (
    <div>
      <label
        htmlFor="pegado-cartera"
        style={{ display: 'block', fontSize: 12.5, color: 'var(--dim)', marginBottom: 6 }}
      >
        Pegá acá el resumen de cuenta.
      </label>
      <textarea
        id="pegado-cartera"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        rows={10}
        placeholder={'AL30D\t1200\nGD35\t850,50\nMR46O\t3.000'}
        className="mono"
        style={{
          width: '100%',
          resize: 'vertical',
          background: 'var(--pan2)',
          border: '1px solid var(--lin)',
          borderRadius: 4,
          color: 'var(--tx)',
          fontSize: 12,
          padding: '8px 10px',
        }}
      />
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <BotonAccion variante="primario" onClick={() => onInterpretar(texto)} disabled={texto.trim() === ''}>
          Interpretar
        </BotonAccion>
        <BotonAccion onClick={onVolver}>Volver</BotonAccion>
      </div>
    </div>
  )
}
