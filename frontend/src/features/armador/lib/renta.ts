/**
 * El motor de F-021: de la grilla de doce meses en plata (`/calendario/cartera`) a lo que el panel
 * dibuja — las dos cordilleras (A2 dólares, A3 pesos) y la renta anual sobre lo invertido (A9).
 * Función pura, sin red ni store, como `resolver.ts`: se testea aislada de la pantalla.
 *
 * **Todo entra y sale abierto por moneda de cobro** (regla 3 del proyecto). No hay ninguna función
 * acá que sume un monto en pesos con uno en dólares — ni siquiera de paso, para un total
 * intermedio. Donde el dato no permite calcular algo (denominador sin posiciones, año sin cupones),
 * el resultado es `null`, nunca 0 ni un valor inventado (regla 1).
 */

import type { MesDelCalendario } from './schema'

/** Lo que paga un instrumento en un mes, dentro de una cordillera de una sola moneda. */
export interface SegmentoDeMes {
  ticker: string
  monto: number
}

/** Una columna de la cordillera: el total del mes en esa moneda y de qué papeles sale. */
export interface ColumnaCordillera {
  indice: number
  etiqueta: string
  nombre: string
  /** Renta del mes en esta moneda. 0 explícito cuando nadie cobra — el calendario ya lo declaró
   *  así, así que acá no hay `null` que inventar. */
  total: number
  /** Un tramo por papel que paga renta ese mes en esta moneda, en el orden en que vienen del
   *  backend. Σ de `monto` sobre `segmentos` es `total`, por construcción. */
  segmentos: SegmentoDeMes[]
  amortizacion: number
}

/**
 * Las doce columnas de una cordillera, filtradas a una sola moneda de cobro.
 *
 * El filtro por `instrumento.moneda === moneda` es lo que separa la cordillera en dólares de la de
 * pesos: son dos gráficos con su propia escala, nunca uno mezclado (regla 2 del design system).
 */
export function columnasDeCordillera(meses: MesDelCalendario[], moneda: string): ColumnaCordillera[] {
  return meses.map((mes, indice) => ({
    indice,
    etiqueta: mes.etiqueta,
    nombre: mes.nombre,
    total: mes.renta?.[moneda] ?? 0,
    segmentos: mes.instrumentos
      .filter((i) => i.moneda === moneda && (i.renta ?? 0) > 0)
      .map((i) => ({ ticker: i.ticker, monto: i.renta ?? 0 })),
    amortizacion: mes.amortizacion?.[moneda] ?? 0,
  }))
}

/** El mes de mayor renta de la cordillera — la escala contra la que se dibuja cada barra. 0 si
 *  ningún mes cobra nada en esa moneda (cordillera plana, no un error). */
export function picoDeColumnas(columnas: ColumnaCordillera[]): number {
  return columnas.reduce((max, c) => Math.max(max, c.total), 0)
}

/**
 * Cuánto está invertido en las posiciones que cobran en cada moneda — el denominador de A9.
 *
 * La moneda de cobro de un ticker sale del propio calendario (`instrumento.moneda`, derivada del
 * segmento), no de `moneda_cotizacion` de la especie: son dos clasificaciones distintas y la que
 * importa para "sobre lo invertido en lo que cobra en esta moneda" es la del cupón. Un ticker que
 * no aparece en ningún mes del calendario (fuera del universo de flujos) no aporta a ningún
 * denominador: no se le adivina la moneda.
 */
export function invertidoPorMoneda(
  meses: MesDelCalendario[],
  resueltas: { ticker: string; invertido: number | null }[],
): Record<string, number> {
  const monedaPorTicker = new Map<string, string>()
  for (const mes of meses) {
    for (const instrumento of mes.instrumentos) {
      if (!monedaPorTicker.has(instrumento.ticker)) monedaPorTicker.set(instrumento.ticker, instrumento.moneda)
    }
  }

  const totales: Record<string, number> = {}
  for (const r of resueltas) {
    if (r.invertido === null) continue
    const moneda = monedaPorTicker.get(r.ticker)
    if (moneda === undefined) continue
    totales[moneda] = (totales[moneda] ?? 0) + r.invertido
  }
  return totales
}

/** Un mes dentro de la serie de renta de una moneda — lo que necesitan "mes más flaco/fuerte". */
export interface MesDeRenta {
  indice: number
  etiqueta: string
  nombre: string
  monto: number
}

/** Renta anual sobre lo invertido de una sola moneda de cobro, con la cuenta completa (A9). */
export interface RentaAnualPorMoneda {
  moneda: string
  /** `resumen.renta_anual[moneda]` del backend — ya excluye amortización por construcción
   *  (GWT-5: la amortización no entra al numerador). */
  rentaAnual: number
  /** Lo invertido en las posiciones que cobran en esta moneda. `null` si no se pudo determinar
   *  ninguna (nada de lo resuelto tiene esta moneda de cobro) — nunca 0 en su lugar. */
  invertido: number | null
  /** `rentaAnual / invertido * 100`. `null` si `invertido` es `null` o cero: no hay con qué
   *  dividir, y dividir por cero no es un resultado, es un dato faltante. */
  pct: number | null
  /** Meses con renta > 0 en esta moneda, de 12. */
  mesesCubiertos: number
  /** `1 - (Σ|renta_mes - promedio| / (2*rentaAnual) * (12/11))`, portado tal cual del design
   *  system. `null` cuando `rentaAnual` es 0: la fórmula divide por la renta anual. */
  parejo: number | null
  mesMasFlaco: MesDeRenta | null
  mesMasFuerte: MesDeRenta | null
  serie: MesDeRenta[]
}

/**
 * Arma la tarjeta de renta anual de cada moneda presente en `rentaAnual` — típicamente lo que
 * devuelve `resumen.renta_anual` del backend, que trae una entrada por cada moneda de cobro de la
 * cartera aunque ese año no cobre nada en ella (0 explícito, nunca ausente).
 */
export function calcularRentaAnualPorMoneda(
  meses: MesDelCalendario[],
  rentaAnual: Record<string, number>,
  invertidoPorMonedaMapa: Record<string, number>,
): RentaAnualPorMoneda[] {
  return Object.entries(rentaAnual).map(([moneda, total]) => {
    const serie: MesDeRenta[] = meses.map((mes, indice) => ({
      indice,
      etiqueta: mes.etiqueta,
      nombre: mes.nombre,
      monto: mes.renta?.[moneda] ?? 0,
    }))

    const mesesCubiertos = serie.filter((m) => m.monto > 0).length
    const promedio = total / 12
    const parejo =
      total > 0
        ? 1 - (serie.reduce((acc, m) => acc + Math.abs(m.monto - promedio), 0) / (2 * total)) * (12 / 11)
        : null

    let mesMasFlaco: MesDeRenta | null = null
    let mesMasFuerte: MesDeRenta | null = null
    for (const m of serie) {
      if (mesMasFlaco === null || m.monto < mesMasFlaco.monto) mesMasFlaco = m
      if (mesMasFuerte === null || m.monto > mesMasFuerte.monto) mesMasFuerte = m
    }

    const invertido = invertidoPorMonedaMapa[moneda] ?? null
    const pct = invertido !== null && invertido > 0 ? (total / invertido) * 100 : null

    return { moneda, rentaAnual: total, invertido, pct, mesesCubiertos, parejo, mesMasFlaco, mesMasFuerte, serie }
  })
}
