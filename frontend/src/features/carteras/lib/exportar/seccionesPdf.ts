/**
 * F-042 — convierte el `ModeloExport` a las secciones que arma el PDF: tablas y párrafos, como
 * estructura de datos pura (sin depender de jsPDF). Acá los números sí se formatean con `fmt.ts`
 * (es-AR): a diferencia de Excel, el PDF es de lectura directa, no una planilla donde el formato de
 * celda hace el trabajo.
 *
 * **Sólo caracteres de Windows-1252 (WinAnsi)**: jsPDF con la fuente estándar `helvetica` no sabe
 * dibujar fuera de esa página de códigos — nada de `→`/`✓`/`✗`. `·` y `—` sí están (0xB7 y 0x97) y
 * se usan en el resto del proyecto, así que se mantienen acá.
 */

import { fmtFechaHora, fmtMonto, fmtNumero, fmtPct, NO_APLICA, SIN_DATO } from '@/lib/fmt'

import type { FilaPosicionExport, ModeloExport } from './modelo'

export interface TablaPdf {
  tipo: 'tabla'
  titulo: string
  columnas: string[]
  filas: string[][]
}

export interface ParrafoPdf {
  tipo: 'parrafo'
  titulo?: string
  texto: string
}

export type SeccionPdf = TablaPdf | ParrafoPdf

export interface DocumentoPdf {
  titulo: string
  bajada: string
  secciones: SeccionPdf[]
  /** Una sola línea, repetida en el pie de cada página (GWT-3). */
  pie: string
}

function origenLegible(origen: 'cargada' | 'armador'): string {
  return origen === 'cargada' ? 'Cartera cargada' : 'Armador'
}

function seccionEncabezado(modelo: ModeloExport): ParrafoPdf {
  const { encabezado } = modelo
  const partes = [
    `Origen: ${origenLegible(encabezado.origen)}`,
    `Guardada el: ${fmtFechaHora(encabezado.snapshotEn)}`,
    `Tipo de cambio implícito: ${encabezado.tipoDeCambio !== null ? fmtNumero(encabezado.tipoDeCambio, 2) : SIN_DATO}`,
    `Monto: ${fmtMonto(encabezado.montoUsd, 'usd')}`,
  ]
  if (encabezado.descripcion) partes.push(encabezado.descripcion)
  return { tipo: 'parrafo', titulo: encabezado.nombre, texto: partes.join(' · ') }
}

function filaTablaCartera(rotuloBloque: string, f: FilaPosicionExport): string[] {
  const aplicaRf = f.rendimientoAplica
  return [
    rotuloBloque,
    f.ticker,
    f.emisorODenominacion ?? SIN_DATO,
    aplicaRf ? (f.naturalezaNombre ?? SIN_DATO) : NO_APLICA,
    f.rendimientoAplica ? fmtPct(f.rendimiento !== null ? f.rendimiento * 100 : null) : NO_APLICA,
    f.duracionAplica ? fmtNumero(f.duracion, 2) : NO_APLICA,
    f.laminaAplica ? fmtNumero(f.lamina, 0) : NO_APLICA,
    f.moneda ? f.moneda.toUpperCase() : SIN_DATO,
    fmtMonto(f.invertidoUsd, 'usd'),
    fmtPct(f.pesoReal),
  ]
}

function seccionCartera(modelo: ModeloExport): TablaPdf {
  const filas = modelo.bloques.flatMap((bloque) => bloque.filas.map((f) => filaTablaCartera(bloque.rotulo, f)))
  return {
    tipo: 'tabla',
    titulo: 'Cartera',
    columnas: ['Bloque', 'Ticker', 'Emisor / Denominación', 'Naturaleza', 'Rendimiento', 'Duración', 'Lámina', 'Moneda', 'Invertido USD', 'Peso real'],
    filas,
  }
}

function seccionRendimientos(modelo: ModeloExport): SeccionPdf[] {
  // GWT-1: una fila por naturaleza, siempre las cuatro, nunca combinadas.
  const filas = modelo.rendimientos.map((r) => [
    r.nombre,
    fmtPct(r.pctCartera),
    fmtPct(r.rendimientoPond !== null ? r.rendimientoPond * 100 : null),
    fmtNumero(r.posiciones, 0),
    fmtNumero(r.posicionesExcluidas, 0),
  ])
  const tabla: TablaPdf = {
    tipo: 'tabla',
    titulo: 'Rendimientos por naturaleza de tasa',
    columnas: ['Naturaleza', '% de la cartera', 'Rendimiento ponderado', 'Posiciones', 'Sin rendimiento'],
    filas,
  }
  const plazo: ParrafoPdf = {
    tipo: 'parrafo',
    texto: `Plazo promedio: ${modelo.plazoPromedio.anios !== null ? `${fmtNumero(modelo.plazoPromedio.anios, 2)} años` : SIN_DATO}.`,
  }
  return [tabla, plazo]
}

function seccionRiesgo(modelo: ModeloExport): SeccionPdf {
  if (modelo.vector === null) {
    return {
      tipo: 'parrafo',
      titulo: 'Riesgo (vector de seis ejes)',
      texto: modelo.declaraciones.mercadoDisponible
        ? 'Vector no disponible: sin respuesta del servicio de concentración al momento de guardar.'
        : 'Vector no disponible: cartera guardada antes de F-042.',
    }
  }
  return {
    tipo: 'tabla',
    titulo: 'Riesgo (vector de seis ejes)',
    columnas: ['Eje', 'Valor', 'Con dato', 'Peso con dato', 'Notas'],
    filas: modelo.vector.map((eje) => [
      eje.nombre,
      eje.valor === null
        ? SIN_DATO
        : eje.unidad === 'pp'
          ? fmtPct(eje.valor)
          : eje.unidad === 'años'
            ? `${fmtNumero(eje.valor, 2)} años`
            : fmtNumero(eje.valor, 2),
      `${eje.cobertura.conDato}/${eje.cobertura.posiciones}`,
      fmtPct(eje.cobertura.pesoConDato),
      eje.cobertura.notas.join(' · ') || '-',
    ]),
  }
}

function seccionCalendario(modelo: ModeloExport): SeccionPdf {
  const { calendario } = modelo
  if (!calendario.disponible) {
    return { tipo: 'parrafo', titulo: 'Calendario de cupones', texto: 'No disponible: cartera guardada antes de F-042.' }
  }
  const columnas = ['Mes', ...calendario.monedas.map((m) => `Renta ${m.toUpperCase()}`)]
  const filas = calendario.meses.map((mes) => [
    mes.etiqueta,
    ...calendario.monedas.map((m) => fmtMonto(mes.porMoneda[m] ?? null, m === 'ars' ? 'ars' : 'usd', 0)),
  ])
  filas.push([
    'Total anual',
    ...calendario.monedas.map((m) => fmtMonto(calendario.totalPorMoneda[m] ?? null, m === 'ars' ? 'ars' : 'usd', 0)),
  ])
  return { tipo: 'tabla', titulo: 'Calendario de cupones', columnas, filas }
}

function seccionDeclaraciones(modelo: ModeloExport): ParrafoPdf {
  const partes: string[] = []

  const lamina = modelo.declaraciones.lamina
  if (!lamina.aplica) {
    partes.push('Lámina: sin dato — cartera guardada antes de F-042.')
  } else if (lamina.pctSinAjustar === null) {
    partes.push('Lámina: sin posiciones de renta fija sobre las que medirla.')
  } else {
    // GWT-2: el conteo y el porcentaje sin ajustar, declarados por nombre.
    partes.push(`Lámina: ${lamina.posicionesSinLamina} posición(es) sin lámina informada (${fmtPct(lamina.pctSinAjustar)} de la cartera sin ajustar).`)
  }

  partes.push(`Perfil de concentración usado: ${modelo.declaraciones.perfilConcentracion ?? SIN_DATO}.`)

  if (modelo.excluidas.length > 0) {
    partes.push(`Posiciones excluidas: ${modelo.excluidas.map((e) => `${e.ticker} (${e.motivo})`).join('; ')}.`)
  }

  for (const nota of modelo.declaraciones.notas) partes.push(nota)

  return { tipo: 'parrafo', titulo: 'Declaraciones', texto: partes.join(' ') }
}

/** GWT-3: la hora de captura de precios y la demora de la fuente, en una sola línea repetible al
 *  pie de cada página — separada de cuándo se generó este archivo. */
function piePdf(modelo: ModeloExport): string {
  const { pie } = modelo
  const capturado = pie.capturadoEn ? fmtFechaHora(pie.capturadoEn) : SIN_DATO
  const demora = pie.demoraMinutos !== null ? `${pie.demoraMinutos} min (${pie.demoraFuente ?? SIN_DATO})` : SIN_DATO
  return `Precios capturados: ${capturado} · Demora de la fuente: ${demora} · Generado: ${fmtFechaHora(pie.generadoEn)}`
}

export function seccionesDesdeModelo(modelo: ModeloExport): DocumentoPdf {
  return {
    titulo: modelo.encabezado.nombre,
    bajada: 'Documento interno de trabajo: el asesor arma la presentación final al cliente por su cuenta.',
    secciones: [
      seccionEncabezado(modelo),
      seccionCartera(modelo),
      ...seccionRendimientos(modelo),
      seccionRiesgo(modelo),
      seccionCalendario(modelo),
      seccionDeclaraciones(modelo),
    ],
    pie: piePdf(modelo),
  }
}
