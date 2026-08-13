import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

import { ColumnaKpis } from './components/ColumnaKpis'
import { GuardarCarteraArmador } from './components/GuardarCarteraArmador'
import { HidratarDesdeCarteraGuardada } from './components/HidratarDesdeCarteraGuardada'
import { OrdenDeSecciones } from './components/OrdenDeSecciones'
import { SeccionDeArmador } from './components/SeccionDeArmador'
import { useCalendarioUniverso } from './hooks/useCalendarioUniverso'
import { useOrdenSecciones } from './hooks/useOrdenSecciones'
import { SECCION_POR_ID } from './lib/secciones'
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
 * daba el `gap`.
 *
 * **El orden lo decide quien arma, no este archivo.** Las seis secciones dejaron de ser JSX literal
 * y viven en `lib/secciones.tsx`; acá se mapean en el orden que devuelve `useOrdenSecciones`, que
 * lo persiste en `localStorage` con el mismo criterio que el plegado. El acento ya no se asigna por
 * posición sino que **viaja con la sección**: si el color dependiera del lugar, mover Renta
 * variable arriba se lo cambiaría y el asesor perdería la referencia visual que venía usando.
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
  const { orden } = useOrdenSecciones()

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
              <OrdenDeSecciones />

              {/* Las secciones salen del registro (`lib/secciones.tsx`) y se apilan en el orden
                  que el asesor eligió (`useOrdenSecciones`), no en el del JSX. Un id guardado que
                  ya no existe se ignora y una sección nueva entra al final: ver
                  `reconciliarOrden`. */}
              {orden.map((id) => {
                const seccion = SECCION_POR_ID.get(id)
                if (seccion === undefined) return null
                const ctx = { meses: consulta.data.meses, alertas: consulta.data.alertas }
                return (
                  <SeccionDeArmador
                    key={seccion.id}
                    id={seccion.id}
                    rotulo={seccion.rotulo}
                    bajada={seccion.bajada}
                    acento={seccion.acento}
                    resumen={seccion.resumen?.(ctx)}
                  >
                    {seccion.contenido(ctx)}
                  </SeccionDeArmador>
                )
              })}

              {/* No es `SeccionDeArmador` y no se reordena: es una acción de cierre, no un tramo de
                  armado, y la paleta categórica (`--cat1`..`--cat6`) ya está agotada por las seis
                  secciones — agregar un séptimo color de identidad excede esta feature (F-041). */}
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
