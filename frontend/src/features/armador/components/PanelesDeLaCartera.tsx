/**
 * Los tres paneles que la Tanda 9 agrega debajo de la cartera — stubs de la base común.
 *
 * Existen ya montados en `ArmadorPage` para que las tres features de la tanda puedan correr en
 * paralelo sin que ninguna tenga que editar la página: cada una reemplaza el cuerpo de **su**
 * componente, y el orquestador no vuelve a tocar el layout. Es el mismo patrón con el que la
 * Tanda 1 dejó los routers montados vacíos antes de repartir trabajo.
 *
 * **Las tres ya están construidas** y este archivo quedó como lo que terminó siendo: el punto de
 * montaje que `ArmadorPage` importa, para que la página no tenga que cambiar cada vez que un panel
 * se conecta. Cada cuerpo vive en su propio archivo, y por eso: son paneles de varios cientos de
 * líneas y tenerlos acá adentro habría obligado a cada feature a abrir el archivo de las otras dos.
 *
 * - `PanelConcentracion` → **F-020** (`PanelConcentracion.tsx`): topes por soberano / emisor /
 *   sector y distribución por sector, ley y naturaleza de tasa.
 * - `PanelRenta` → **F-021** (`PanelRenta.tsx`): cordillera en dólares (A2), cordillera en pesos
 *   aparte (A3) y la tarjeta de renta anual sobre lo invertido con la cuenta a la vista (A9).
 * - `BloqueRentaVariable` → **F-026** (`BloqueRentaVariable.tsx`): acciones y CEDEARs con subtotal
 *   propio, fuera de todo cálculo de renta fija.
 *
 * El `Pendiente` que dibujaba los stubs se sacó cuando el último de los tres se conectó: dejarlo
 * habría sido código muerto en un archivo que las tres features leen.
 */

import { BloqueRentaVariable as BloqueRentaVariableF026 } from './BloqueRentaVariable'
import { PanelConcentracion as PanelConcentracionF020 } from './PanelConcentracion'
import { PanelRenta as PanelRentaF021 } from './PanelRenta'

export function PanelConcentracion() {
  return <PanelConcentracionF020 />
}

export function PanelRenta() {
  return <PanelRentaF021 />
}

export function BloqueRentaVariable() {
  return <BloqueRentaVariableF026 />
}
