/**
 * Tests del reparto pro-rata — Tanda 13.
 *
 * El invariante que se prueba una y otra vez es el mismo: después de agregar, quitar, equiponderar
 * o normalizar, los pesos suman 100,0 exacto. Se prueba con cantidades primas (3, 7, 13) porque son
 * las que no dividen 1000 y obligan a repartir residuo; con potencias de 10 el bug de redondeo no
 * aparece nunca.
 */

import { describe, expect, it } from 'vitest'

import {
  agregarConProRata,
  equiponderarPesos,
  normalizarA100,
  quitarConProRata,
  TOLERANCIA_SUMA,
} from '../lib/rebalanceo'

function suma(pesos: readonly { peso: number }[] | readonly number[]): number {
  const numeros = pesos.map((p) => (typeof p === 'number' ? p : p.peso))
  return numeros.reduce((acumulado, peso) => acumulado + peso, 0)
}

function papel(ticker: string, peso: number) {
  return { ticker, peso, clase: 'renta_fija' as const }
}

describe('normalizarA100', () => {
  it.each([3, 7, 13])('reparte 100 entre %i pesos iguales sin perder décimas', (cantidad) => {
    const repartidos = normalizarA100(Array.from({ length: cantidad }, () => 1))

    expect(repartidos).toHaveLength(cantidad)
    expect(suma(repartidos)).toBeCloseTo(100, 10)
  })

  it('da 33,4 / 33,3 / 33,3 y no tres veces 33,3', () => {
    expect(normalizarA100([1, 1, 1])).toEqual([33.4, 33.3, 33.3])
  })

  it('respeta las proporciones de entrada', () => {
    // 60/30/10 sobre un total de 200 → mismas proporciones llevadas a 100.
    expect(normalizarA100([120, 60, 20])).toEqual([60, 30, 10])
  })

  it('escala a 100 una cartera que venía desviada', () => {
    const repartidos = normalizarA100([20, 20, 20])

    expect(suma(repartidos)).toBeCloseTo(100, 10)
    expect(repartidos).toEqual([33.4, 33.3, 33.3])
  })

  it('normaliza los decimales largos que manda el backend', () => {
    // Siete posiciones equiponderadas por el motor: 100/7 = 14.285714285714286.
    const delBackend = Array.from({ length: 7 }, () => 100 / 7)
    const repartidos = normalizarA100(delBackend)

    expect(suma(repartidos)).toBeCloseTo(100, 10)
    for (const peso of repartidos) {
      // Un decimal exacto: nada de 14.285714285714286 llegando a la pantalla.
      expect(Math.round(peso * 10)).toBeCloseTo(peso * 10, 10)
    }
  })

  it('reparte en partes iguales si todos los pesos son cero — no hay proporción de la que agarrarse', () => {
    expect(suma(normalizarA100([0, 0, 0]))).toBeCloseTo(100, 10)
  })

  it('un array vacío queda vacío, no una cartera de la nada', () => {
    expect(normalizarA100([])).toEqual([])
  })

  it('una sola posición se queda con el 100', () => {
    expect(normalizarA100([42])).toEqual([100])
  })

  it('es reproducible: el mismo input da siempre el mismo output', () => {
    const entrada = [17.3, 17.3, 22.1, 43.3]
    expect(normalizarA100(entrada)).toEqual(normalizarA100(entrada))
  })
})

describe('agregarConProRata', () => {
  it('la nueva entra con 100/(n+1) y las viejas se achican para hacerle lugar', () => {
    const antes = [papel('AL30', 50), papel('GD41', 50)]
    const despues = agregarConProRata(antes, papel('YMCXO', 0))

    expect(despues).toHaveLength(3)
    expect(suma(despues)).toBeCloseTo(100, 10)
    // La nueva pide 33,33 y las dos viejas se reparten el resto en partes iguales.
    expect(despues.map((p) => p.ticker)).toEqual(['AL30', 'GD41', 'YMCXO'])
    for (const posicion of despues) {
      expect(posicion.peso).toBeGreaterThan(33)
      expect(posicion.peso).toBeLessThan(34)
    }
  })

  it('mantiene la proporción relativa entre las que ya estaban', () => {
    const antes = [papel('AL30', 75), papel('GD41', 25)]
    const despues = agregarConProRata(antes, papel('YMCXO', 0))

    // AL30 seguía pesando el triple que GD41 antes de agregar; sigue pesando el triple después.
    expect(despues[0].peso / despues[1].peso).toBeCloseTo(3, 1)
    expect(suma(despues)).toBeCloseTo(100, 10)
  })

  it('agregar sobre una cartera vacía deja una sola posición con el 100', () => {
    expect(agregarConProRata([], papel('AL30', 0))).toEqual([papel('AL30', 100)])
  })

  it('reconcilia de paso una cartera que venía desviada de 100', () => {
    const desviada = [papel('AL30', 10), papel('GD41', 10)]
    const despues = agregarConProRata(desviada, papel('YMCXO', 0))

    expect(suma(despues)).toBeCloseTo(100, 10)
  })

  it('con peso pedido, la nueva se queda con ese peso exacto', () => {
    const antes = [papel('AL30', 50), papel('GD41', 50)]
    const despues = agregarConProRata(antes, papel('FCI Pesos', 10), 10)

    expect(despues[2].peso).toBe(10)
    expect(suma(despues)).toBeCloseTo(100, 10)
    // Las dos viejas se reparten el 90 restante.
    expect(despues[0].peso).toBeCloseTo(45, 1)
    expect(despues[1].peso).toBeCloseTo(45, 1)
  })

  it.each([3, 7, 13])('agregar hasta %i posiciones mantiene la suma en 100', (cantidad) => {
    let cartera: ReturnType<typeof papel>[] = []
    for (let i = 0; i < cantidad; i += 1) {
      cartera = agregarConProRata(cartera, papel(`T${i}`, 0))
      expect(suma(cartera)).toBeCloseTo(100, 10)
    }
    expect(cartera).toHaveLength(cantidad)
  })
})

describe('quitarConProRata', () => {
  it('reparte lo que liberó la posición que sale entre las que quedan', () => {
    const antes = [papel('AL30', 40), papel('GD41', 30), papel('YMCXO', 30)]
    const despues = quitarConProRata(antes, (p) => p.ticker === 'YMCXO')

    expect(despues.map((p) => p.ticker)).toEqual(['AL30', 'GD41'])
    expect(suma(despues)).toBeCloseTo(100, 10)
    // 40 y 30 escalados a 100: la proporción 4:3 se mantiene.
    expect(despues[0].peso).toBeCloseTo(57.1, 1)
    expect(despues[1].peso).toBeCloseTo(42.9, 1)
  })

  it('sacar toda la renta variable devuelve su porcentaje a los bonos', () => {
    const mixta = [
      { ticker: 'AL30', peso: 37.5, clase: 'renta_fija' as const },
      { ticker: 'GD41', peso: 37.5, clase: 'renta_fija' as const },
      { ticker: 'GGAL', peso: 12.5, clase: 'renta_variable' as const },
      { ticker: 'YPFD', peso: 12.5, clase: 'renta_variable' as const },
    ]
    const soloBonos = quitarConProRata(mixta, (p) => p.clase === 'renta_variable')

    expect(soloBonos).toHaveLength(2)
    expect(suma(soloBonos)).toBeCloseTo(100, 10)
    expect(soloBonos.map((p) => p.peso)).toEqual([50, 50])
  })

  it('sacar la última posición deja la cartera vacía, no una con el 100', () => {
    expect(quitarConProRata([papel('AL30', 100)], (p) => p.ticker === 'AL30')).toEqual([])
  })

  it('quitar algo que no está deja la cartera igual, pero normalizada', () => {
    const antes = [papel('AL30', 50), papel('GD41', 50)]
    const despues = quitarConProRata(antes, (p) => p.ticker === 'NO_EXISTE')

    expect(despues).toHaveLength(2)
    expect(suma(despues)).toBeCloseTo(100, 10)
  })

  it.each([3, 7, 13])('quitar de a una desde %i posiciones mantiene la suma en 100', (cantidad) => {
    let cartera = Array.from({ length: cantidad }, (_, i) => papel(`T${i}`, 100 / cantidad))
    while (cartera.length > 0) {
      const primero = cartera[0].ticker
      cartera = quitarConProRata(cartera, (p) => p.ticker === primero)
      if (cartera.length > 0) expect(suma(cartera)).toBeCloseTo(100, 10)
    }
    expect(cartera).toEqual([])
  })
})

describe('equiponderarPesos', () => {
  it('deja a todas casi iguales y sumando 100 exacto', () => {
    const parejas = equiponderarPesos([papel('A', 80), papel('B', 15), papel('C', 5)])

    expect(suma(parejas)).toBeCloseTo(100, 10)
    expect(parejas.map((p) => p.peso)).toEqual([33.4, 33.3, 33.3])
  })

  it('una cartera vacía queda vacía', () => {
    expect(equiponderarPesos([])).toEqual([])
  })

  it.each([3, 7, 13])('con %i posiciones el residuo no se pierde', (cantidad) => {
    const parejas = equiponderarPesos(Array.from({ length: cantidad }, (_, i) => papel(`T${i}`, 1)))

    expect(Math.abs(suma(parejas) - 100)).toBeLessThan(TOLERANCIA_SUMA + 1e-9)
  })
})
