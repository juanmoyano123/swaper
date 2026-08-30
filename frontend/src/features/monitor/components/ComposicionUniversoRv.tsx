/**
 * Cómo se reparte el universo filtrado en cada eje de diversificación — F-078, fase 2 (28/08/2026),
 * ejes actualizados por F-079 (fase 5, 29/08/2026).
 *
 * Cinco `DistribucionBarras` —región, país, sector, estrategia del fondo, mercado— sobre lo que
 * dejaron los filtros. Rubro específico (`sic_codigo`, ~120 valores posibles) se fue de acá: con esa
 * cardinalidad no es una barra legible, sigue siendo filtro y nada más (ver `filtrosRentaVariable.ts`
 * y `FiltrosRentaVariable.tsx`). Es la mitad "veo" del mission control: los filtros recortan y esto
 * muestra qué quedó, para poder decir "esta selección es 70 % Estados Unidos" antes de armar nada.
 *
 * ## El peso es por cantidad de papeles, y la leyenda lo dice
 *
 * No hay "monto invertido" acá: esto es el universo negociable, no una cartera. Cada papel pesa
 * uno. Un porcentaje sin la unidad declarada es exactamente lo que este proyecto no hace, así que
 * la leyenda lo escribe en pantalla en vez de dejarlo en un comentario del código.
 *
 * **Se agrupa por papel, no por especie.** `AAPL`, `AAPLC` y `AAPLD` son el mismo CEDEAR de Apple
 * en pesos, cable y MEP —comparten `emision`, el backend lo determina en
 * `app/renta_variable/agrupamiento.py`— y contarlas por separado triplicaría el peso de Estados
 * Unidos frente a un papel sin variantes. Con una sola moneda a la vista suele haber una especie
 * por papel, pero eso es una consecuencia del selector, no una garantía: agrupar acá lo hace cierto
 * en cualquier caso.
 *
 * El representante del papel es su especie de ticker menor entre las visibles, y los atributos que
 * se leen —país, región, sector, estrategia, mercado— son atributos **del papel**, no de la
 * especie: las hermanas son la misma empresa liquidando distinto. No se completa un faltante de una
 * hermana con el valor de otra (eso sería propagar por analogía); simplemente se lee el papel una
 * sola vez.
 *
 * ## Lo que no tiene el dato es un tramo, nunca un reparto
 *
 * Es el contrato de `DistribucionBarras` y la razón por la que ese componente existe: un papel sin
 * país cae en "(sin país)" con su peso real y su color apagado. Repartirlo entre los países
 * conocidos, o simplemente omitirlo, haría que la distribución sume 100 % mintiendo sobre la
 * cobertura (reglas 1 y 11). Por eso un eje que hoy no tiene fuente aparece como una sola barra de
 * "sin dato" al 100 % en vez de desaparecer: eso **es** la respuesta, no un panel roto.
 */

import { useMemo } from 'react'

import { DistribucionBarras, type TramoDistribucion } from '@/components/DistribucionBarras'
import type { EspecieRentaVariable } from '@/lib/rentaVariable'
import { fmtNumero } from '@/lib/fmt'

import {
  CENTINELA_DE,
  etiquetaDeValorRv,
  type DimensionRv,
} from '../lib/filtrosRentaVariable'

/** Los cinco ejes, del más general al más específico — el mismo orden de los filtros, para que la
 *  lectura de arriba abajo no cambie de criterio a mitad de camino. */
const EJES: readonly { dimension: DimensionRv; titulo: string }[] = [
  { dimension: 'region', titulo: 'Región' },
  { dimension: 'pais', titulo: 'País' },
  { dimension: 'sector', titulo: 'Sector' },
  { dimension: 'estrategiaEtf', titulo: 'Estrategia del fondo' },
  { dimension: 'mercado', titulo: 'Mercado' },
]

/**
 * Un papel: la especie que lo representa y su clave de agrupamiento.
 *
 * `emision` puede venir `null` cuando la especie no tiene variantes; en ese caso el papel es ella
 * misma y su propio ticker alcanza como clave.
 */
function papelesDe(especies: readonly EspecieRentaVariable[]): EspecieRentaVariable[] {
  const porPapel = new Map<string, EspecieRentaVariable>()
  for (const especie of especies) {
    const clave = especie.emision ?? especie.ticker
    const actual = porPapel.get(clave)
    // Desempate por ticker y no por orden de llegada: la composición no puede cambiar porque el
    // backend haya paginado distinto.
    if (actual === undefined || especie.ticker.localeCompare(actual.ticker) < 0) {
      porPapel.set(clave, especie)
    }
  }
  return [...porPapel.values()]
}

/**
 * El valor del papel en cada eje, o `null` cuando la fuente no lo declara.
 *
 * **País y región** siguen la misma cascada que `filtrosRentaVariable.ts`: país es
 * `pais ?? etf_pais` (curados en el mismo vocabulario ISO, ver el docstring de ese módulo); región
 * cae de la subregión M49 curada al alcance del ETF y sólo como último recurso al token crudo del
 * nombre del fondo. Es una cascada de un único valor, no dos sumados: si un papel declarara dos
 * niveles a la vez, contar los dos duplicaría su peso y la distribución pasaría de 100 %.
 *
 * **Sector** usa `especie.sector ?? especie.sector_codigo`: la etiqueta ES si el curado la trae
 * cargada para esa fila, si no el código crudo — nunca se completa con la etiqueta de otra especie
 * del mismo código (regla 1: no se propaga un dato por analogía).
 */
function valorEnEje(
  especie: EspecieRentaVariable,
  dimension: DimensionRv,
  mercados: Map<string, string>,
): string | null {
  switch (dimension) {
    case 'region':
      return especie.region ?? especie.etf_region ?? especie.etf_alcance ?? especie.region_etf
    case 'pais':
      return especie.pais ?? especie.etf_pais
    case 'sector':
      return especie.sector ?? especie.sector_codigo
    case 'rubroEspecifico':
      return especie.rubro_especifico ?? especie.sic_codigo
    case 'estrategiaEtf':
      return especie.estrategia_etf
    case 'mercado': {
      const crudo = especie.mercado_origen
      if (crudo === null) return null
      // Misma forma canónica que los filtros (la variante de caja más frecuente): si acá se
      // agrupara por el literal crudo, "NYSE Arca" y "NYSE ARCA" darían dos barras del mismo
      // mercado.
      return mercados.get(crudo.toLowerCase()) ?? crudo
    }
  }
}

/** Los tramos de un eje: lo más pesado primero y el hueco al final, con su peso real. */
function tramosDeEje(
  papeles: readonly EspecieRentaVariable[],
  dimension: DimensionRv,
  mercados: Map<string, string>,
): TramoDistribucion[] {
  const conteo = new Map<string | null, number>()
  for (const papel of papeles) {
    const valor = valorEnEje(papel, dimension, mercados)
    conteo.set(valor, (conteo.get(valor) ?? 0) + 1)
  }

  const total = papeles.length
  const tramos = [...conteo.entries()].map(([valor, cantidad]) => ({
    nombre:
      valor === null
        ? etiquetaDeValorRv(dimension, CENTINELA_DE[dimension])
        : etiquetaDeValorRv(dimension, valor),
    peso: total > 0 ? (cantidad / total) * 100 : 0,
    sinDato: valor === null,
  }))

  return tramos.sort((a, b) => {
    if (a.sinDato !== b.sinDato) return a.sinDato ? 1 : -1
    return b.peso - a.peso || a.nombre.localeCompare(b.nombre, 'es')
  })
}

export function ComposicionUniversoRv({
  especies,
  mercados,
}: {
  /** El universo ya filtrado: lo que la tabla está mostrando, no el universo entero. */
  especies: readonly EspecieRentaVariable[]
  /** Las formas canónicas de mercado que devolvió `facetarRentaVariable`, para agrupar con el
   *  mismo criterio que los chips en vez de recalcularlo acá y arriesgarse a divergir. */
  mercados: Map<string, string>
}) {
  const papeles = useMemo(() => papelesDe(especies), [especies])
  const porEje = useMemo(
    () => EJES.map((eje) => ({ ...eje, tramos: tramosDeEje(papeles, eje.dimension, mercados) })),
    [papeles, mercados],
  )

  return (
    <section style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <h3
        style={{
          margin: 0,
          fontSize: 11,
          color: 'var(--dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        Composición de la selección
      </h3>
      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
        Porcentaje sobre {fmtNumero(papeles.length, 0)}{' '}
        {papeles.length === 1 ? 'papel' : 'papeles'} — por cantidad, no por monto invertido: el
        universo no tiene plata asignada. Las especies del mismo papel (AAPL, AAPLC y AAPLD) cuentan
        una vez. Lo que no declara el dato va en su propio tramo, nunca repartido entre los demás.
      </p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 14,
        }}
      >
        {porEje.map(({ dimension, titulo, tramos }) => (
          <DistribucionBarras
            key={dimension}
            titulo={titulo}
            tramos={tramos}
            vacio="Ningún papel bajo los filtros activos."
          />
        ))}
      </div>
    </section>
  )
}
