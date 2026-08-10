/**
 * El final de F-028 y el enganche con F-029: la lista quedó confirmada y se resuelve.
 *
 * F-028 termina acá y no sabe nada de instrumentos: lo que produce es la lista cruda. Quién es cada
 * ticker lo contesta `ResolucionCartera`, que es F-029 y vive en su propia feature — este
 * componente sólo le pasa las posiciones. La división importa: si la resolución viviera acá, el
 * ingreso de cartera dependería del backend para poder terminar, y hoy no depende de nada.
 *
 * **Tanda 11:** `DiagnosticoCartera` (F-030) se monta debajo de `ResolucionCartera`, con el mismo
 * criterio — recibe las posiciones crudas y resuelve por su cuenta lo que necesita valuar la
 * cartera. Base común de la tanda; el cuerpo lo reemplaza F-030.
 *
 * **Tanda 13:** `SeccionBajarRiesgo` (F-033) necesita posiciones con peso y el perfil elegido, que
 * `DiagnosticoCartera` calcula puertas adentro (no los expone). En vez de tocar ese componente
 * (fuera de la columna de F-033), este archivo llama a la misma `useCarteraCargadaValuada` que ya
 * usa el diagnóstico — TanStack Query dedupea por clave, así que no dispara un segundo pedido — y
 * mantiene su propio estado de perfil, independiente del selector de `DiagnosticoCartera`: elegir
 * un perfil para medir concentración no tiene por qué ser el mismo perfil contra el que se buscan
 * rotaciones.
 *
 * **Tanda 15 (F-036):** el bloque del optimizador se monta dentro de `PlanRotacionProvider`, con
 * `key={firmaDePesos(...)}` — confirmar otra cartera desmonta el plan de rotaciones de la anterior y
 * arranca uno vacío. `BloqueOptimizador` lee el plan y pasa a las dos secciones la cartera
 * acumulada, las claves ya decididas en la sesión y los montos de la cartera propuesta.
 *
 * **Tanda 16 (F-037):** `BloqueOptimizador` suma `ComparacionCarteras` debajo de `PlanDeRotacion`,
 * con los mismos `montosOriginales`/`propuesta` que ya calculaba para las otras dos secciones — no
 * agrega ningún pedido nuevo al backend, sólo un consumidor más de lo que ya está en caché.
 */

import { useState } from 'react'

import { DiagnosticoCartera } from '@/features/cartera-diagnostico/components/DiagnosticoCartera'
import { useCarteraCargadaValuada } from '@/features/cartera-diagnostico/hooks/useCarteraCargadaValuada'
import { ResolucionCartera } from '@/features/cartera-resolucion/components/ResolucionCartera'
import { firmaDePesos, type PosicionConPeso } from '@/lib/cartera/hooks/useConcentracion'
import { PERFILES, type NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import type { PosicionConMonto } from '@/lib/rotaciones/plan'

import type { PosicionCruda } from '../types'

import { ComparacionCarteras } from '@/features/optimizador/components/ComparacionCarteras'
import { PlanDeRotacion } from '@/features/optimizador/components/PlanDeRotacion'
import { SeccionBajarRiesgo } from '@/features/optimizador/components/SeccionBajarRiesgo'
import { SeccionSubirTir } from '@/features/optimizador/components/SeccionSubirTir'
import { useCarteraPropuesta } from '@/features/optimizador/hooks/useCarteraPropuesta'
import { PlanRotacionProvider, usePlanRotacion } from '@/features/optimizador/store/planRotacionStore'

import { BotonAccion } from './BotonAccion'

function BloqueOptimizador({ montosOriginales, perfil }: { montosOriginales: PosicionConMonto[]; perfil: NombreDePerfil }) {
  const plan = usePlanRotacion()
  const propuesta = useCarteraPropuesta(montosOriginales)

  return (
    <>
      <div style={{ display: 'grid', gap: 12 }}>
        <SeccionBajarRiesgo
          posiciones={plan.posicionesAcumuladas}
          perfil={perfil}
          excluir={plan.clavesExcluidas}
          montos={propuesta.montos}
          monedaDe={propuesta.monedaDe}
          tipoDeCambio={propuesta.tipoDeCambio}
          noConvertibles={propuesta.noConvertibles}
        />
        <SeccionSubirTir
          posiciones={plan.posicionesAcumuladas}
          perfil={perfil}
          excluir={plan.clavesExcluidas}
          montos={propuesta.montos}
          monedaDe={propuesta.monedaDe}
          tipoDeCambio={propuesta.tipoDeCambio}
          noConvertibles={propuesta.noConvertibles}
        />
      </div>
      <PlanDeRotacion />
      <ComparacionCarteras
        montosOriginales={montosOriginales}
        montos={propuesta.montos}
        monedaDe={propuesta.monedaDe}
        tipoDeCambio={propuesta.tipoDeCambio}
        perfil={perfil}
      />
    </>
  )
}

export function CarteraConfirmada({
  posiciones,
  onCargarOtra,
}: {
  posiciones: PosicionCruda[]
  onCargarOtra: () => void
}) {
  const invalidas = posiciones.filter((p) => !p.valida).length

  const { valuacion } = useCarteraCargadaValuada(posiciones)
  const posicionesConPeso: PosicionConPeso[] = (valuacion?.valuadas ?? []).map((v) => ({ ticker: v.ticker, peso: v.pesoReal }))
  const montosOriginales: PosicionConMonto[] = (valuacion?.valuadas ?? []).map((v) => ({ ticker: v.ticker, monto: v.invertido }))
  const [perfil, setPerfil] = useState<NombreDePerfil>('moderado')

  return (
    <div>
      <p style={{ margin: '0 0 10px', fontSize: 12.5, color: 'var(--dim)' }}>
        Cartera cargada: {posiciones.length} {posiciones.length === 1 ? 'posición' : 'posiciones'}
        {invalidas > 0 && (
          <span style={{ color: 'var(--neg)' }}> ({invalidas} con la fila mal leída)</span>
        )}
        {'.'}
      </p>

      {/* Se mandan también las inválidas: una fila que no se pudo leer sigue siendo plata del
          cliente, y sacarla del pedido la sacaría del diagnóstico de cobertura. */}
      <ResolucionCartera posiciones={posiciones} />

      <DiagnosticoCartera posiciones={posiciones} />

      {posicionesConPeso.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--dim)', marginBottom: 10 }}>
            Perfil para buscar rotaciones
            <select
              value={perfil}
              onChange={(evento) => setPerfil(evento.target.value as NombreDePerfil)}
              style={{ font: 'inherit', fontSize: 12, color: 'var(--tx)', background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 3, padding: '3px 6px' }}
            >
              {PERFILES.map((nombre) => (
                <option key={nombre} value={nombre}>
                  {nombre}
                </option>
              ))}
            </select>
          </label>
          {/* Los dos modos del optimizador, apilados: parten de las mismas candidatas de F-032 y
              las particionan sin solaparse —F-033 se queda con las que mantienen el rendimiento
              dentro de ±0,5pp, F-034 con las que lo suben más que eso—, así que mostrar uno no
              implica esconder el otro. El plan de rotaciones (F-036) vive en su propio provider,
              reiniciado por `key` cada vez que cambia la cartera confirmada. */}
          <PlanRotacionProvider posiciones={posicionesConPeso} key={firmaDePesos(posicionesConPeso)}>
            <BloqueOptimizador montosOriginales={montosOriginales} perfil={perfil} />
          </PlanRotacionProvider>
        </div>
      )}

      <div style={{ marginTop: 14 }}>
        <BotonAccion onClick={onCargarOtra}>Cargar otra cartera</BotonAccion>
      </div>
    </div>
  )
}
