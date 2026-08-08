/**
 * Los tres paneles que la Tanda 9 agrega debajo de la cartera — stubs de la base común.
 *
 * Existen ya montados en `ArmadorPage` para que las tres features de la tanda puedan correr en
 * paralelo sin que ninguna tenga que editar la página: cada una reemplaza el cuerpo de **su**
 * componente, y el orquestador no vuelve a tocar el layout. Es el mismo patrón con el que la
 * Tanda 1 dejó los routers montados vacíos antes de repartir trabajo.
 *
 * Cada stub se ve en pantalla y dice qué falta. Un `return null` habría sido más limpio de leer
 * pero deja la página igual a como estaba, y entonces nadie nota si una feature no llegó a
 * conectarse.
 *
 * - `PanelConcentracion` → **F-020**: topes por emisor / soberano / sector y distribución por
 *   sector, ley y naturaleza de tasa. Usa `DistribucionBarras` de `components/`.
 * - `PanelRenta` → **F-021**: cordillera en dólares (A2), cordillera en pesos aparte (A3) y la
 *   tarjeta de renta anual sobre lo invertido con la cuenta a la vista (A9).
 * - `BloqueRentaVariable` → **F-026**, ya construido: acciones y CEDEARs con subtotal propio,
 *   fuera de todo cálculo de renta fija. Vive en su propio archivo (`BloqueRentaVariable.tsx`).
 */

import type { ReactNode } from 'react'

import { BloqueRentaVariable as BloqueRentaVariableF026 } from './BloqueRentaVariable'
import { PanelRenta as PanelRentaF021 } from './PanelRenta'

function Pendiente({ feature, que }: { feature: string; que: string }) {
  return (
    <section
      style={{
        marginTop: 16,
        padding: '10px 12px',
        border: '1px dashed var(--lin)',
        borderRadius: 4,
        fontSize: 11.5,
        color: 'var(--sd)',
      }}
    >
      <strong style={{ color: 'var(--dim)' }}>{feature}</strong> — {que}
    </section>
  ) as ReactNode
}

export function PanelConcentracion() {
  return <Pendiente feature="F-020" que="límites de concentración y distribución de la cartera" />
}

export function PanelRenta() {
  return <PanelRentaF021 />
}

export function BloqueRentaVariable() {
  return <BloqueRentaVariableF026 />
}
