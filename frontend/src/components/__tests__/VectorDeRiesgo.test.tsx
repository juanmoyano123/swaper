/**
 * `VectorDeRiesgo`, presentacional puro: seis filas fijas, nunca combinadas en un color o número
 * único (GWT-1). Se le pasan `EjeDeRiesgo[]` armados a mano, sin pasar por `vectorDeRiesgo()`.
 */

import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { EjeDeRiesgo } from '@/lib/cartera/riesgo'

import { VectorDeRiesgo } from '../VectorDeRiesgo'

function eje(extra: Partial<EjeDeRiesgo> & { id: EjeDeRiesgo['id'] }): EjeDeRiesgo {
  return {
    nombre: 'Eje de prueba',
    valor: null,
    unidad: null,
    grupos: [],
    cobertura: { conDato: 0, posiciones: 0, pesoConDato: 0, pesoTotal: 0, notas: [] },
    ...extra,
  }
}

describe('GWT-1: seis filas separadas, nunca un número único que las combine', () => {
  it('renderiza una fila por eje, ninguna fila ni texto de "riesgo total"', () => {
    const ejes: EjeDeRiesgo[] = [
      eje({ id: 'duracion', nombre: 'Duración', valor: 4.2, unidad: 'años', cobertura: { conDato: 1, posiciones: 1, pesoConDato: 100, pesoTotal: 100, notas: [] } }),
      eje({ id: 'credito', nombre: 'Crédito' }),
      eje({ id: 'legislacion', nombre: 'Legislación', valor: 30, unidad: 'pp' }),
      eje({ id: 'liquidez', nombre: 'Liquidez', valor: 60, unidad: 'percentil' }),
      eje({ id: 'concentracion', nombre: 'Concentración', valor: 45, unidad: 'pp' }),
      eje({ id: 'moneda', nombre: 'Moneda' }),
    ]

    render(<VectorDeRiesgo ejes={ejes} />)

    const filas = screen.getAllByRole('listitem')
    expect(filas).toHaveLength(6)
    expect(screen.queryByText(/riesgo total/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/score/i)).not.toBeInTheDocument()
  })

  it('un eje compositivo (valor: null, unidad: null) muestra "no aplica", no "s/d"', () => {
    render(<VectorDeRiesgo ejes={[eje({ id: 'credito', nombre: 'Crédito' })]} />)
    expect(screen.getByText('no aplica')).toBeInTheDocument()
  })

  it('un eje con unidad conocida que no se pudo medir muestra "s/d"', () => {
    render(<VectorDeRiesgo ejes={[eje({ id: 'duracion', nombre: 'Duración', unidad: 'años' })]} />)
    expect(screen.getByText('s/d')).toBeInTheDocument()
  })
})

describe('eje duración', () => {
  it('muestra el valor en años', () => {
    render(
      <VectorDeRiesgo
        ejes={[eje({ id: 'duracion', nombre: 'Duración', valor: 4.2, unidad: 'años' })]}
      />,
    )
    expect(screen.getByText('4,2 años')).toBeInTheDocument()
  })
})

describe('eje crédito', () => {
  it('GWT-2: muestra la cobertura de calificación al lado y declara lo sin calificación', () => {
    const credito = eje({
      id: 'credito',
      nombre: 'Crédito',
      grupos: [
        { titulo: 'Clase', tramos: [{ nombre: 'soberano', valor: 100, unidad: 'pp', sinDato: false, tope: null }] },
        {
          titulo: 'Calificación',
          tramos: [
            { nombre: 'AAA(arg)', valor: 40, unidad: 'pp', sinDato: false, tope: null },
            { nombre: 'sin calificación', valor: 60, unidad: 'pp', sinDato: true, tope: null },
          ],
        },
      ],
      cobertura: {
        conDato: 1,
        posiciones: 2,
        pesoConDato: 40,
        pesoTotal: 100,
        notas: ['sin calificación en 1 posiciones: la calificación nunca filtra'],
      },
    })

    render(<VectorDeRiesgo ejes={[credito]} />)

    expect(screen.getByText('1 de 2 con dato (50%)')).toBeInTheDocument()
    expect(screen.getByText('sin calificación')).toBeInTheDocument()
    expect(screen.getByText(/la calificación nunca filtra/)).toBeInTheDocument()
  })
})

describe('eje concentración', () => {
  it('marca el tope con línea vertical y color de exceso cuando está excedido', () => {
    const concentracion = eje({
      id: 'concentracion',
      nombre: 'Concentración',
      valor: 70,
      unidad: 'pp',
      grupos: [
        {
          titulo: 'Topes',
          tramos: [{ nombre: 'máximo por crédito', valor: 70, unidad: 'pp', sinDato: false, tope: 60 }],
        },
      ],
    })

    render(<VectorDeRiesgo ejes={[concentracion]} />)

    const fila = screen.getByLabelText('Concentración')
    expect(within(fila).getByText('máximo por crédito')).toBeInTheDocument()
    expect(
      within(fila).getByText((_, node) => node?.textContent === '70,0% / 60%'),
    ).toBeInTheDocument()
  })
})

describe('eje liquidez', () => {
  it('muestra el percentil por segmento como barras independientes, no apiladas', () => {
    const liquidez = eje({
      id: 'liquidez',
      nombre: 'Liquidez',
      valor: 55,
      unidad: 'percentil',
      grupos: [
        {
          titulo: 'Por segmento',
          tramos: [
            { nombre: 'bonos_soberanos', valor: 80, unidad: 'percentil', sinDato: false, tope: null },
            { nombre: 'letras', valor: 30, unidad: 'percentil', sinDato: false, tope: null },
          ],
        },
      ],
    })

    render(<VectorDeRiesgo ejes={[liquidez]} />)

    expect(screen.getByText('p80')).toBeInTheDocument()
    expect(screen.getByText('p30')).toBeInTheDocument()
  })
})

describe('notas de cobertura', () => {
  it('cada nota de la cobertura se muestra en pantalla', () => {
    const eje1 = eje({
      id: 'liquidez',
      nombre: 'Liquidez',
      cobertura: {
        conDato: 0,
        posiciones: 0,
        pesoConDato: 0,
        pesoTotal: 0,
        notas: ['spread bid/ask: no entra en este percentil — se mide por rotación, dentro del costo de rotar (F-035)'],
      },
    })

    render(<VectorDeRiesgo ejes={[eje1]} />)
    expect(screen.getByText(/spread bid\/ask/)).toBeInTheDocument()
  })
})
