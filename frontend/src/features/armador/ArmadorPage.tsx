import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

import { AlertasCalendario } from './components/AlertasCalendario'
import { CarteraEditable } from './components/CarteraEditable'
import { ColumnaKpis } from './components/ColumnaKpis'
import { CoberturaSeleccion } from './components/CoberturaSeleccion'
import { GrillaFiltrada } from './components/GrillaFiltrada'
import { GuardarCarteraArmador } from './components/GuardarCarteraArmador'
import { HidratarDesdeCarteraGuardada } from './components/HidratarDesdeCarteraGuardada'
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
 *
 * **Tanda 13**: las bajadas declaran los **dos caminos** que llegan a la misma cartera — el
 * asistido (un botón arma renta fija y renta variable juntas) y el manual (Cordillera + Renta
 * variable, con atajos temáticos que filtran los dos lados a la vez). La sección Cartera dejó de
 * ser "la tabla de bonos" para pasar a mostrar la cartera entera agrupada por clase de activo, así
 * que Renta variable quedó como el buscador para sumar papeles, no como el único lugar donde se
 * los pondera.
 *
 * **Etapa 6**: columna lateral fija (`ColumnaKpis`, A9) con los números que resumen la cartera —
 * renta anual, meses cubiertos, TIR ponderada, duración y mix RF/RV — para no tener que scrollear
 * hasta el final de la página a chequear cómo va. `.layout-armador` (`index.css`) hace la grilla de
 * dos columnas y la apila abajo en pantallas angostas (media query, no soportado por estilos
 * inline). Bajo 1280px la columna deja de ser sticky y pasa a un bloque más al final.
 */
export function ArmadorPage() {
  const consulta = useCalendarioUniverso()

  return (
    <Pantalla
      titulo="Armador"
      bajada="Dos caminos para llegar a la misma cartera: Armado asistido la arma entera de un botón y después la editás, o la armás vos papel por papel desde Cordillera y Renta variable. Los dos terminan en la sección Cartera, que muestra el 100% repartido entre bonos y acciones."
    >
      {consulta.isPending && <EstadoCarga que="la grilla de doce meses" />}
      {consulta.isError && (
        <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />
      )}
      {consulta.data && (
        <ArmadorProvider>
          <HidratarDesdeCarteraGuardada />
          <div className="layout-armador">
            <div style={{ display: 'grid', gap: 28, minWidth: 0 }}>
              <SeccionDeArmador
                id="cordillera"
                rotulo="Cordillera"
                bajada="Camino manual: elegí bonos por mes de cobro. Los atajos temáticos filtran de un clic los dos lados de la cartera —bonos acá y acciones en Renta variable— y después afinás con los filtros."
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
                bajada="Camino asistido: con el mandato del cliente arma una cartera entera de arranque y la carga en Cartera, donde se edita posición por posición. Reemplaza lo que hubiera cargado."
                acento="var(--cat2)"
              >
                <Panel>
                  <PanelArmadoAsistido />
                </Panel>
              </SeccionDeArmador>

              <SeccionDeArmador
                id="cartera"
                rotulo="Cartera"
                bajada="La cartera entera, agrupada por clase de activo y con subtotal por bloque: soberanos, corporativos, fondos y acciones sobre el mismo 100%. El % pedido se edita acá; agregar o sacar una posición reparte el resto pro-rata."
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
                bajada="El buscador para sumar acciones y CEDEARs a la cartera. Ya cargadas se editan también desde Cartera, arriba. No suman a la renta ni a los rendimientos: una acción no tiene cupón ni TIR (regla 2)."
                acento="var(--cat6)"
                resumen={<ResumenRentaVariable />}
              >
                <Panel>
                  <BloqueRentaVariable />
                </Panel>
              </SeccionDeArmador>

              {/* No es `SeccionDeArmador`: es una acción de cierre, no un tramo de armado, y la
                  paleta categórica (`--cat1`..`--cat6`) ya está agotada por las seis secciones de
                  arriba — agregar un séptimo color de identidad es una decisión de diseño que
                  excede esta feature (F-041). */}
              <Panel rotulo="Guardar cartera" ariaLabel="Guardar esta cartera">
                <GuardarCarteraArmador />
              </Panel>
            </div>

            <ColumnaKpis meses={consulta.data.meses} />
          </div>
        </ArmadorProvider>
      )}
    </Pantalla>
  )
}
