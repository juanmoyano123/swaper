/**
 * Select compacto con rótulo arriba — F-079, Fase 4.
 *
 * Reemplaza las cuatro copias locales del mismo par rótulo+select (`estiloInput` de
 * `features/monitor/components/FiltrosPerfil.tsx` y `features/armador/components/
 * FiltrosGrilla.tsx`/`PanelArmadoAsistido.tsx`, `estiloSelectPicker` de
 * `features/armador/components/BloqueRentaVariable.tsx`) por un único componente compartido en
 * `src/components/`, para que el monitor y el armador — que tienen prohibido importarse entre sí
 * (precedente F-017/F-038) — puedan converger en el mismo look sin duplicar el estilo.
 *
 * El estilo tomado como base es `estiloSelectPicker`: es el más nuevo de las cuatro copias y ya
 * está pensado para empaquetar varios selects en poco espacio (D4 del plan F-079, ~90px de cromo).
 *
 * **No agrega ninguna opción por su cuenta** —ni "todos" ni ningún placeholder—: `opciones` es la
 * lista completa a renderizar, en el orden que decida quien lo usa. Así conviven sin que el
 * componente tenga que adivinar cuál es cuál: un select de valores fijos (Moneda, Perfil…, sin
 * "todos") y uno facetado (Ley, Sector…, con "todos" como primera opción) arman esa primera opción
 * ellos mismos y se la pasan como una fila más de `opciones`.
 *
 * El rótulo sigue envolviendo el control (`<label>{etiqueta}<select>…`), como ya hacían las cuatro
 * copias: es lo que le da nombre accesible al select sin declarar un `id` a mano en cada sitio.
 */

import type { CSSProperties } from 'react'

export interface OpcionCampoSelect {
  valor: string
  texto: string
  /** Tooltip de esta opción puntual (no del select entero) — p. ej. la fuente de una etiqueta sin
   *  traducción curada. F-079. `undefined` no renderiza `title` en el `<option>`. */
  title?: string
}

export function CampoSelect({
  etiqueta,
  valor,
  onChange,
  opciones,
  title,
  disabled,
}: {
  etiqueta: string
  valor: string
  onChange: (valor: string) => void
  opciones: OpcionCampoSelect[]
  /** Tooltip con la fuente del dato, ej. `"SIC 73 — Services-Prepackaged Software (SEC)"`. */
  title?: string
  disabled?: boolean
}) {
  return (
    <label style={estiloRotulo}>
      {etiqueta}
      <select
        value={valor}
        disabled={disabled}
        title={title}
        onChange={(evento) => onChange(evento.target.value)}
        style={estiloSelect}
      >
        {opciones.map((opcion) => (
          <option key={opcion.valor} value={opcion.valor} title={opcion.title}>
            {opcion.texto}
          </option>
        ))}
      </select>
    </label>
  )
}

const estiloRotulo: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 3,
  fontSize: 11,
  color: 'var(--dim)',
}

const estiloSelect: CSSProperties = {
  minWidth: 140,
  font: 'inherit',
  fontSize: 12,
  padding: '4px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
}
