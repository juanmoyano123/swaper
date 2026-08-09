import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

import { AlertasCalendario } from './components/AlertasCalendario'
import { CarteraEditable } from './components/CarteraEditable'
import { CoberturaSeleccion } from './components/CoberturaSeleccion'
import { GrillaFiltrada } from './components/GrillaFiltrada'
import { PanelArmadoAsistido } from './components/PanelArmadoAsistido'
import {
  BloqueRentaVariable,
  PanelConcentracion,
  PanelRenta,
} from './components/PanelesDeLaCartera'
import { PanelRendimientos } from './components/PanelRendimientos'
import { useCalendarioUniverso } from './hooks/useCalendarioUniverso'
import { ArmadorProvider } from './store/carteraStore'

/**
 * Armado de una cartera nueva a partir del mandato del cliente. Es el diseño Cordillera.
 *
 * F-016 invierte el orden habitual: el calendario es la entrada, no la salida. `ArmadorProvider`
 * envuelve sólo lo que depende de la selección en curso — F-018 agregó `CarteraEditable`, debajo
 * de la grilla; F-017 agregó la barra de filtros y el cruce grilla × universo (`GrillaFiltrada`),
 * adentro del mismo provider. La maqueta final de dos columnas (A7 izquierda / A8+A9 derecha) es
 * de una tanda de refinamiento visual posterior — acá lo que importa es que el dato y las
 * acciones existan y sean correctos.
 *
 * **Los tres paneles de la Tanda 9 ya están montados** (ver `PanelesDeLaCartera`): cada feature
 * reemplaza el cuerpo del suyo y nadie edita este archivo, que queda congelado durante la
 * ejecución en paralelo. El orden es deliberado: primero qué cobra la cartera (F-021), después
 * qué riesgo tiene (F-020), y al final el bloque que no participa de ninguno de los dos (F-026).
 *
 * **Tanda 10:** `PanelArmadoAsistido` (F-019) va arriba de `CarteraEditable` — precarga la
 * cartera que esa tabla después edita a mano. `PanelRendimientos` (F-022) va junto a `PanelRenta`
 * y `PanelConcentracion`: los tres leen `useCarteraResuelta` y responden "cuánto cobra", "qué
 * riesgo tiene" y "qué rinde", en ese orden. Mismo criterio de congelamiento: cada feature
 * reemplaza el cuerpo de su propio stub, nadie más edita este archivo.
 */
export function ArmadorPage() {
  const consulta = useCalendarioUniverso()

  return (
    <Pantalla
      titulo="Armador"
      bajada="Elegir bonos de forma que los cupones caigan repartidos a lo largo del año."
    >
      <Panel rotulo="Cordillera">
        {consulta.isPending && <EstadoCarga que="la grilla de doce meses" />}
        {consulta.isError && (
          <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />
        )}
        {consulta.data && (
          <ArmadorProvider>
            <CoberturaSeleccion meses={consulta.data.meses} />
            <GrillaFiltrada meses={consulta.data.meses} />
            <AlertasCalendario alertas={consulta.data.alertas} />
            <PanelArmadoAsistido />
            <CarteraEditable />
            <PanelRenta />
            <PanelRendimientos />
            <PanelConcentracion />
            <BloqueRentaVariable />
          </ArmadorProvider>
        )}
      </Panel>
    </Pantalla>
  )
}
