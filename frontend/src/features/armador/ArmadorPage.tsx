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
import {
  ResumenCartera,
  ResumenCordillera,
  ResumenRentaVariable,
} from './components/ResumenesDeSeccion'
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
 *
 * **Etapa 2 del rediseño**: cada sección es plegable (`SeccionDeArmador` guarda el estado en
 * `localStorage`, ver `lib/plegado.ts`) y tiene su propio color de identidad (borde izquierdo de
 * 3px, un `--catN` de la paleta categórica) — es la separación visual entre bloques que antes sólo
 * daba el `gap`. El orden de acentos sigue el orden vertical: cat1 a cat6, sin repetir.
 *
 * **Etapa 3**: las `bajada` de cada sección se reescribieron para declarar el flujo RF/RV en vez
 * de sólo describir el contenido — en particular, que Cordillera/Armado asistido/Cartera arman la
 * parte de renta fija y Renta variable arma su propia parte con su propio % pedido, las dos sobre
 * el mismo 100% (ver `mixPedido` en `lib/mix.ts` y el % pedido editable de `BloqueRentaVariable`).
 * No se numeraron como pasos 1-2-3 porque Cartera y Renta variable no son secciones consecutivas
 * en la página — una numeración que salta habría sido más confusa que las referencias cruzadas.
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
              id="cordillera"
              rotulo="Cordillera"
              bajada="Elegí bonos por mes de cobro, o filtrá la oferta antes de mirar la grilla. Punto de partida si la cartera lleva renta fija — si es sólo acciones y CEDEARs, se puede saltar directo a la sección Renta variable, al final."
              acento="var(--cat1)"
              resumen={<ResumenCordillera meses={consulta.data.meses} />}
            >
              <Panel>
                <CoberturaSeleccion meses={consulta.data.meses} />
                <GrillaFiltrada meses={consulta.data.meses} />
                <AlertasCalendario alertas={consulta.data.alertas} />
              </Panel>
            </SeccionDeArmador>

            <SeccionDeArmador
              id="asistido"
              rotulo="Armado asistido"
              bajada="Opcional: precarga una cartera de arranque a partir del mandato del cliente; después se edita a mano, papel por papel, en la sección Cartera."
              acento="var(--cat2)"
            >
              <Panel>
                <PanelArmadoAsistido />
              </Panel>
            </SeccionDeArmador>

            <SeccionDeArmador
              id="cartera"
              rotulo="Cartera"
              bajada="Ponderación pedida y ponderación real de los bonos elegidos arriba: si no coinciden, se muestra tal cual. Las acciones y CEDEARs comparten el mismo 100% pero se ponderan aparte, en Renta variable — no aparecen en esta tabla."
              acento="var(--cat3)"
              resumen={<ResumenCartera />}
            >
              <Panel>
                <CarteraEditable />
              </Panel>
            </SeccionDeArmador>

            <SeccionDeArmador
              id="calendario"
              rotulo="Calendario de pagos"
              bajada="Cómo cae la renta mes a mes, sólo de la parte de renta fija — una acción no tiene cupón que calendarizar."
              acento="var(--cat4)"
            >
              <PanelRenta />
            </SeccionDeArmador>

            <SeccionDeArmador
              id="analisis"
              rotulo="Análisis"
              bajada="Rendimientos, composición, concentración y riesgo de la cartera armada hasta acá — incluye lo pedido en Cartera y en Renta variable."
              acento="var(--cat5)"
            >
              <div style={{ display: 'grid', gap: 16 }}>
                <PanelRendimientos />
                <PanelComposicion />
                <PanelConcentracion />
                <PanelRiesgo />
              </div>
            </SeccionDeArmador>

            <SeccionDeArmador
              id="rv"
              rotulo="Renta variable"
              bajada="Acciones y CEDEARs, con su propio % pedido sobre el mismo 100% de la cartera. Se suman al monto total pero no a la renta ni a los rendimientos de arriba — son otra clase de instrumento (regla 2)."
              acento="var(--cat6)"
              resumen={<ResumenRentaVariable />}
            >
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
