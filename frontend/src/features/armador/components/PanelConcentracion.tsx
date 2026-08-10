/**
 * Los límites de concentración de la cartera en construcción — F-020.
 *
 * **No hay mockup para este panel en el design system**: la maqueta de Cordillera no lo dibujó. El
 * estilo se deriva de lo que ya existe — el contenedor de `components/Panel.tsx`, los rótulos en
 * mayúsculas con `letter-spacing`, las barras de `components/DistribucionBarras.tsx` — y el
 * tratamiento de advertencia sale de la sección A1: **el aviso se tiñe, el fondo no**. Un panel de
 * riesgo con el fondo rojo enseña a ignorarlo en tres carteras.
 *
 * ## Qué muestra, y por qué en ese orden
 *
 * 1. **Los topes**, abiertos por eje: soberano, por emisor y por sector. No hay un score de riesgo
 *    compuesto y no lo va a haber — es la regla 7 del dominio: ponderar años contra una calificación
 *    que sólo existe para el 39 % del universo sería un juicio inventado presentado como dato.
 * 2. **La distribución** en tres cortes: por sector, por legislación —el proxy de país en renta
 *    fija— y por naturaleza de tasa. Cada uno con su tramo de "no informado", que nunca se reparte.
 * 3. **Las advertencias**, tal como las redactó el backend. Informan y no bloquean: el asesor puede
 *    dejar la cartera como está.
 *
 * ## Sobre qué peso se mide, dicho en pantalla
 *
 * Las posiciones salen de `useCarteraResuelta` con `pesoReal ?? peso`: el peso real es el que sale
 * del invertido después de redondear a lámina, y es el que el asesor efectivamente va a tener. No
 * siempre existe —hace falta precio y tipo de cambio—, así que la leyenda dice cuántas posiciones
 * se midieron con cada uno. Mostrar un veredicto de riesgo sin decir sobre qué números se calculó
 * sería exactamente lo que la regla 11 prohíbe.
 *
 * La renta variable no entra: `useCarteraResuelta` devuelve renta fija y FCI, y el bloque de
 * acciones y CEDEARs tiene su propio subtotal (F-026). Los FCI llegan igual y el backend los
 * devuelve en `fuera_del_universo`, que es lo correcto: no tienen emisor, ni sector, ni ley.
 */

import { useMemo, useState } from 'react'

import { DistribucionBarras, type TramoDistribucion } from '@/components/DistribucionBarras'
import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { Panel } from '@/components/Panel'
import { fmtPct } from '@/lib/fmt'

import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { useConcentracion } from '../hooks/useConcentracion'
import {
  PERFILES,
  type AlertaConcentracion,
  type Concentracion,
  type EstadoDeTope,
  type NombreDePerfil,
  type TipoDeTope,
  type TramoConcentracion,
} from '../lib/schemaConcentracion'

const TITULO_TOPE: Record<TipoDeTope, string> = {
  soberano: 'Riesgo soberano',
  emisor: 'Por emisor',
  sector: 'Por sector',
}

const AYUDA_TOPE: Record<TipoDeTope, string> = {
  soberano:
    'Todas las emisiones del Tesoro cuentan como un solo crédito, bajo cualquier prefijo (GD, AE, DIC, TZX, TY3).',
  emisor: 'Cada emisor corporativo o provincial, con todas sus emisiones sumadas.',
  sector:
    'Soberano y Subsoberano quedan exentos: ya los acota el tope soberano. Lo que no tiene sector informado no se acota.',
}

const COLOR_SEVERIDAD: Record<AlertaConcentracion['severidad'], string> = {
  error: 'var(--neg)',
  advertencia: 'var(--ac2)',
  info: 'var(--dim)',
}

export function PanelConcentracion() {
  const [perfil, setPerfil] = useState<NombreDePerfil>('moderado')
  const { resueltas } = useCarteraResuelta()

  // `pesoReal ?? peso`: el real cuando se pudo calcular, la ponderación pedida cuando no. La
  // leyenda de abajo declara cuántas cayeron de cada lado — no se elige en silencio.
  const posiciones = useMemo(
    () => resueltas.map((r) => ({ ticker: r.ticker, peso: r.pesoReal ?? r.peso })),
    [resueltas],
  )
  const conPesoReal = resueltas.filter((r) => r.pesoReal !== null).length

  const consulta = useConcentracion(posiciones, perfil)

  return (
    <Panel
      ariaLabel="Límites de concentración"
      rotulo="Concentración"
      titulo="Límites del perfil, en vivo"
      acciones={
        <label
          style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--dim)' }}
        >
          Perfil
          <select
            value={perfil}
            onChange={(evento) => setPerfil(evento.target.value as NombreDePerfil)}
            style={{
              font: 'inherit',
              fontSize: 12,
              color: 'var(--tx)',
              background: 'var(--pan2)',
              border: '1px solid var(--lin)',
              borderRadius: 3,
              padding: '3px 6px',
            }}
          >
            {PERFILES.map((nombre) => (
              <option key={nombre} value={nombre}>
                {nombre}
              </option>
            ))}
          </select>
        </label>
      }
    >
      {posiciones.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--sd)' }}>
          Sin posiciones de renta fija. Los topes se miden cuando haya al menos una.
        </p>
      ) : (
        <>
          <p style={{ margin: '0 0 10px', fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>
            {leyendaDelPeso(conPesoReal, posiciones.length)}
          </p>
          {consulta.isPending && <EstadoCarga que="los límites de concentración" />}
          {consulta.isError && (
            <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />
          )}
          {consulta.data && <Veredicto datos={consulta.data} />}
        </>
      )}
    </Panel>
  )
}

/** Qué peso se midió, dicho antes de mostrar cualquier número. */
function leyendaDelPeso(conPesoReal: number, total: number): string {
  if (conPesoReal === total)
    return `Medido sobre el peso real de las ${total} posiciones (invertido sobre el total invertido), no sobre la ponderación pedida.`
  if (conPesoReal === 0)
    return `Medido sobre la ponderación pedida de las ${total} posiciones: ninguna se pudo resolver a peso real por falta de precio o de tipo de cambio.`
  return `Medido sobre el peso real en ${conPesoReal} de ${total} posiciones; en las otras ${total - conPesoReal}, sobre la ponderación pedida (sin precio o sin tipo de cambio).`
}

function Veredicto({ datos }: { datos: Concentracion }) {
  const porTipo = (tipo: TipoDeTope) => datos.topes.filter((t) => t.tipo === tipo)

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))',
          gap: 14,
        }}
      >
        {(['soberano', 'emisor', 'sector'] as const).map((tipo) => (
          <BloqueDeTopes key={tipo} tipo={tipo} topes={porTipo(tipo)} />
        ))}
      </div>

      <Diversificacion sectores={datos.sectores} />

      <div style={{ borderTop: '1px solid var(--lin)', paddingTop: 12 }}>
        <h3
          style={{
            margin: '0 0 10px',
            font: '600 12px/1.3 inherit',
            color: 'var(--tx)',
          }}
        >
          Distribución de la cartera
        </h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 14,
          }}
        >
          <DistribucionBarras titulo="Sector" tramos={aTramos(datos.distribucion.sector)} />
          <DistribucionBarras titulo="Legislación" tramos={aTramos(datos.distribucion.ley)} />
          <DistribucionBarras
            titulo="Naturaleza de tasa"
            tramos={aTramos(datos.distribucion.naturaleza)}
          />
        </div>
      </div>

      <PesoMedido peso={datos.peso} fuera={datos.fuera_del_universo} />
      <Advertencias alertas={datos.alertas} />
    </div>
  )
}

/** El contrato del backend al del componente compartido: mismo dato, otro nombre de campo. */
function aTramos(tramos: TramoConcentracion[]): TramoDistribucion[] {
  return tramos.map((t) => ({ nombre: t.nombre, peso: t.peso, sinDato: t.sin_dato }))
}

function BloqueDeTopes({ tipo, topes }: { tipo: TipoDeTope; topes: EstadoDeTope[] }) {
  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <h4
        style={{
          margin: 0,
          fontSize: 10,
          color: 'var(--dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
        title={AYUDA_TOPE[tipo]}
      >
        {TITULO_TOPE[tipo]}
      </h4>
      {topes.length === 0 ? (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--sd)' }}>
          {tipo === 'sector'
            ? 'Ningún sector computable en la cartera.'
            : 'Sin posiciones de este tipo.'}
        </p>
      ) : (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
          {topes.map((tope) => (
            <FilaDeTope key={`${tope.tipo}:${tope.clave}`} tope={tope} />
          ))}
        </ul>
      )}
    </section>
  )
}

function FilaDeTope({ tope }: { tope: EstadoDeTope }) {
  // La escala llega hasta el mayor de los dos con un margen, para que el tope se vea siempre y un
  // exceso del doble no se salga de la barra ni se recorte a "lleno".
  const escala = Math.max(tope.peso, tope.tope) * 1.08
  const color = tope.excedido ? 'var(--neg)' : 'var(--ac)'

  return (
    <li style={{ display: 'grid', gap: 2 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11.5 }}>
        <span
          style={{
            color: tope.excedido ? 'var(--neg)' : 'var(--tx)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={tope.nombre}
        >
          {tope.nombre}
        </span>
        <span className="mono" style={{ color, whiteSpace: 'nowrap' }}>
          {fmtPct(tope.peso, 1)} / {fmtPct(tope.tope, 0)}
        </span>
      </div>
      <div
        aria-hidden
        style={{ position: 'relative', height: 8, background: 'var(--pan2)', borderRadius: 2 }}
      >
        <div
          style={{
            width: `${Math.min(100, (tope.peso / escala) * 100)}%`,
            height: '100%',
            background: color,
            borderRadius: 2,
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: -1,
            bottom: -1,
            left: `${(tope.tope / escala) * 100}%`,
            width: 1,
            background: 'var(--dim)',
          }}
        />
      </div>
      {tope.excedido && (
        <span className="mono" style={{ fontSize: 10, color: 'var(--neg)' }}>
          +{fmtPct(tope.exceso, 1)} sobre el tope
        </span>
      )}
    </li>
  )
}

function Diversificacion({ sectores }: { sectores: Concentracion['sectores'] }) {
  const falta = !sectores.suficiente
  return (
    <p
      style={{
        margin: 0,
        fontSize: 11.5,
        color: falta ? 'var(--ac2)' : 'var(--dim)',
        textWrap: 'pretty',
      }}
    >
      {sectores.cantidad} de {sectores.minimo} sectores mínimos del perfil
      {sectores.presentes.length > 0 && <> · {sectores.presentes.join(', ')}</>}
      {sectores.peso_sin_sector > 0 && (
        <>
          {' · '}
          {fmtPct(sectores.peso_sin_sector, 1)} sin sector informado, que no cuenta para el mínimo
        </>
      )}
    </p>
  )
}

function PesoMedido({
  peso,
  fuera,
}: {
  peso: Concentracion['peso']
  fuera: string[]
}) {
  // Los pesos no se normalizan a 100 (regla de F-018): que declarado y medido se muestren siempre,
  // aunque coincidan, es lo que evita leer "los topes están bien" sobre media cartera.
  return (
    <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--sd)' }}>
      Σ declarada {fmtPct(peso.declarado, 1)} · medida {fmtPct(peso.medido, 1)}
      {fuera.length > 0 && <> · {fuera.length} posición(es) fuera del universo de renta fija</>}
    </p>
  )
}

function Advertencias({ alertas }: { alertas: AlertaConcentracion[] }) {
  if (alertas.length === 0) {
    return (
      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
        Sin advertencias: la cartera está dentro de todos los topes del perfil.
      </p>
    )
  }

  return (
    <div role="list" aria-label="Advertencias de concentración" style={{ display: 'grid', gap: 6 }}>
      {alertas.map((alerta, indice) => (
        <div
          role="listitem"
          // El código se repite —hay una alerta por emisor excedido— así que no alcanza como clave.
          key={`${alerta.codigo}:${indice}`}
          style={{
            borderLeft: `2px solid ${COLOR_SEVERIDAD[alerta.severidad]}`,
            background: 'var(--pan2)',
            borderRadius: '0 3px 3px 0',
            padding: '7px 10px',
          }}
        >
          <p style={{ margin: 0, fontSize: 12, color: 'var(--tx)', textWrap: 'pretty' }}>
            {alerta.mensaje}
          </p>
          <p className="mono" style={{ margin: '4px 0 0', fontSize: 10, color: 'var(--sd)' }}>
            {alerta.codigo} · informa, no bloquea
          </p>
        </div>
      ))}
    </div>
  )
}
