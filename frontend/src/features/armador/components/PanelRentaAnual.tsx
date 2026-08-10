/**
 * La tarjeta de renta anual sobre lo invertido — A9. Una por moneda de cobro presente en la
 * cartera: no hay una versión que las junte, porque un cupón en pesos y uno en dólares no son el
 * mismo peso hasta que se declara un tipo de cambio, y eso es justamente lo que esta tarjeta no
 * hace (regla 3 del proyecto). El número que cierra la venta es éste, con la cuenta a la vista.
 */

import { fmtMonto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

import type { RentaAnualPorMoneda } from '../lib/renta'

/** El dominio sólo declara `usd`/`ars` (`MONEDA_SEGMENTO`); un código nuevo se muestra crudo en vez
 *  de forzarlo a una de las dos monedas conocidas. */
function fmtMontoMoneda(valor: number, moneda: string): string {
  if (moneda === 'usd' || moneda === 'ars') return fmtMonto(valor, moneda)
  return `${moneda.toUpperCase()} ${fmtNumero(valor)}`
}

const ROTULO_MONEDA: Record<string, string> = { usd: 'dólares', ars: 'pesos' }

export function PanelRentaAnual({ datos }: { datos: RentaAnualPorMoneda[] }) {
  if (datos.length === 0) {
    return (
      <div
        style={{
          background: 'var(--pan)',
          border: '1px dashed var(--lin)',
          borderRadius: 4,
          padding: '14px 16px',
          fontSize: 12,
          color: 'var(--dim)',
        }}
      >
        Sin cupones que calcular en ninguna moneda: la cartera no tiene posiciones de renta fija
        resueltas con cronograma de pagos.
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
      {datos.map((d) => (
        <TarjetaRentaAnual key={d.moneda} datos={d} />
      ))}
    </div>
  )
}

function TarjetaRentaAnual({ datos }: { datos: RentaAnualPorMoneda }) {
  const rotuloMoneda = ROTULO_MONEDA[datos.moneda] ?? datos.moneda

  return (
    <div style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '14px 16px' }}>
      <div
        className="rotulo"
        style={{ fontSize: 10, letterSpacing: '0.13em', textTransform: 'uppercase' }}
      >
        Renta anual en {rotuloMoneda}
      </div>

      <div className="mono" style={{ fontSize: 36, fontWeight: 600, lineHeight: 1.15, color: 'var(--pos)' }}>
        {datos.pct !== null ? fmtPct(datos.pct) : SIN_DATO}
      </div>

      <p className="mono" style={{ margin: '2px 0 0', fontSize: 11, color: 'var(--dim)' }}>
        {fmtMontoMoneda(datos.rentaAnual, datos.moneda)} /{' '}
        {datos.invertido !== null ? fmtMontoMoneda(datos.invertido, datos.moneda) : SIN_DATO}
        {datos.pct !== null ? ` = ${fmtPct(datos.pct)}` : ''}
      </p>

      <p style={{ margin: '4px 0 0', fontSize: 10.5, color: 'var(--sd)', textWrap: 'pretty' }}>
        Sólo cupones: la amortización no entra en este número, y no se promedia con la renta de
        otra moneda.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 12 }}>
        <Kpi rotulo="Meses cubiertos" valor={`${datos.mesesCubiertos}/12`} />
        <Kpi rotulo="Parejo" valor={datos.parejo !== null ? fmtPct(datos.parejo * 100) : SIN_DATO} />
        <Kpi
          rotulo="Mes más flaco"
          valor={
            datos.mesMasFlaco
              ? `${datos.mesMasFlaco.nombre} · ${fmtMontoMoneda(datos.mesMasFlaco.monto, datos.moneda)}`
              : SIN_DATO
          }
        />
        <Kpi
          rotulo="Mes más fuerte"
          valor={
            datos.mesMasFuerte
              ? `${datos.mesMasFuerte.nombre} · ${fmtMontoMoneda(datos.mesMasFuerte.monto, datos.moneda)}`
              : SIN_DATO
          }
        />
      </div>
    </div>
  )
}

function Kpi({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 13, color: 'var(--tx)' }}>
        {valor}
      </div>
      <div style={{ fontSize: 9.5, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        {rotulo}
      </div>
    </div>
  )
}
