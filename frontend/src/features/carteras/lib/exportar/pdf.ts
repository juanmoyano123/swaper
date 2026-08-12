/**
 * F-042 — genera el `.pdf` a partir de las secciones puras de `seccionesPdf.ts`. `jspdf` y
 * `jspdf-autotable` se importan recién acá, con `import()` dinámico: el documento es casi todo
 * tablas, así que autoTable hace la maquetación en vez de reinventarla a mano con `doc.text`.
 *
 * A4 apaisado: la tabla de posiciones es la más ancha del documento (diez columnas) y define el
 * formato de toda la página. Sólo `helvetica` (WinAnsi) — `seccionesPdf.ts` ya garantiza que ningún
 * texto salga de esa página de códigos.
 *
 * El pie se dibuja **al final, recorriendo todas las páginas** (`getNumberOfPages`), y no con el
 * hook `didDrawPage` de autoTable: así queda en toda página del documento, no sólo en las que
 * tienen una tabla — GWT-3 no puede depender de qué sección cayó en qué hoja.
 */

import type { DocumentoPdf, SeccionPdf } from './seccionesPdf'
import { seccionesDesdeModelo } from './seccionesPdf'
import type { ModeloExport } from './modelo'

const MARGEN = 40

function dibujarParrafo(doc: import('jspdf').jsPDF, seccion: Extract<SeccionPdf, { tipo: 'parrafo' }>, y: number, anchoUtil: number): number {
  let cursor = y
  if (seccion.titulo) {
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(12)
    doc.text(seccion.titulo, MARGEN, cursor)
    cursor += 16
  }
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9.5)
  const lineas = doc.splitTextToSize(seccion.texto, anchoUtil)
  doc.text(lineas, MARGEN, cursor)
  return cursor + lineas.length * 12 + 14
}

export async function generarPdf(modelo: ModeloExport): Promise<Blob> {
  const { jsPDF } = await import('jspdf')
  const { default: autoTable } = await import('jspdf-autotable')

  const documento: DocumentoPdf = seccionesDesdeModelo(modelo)
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' })
  const anchoPagina = doc.internal.pageSize.getWidth()
  const anchoUtil = anchoPagina - MARGEN * 2

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(16)
  doc.text(documento.titulo, MARGEN, MARGEN)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.text(documento.bajada, MARGEN, MARGEN + 16)

  let y = MARGEN + 40
  for (const seccion of documento.secciones) {
    if (seccion.tipo === 'parrafo') {
      if (y > doc.internal.pageSize.getHeight() - 80) {
        doc.addPage()
        y = MARGEN
      }
      y = dibujarParrafo(doc, seccion, y, anchoUtil)
      continue
    }

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(11)
    if (y > doc.internal.pageSize.getHeight() - 100) {
      doc.addPage()
      y = MARGEN
    }
    doc.text(seccion.titulo, MARGEN, y)
    y += 14

    autoTable(doc, {
      startY: y,
      margin: { left: MARGEN, right: MARGEN },
      head: [seccion.columnas],
      body: seccion.filas.length > 0 ? seccion.filas : [seccion.columnas.map(() => '-')],
      styles: { font: 'helvetica', fontSize: 8, cellPadding: 4 },
      headStyles: { fillColor: [40, 40, 40] },
    })
    // `lastAutoTable` lo agrega el plugin al documento en runtime — no está en los tipos públicos.
    y = (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 20
  }

  // GWT-3: el pie en cada página del documento, no sólo en las que tienen una tabla.
  const totalPaginas = doc.getNumberOfPages()
  for (let pagina = 1; pagina <= totalPaginas; pagina++) {
    doc.setPage(pagina)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7.5)
    doc.text(documento.pie, MARGEN, doc.internal.pageSize.getHeight() - 16)
    doc.text(`${pagina} / ${totalPaginas}`, anchoPagina - MARGEN - 30, doc.internal.pageSize.getHeight() - 16)
  }

  return doc.output('blob')
}
