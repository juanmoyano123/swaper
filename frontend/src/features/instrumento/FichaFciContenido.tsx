/**
 * El detalle de un fondo común de inversión — F-057.
 *
 * Lo que no entra a la grilla de doce columnas del monitor: sociedad gerente y depositaria, las
 * siete columnas de costos, market share, cantidad de cuotapartes, los dos códigos, y la
 * discrepancia entre `Moneda` y `Moneda Fondo` cuando existe — declarada, nunca resuelta a una de
 * las dos (regla 11).
 */

import { EstadoVacio } from '@/components/EstadoVacio'
import { useFichaFci } from '@/lib/fci'
import { fmtCompacto, fmtFecha, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

function Fila({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '5px 0', borderBottom: '1px solid var(--lin)' }}>
      <span style={{ fontSize: 12, color: 'var(--dim)' }}>{etiqueta}</span>
      <span className="mono" style={{ fontSize: 12.5, textAlign: 'right' }}>{valor}</span>
    </div>
  )
}

export function FichaFciContenido({ codigoCafci }: { codigoCafci: string | null }) {
  const ficha = useFichaFci(codigoCafci)

  if (ficha.isPending) {
    return <p style={{ color: 'var(--dim)', fontSize: 12.5 }}>consultando el fondo…</p>
  }

  if (ficha.isError) {
    return (
      <EstadoVacio
        titulo="No se pudo traer este fondo."
        detalle="El código puede no estar en la planilla de hoy, o la base no responde."
      />
    )
  }

  const f = ficha.data

  return (
    <div>
      <p style={{ fontSize: 13, margin: '0 0 4px' }}>{f.fondo}</p>

      {f.enlace_composicion_cnv ? (
        <div style={{ margin: '0 0 12px' }}>
          <a
            href={f.enlace_composicion_cnv}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-block',
              fontSize: 12.5,
              fontWeight: 600,
              padding: '7px 14px',
              borderRadius: 3,
              border: '1px solid var(--ac)',
              background: 'var(--ac)',
              color: '#08120c',
              textDecoration: 'none',
            }}
          >
            Composición de cartera en CNV ↗
          </a>
          <p style={{ fontSize: 10.5, color: 'var(--dim)', margin: '4px 0 0' }}>
            La composición semanal completa del fondo, publicada por la CNV — artículo 34.
          </p>
        </div>
      ) : (
        <p style={{ fontSize: 11, color: 'var(--dim)', margin: '0 0 12px' }}>
          El mapeo contra el registro público de la CNV está pendiente de curación para este fondo.
        </p>
      )}

      <p style={{ fontSize: 11, color: 'var(--dim)', margin: '0 0 12px' }}>
        {f.tipo_renta} · {f.moneda}
        {f.discrepancia_moneda && f.moneda_fondo ? ` (moneda del fondo: ${f.moneda_fondo} — la sección y el fondo declaran monedas distintas)` : ''}
      </p>

      <Fila etiqueta="Valor de cuotaparte (por mil)" valor={fmtNumero(f.vcp)} />
      <Fila etiqueta="Fecha del VCP" valor={f.fecha_vcp ? fmtFecha(f.fecha_vcp) : SIN_DATO} />
      <Fila etiqueta="Cantidad de cuotapartes" valor={fmtCompacto(f.cuotapartes)} />
      <Fila etiqueta="Patrimonio" valor={fmtCompacto(f.patrimonio)} />
      <Fila etiqueta="Market share" valor={f.market_share === null ? SIN_DATO : fmtPct(f.market_share)} />

      <p style={{ fontSize: 11, color: 'var(--dim)', margin: '16px 0 4px' }}>Sociedad</p>
      <Fila etiqueta="Sociedad gerente" valor={f.gerente ?? SIN_DATO} />
      <Fila etiqueta="Sociedad depositaria" valor={f.depositaria ?? SIN_DATO} />
      <Fila etiqueta="Código CAFCI" valor={f.codigo_cafci} />
      <Fila etiqueta="Código CNV" valor={f.codigo_cnv ?? SIN_DATO} />

      <p style={{ fontSize: 11, color: 'var(--dim)', margin: '16px 0 4px' }}>Costos</p>
      <Fila etiqueta="Comisión de ingreso" valor={f.comision_ingreso === null ? SIN_DATO : fmtPct(f.comision_ingreso)} />
      <Fila etiqueta="Honorarios adm. sociedad gerente" valor={f.honorarios_adm_sg === null ? SIN_DATO : fmtPct(f.honorarios_adm_sg)} />
      <Fila etiqueta="Honorarios adm. sociedad depositaria" valor={f.honorarios_adm_sd === null ? SIN_DATO : fmtPct(f.honorarios_adm_sd)} />
      <Fila etiqueta="Gastos ordinarios de gestión" valor={f.gastos_ord_gestion === null ? SIN_DATO : fmtPct(f.gastos_ord_gestion)} />
      <Fila etiqueta="Comisión de rescate" valor={f.comision_rescate === null ? SIN_DATO : fmtPct(f.comision_rescate)} />
      <Fila etiqueta="Comisión de transferencia" valor={f.comision_transferencia === null ? SIN_DATO : fmtPct(f.comision_transferencia)} />
      <Fila etiqueta="Honorarios de éxito" valor={f.honorarios_exito === null ? SIN_DATO : fmtPct(f.honorarios_exito)} />
      <Fila etiqueta="Mínimo de inversión" valor={f.minimo_inversion === null ? SIN_DATO : fmtNumero(f.minimo_inversion)} />
      <Fila etiqueta="Plazo de rescate (días)" valor={f.dias_para_rescatar === null ? SIN_DATO : fmtNumero(f.dias_para_rescatar, 0)} />

      <p style={{ fontSize: 11, color: 'var(--dim)', margin: '16px 0 0' }}>{f.advertencia_distribucion}</p>
    </div>
  )
}
