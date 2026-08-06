/**
 * El contenido de la ficha, compartido por las dos formas en que se la puede ver: el drawer
 * superpuesto y la página completa. Lo que cambia entre una y otra es el contenedor, no el dato.
 *
 * F-039 llena esto con las condiciones de emisión, las tres especies y el cronograma de pagos.
 */

import { EstadoVacio } from '@/components/EstadoVacio'
import { Panel } from '@/components/Panel'

export function FichaInstrumento({ ticker }: { ticker: string | undefined }) {
  return (
    <Panel rotulo="Ficha">
      <EstadoVacio
        titulo={`No hay datos de ${ticker ?? 'este instrumento'} todavía.`}
        detalle="La ficha completa la construye F-039 y se alimenta del universo consolidado que puebla la ingesta."
      />
    </Panel>
  )
}
