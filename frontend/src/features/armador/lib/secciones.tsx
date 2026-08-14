/**
 * Las seis secciones del armador como **datos**, no como JSX literal.
 *
 * Estaban escritas una abajo de la otra en `ArmadorPage.tsx`, y ese orden era el orden de la
 * pantalla. Con el orden configurable (`lib/ordenSecciones.ts`) hace falta poder mapearlas, así
 * que cada una pasa a ser una entrada de este registro.
 *
 * **El acento viaja con la sección, no con la posición.** Antes los `--cat1`..`--cat6` se asignaban
 * por orden vertical; si siguieran haciéndolo, mover Renta variable arriba le cambiaría el color y
 * el asesor perdería la referencia visual que venía usando. El color es identidad de la sección.
 *
 * El contenido llega como función y no como elemento ya construido porque tres secciones necesitan
 * los meses del calendario, que sólo la página tiene.
 */

import type { ReactNode } from 'react'

import { Panel } from '@/components/Panel'

import { AlertasCalendario } from '../components/AlertasCalendario'
import { CarteraEditable } from '../components/CarteraEditable'
import { CoberturaSeleccion } from '../components/CoberturaSeleccion'
import { GrillaFiltrada } from '../components/GrillaFiltrada'
import { PanelArmadoAsistido } from '../components/PanelArmadoAsistido'
import { PanelComposicion } from '../components/PanelComposicion'
import {
  BloqueRentaVariable,
  PanelConcentracion,
  PanelRenta,
} from '../components/PanelesDeLaCartera'
import { PanelRendimientos } from '../components/PanelRendimientos'
import { PanelRiesgo } from '../components/PanelRiesgo'
import {
  ResumenCartera,
  ResumenCordillera,
  ResumenRentaVariable,
} from '../components/ResumenesDeSeccion'
import type { AlertaCalendario, MesDelCalendario } from './schema'
import type { SeccionId } from './plegado'

/** Lo que la página le pasa a las secciones que dependen del calendario del universo. */
export interface ContextoDeSeccion {
  meses: MesDelCalendario[]
  alertas: AlertaCalendario[]
}

export interface DefinicionDeSeccion {
  id: SeccionId
  rotulo: string
  bajada: string
  /** Color de identidad de la sección. Viaja con ella aunque se mueva de lugar. */
  acento: string
  /** Qué se muestra cuando está plegada. `undefined` = nada. */
  resumen?: (ctx: ContextoDeSeccion) => ReactNode
  contenido: (ctx: ContextoDeSeccion) => ReactNode
}

export const SECCIONES: readonly DefinicionDeSeccion[] = [
  {
    id: 'cordillera',
    rotulo: 'Cordillera',
    bajada:
      'Camino manual: elegí bonos por mes de cobro. Los atajos temáticos filtran de un clic los dos lados de la cartera —bonos acá y acciones en Renta variable— y después afinás con los filtros.',
    acento: 'var(--cat1)',
    resumen: ({ meses }) => <ResumenCordillera meses={meses} />,
    contenido: ({ meses, alertas }) => (
      <Panel>
        <CoberturaSeleccion meses={meses} />
        <GrillaFiltrada meses={meses} />
        <AlertasCalendario alertas={alertas} />
      </Panel>
    ),
  },
  {
    id: 'asistido',
    rotulo: 'Armador de cartera',
    bajada:
      'El mandato del cliente: cuánto invertir, cómo repartirlo entre renta fija y renta variable, y qué le exigís a los bonos —rendimiento mínimo, plazo, cada cuánto cobra y con qué calificación—. El botón arma una cartera entera de arranque y la carga en Cartera, donde se edita posición por posición.',
    acento: 'var(--cat2)',
    contenido: () => (
      <Panel>
        <PanelArmadoAsistido />
      </Panel>
    ),
  },
  {
    id: 'cartera',
    rotulo: 'Cartera',
    bajada:
      'La cartera entera, agrupada por clase de activo y con subtotal por bloque: soberanos, corporativos, fondos y acciones sobre el mismo 100%. El % pedido se edita acá; agregar o sacar una posición reparte el resto pro-rata.',
    acento: 'var(--cat3)',
    resumen: () => <ResumenCartera />,
    contenido: () => (
      <Panel>
        <CarteraEditable />
      </Panel>
    ),
  },
  {
    id: 'calendario',
    rotulo: 'Calendario de pagos',
    bajada:
      'Cómo cae la renta mes a mes, sólo de la parte de renta fija — una acción no tiene cupón que calendarizar.',
    acento: 'var(--cat4)',
    contenido: () => <PanelRenta />,
  },
  {
    id: 'analisis',
    rotulo: 'Análisis',
    bajada:
      'Rendimientos, composición, concentración y riesgo de la cartera armada hasta acá — incluye lo pedido en Cartera y en Renta variable.',
    acento: 'var(--cat5)',
    contenido: () => (
      <div style={{ display: 'grid', gap: 16 }}>
        <PanelRendimientos />
        <PanelComposicion />
        <PanelConcentracion />
        <PanelRiesgo />
      </div>
    ),
  },
  {
    id: 'rv',
    rotulo: 'Renta variable',
    bajada:
      'El buscador para sumar CEDEARs a la cartera (14/08/2026: las acciones argentinas se sacaron de acá). Una acción de una cartera anterior sigue viéndose y se edita desde Cartera. No suman a la renta ni a los rendimientos: ni una acción ni un CEDEAR tienen cupón ni TIR (regla 2).',
    acento: 'var(--cat6)',
    resumen: () => <ResumenRentaVariable />,
    contenido: () => (
      <Panel>
        <BloqueRentaVariable />
      </Panel>
    ),
  },
]

export const SECCION_POR_ID: ReadonlyMap<SeccionId, DefinicionDeSeccion> = new Map(
  SECCIONES.map((s) => [s.id, s]),
)
