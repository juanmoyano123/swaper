/**
 * El armado asistido: precarga una cartera de arranque a partir del mandato del cliente — F-019.
 *
 * Reemplaza el stub de la base común de la Tanda 10. Formulario chico con los cinco parámetros
 * del mandato (monto, moneda, objetivo de cobertura, perfil, horizonte) — es lo único que
 * `ParametrosArmado` del backend pide como input de esta feature; la sección completa de A1
 * ("Mandato del cliente" con chips de restricciones y "Filtrar universo por mandato") no es esta
 * ficha, y no se construye acá.
 *
 * El botón dispara `useArmadoAsistido`, que en éxito reemplaza la cartera del store entero — es un
 * punto de partida, no un agregado, así que no pide confirmación aunque ya hubiera posiciones
 * cargadas: el asesor sigue pudiendo editar cada una después en `CarteraEditable`.
 *
 * **El monto sale del store, no de un estado local (Tanda 13).** Antes había dos campos "monto"
 * sin relación: el de esta ficha, que se mandaba al backend y se descartaba, y el de la cartera,
 * que era el único que los resolvers usaban para calcular nominales. Cargar el capital acá no
 * hacía nada visible más abajo, y cargarlo en los dos lugares se leía como el doble de plata.
 */

import { useState, type ReactNode } from 'react'

import { AlertasCalendario } from './AlertasCalendario'
import { useArmadoAsistido } from '../hooks/useArmadoAsistido'
import { PCT_RV_PERFIL, type ParametrosArmadoAsistido } from '../lib/schemaArmado'
import { PRESETS_TEMATICOS, presetPorId } from '../lib/tematicas'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

const MONEDAS: Array<{ valor: ParametrosArmadoAsistido['moneda']; etiqueta: string }> = [
  { valor: 'todas', etiqueta: 'cualquiera' },
  { valor: 'usd', etiqueta: 'dólares' },
  { valor: 'ars', etiqueta: 'pesos' },
]

const COBERTURAS: Array<{ valor: ParametrosArmadoAsistido['cobertura']; etiqueta: string }> = [
  { valor: 'mixta', etiqueta: 'mixta (balanceada)' },
  { valor: 'devaluacion', etiqueta: 'devaluación' },
  { valor: 'inflacion', etiqueta: 'inflación' },
  { valor: 'tasa-pesos', etiqueta: 'tasa en pesos' },
]

const PERFILES: Array<{ valor: ParametrosArmadoAsistido['perfil']; etiqueta: string }> = [
  { valor: 'conservador', etiqueta: 'conservador' },
  { valor: 'moderado', etiqueta: 'moderado' },
  { valor: 'agresivo', etiqueta: 'agresivo' },
]

const HORIZONTES: Array<{ valor: ParametrosArmadoAsistido['horizonte']; etiqueta: string }> = [
  { valor: 'corto', etiqueta: 'corto' },
  { valor: 'medio', etiqueta: 'medio' },
  { valor: 'largo', etiqueta: 'largo' },
]

export function PanelArmadoAsistido() {
  // El monto vive en el store y no acá: es el mismo capital que reparte `CarteraEditable`, y
  // tenerlo duplicado hacía que cargar 10.000 en el asistido y 10.000 en la cartera se leyera como
  // 20.000 sin que nada lo dijera. Los dos campos son ahora dos vistas del mismo número.
  const { montoTotal, objetivoRv } = useArmador()
  const { fijarMontoTotal, fijarObjetivoRv } = useArmadorAcciones()

  const [moneda, setMoneda] = useState<ParametrosArmadoAsistido['moneda']>('todas')
  const [cobertura, setCobertura] = useState<ParametrosArmadoAsistido['cobertura']>('mixta')
  const [perfil, setPerfilCrudo] = useState<ParametrosArmadoAsistido['perfil']>('moderado')
  const [horizonte, setHorizonte] = useState<ParametrosArmadoAsistido['horizonte']>('medio')
  const [tematica, setTematica] = useState<string>('')

  // El % de renta variable dejó de ser estado local y pasó al store, por la misma razón que el
  // monto: es el mandato del cliente y la cartera se sigue comparando contra él mucho después de
  // que este panel se pliegue. Sin objetivo declarado se muestra el default del perfil, que es lo
  // que el backend va a aplicar si no se manda nada.
  const pctRv = objetivoRv ?? PCT_RV_PERFIL[perfil]
  const setPctRv = fijarObjetivoRv

  // Cambiar de perfil pisa el % de renta variable con el default del perfil nuevo, aunque el asesor
  // lo hubiera editado. Es lo menos sorpresivo: elegir "conservador" y que quede un 60% de acciones
  // de la vez anterior sería peor que perder el valor escrito, que se vuelve a tipear en un segundo.
  function setPerfil(nuevo: ParametrosArmadoAsistido['perfil']) {
    setPerfilCrudo(nuevo)
    fijarObjetivoRv(PCT_RV_PERFIL[nuevo])
  }

  const mutacion = useArmadoAsistido()

  const montoValido = Number.isFinite(montoTotal) && montoTotal > 0

  function armar() {
    if (!montoValido) return
    mutacion.mutate({
      monto: montoTotal,
      moneda,
      cobertura,
      perfil,
      horizonte,
      pct_rv: pctRv,
      sector_rv: presetPorId(tematica === '' ? null : tematica)?.sectorRv ?? null,
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={estiloFila}>
        <Campo etiqueta="Monto a invertir (USD)">
          <input
            type="number"
            inputMode="decimal"
            min={0}
            value={montoTotal === 0 ? '' : montoTotal}
            onChange={(e) => fijarMontoTotal(Number(e.target.value) || 0)}
            style={estiloInput}
          />
        </Campo>

        <Campo etiqueta="Moneda de referencia">
          <select
            value={moneda}
            onChange={(e) => setMoneda(e.target.value as ParametrosArmadoAsistido['moneda'])}
            style={estiloInput}
          >
            {MONEDAS.map((m) => (
              <option key={m.valor} value={m.valor}>
                {m.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="Objetivo de cobertura">
          <select
            value={cobertura}
            onChange={(e) => setCobertura(e.target.value as ParametrosArmadoAsistido['cobertura'])}
            style={estiloInput}
          >
            {COBERTURAS.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="Perfil">
          <select
            value={perfil}
            onChange={(e) => setPerfil(e.target.value as ParametrosArmadoAsistido['perfil'])}
            style={estiloInput}
          >
            {PERFILES.map((p) => (
              <option key={p.valor} value={p.valor}>
                {p.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="Horizonte">
          <select
            value={horizonte}
            onChange={(e) => setHorizonte(e.target.value as ParametrosArmadoAsistido['horizonte'])}
            style={estiloInput}
          >
            {HORIZONTES.map((h) => (
              <option key={h.valor} value={h.valor}>
                {h.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="% renta variable">
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={100}
            step={5}
            value={pctRv}
            onChange={(e) => setPctRv(Math.min(100, Math.max(0, Number(e.target.value) || 0)))}
            style={{ ...estiloInput, minWidth: 76 }}
          />
        </Campo>

        <Campo etiqueta="Temática (acciones)">
          <select
            value={tematica}
            onChange={(e) => setTematica(e.target.value)}
            style={estiloInput}
          >
            <option value="">sin temática</option>
            {PRESETS_TEMATICOS.filter((preset) => preset.sectorRv !== null).map((preset) => (
              <option key={preset.id} value={preset.id}>
                {preset.etiqueta}
              </option>
            ))}
          </select>
        </Campo>

        <button
          type="button"
          onClick={armar}
          disabled={!montoValido || mutacion.isPending}
          style={estiloBoton}
        >
          {mutacion.isPending ? 'armando…' : 'Armar cartera asistida'}
        </button>

        <p style={{ flexBasis: '100%', margin: 0, fontSize: 11, color: 'var(--dim)' }}>
          {pctRv > 0
            ? `Los bonos se arman sobre el ${100 - pctRv}% restante; las acciones se eligen por liquidez, diversificando sectores.`
            : 'Sin renta variable: la cartera se arma entera con renta fija.'}
        </p>
      </div>

      {mutacion.isError && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--neg)' }}>
          {mutacion.error.message}
        </p>
      )}

      {mutacion.isSuccess && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
          {mutacion.data.posiciones.length} posiciones precargadas · {mutacion.data.origen_mix} ·
          perfil {mutacion.data.perfil} · {mutacion.data.sectores.presentes} de{' '}
          {mutacion.data.sectores.minimo} sectores mínimos · renta variable{' '}
          {mutacion.data.pct_rv_aplicado}%
        </p>
      )}

      {/* Lo pedido y lo aplicado pueden no coincidir: si no hubo acciones que cumplieran (hoy pasa
          con cualquier temática, porque el job de perfiles de empresa nunca corrió), la renta fija
          queda ocupando la cartera entera sin reescalarse. Sin este aviso, el pedido se vería
          ignorado en silencio y sólo lo explicaría una alerta más abajo. */}
      {mutacion.isSuccess &&
        mutacion.data.pct_rv_aplicado < (mutacion.variables?.pct_rv ?? 0) && (
          <p style={{ margin: 0, fontSize: 11.5, color: 'var(--ac2)' }}>
            Pediste {mutacion.variables?.pct_rv}% en renta variable y entró{' '}
            {mutacion.data.pct_rv_aplicado}%: no hubo acciones que cumplieran. El resto quedó en
            renta fija — mirá las alertas de abajo.
          </p>
        )}

      {mutacion.isSuccess && <AlertasCalendario alertas={mutacion.data.alertas} />}
    </div>
  )
}

function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <label
      style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: 'var(--dim)' }}
    >
      {etiqueta}
      {children}
    </label>
  )
}

const estiloFila = {
  display: 'flex',
  gap: 12,
  alignItems: 'flex-end',
  flexWrap: 'wrap',
} as const

const estiloInput = {
  minWidth: 108,
  font: 'inherit',
  fontSize: 12.5,
  padding: '5px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const

const estiloBoton = {
  font: 'inherit',
  fontSize: 12.5,
  fontWeight: 600,
  padding: '7px 14px',
  borderRadius: 3,
  border: '1px solid var(--ac)',
  background: 'var(--ac)',
  color: 'var(--bg)',
  cursor: 'pointer',
} as const
