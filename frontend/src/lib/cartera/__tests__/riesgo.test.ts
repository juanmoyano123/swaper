/**
 * `vectorDeRiesgo`, aislado: sin red, sin React. Cubre los cinco GWT de F-031 y los edge cases
 * que el plan deja explícitos — incluido el de igualdad de los tres orígenes (armador,
 * diagnóstico, propuesta cruda) que es el criterio de aceptación del riesgo R12.
 */

import { describe, expect, it } from 'vitest'

import type { Concentracion } from '../esquemaConcentracion'
import { vectorDeRiesgo, type EspecieRiesgo, type PosicionConPeso } from '../riesgo'

function especie(extra: Partial<EspecieRiesgo> & { ticker: string }): EspecieRiesgo {
  return {
    segmento: 'bonos_soberanos',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    clase_activo: 'soberano',
    duracion: 4,
    ley: 'Ley Argentina',
    volumen_usd: 1_000_000,
    calificacion: null,
    dato_sano: true,
    ...extra,
  }
}

function universo(especies: EspecieRiesgo[]): Map<string, EspecieRiesgo> {
  return new Map(especies.map((e) => [e.ticker, e]))
}

function concentracionBase(extra: Partial<Concentracion> = {}): Concentracion {
  return {
    perfil: 'moderado',
    limites: {
      tope_rend_usd: 10,
      percentil_liquidez: 20,
      max_emisor: 15,
      max_soberano: 60,
      max_sector: 25,
      min_sectores: 3,
    },
    topes: [],
    excedidos: 0,
    distribucion: { sector: [], ley: [], naturaleza: [] },
    sectores: { presentes: [], cantidad: 0, minimo: 3, suficiente: false, peso_sin_sector: 0 },
    peso: { declarado: 100, medido: 100 },
    fuera_del_universo: [],
    fci: [],
    alertas: [],
    ...extra,
  }
}

describe('GWT-1: nunca hay un número único de riesgo', () => {
  it('siempre devuelve exactamente seis ejes, en el orden fijo', () => {
    const ejes = vectorDeRiesgo([{ ticker: 'AL30', peso: 100 }], universo([especie({ ticker: 'AL30' })]), null)

    expect(ejes.map((e) => e.id)).toEqual([
      'duracion',
      'credito',
      'legislacion',
      'liquidez',
      'concentracion',
      'moneda',
    ])
  })

  it('ningún eje individual, ni ningún campo del vector, agrega los seis en un número', () => {
    const ejes = vectorDeRiesgo([{ ticker: 'AL30', peso: 100 }], universo([especie({ ticker: 'AL30' })]), null)
    // No existe estructuralmente un campo "score" en `EjeDeRiesgo`: esta afirmación documenta la
    // garantía de tipos, no la testea en runtime (no hay dónde ponerla).
    for (const eje of ejes) {
      expect(Object.keys(eje).sort()).toEqual(['cobertura', 'grupos', 'id', 'nombre', 'unidad', 'valor'])
    }
  })
})

describe('eje duración', () => {
  it('pondera sólo sobre el peso con duración informada, no la reparte como si pesara cero', () => {
    const posiciones: PosicionConPeso[] = [
      { ticker: 'AL30', peso: 60 },
      { ticker: 'SIN-DURACION', peso: 40 },
    ]
    const porTicker = universo([
      especie({ ticker: 'AL30', duracion: 5 }),
      especie({ ticker: 'SIN-DURACION', duracion: null }),
    ])

    const [duracion] = vectorDeRiesgo(posiciones, porTicker, null)

    expect(duracion.valor).toBeCloseTo(5, 6) // pondera sólo AL30, no divide por 100
    expect(duracion.cobertura.conDato).toBe(1)
    expect(duracion.cobertura.posiciones).toBe(2)
    expect(duracion.cobertura.pesoConDato).toBe(60)
    expect(duracion.cobertura.notas).toContain('sobre el 60% del peso con duración informada')
    expect(duracion.grupos).toEqual([])
  })

  it('valor null cuando ninguna posición tiene duración', () => {
    const porTicker = universo([especie({ ticker: 'AL30', duracion: null })])
    const [duracion] = vectorDeRiesgo([{ ticker: 'AL30', peso: 100 }], porTicker, null)

    expect(duracion.valor).toBeNull()
  })
})

describe('eje crédito', () => {
  it('GWT-2: lleva al lado la cobertura de calificación y declara las posiciones sin calificación', () => {
    const posiciones: PosicionConPeso[] = [
      { ticker: 'A', peso: 40 },
      { ticker: 'B', peso: 60 },
    ]
    const porTicker = universo([
      especie({ ticker: 'A', calificacion: 'AAA(arg)' }),
      especie({ ticker: 'B', calificacion: null }),
    ])

    const [, credito] = vectorDeRiesgo(posiciones, porTicker, null)

    expect(credito.valor).toBeNull() // compositivo
    expect(credito.cobertura.conDato).toBe(1)
    expect(credito.cobertura.posiciones).toBe(2)
    const notaProxies = credito.cobertura.notas.find((n) => n.startsWith('sin calificación en'))
    expect(notaProxies).toContain('sin calificación en 1 posiciones')
    expect(notaProxies).toContain('la calificación nunca filtra')

    const grupoCalificacion = credito.grupos.find((g) => g.titulo === 'Calificación')!
    expect(grupoCalificacion.tramos.find((t) => t.nombre === 'sin calificación')).toMatchObject({
      valor: 60,
      sinDato: true,
    })
  })

  it('agrupa por string exacto de calificación, nunca ordena alfabéticamente ni por severidad', () => {
    const posiciones: PosicionConPeso[] = [
      { ticker: 'A', peso: 10 },
      { ticker: 'B', peso: 70 },
      { ticker: 'C', peso: 20 },
    ]
    const porTicker = universo([
      especie({ ticker: 'A', calificacion: 'AAA(arg)' }),
      especie({ ticker: 'B', calificacion: 'BB-(arg)' }),
      especie({ ticker: 'C', calificacion: 'AA(arg)' }),
    ])

    const [, credito] = vectorDeRiesgo(posiciones, porTicker, null)
    const grupoCalificacion = credito.grupos.find((g) => g.titulo === 'Calificación')!

    // Orden por peso descendente: B (70) primero, no orden alfabético (A, AA, AAA) ni por
    // severidad (AAA mejor que BB-).
    expect(grupoCalificacion.tramos.map((t) => t.nombre)).toEqual(['BB-(arg)', 'AA(arg)', 'AAA(arg)'])
  })

  it('ninguna posición con calificación: un único tramo "sin calificación" al 100%', () => {
    const porTicker = universo([especie({ ticker: 'A', calificacion: null })])
    const [, credito] = vectorDeRiesgo([{ ticker: 'A', peso: 100 }], porTicker, null)

    const grupoCalificacion = credito.grupos.find((g) => g.titulo === 'Calificación')!
    expect(grupoCalificacion.tramos).toEqual([{ nombre: 'sin calificación', valor: 100, unidad: 'pp', sinDato: true, tope: null }])
    expect(credito.cobertura.notas.some((n) => n.includes('la calificación nunca filtra'))).toBe(true)
  })

  it('agrupa la clase de activo con el vocabulario de categoria_credito, cobertura 100%', () => {
    const posiciones: PosicionConPeso[] = [
      { ticker: 'GD30', peso: 50 },
      { ticker: 'CORP1', peso: 50 },
    ]
    const porTicker = universo([
      especie({ ticker: 'GD30', clase_activo: 'soberano' }),
      especie({ ticker: 'CORP1', clase_activo: 'corporativo' }),
    ])

    const [, credito] = vectorDeRiesgo(posiciones, porTicker, null)
    const grupoClase = credito.grupos.find((g) => g.titulo === 'Clase')!
    expect(grupoClase.tramos).toEqual([
      { nombre: 'soberano', valor: 50, unidad: 'pp', sinDato: false, tope: null },
      { nombre: 'corporativo', valor: 50, unidad: 'pp', sinDato: false, tope: null },
    ])
  })
})

describe('eje legislación', () => {
  it('mide el peso bajo ley extranjera con el conjunto exacto de detectar_swaps.py', () => {
    const posiciones: PosicionConPeso[] = [
      { ticker: 'LOCAL', peso: 40 },
      { ticker: 'NY', peso: 35 },
      { ticker: 'EUROPEA', peso: 25 },
    ]
    const porTicker = universo([
      especie({ ticker: 'LOCAL', ley: 'Ley Argentina' }),
      especie({ ticker: 'NY', ley: 'Ley N.Y.' }),
      especie({ ticker: 'EUROPEA', ley: 'Ley Europea' }),
    ])

    const [, , legislacion] = vectorDeRiesgo(posiciones, porTicker, null)

    expect(legislacion.valor).toBeCloseTo(60, 6) // NY + Europea
    expect(legislacion.unidad).toBe('pp')
  })

  it('ley no informada y ley en conflicto (null) van al mismo tramo declarado, marcado sinDato', () => {
    const porTicker = universo([especie({ ticker: 'A', ley: null })])
    const [, , legislacion] = vectorDeRiesgo([{ ticker: 'A', peso: 100 }], porTicker, null)

    const grupo = legislacion.grupos[0]
    expect(grupo.tramos).toEqual([{ nombre: 'ley no informada', valor: 100, unidad: 'pp', sinDato: true, tope: null }])
  })

  it('ninguna posición con ley conocida (todas null): valor 0 declarado, no null (decisión documentada)', () => {
    const porTicker = universo([especie({ ticker: 'A', ley: null }), especie({ ticker: 'B', ley: null })])
    const [, , legislacion] = vectorDeRiesgo(
      [
        { ticker: 'A', peso: 50 },
        { ticker: 'B', peso: 50 },
      ],
      porTicker,
      null,
    )

    expect(legislacion.valor).toBe(0)
    expect(legislacion.cobertura.notas).toContain('ninguna posición con ley informada: el 0% no implica ley local, es ausencia de dato')
  })

  it('una ley fuera de los dos conjuntos conocidos no se fuerza a ningún lado y se nombra', () => {
    const porTicker = universo([especie({ ticker: 'A', ley: 'Ley de Delaware' })])
    const [, , legislacion] = vectorDeRiesgo([{ ticker: 'A', peso: 100 }], porTicker, null)

    expect(legislacion.valor).toBe(0) // no cuenta como extranjera conocida
    expect(legislacion.grupos[0].tramos).toEqual([
      { nombre: 'Ley de Delaware', valor: 100, unidad: 'pp', sinDato: false, tope: null },
    ])
    expect(legislacion.cobertura.notas.some((n) => n.includes("ley 'Ley de Delaware' no reconocida"))).toBe(true)
  })
})

describe('eje liquidez', () => {
  it('percentila dentro del propio segmento, sobre las especies sanas con volumen', () => {
    const porTicker = universo([
      especie({ ticker: 'BAJO', segmento: 'bonos_soberanos', volumen_usd: 100, dato_sano: true }),
      especie({ ticker: 'MEDIO', segmento: 'bonos_soberanos', volumen_usd: 500, dato_sano: true }),
      especie({ ticker: 'ALTO', segmento: 'bonos_soberanos', volumen_usd: 900, dato_sano: true }),
    ])
    const [, , , liquidez] = vectorDeRiesgo([{ ticker: 'MEDIO', peso: 100 }], porTicker, null)

    // MEDIO es el 2do de 3 → 2/3*100 = 66,67
    expect(liquidez.valor).toBeCloseTo((2 / 3) * 100, 6)
    expect(liquidez.unidad).toBe('percentil')
  })

  it('segmento con una sola especie sana: percentil 100 contra sí misma, no es un bug', () => {
    const porTicker = universo([especie({ ticker: 'UNICA', segmento: 'letras', volumen_usd: 50, dato_sano: true })])
    const [, , , liquidez] = vectorDeRiesgo([{ ticker: 'UNICA', peso: 100 }], porTicker, null)

    expect(liquidez.valor).toBe(100)
  })

  it('declara el faltante estructural del spread bid/ask, siempre', () => {
    const porTicker = universo([especie({ ticker: 'A' })])
    const [, , , liquidez] = vectorDeRiesgo([{ ticker: 'A', peso: 100 }], porTicker, null)

    expect(liquidez.cobertura.notas.some((n) => n.includes('spread bid/ask'))).toBe(true)
    expect(liquidez.cobertura.notas.some((n) => n.includes('F-035'))).toBe(true)
  })

  it('el grupo abre la agregación por segmento, para que el número global no sea lo único visible', () => {
    const porTicker = universo([
      especie({ ticker: 'A', segmento: 'bonos_soberanos', volumen_usd: 100 }),
      especie({ ticker: 'B', segmento: 'letras', volumen_usd: 200 }),
    ])
    const posiciones: PosicionConPeso[] = [
      { ticker: 'A', peso: 50 },
      { ticker: 'B', peso: 50 },
    ]
    const [, , , liquidez] = vectorDeRiesgo(posiciones, porTicker, null)

    const grupo = liquidez.grupos[0]
    expect(grupo.titulo).toBe('Por segmento')
    expect(grupo.tramos.map((t) => t.nombre).sort()).toEqual(['bonos_soberanos', 'letras'])
  })
})

describe('eje concentración', () => {
  it('lee el Concentracion ya cacheado, sin recalcular: máximo entre soberano y emisor', () => {
    const datos = concentracionBase({
      topes: [
        { tipo: 'soberano', clave: 'SOBERANO_AR', nombre: 'Soberano AR', peso: 45, tope: 60, excedido: false, exceso: 0 },
        { tipo: 'emisor', clave: 'YPF', nombre: 'YPF', peso: 12, tope: 15, excedido: false, exceso: 0 },
        { tipo: 'sector', clave: 'Energía', nombre: 'Energía', peso: 20, tope: 25, excedido: false, exceso: 0 },
      ],
    })
    const [, , , , concentracion] = vectorDeRiesgo([{ ticker: 'X', peso: 100 }], new Map(), datos)

    expect(concentracion.valor).toBe(45) // máximo entre soberano (45) y emisor (12), no el sector
    const grupo = concentracion.grupos[0]
    expect(grupo.tramos.find((t) => t.nombre === 'máximo por crédito')).toMatchObject({ valor: 45, tope: 60 })
    expect(grupo.tramos.find((t) => t.nombre === 'máximo por sector')).toMatchObject({ valor: 20, tope: 25 })
  })

  it('GWT-4: GD30, AE38 y TZX26 cuentan bajo SOBERANO_AR como una sola clave', () => {
    // El colapso a SOBERANO_AR ya lo garantiza el backend de F-020 (verificado en sus propios
    // tests): acá se verifica que este eje sólo lee ese resultado sin desagregarlo de nuevo.
    const datos = concentracionBase({
      topes: [{ tipo: 'soberano', clave: 'SOBERANO_AR', nombre: 'Soberano AR', peso: 100, tope: 60, excedido: true, exceso: 40 }],
    })
    const [, , , , concentracion] = vectorDeRiesgo([{ ticker: 'GD30', peso: 100 }], new Map(), datos)

    const tramoCredito = concentracion.grupos[0].tramos.find((t) => t.nombre === 'máximo por crédito')!
    expect(tramoCredito.valor).toBe(100)
  })

  it('agrega "sin sector informado" con sinDato cuando hay peso sin sector', () => {
    const datos = concentracionBase({ sectores: { presentes: [], cantidad: 0, minimo: 3, suficiente: false, peso_sin_sector: 30 } })
    const [, , , , concentracion] = vectorDeRiesgo([{ ticker: 'X', peso: 100 }], new Map(), datos)

    const tramo = concentracion.grupos[0].tramos.find((t) => t.nombre === 'sin sector informado')
    expect(tramo).toMatchObject({ valor: 30, sinDato: true })
  })

  it('eje "no medido" cuando concentracion es null: no se estima con un valor a mitad de camino', () => {
    const [, , , , concentracion] = vectorDeRiesgo([{ ticker: 'X', peso: 100 }], new Map(), null)

    expect(concentracion.valor).toBeNull()
    expect(concentracion.grupos).toEqual([])
    expect(concentracion.cobertura.notas).toEqual(['eje no medido: sin respuesta del servicio de concentración'])
  })
})

describe('eje moneda', () => {
  it('reusa rendimientosPorNaturaleza y descarta el rendimiento, sólo mide composición', () => {
    const porTicker = universo([
      especie({ ticker: 'A', naturaleza: 'tir_usd', naturaleza_nombre: 'TIR en dólares (hard dollar)' }),
      especie({ ticker: 'B', naturaleza: 'tna_nominal_ars', naturaleza_nombre: 'TNA nominal en pesos' }),
    ])
    const posiciones: PosicionConPeso[] = [
      { ticker: 'A', peso: 70 },
      { ticker: 'B', peso: 30 },
    ]
    const [, , , , , moneda] = vectorDeRiesgo(posiciones, porTicker, null)

    expect(moneda.valor).toBeNull() // compositivo
    expect(moneda.unidad).toBeNull()
    const tramoUsd = moneda.grupos[0].tramos.find((t) => t.nombre === 'TIR en dólares (hard dollar)')!
    expect(tramoUsd.valor).toBeCloseTo(70, 6)
    const tramoArs = moneda.grupos[0].tramos.find((t) => t.nombre === 'TNA nominal en pesos')!
    expect(tramoArs.valor).toBeCloseTo(30, 6)
  })
})

describe('edge case: posición fuera del universo', () => {
  it('cuenta sin dato en los seis ejes y se nombra en cada cobertura.notas', () => {
    const porTicker = universo([especie({ ticker: 'CONOCIDO' })])
    const posiciones: PosicionConPeso[] = [
      { ticker: 'CONOCIDO', peso: 70 },
      { ticker: 'ACCION-XYZ', peso: 30 },
    ]

    const ejes = vectorDeRiesgo(posiciones, porTicker, concentracionBase({ fuera_del_universo: ['ACCION-XYZ'] }))

    for (const eje of ejes) {
      expect(eje.cobertura.posiciones).toBe(2)
      const notaFuera = eje.cobertura.notas.find((n) => n.includes('fuera del universo de renta fija'))
      expect(notaFuera, `eje ${eje.id} debería declarar la posición fuera del universo`).toBeDefined()
      expect(notaFuera).toContain('1 posición(es)')
    }
  })
})

describe('edge case: cartera vacía', () => {
  it('no tira y devuelve los seis ejes con cobertura en cero', () => {
    const ejes = vectorDeRiesgo([], new Map(), null)

    expect(ejes).toHaveLength(6)
    for (const eje of ejes) {
      expect(eje.cobertura.posiciones).toBe(0)
      expect(eje.cobertura.pesoTotal).toBe(0)
    }
  })
})

describe('GWT-5: la misma composición da el mismo vector desde los tres orígenes', () => {
  it('armador (pesoReal colapsado a peso), diagnóstico (peso: pesoReal) y una propuesta cruda coinciden por deepEqual', () => {
    const porTicker = universo([
      especie({ ticker: 'GD30', clase_activo: 'soberano', ley: 'Ley N.Y.', calificacion: null }),
      especie({ ticker: 'AE38', clase_activo: 'soberano', ley: 'Ley Argentina', calificacion: 'CCC' }),
      especie({ ticker: 'TZX26', clase_activo: 'soberano', ley: 'Ley Argentina', calificacion: null, duracion: 2 }),
    ])
    const concentracion = concentracionBase({
      topes: [{ tipo: 'soberano', clave: 'SOBERANO_AR', nombre: 'Soberano AR', peso: 100, tope: 60, excedido: true, exceso: 40 }],
    })

    // Origen 1: armador — `resueltas.map(r => ({ ticker: r.ticker, peso: r.pesoReal ?? r.peso }))`
    const resueltasArmador = [
      { ticker: 'GD30', peso: 40, pesoReal: 38 },
      { ticker: 'AE38', peso: 35, pesoReal: 34 },
      { ticker: 'TZX26', peso: 25, pesoReal: 28 },
    ]
    const posicionesArmador = resueltasArmador.map((r) => ({ ticker: r.ticker, peso: r.pesoReal ?? r.peso }))

    // Origen 2: diagnóstico — `posicionesConPeso = valuadas.map(v => ({ ticker: v.ticker, peso: v.pesoReal }))`
    const valuadasDiagnostico = [
      { ticker: 'GD30', pesoReal: 38 },
      { ticker: 'AE38', pesoReal: 34 },
      { ticker: 'TZX26', pesoReal: 28 },
    ]
    const posicionesDiagnostico = valuadasDiagnostico.map((v) => ({ ticker: v.ticker, peso: v.pesoReal }))

    // Origen 3: una "propuesta" cruda, armada a mano sin pasar por ningún hook.
    const posicionesPropuesta: PosicionConPeso[] = [
      { ticker: 'GD30', peso: 38 },
      { ticker: 'AE38', peso: 34 },
      { ticker: 'TZX26', peso: 28 },
    ]

    const vectorArmador = vectorDeRiesgo(posicionesArmador, porTicker, concentracion)
    const vectorDiagnostico = vectorDeRiesgo(posicionesDiagnostico, porTicker, concentracion)
    const vectorPropuesta = vectorDeRiesgo(posicionesPropuesta, porTicker, concentracion)

    expect(vectorArmador).toEqual(vectorDiagnostico)
    expect(vectorDiagnostico).toEqual(vectorPropuesta)
  })
})

describe('preprocesamiento común', () => {
  it('suma pesos por ticker repetido antes de calcular cualquier eje', () => {
    const porTicker = universo([especie({ ticker: 'AL30', duracion: 4 })])
    const posiciones: PosicionConPeso[] = [
      { ticker: 'AL30', peso: 30 },
      { ticker: 'AL30', peso: 20 },
    ]

    const [duracion] = vectorDeRiesgo(posiciones, porTicker, null)

    expect(duracion.cobertura.posiciones).toBe(1) // un solo ticker, sumado
    expect(duracion.cobertura.pesoTotal).toBe(50)
  })
})

describe('F-046: nota de FCI, distinta de "fuera del universo" genérico', () => {
  const porTicker = universo([especie({ ticker: 'AL30', duracion: 4 })])
  const posiciones: PosicionConPeso[] = [
    { ticker: 'AL30', peso: 70 },
    { ticker: 'Fondo X', peso: 30, esFci: true },
  ]

  it('crédito y legislación: nota propia con el peso del FCI, no un typo genérico', () => {
    const [, credito, legislacion] = vectorDeRiesgo(posiciones, porTicker, null)

    expect(credito.cobertura.notas.some((n) => n.includes('30.0% en FCI'))).toBe(true)
    expect(legislacion.cobertura.notas.some((n) => n.includes('30.0% en FCI'))).toBe(true)
  })

  it('duración: sigue usando la nota genérica, sin desglosar el FCI (fuera del alcance del eje)', () => {
    const [duracion] = vectorDeRiesgo(posiciones, porTicker, null)

    expect(duracion.cobertura.notas.some((n) => n.includes('en FCI'))).toBe(false)
    expect(duracion.cobertura.notas.some((n) => n.includes('fuera del universo'))).toBe(true)
  })

  it('un typo real y un FCI en la misma cartera producen las dos notas por separado', () => {
    const conTypo: PosicionConPeso[] = [
      { ticker: 'AL30', peso: 50 },
      { ticker: 'NOEXISTE', peso: 20 },
      { ticker: 'Fondo X', peso: 30, esFci: true },
    ]
    const [, credito] = vectorDeRiesgo(conTypo, porTicker, null)

    expect(credito.cobertura.notas.some((n) => n.includes('1 posición(es) fuera del universo'))).toBe(true)
    expect(credito.cobertura.notas.some((n) => n.includes('en FCI'))).toBe(true)
  })

  it('concentración: nota con la cantidad de FCI cuando el backend los declaró aparte', () => {
    const concentracion = concentracionBase({ fci: ['Fondo X'], peso: { declarado: 100, medido: 100 } })
    const [, , , , concentracionEje] = vectorDeRiesgo(posiciones, porTicker, concentracion)

    expect(concentracionEje.cobertura.notas.some((n) => n.includes('1 FCI'))).toBe(true)
  })
})
