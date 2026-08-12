/**
 * Los atajos temáticos, arriba de los filtros — Tanda 13.
 *
 * Un clic deja la grilla filtrada por el sector del tema y, si el preset lo define, el bloque de
 * renta variable filtrado por el rubro equivalente. Los filtros quedan visibles y editables abajo:
 * el chip es un punto de partida, no un modo.
 *
 * El chip se apaga solo cuando los filtros dejan de coincidir con lo que dejó puesto (porque el
 * asesor tocó alguno a mano), pero no deshace nada: seguir mostrando "Energía" prendido sobre una
 * grilla que ya muestra otra cosa sería mentir sobre el estado.
 */

import { useArmador, useArmadorAcciones } from '../store/carteraStore'
import {
  coincideConPreset,
  filtrosDelPreset,
  PRESETS_TEMATICOS,
  type PresetTematico,
} from '../lib/tematicas'

export function ChipsTematicos() {
  const { filtros, tematicaId } = useArmador()
  const { aplicarTematica, limpiarFiltros } = useArmadorAcciones()

  function alternar(preset: PresetTematico, activo: boolean) {
    if (activo) limpiarFiltros()
    else aplicarTematica(preset.id, filtrosDelPreset(preset))
  }

  return (
    <div
      role="group"
      aria-label="Temáticas"
      style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginBottom: 10 }}
    >
      <span
        style={{
          fontSize: 10,
          color: 'var(--dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          marginRight: 2,
        }}
      >
        Temáticas
      </span>
      {PRESETS_TEMATICOS.map((preset) => {
        // Prendido sólo si el chip es el aplicado Y los filtros siguen siendo los suyos: alcanza
        // con que el asesor cambie un select para que deje de describir lo que se ve.
        const activo = tematicaId === preset.id && coincideConPreset(filtros, preset)
        return (
          <button
            key={preset.id}
            type="button"
            onClick={() => alternar(preset, activo)}
            aria-pressed={activo}
            title={preset.nota}
            style={{
              font: 'inherit',
              fontSize: 11.5,
              padding: '4px 11px',
              borderRadius: 12,
              border: `1px solid ${activo ? 'var(--ac)' : 'var(--lin)'}`,
              background: activo ? 'var(--ac)' : 'transparent',
              color: activo ? 'var(--bg)' : 'var(--dim)',
              cursor: 'pointer',
            }}
          >
            {preset.etiqueta}
          </button>
        )
      })}
    </div>
  )
}
