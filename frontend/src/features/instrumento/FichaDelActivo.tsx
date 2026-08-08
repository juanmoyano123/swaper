/**
 * Qué ficha corresponde a este ticker — F-053.
 *
 * Son dos fichas distintas: la de renta fija gira alrededor de la TIR, el cronograma y la paridad;
 * la de renta variable, alrededor de quién es la empresa. La ruta es una sola (`/instrumento/:t`) y
 * el gesto de abrirla también, así que alguien tiene que decidir cuál de las dos se muestra.
 *
 * **La decisión la toma el backend, no el ticker.** Se pide la ficha de renta variable y se mira si
 * el ticker está: `GET /renta-variable/{ticker}/ficha` responde 404 cuando no es una acción ni un
 * CEDEAR del universo de hoy, y ese 404 es la respuesta, no un fallo. Deducirlo del ticker sería
 * inventar una regla que no existe —no hay forma de saber por el símbolo si `PAMP` es una acción o
 * una ON— y en este proyecto derivar cosas del string del ticker ya costó revertir 121 tickers
 * (regla 1). Mirar la clase en el listado del monitor tampoco sirve: al entrar por un link o al
 * recargar no hay ningún listado cargado.
 *
 * El costo es un request extra por cada ficha de renta fija, contra nuestra propia API. Se paga
 * mostrando el estado de carga mientras se resuelve, y no montando la ficha de renta fija de entrada
 * para reemplazarla después: eso haría parpadear "no está en el universo de hoy" en la cara del
 * asesor cada vez que abre una acción, que es peor que esperar un momento.
 */

import { EstadoCarga } from '@/components/EstadoCarga'
import { Panel } from '@/components/Panel'

import { FichaInstrumento } from './FichaInstrumento'
import { FichaRentaVariable } from './FichaRentaVariable'
import { useFichaRentaVariable } from './hooks/useFichaRentaVariable'

export function FichaDelActivo({ ticker }: { ticker: string | undefined }) {
  // La misma clave que usa `FichaRentaVariable`: cuando resuelve, aquella lee de la caché y no
  // vuelve a pedir nada.
  const query = useFichaRentaVariable(ticker)

  if (ticker === undefined) return <FichaInstrumento ticker={undefined} />

  if (query.isPending) {
    return (
      <Panel rotulo="Ficha">
        <EstadoCarga que={`la ficha de ${ticker}`} />
      </Panel>
    )
  }

  // Cualquier fallo —el 404 de "no es renta variable", pero también un 503— cae en la ficha de renta
  // fija, que muestra su propio estado. Un problema de la API no puede dejar la pantalla en blanco.
  if (query.isError) return <FichaInstrumento ticker={ticker} />

  return <FichaRentaVariable ticker={ticker} />
}
