/**
 * F-042 — convierte el `ModeloExport` a hojas de Excel, como estructura de datos pura (sin
 * depender de `write-excel-file`): cada celda declara su tipo y su formato de celda, nunca un
 * string es-AR — Excel aplica el formato y respeta el locale del usuario. Precedente de layout:
 * `tools/armar_cartera.py:470-556` (hojas Cartera/Resumen/Calendario/Alertas/Leyenda/Parametros).
 *
 * **Escala de los números**: `rendimiento` (de `/especies`) es una fracción (0,12 = 12%) — formato
 * `'0.00%'`, que Excel multiplica al mostrar. `pesoReal`/`pctCartera`/los ejes de unidad `'pp'` ya
 * vienen en puntos (60 = 60%) — formato `'0.00"%"'` (literal, sin multiplicar), para no tener que
 * dividir por 100 y arriesgar un error de escala en el medio.
 *
 * **`s/d` y `no aplica` son celdas de texto**, no números vacíos: una columna de rendimiento puede
 * mezclar celdas numéricas y celdas de texto fila por fila — `write-excel-file` tipa cada celda por
 * separado, no por columna.
 */

import { NO_APLICA, SIN_DATO } from '@/lib/fmt'

import type { FilaPosicionExport, ModeloExport } from './modelo'

export type TipoCeldaExcel = 'texto' | 'numero' | 'fecha'

export interface CeldaExcel {
  valor: string | number | Date
  tipo: TipoCeldaExcel
  formato?: string
}

export type FilaExcel = CeldaExcel[]

export interface HojaExcel {
  nombre: string
  anchoDeColumnas?: number[]
  /** Filas superiores que quedan fijas al scrollear — `freeze panes`. */
  filasFijas?: number
  filas: FilaExcel[]
}

const FORMATO_MONTO = '#,##0.00'
const FORMATO_ENTERO = '#,##0'
/** Porcentaje sobre una fracción (0–1): Excel multiplica por 100 al mostrar. */
const FORMATO_PCT_FRACCION = '0.00%'
/** Porcentaje sobre un valor ya en puntos (0–100): literal, sin multiplicar. */
const FORMATO_PCT_PUNTOS = '0.00"%"'
const FORMATO_FECHA = 'dd/mm/yyyy'
const FORMATO_FECHA_HORA = 'dd/mm/yyyy hh:mm'

function texto(valor: string | null | undefined, faltante: string = SIN_DATO): CeldaExcel {
  return { tipo: 'texto', valor: valor ?? faltante }
}

function noAplica(): CeldaExcel {
  return { tipo: 'texto', valor: NO_APLICA }
}

function numero(valor: number | null | undefined, formato: string = FORMATO_MONTO): CeldaExcel {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return { tipo: 'texto', valor: SIN_DATO }
  return { tipo: 'numero', valor, formato }
}

function pctFraccion(valor: number | null | undefined): CeldaExcel {
  return numero(valor, FORMATO_PCT_FRACCION)
}

function pctPuntos(valor: number | null | undefined): CeldaExcel {
  return numero(valor, FORMATO_PCT_PUNTOS)
}

function fecha(valor: string | null | undefined): CeldaExcel {
  if (!valor) return { tipo: 'texto', valor: SIN_DATO }
  const d = new Date(valor)
  if (Number.isNaN(d.getTime())) return { tipo: 'texto', valor: SIN_DATO }
  return { tipo: 'fecha', valor: d, formato: FORMATO_FECHA }
}

function fechaHora(valor: string | null | undefined): CeldaExcel {
  if (!valor) return { tipo: 'texto', valor: SIN_DATO }
  const d = new Date(valor)
  if (Number.isNaN(d.getTime())) return { tipo: 'texto', valor: SIN_DATO }
  return { tipo: 'fecha', valor: d, formato: FORMATO_FECHA_HORA }
}

// --- Hoja Cartera --------------------------------------------------------------------------------

const ENCABEZADO_CARTERA = [
  'Bloque',
  'Ticker',
  'Emisor / Denominación',
  'Ley',
  'Calificación',
  'Sector',
  'Naturaleza',
  'Rendimiento',
  'Duración (años)',
  'Vencimiento',
  'Lámina',
  'Moneda',
  'Precio',
  'VN / Cantidad',
  'Invertido',
  'Invertido USD',
  'Peso real',
]

function filaCartera(rotuloBloque: string, f: FilaPosicionExport): FilaExcel {
  // `rendimientoAplica` se reusa como señal de "aplica atributos de renta fija" (ley, calificación,
  // sector y naturaleza se congelan o se dejan de lado juntos — ver `modelo.ts`).
  const aplicaRf = f.rendimientoAplica
  return [
    texto(rotuloBloque),
    texto(f.ticker),
    texto(f.emisorODenominacion),
    aplicaRf ? texto(f.ley) : noAplica(),
    aplicaRf ? texto(f.calificacion) : noAplica(),
    aplicaRf ? texto(f.sector) : noAplica(),
    aplicaRf ? texto(f.naturalezaNombre) : noAplica(),
    f.rendimientoAplica ? pctFraccion(f.rendimiento) : noAplica(),
    f.duracionAplica ? numero(f.duracion, '0.00') : noAplica(),
    aplicaRf ? fecha(f.vencimiento) : noAplica(),
    f.laminaAplica ? numero(f.lamina, FORMATO_ENTERO) : noAplica(),
    texto(f.moneda?.toUpperCase() ?? null),
    numero(f.precio),
    numero(f.vnOCantidad),
    numero(f.invertido),
    numero(f.invertidoUsd),
    pctPuntos(f.pesoReal),
  ]
}

function hojaCartera(modelo: ModeloExport): HojaExcel {
  const filas: FilaExcel[] = [ENCABEZADO_CARTERA.map((titulo) => texto(titulo))]
  for (const bloque of modelo.bloques) {
    for (const fila of bloque.filas) filas.push(filaCartera(bloque.rotulo, fila))
  }
  return {
    nombre: 'Cartera',
    filasFijas: 1,
    anchoDeColumnas: [16, 12, 26, 12, 12, 16, 24, 12, 12, 12, 10, 8, 12, 14, 14, 14, 12],
    filas,
  }
}

// --- Hoja Rendimientos ---------------------------------------------------------------------------

function hojaRendimientos(modelo: ModeloExport): HojaExcel {
  const filas: FilaExcel[] = [
    ['Naturaleza', '% de la cartera', 'Rendimiento ponderado', 'Posiciones', 'Sin rendimiento informado'].map((t) =>
      texto(t),
    ),
  ]
  // GWT-1: cada naturaleza en su propia fila — nunca una fila que las combine.
  for (const r of modelo.rendimientos) {
    filas.push([
      texto(r.nombre),
      pctPuntos(r.pctCartera),
      pctFraccion(r.rendimientoPond),
      numero(r.posiciones, FORMATO_ENTERO),
      numero(r.posicionesExcluidas, FORMATO_ENTERO),
    ])
  }
  filas.push([texto(''), texto(''), texto(''), texto(''), texto('')])
  filas.push([
    texto('Plazo promedio (años)'),
    numero(modelo.plazoPromedio.anios, '0.00'),
    texto(''),
    texto(''),
    numero(modelo.plazoPromedio.posicionesExcluidas, FORMATO_ENTERO),
  ])
  return { nombre: 'Rendimientos', filasFijas: 1, anchoDeColumnas: [34, 16, 20, 12, 22], filas }
}

// --- Hoja Riesgo ----------------------------------------------------------------------------------

function celdaValorEje(valor: number | null, unidad: 'años' | 'percentil' | 'pp' | null): CeldaExcel {
  if (valor === null) return { tipo: 'texto', valor: SIN_DATO }
  if (unidad === 'pp') return pctPuntos(valor)
  if (unidad === 'años') return numero(valor, '0.00')
  return numero(valor, '0.00') // percentil: número plano, no es un porcentaje de cartera
}

function hojaRiesgo(modelo: ModeloExport): HojaExcel {
  const filas: FilaExcel[] = [
    ['Eje', 'Valor', 'Unidad', 'Con dato', 'Posiciones', 'Peso con dato', 'Peso total', 'Notas'].map((t) => texto(t)),
  ]
  if (modelo.vector === null) {
    filas.push([texto('Vector no disponible'), texto(SIN_DATO), texto(''), texto(''), texto(''), texto(''), texto(''), texto(modelo.declaraciones.mercadoDisponible ? 'Sin respuesta del servicio de concentración al momento de guardar.' : 'Cartera guardada antes de F-042.')])
  } else {
    for (const eje of modelo.vector) {
      filas.push([
        texto(eje.nombre),
        celdaValorEje(eje.valor, eje.unidad),
        texto(eje.unidad ?? ''),
        numero(eje.cobertura.conDato, FORMATO_ENTERO),
        numero(eje.cobertura.posiciones, FORMATO_ENTERO),
        pctPuntos(eje.cobertura.pesoConDato),
        pctPuntos(eje.cobertura.pesoTotal),
        texto(eje.cobertura.notas.join(' · ') || ''),
      ])
    }
  }
  return { nombre: 'Riesgo', filasFijas: 1, anchoDeColumnas: [16, 12, 12, 10, 12, 12, 12, 50], filas }
}

// --- Hoja Calendario ------------------------------------------------------------------------------

function hojaCalendario(modelo: ModeloExport): HojaExcel {
  const { calendario } = modelo
  if (!calendario.disponible) {
    return {
      nombre: 'Calendario',
      filas: [[texto('Calendario no disponible: cartera guardada antes de F-042.')]],
    }
  }

  const encabezado = ['Mes', ...calendario.monedas.map((m) => `Renta ${m.toUpperCase()}`)]
  const filas: FilaExcel[] = [encabezado.map((t) => texto(t))]
  for (const mes of calendario.meses) {
    filas.push([texto(mes.etiqueta), ...calendario.monedas.map((m) => numero(mes.porMoneda[m] ?? null))])
  }
  filas.push(encabezado.map(() => texto('')))
  filas.push([
    texto('Total anual'),
    ...calendario.monedas.map((m) => numero(calendario.totalPorMoneda[m] ?? null)),
  ])

  if (calendario.detalle.length > 0) {
    filas.push(encabezado.map(() => texto('')))
    filas.push(['Detalle por instrumento', 'Ticker', 'Moneda', 'Renta', 'Amortización'].map((t) => texto(t)))
    for (const d of calendario.detalle) {
      filas.push([texto(d.etiqueta), texto(d.ticker), texto(d.moneda.toUpperCase()), numero(d.renta), numero(d.amortizacion)])
    }
  }

  return { nombre: 'Calendario', filasFijas: 1, anchoDeColumnas: [14, ...calendario.monedas.map(() => 14)], filas }
}

// --- Hoja Declaraciones ---------------------------------------------------------------------------

function hojaDeclaraciones(modelo: ModeloExport): HojaExcel {
  const filas: FilaExcel[] = []

  filas.push([texto('Lámina'), texto('')])
  if (!modelo.declaraciones.lamina.aplica) {
    filas.push([texto('Sin dato de lámina: cartera guardada antes de F-042.'), texto('')])
  } else if (modelo.declaraciones.lamina.pctSinAjustar === null) {
    filas.push([texto('Sin posiciones de renta fija sobre las que medir la lámina.'), texto('')])
  } else {
    filas.push([
      texto(`${modelo.declaraciones.lamina.posicionesSinLamina} posición(es) sin lámina informada`),
      pctPuntos(modelo.declaraciones.lamina.pctSinAjustar),
    ])
  }

  filas.push([texto(''), texto('')])
  filas.push([texto('Perfil de concentración usado'), texto(modelo.declaraciones.perfilConcentracion)])

  if (modelo.excluidas.length > 0) {
    filas.push([texto(''), texto('')])
    filas.push([texto('Posiciones excluidas'), texto('')])
    for (const e of modelo.excluidas) {
      filas.push([texto(e.ticker), texto(e.motivo)])
    }
  }

  filas.push([texto(''), texto('')])
  filas.push([texto('Notas'), texto('')])
  for (const nota of modelo.declaraciones.notas) filas.push([texto(nota), texto('')])

  return { nombre: 'Declaraciones', anchoDeColumnas: [60, 16], filas }
}

// --- Hoja Parámetros -------------------------------------------------------------------------------

function hojaParametros(modelo: ModeloExport): HojaExcel {
  const { encabezado, pie } = modelo
  const filas: FilaExcel[] = [
    [texto('Cartera'), texto(encabezado.nombre)],
    [texto('Descripción'), texto(encabezado.descripcion, '')],
    [texto('Origen'), texto(encabezado.origen === 'cargada' ? 'Cartera cargada' : 'Armador')],
    [texto('Tipo de cambio implícito'), numero(encabezado.tipoDeCambio)],
    [texto('Monto (USD)'), numero(encabezado.montoUsd)],
    [texto(''), texto('')],
    // GWT-3: la hora del snapshot de precios y la demora de la fuente, separadas de cuándo se
    // generó este archivo.
    [texto('Precios capturados el'), fechaHora(pie.capturadoEn)],
    [texto('Demora declarada de la fuente'), pie.demoraMinutos !== null ? texto(`${pie.demoraMinutos} min (${pie.demoraFuente ?? SIN_DATO})`) : texto(SIN_DATO)],
    [texto('Cartera guardada el'), fechaHora(pie.snapshotEn)],
    [texto('Archivo generado el'), fechaHora(pie.generadoEn)],
    [texto(''), texto('')],
    [texto('Documento interno de trabajo: el asesor arma la presentación final al cliente por su cuenta.'), texto('')],
  ]
  return { nombre: 'Parámetros', anchoDeColumnas: [34, 34], filas }
}

export function hojasDesdeModelo(modelo: ModeloExport): HojaExcel[] {
  return [
    hojaCartera(modelo),
    hojaRendimientos(modelo),
    hojaRiesgo(modelo),
    hojaCalendario(modelo),
    hojaDeclaraciones(modelo),
    hojaParametros(modelo),
  ]
}
