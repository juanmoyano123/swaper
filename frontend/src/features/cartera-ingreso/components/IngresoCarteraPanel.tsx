/**
 * El punto de entrada de F-028: reemplaza el `EstadoVacio` del panel "Cartera del cliente" del
 * Optimizador por la máquina de estados completa de las tres vías.
 *
 * Todo el parseo es local al navegador — no hay backend involucrado en esta feature, la validación
 * de esquema la hace Zod en el borde de `construirPosiciones` y no una respuesta de API. Por eso
 * acá no hay `EstadoCarga` de consulta ni `EstadoError` de contrato: los errores que puede haber
 * son de formato de archivo, y se muestran con su propio mensaje en vez del genérico que usa
 * `EstadoError` para no tapar el motivo real con un texto pensado para fallas de red.
 */

import { EstadoCarga } from '@/components/EstadoCarga'

import { useIngresoCartera } from '../hooks/useIngresoCartera'

import { BotonAccion } from './BotonAccion'
import { CargaManual } from './CargaManual'
import { CarteraConfirmada } from './CarteraConfirmada'
import { MapeoColumnas } from './MapeoColumnas'
import { PegarPortapapeles } from './PegarPortapapeles'
import { PrevisualizacionPosiciones } from './PrevisualizacionPosiciones'
import { SelectorVia } from './SelectorVia'
import { SubirArchivo } from './SubirArchivo'

export function IngresoCarteraPanel() {
  const {
    paso,
    elegirVia,
    volverAlMenu,
    interpretarPegado,
    subirArchivo,
    confirmarMapeo,
    agregarPosicionManual,
    quitarPosicionManual,
    confirmarCargaManual,
    confirmar,
    volver,
    reiniciar,
    identificarComoFci,
  } = useIngresoCartera()

  switch (paso.tipo) {
    case 'menu':
      return <SelectorVia onElegir={elegirVia} />

    case 'pegar':
      return (
        <PegarPortapapeles textoInicial={paso.textoPrevio} onInterpretar={interpretarPegado} onVolver={volverAlMenu} />
      )

    case 'archivo':
      return <SubirArchivo onArchivo={subirArchivo} onVolver={volverAlMenu} />

    case 'manual':
      return (
        <CargaManual
          posiciones={paso.posiciones}
          onAgregar={agregarPosicionManual}
          onQuitar={quitarPosicionManual}
          onConfirmar={confirmarCargaManual}
          onVolver={volverAlMenu}
        />
      )

    case 'cargando':
      return <EstadoCarga que={paso.que} />

    case 'mapeo':
      return (
        <MapeoColumnas
          encabezados={paso.encabezados}
          filas={paso.filas}
          mapeoInicial={paso.mapeoPropuesto}
          onConfirmar={confirmarMapeo}
          onVolver={volver}
        />
      )

    case 'previsualizacion':
      return (
        <PrevisualizacionPosiciones
          origen={paso.origen}
          posiciones={paso.posiciones}
          onConfirmar={confirmar}
          onVolver={volver}
        />
      )

    case 'error':
      return (
        <div
          role="alert"
          style={{
            border: '1px solid var(--neg)',
            borderLeftWidth: 3,
            borderRadius: 4,
            background: 'var(--pan)',
            padding: '12px 14px',
            maxWidth: '62ch',
          }}
        >
          <p style={{ margin: 0, fontSize: 13.5, color: 'var(--tx)' }}>{paso.mensaje}</p>
          <div style={{ marginTop: 10 }}>
            <BotonAccion onClick={volver}>Volver</BotonAccion>
          </div>
        </div>
      )

    case 'confirmada':
      return (
        <CarteraConfirmada
          posiciones={paso.posiciones}
          onCargarOtra={reiniciar}
          onIdentificarComoFci={identificarComoFci}
        />
      )
  }
}
