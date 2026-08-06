/**
 * La máquina de estados del ingreso de cartera: qué vía se eligió, qué hay que mostrar en cada
 * paso, y las transiciones entre pasos.
 *
 * Las tres vías convergen siempre en el mismo paso de previsualización antes de confirmar — es la
 * exigencia central de F-028, y tenerla en un solo lugar evita que una de las tres rutas se
 * escape sin pasar por ahí.
 */

import { useState } from 'react'

import { construirPosiciones } from '../lib/construirPosiciones'
import { leerArchivo } from '../lib/parseArchivo'
import { intentarMapeoAutomatico, mapeoVacio } from '../lib/mapeoColumnas'
import { parsePegado } from '../lib/parseTabla'
import type { MapeoColumnas, PosicionCruda, ViaIngreso } from '../types'

type Paso =
  | { tipo: 'menu' }
  | { tipo: 'pegar'; textoPrevio: string }
  | { tipo: 'archivo' }
  | { tipo: 'manual'; posiciones: PosicionCruda[] }
  | { tipo: 'cargando'; que: string }
  | {
      tipo: 'mapeo'
      origen: 'portapapeles' | 'archivo'
      encabezados: string[] | null
      filas: string[][]
      mapeoPropuesto: MapeoColumnas
    }
  | { tipo: 'previsualizacion'; origen: ViaIngreso; posiciones: PosicionCruda[] }
  | { tipo: 'error'; mensaje: string; anterior: Paso }
  | { tipo: 'confirmada'; posiciones: PosicionCruda[] }

const PASO_INICIAL: Paso = { tipo: 'menu' }

export function useIngresoCartera() {
  const [paso, setPaso] = useState<Paso>(PASO_INICIAL)

  function elegirVia(via: ViaIngreso) {
    if (via === 'portapapeles') setPaso({ tipo: 'pegar', textoPrevio: '' })
    else if (via === 'archivo') setPaso({ tipo: 'archivo' })
    else setPaso({ tipo: 'manual', posiciones: [] })
  }

  function volverAlMenu() {
    setPaso({ tipo: 'menu' })
  }

  /** Cuando no hubo ni una fila de datos que interpretar, no hay nada que previsualizar. */
  function finalizarPosiciones(origen: ViaIngreso, posiciones: PosicionCruda[], anterior: Paso) {
    if (posiciones.length === 0) {
      setPaso({ tipo: 'error', mensaje: 'No se encontraron filas de datos para interpretar.', anterior })
      return
    }
    setPaso({ tipo: 'previsualizacion', origen, posiciones })
  }

  /**
   * El pegado y el archivo comparten esta ruta desde acá: una vez que hay filas crudas, da lo
   * mismo de dónde vinieron.
   *
   * Para el pegado, un encabezado reconocido alcanza para ir directo a la previsualización — es el
   * formato en que llega siempre el resumen de cuenta, y pedir una confirmación extra en cada
   * pegado sería fricción sin beneficio. Para un archivo se pide el mapeo aunque el encabezado se
   * haya reconocido: la Fase 2 lo exige explícitamente para no asumir nunca el orden de columnas
   * de un archivo ajeno.
   */
  function procesarTabla(filasCrudas: string[][], origen: 'portapapeles' | 'archivo', anterior: Paso) {
    const [primeraFila, ...resto] = filasCrudas
    const propuesto = intentarMapeoAutomatico(primeraFila)

    if (propuesto && origen === 'portapapeles') {
      const posiciones = construirPosiciones(resto, propuesto, 2)
      finalizarPosiciones(origen, posiciones, anterior)
      return
    }

    setPaso({
      tipo: 'mapeo',
      origen,
      encabezados: propuesto ? primeraFila : null,
      filas: propuesto ? resto : filasCrudas,
      mapeoPropuesto: propuesto ?? mapeoVacio(primeraFila.length),
    })
  }

  function interpretarPegado(texto: string) {
    const anterior: Paso = { tipo: 'pegar', textoPrevio: texto }
    const filasCrudas = parsePegado(texto)
    if (filasCrudas.length === 0) {
      setPaso({ tipo: 'error', mensaje: 'No se encontró texto para interpretar.', anterior })
      return
    }
    procesarTabla(filasCrudas, 'portapapeles', anterior)
  }

  async function subirArchivo(archivo: File) {
    const anterior: Paso = { tipo: 'archivo' }
    setPaso({ tipo: 'cargando', que: 'el archivo' })
    try {
      const filasCrudas = await leerArchivo(archivo)
      if (filasCrudas.length === 0) {
        setPaso({ tipo: 'error', mensaje: 'El archivo no tiene filas para leer.', anterior })
        return
      }
      procesarTabla(filasCrudas, 'archivo', anterior)
    } catch (causa) {
      setPaso({
        tipo: 'error',
        mensaje: causa instanceof Error ? causa.message : 'No se pudo leer el archivo.',
        anterior,
      })
    }
  }

  function confirmarMapeo(mapeo: MapeoColumnas) {
    if (paso.tipo !== 'mapeo') return
    const offsetFila = paso.encabezados ? 2 : 1
    const posiciones = construirPosiciones(paso.filas, mapeo, offsetFila)
    finalizarPosiciones(paso.origen, posiciones, paso)
  }

  /** Corregir el mapeo propuesto sin perder las filas ya leídas. */
  function corregirMapeo(mapeo: MapeoColumnas) {
    if (paso.tipo !== 'mapeo') return
    setPaso({ ...paso, mapeoPropuesto: mapeo })
  }

  function agregarPosicionManual(tickerDeclarado: string, nominalTexto: string, montoTexto: string) {
    if (paso.tipo !== 'manual') return
    const [nueva] = construirPosiciones(
      [[tickerDeclarado, nominalTexto, montoTexto]],
      ['ticker', 'nominal', 'monto'],
      paso.posiciones.length + 1,
    )
    setPaso({ tipo: 'manual', posiciones: [...paso.posiciones, nueva] })
  }

  function quitarPosicionManual(id: string) {
    if (paso.tipo !== 'manual') return
    setPaso({ tipo: 'manual', posiciones: paso.posiciones.filter((p) => p.id !== id) })
  }

  function confirmarCargaManual() {
    if (paso.tipo !== 'manual') return
    finalizarPosiciones('manual', paso.posiciones, paso)
  }

  function confirmar() {
    if (paso.tipo !== 'previsualizacion') return
    setPaso({ tipo: 'confirmada', posiciones: paso.posiciones })
  }

  function volver() {
    if (paso.tipo === 'error') {
      setPaso(paso.anterior)
      return
    }
    if (paso.tipo === 'previsualizacion' || paso.tipo === 'mapeo') {
      setPaso({ tipo: 'menu' })
      return
    }
    setPaso({ tipo: 'menu' })
  }

  function reiniciar() {
    setPaso({ tipo: 'menu' })
  }

  return {
    paso,
    elegirVia,
    volverAlMenu,
    interpretarPegado,
    subirArchivo,
    confirmarMapeo,
    corregirMapeo,
    agregarPosicionManual,
    quitarPosicionManual,
    confirmarCargaManual,
    confirmar,
    volver,
    reiniciar,
  }
}

export type { Paso as PasoIngresoCartera }
