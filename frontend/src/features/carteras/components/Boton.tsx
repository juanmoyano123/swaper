/** El botón de esta feature, en sus tres variantes — mismo criterio que
 *  `features/cartera-ingreso/components/BotonAccion.tsx`: no es un componente del design system
 *  global, es nada más no repetir el mismo objeto de estilos entre Guardar, Revaluar y Borrar. */

import type { ButtonHTMLAttributes } from 'react'

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: 'primario' | 'secundario' | 'peligro'
}

export function Boton({ variante = 'secundario', style, ...resto }: Props) {
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
      : variante === 'peligro'
        ? { border: '1px solid var(--neg)', background: 'transparent', color: 'var(--neg)' }
        : { border: '1px solid var(--lin)', background: 'transparent', color: 'var(--tx)' }

  return <button type="button" style={{ ...base, ...porVariante, ...style }} {...resto} />
}
