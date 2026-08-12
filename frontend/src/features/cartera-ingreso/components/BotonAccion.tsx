/**
 * El botón de acción de esta feature, en sus dos variantes.
 *
 * No es un componente nuevo del design system global —esa decisión es de otra fase—, es nada más
 * la manera de no repetir seis veces el mismo objeto de estilos entre pegado, archivo, mapeo,
 * manual y previsualización.
 */

import type { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: 'primario' | 'secundario'
}

export function BotonAccion({ variante = 'secundario', style, ...resto }: Props) {
  const base = {
    font: 'inherit',
    fontSize: 12.5,
    fontWeight: 600,
    padding: '7px 14px',
    borderRadius: 3,
    cursor: 'pointer',
  } as const

  const porVariante =
    variante === 'primario'
      ? { border: '1px solid var(--ac)', background: 'var(--ac)', color: '#08120c' }
      : { border: '1px solid var(--lin)', background: 'transparent', color: 'var(--tx)' }

  return <button type="button" style={{ ...base, ...porVariante, ...style }} {...resto} />
}
