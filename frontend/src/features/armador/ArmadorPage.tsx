import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

import { AlertasCalendario } from './components/AlertasCalendario'
import { CarteraEditable } from './components/CarteraEditable'
import { CoberturaSeleccion } from './components/CoberturaSeleccion'
import { GrillaFiltrada } from './components/GrillaFiltrada'
import { PanelArmadoAsistido } from './components/PanelArmadoAsistido'
import { PanelComposicion } from './components/PanelComposicion'
import {
  BloqueRentaVariable,
  PanelConcentracion,
  PanelRenta,
} from './components/PanelesDeLaCartera'
import { PanelRendimientos } from './components/PanelRendimientos'
import { PanelRiesgo } from './components/PanelRiesgo'
import { SeccionDeArmador } from './components/SeccionDeArmador'
import { useCalendarioUniverso } from './hooks/useCalendarioUniverso'
import { ArmadorProvider } from './store/carteraStore'

/**
 * Armado de una cartera nueva a partir del mandato del cliente. Es el diseño Cordillera.
 *
 * F-016 invierte el orden habitual: el calendario es la entrada, no la salida. `ArmadorProvider`
 * envuelve todo lo que depende de la selección en curso.
 *
 * **Refinamiento visual posterior a la Tanda 12: sección / tarjeta / sub-tarjeta.** Hasta acá la
 * página apilaba once componentes como hermanos planos dentro de un único `<Panel>` — sin
 * separación entre bloques, y con `--pan` (la tarjeta) anidado sobre `--pan` (el panel envolvente),
 * que en los dos temas se lee sin contraste. La regla que reemplaza eso:
 *
 * - **Sección** (`SeccionDeArmador`): un rótulo sobre `--bg`, sin fondo propio. Agrupa un tramo de
 *   la página; no es una tarjeta y no debe anidarse dentro de una.
 * - **Tarjeta** (`Panel`, o un `<section>` que arma el mismo contenedor a mano): `--pan` + borde
 *   `--lin`, siempre montada directo sobre `--bg` — nunca dentro de otra tarjeta.
 * - **Sub-tarjeta**: `--pan2`, para lo que vive adentro de una tarjeta (inputs, tramos, celdas).
 *
 * El orden vertical de las once piezas no cambió — sólo se agruparon bajo seis secciones y cada una
 * dejó de autoimponerse su propio `marginTop`, porque ahora el espaciado entre bloques lo da el
 * `gap` del contenedor de la página y el de cada sección.
 */
export function ArmadorPage() {
  const consulta = useCalendarioUniverso()

  return (
    <Pantalla
      titulo="Armador"
      bajada="Elegir bonos de forma que los cupones caigan repartidos a lo largo del año."
    >
      {consulta.isPending && <EstadoCarga que="la grilla de doce meses" />}
      {consulta.isError && (
        <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />
      )}
      {consulta.data && (
        <ArmadorProvider>
          <div style={{ display: 'grid', gap: 28 }}>
            <SeccionDeArmador
              rotulo="Cordillera"
              bajada="Elegí papeles por mes de cobro, o filtrá la oferta antes de mirar la grilla."
            >
              <Panel>
                <CoberturaSeleccion meses={consulta.data.meses} />
                <GrillaFiltrada meses={consulta.data.meses} />
                <AlertasCalendario alertas={consulta.data.alertas} />
              </Panel>
            </SeccionDeArmador>

            <SeccionDeArmador
              rotulo="Armado asistido"
              bajada="Precarga una cartera de arranque a partir del mandato del cliente; después se edita a mano."
            >
              <Panel>
                <PanelArmadoAsistido />
              </Panel>
            </SeccionDeArmador>

            <SeccionDeArmador
              rotulo="Cartera"
              bajada="Ponderación pedida y ponderación real: si no coinciden, se muestra tal cual."
            >
              <Panel>
                <CarteraEditable />
              </Panel>
            </SeccionDeArmador>

            <SeccionDeArmador rotulo="Calendario de pagos">
              <PanelRenta />
            </SeccionDeArmador>

            <SeccionDeArmador rotulo="Análisis">
              <div style={{ display: 'grid', gap: 16 }}>
                <PanelRendimientos />
                <PanelComposicion />
                <PanelConcentracion />
                <PanelRiesgo />
              </div>
            </SeccionDeArmador>

            <SeccionDeArmador rotulo="Renta variable">
              <Panel>
                <BloqueRentaVariable />
              </Panel>
            </SeccionDeArmador>
          </div>
        </ArmadorProvider>
      )}
    </Pantalla>
  )
}
