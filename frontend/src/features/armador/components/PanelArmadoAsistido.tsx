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
 *
 * ## Los topes de renta variable (F-078)
 *
 * El bloque "Topes de renta variable" es la parte de esta ficha que **sí cambia lo que el motor
 * elige**, no sólo lo que filtra: cinco máximos por eje —rubro, país, región, moneda, mercado—
 * sobre el bloque de renta variable. Vienen precargados con los del perfil y **a la vista**, que es
 * la promesa entera de la feature: un tope que se aplica sin mostrarse obliga al asesor a adivinar
 * con qué se armó la cartera que está por defender ante un cliente.
 *
 * Tres decisiones que conviene no revisitar:
 *
 * - **Inputs numéricos, nunca sliders.** El design system no tiene ninguno (cero usos de
 *   `type="range"` en todo el repo) y un rango se expresa con `min`/`max` sobre un `number`. Un
 *   tope de diversificación es un número que se defiende, no un gesto de arrastre.
 * - **Campo vacío = eje apagado**, y viaja como `null`. Un `0` significaría "ninguna categoría
 *   puede pesar nada", que es incumplible por construcción, y el backend además lo rechaza
 *   (`gt=0`).
 * - **Se mandan siempre los cinco**, porque el backend no hace merge parcial contra los defaults
 *   del perfil: `topes_rv` presente significa "exactamente esto". Ver `TOPES_RV_PERFIL`.
 *
 * Cada campo declara además **cuántos papeles del universo tienen el dato de ese eje**. Es la única
 * defensa contra el peor estado de la feature: un tope configurado, aplicado, y que en silencio no
 * mide nada porque a la fuente le falta la columna — hoy, literalmente el caso de `país` hasta que
 * corra la siembra del curado.
 */

import { useMemo, useState, type ReactNode } from 'react'

import { CampoSelect } from '@/components/CampoSelect'
import { useRentaVariable } from '@/lib/rentaVariable'

import { AlertasCalendario } from './AlertasCalendario'
import { useArmadoAsistido } from '../hooks/useArmadoAsistido'
import { useEspeciesUniverso } from '../hooks/useEspeciesUniverso'
import { CALIFICACION_NO_INFORMADA } from '../lib/filtros'
import {
  CAMPO_TOPE_RV,
  EJES_TOPE_RV,
  filtroRvABackend,
  PCT_RV_PERFIL,
  TOPES_RV_PERFIL,
  type EjeTopeRv,
  type ParametrosArmadoAsistido,
  type TopesRv,
} from '../lib/schemaArmado'
import { filtraRentaVariable, PRESETS_TEMATICOS, presetPorId } from '../lib/tematicas'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

/** De la que paga más seguido a la que paga menos, con lo no medible al final. Es el orden en que
 *  el asesor los piensa —"quiero cobrar todos los meses"— y sale de la escala del backend
 *  (`ESCALA_FRECUENCIA` en `app/rotaciones/frecuencia.py`), no de una opinión. */
const ORDEN_PERIODICIDAD = [
  'mensual',
  'bimestral',
  'trimestral',
  'semestral',
  'anual',
  'al vencimiento',
  'irregular',
] as const

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
  const { montoTotal, objetivoRv, filtros } = useArmador()
  const { fijarMontoTotal, fijarObjetivoRv, fijarFiltros } = useArmadorAcciones()

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
    setTopes(topesComoTexto(TOPES_RV_PERFIL[nuevo]))
  }

  // Los topes de renta variable se guardan como **texto** y no como números — F-078. El campo
  // vacío es un estado del dominio, no un 0: significa "no acotes por este eje", y un `number`
  // obliga a elegir un centinela para decirlo (`0`, `NaN`, `-1`) que después hay que recordar en
  // cada lectura. El texto vacío ya es esa distinción, y es además lo que el input devuelve.
  //
  // Arrancan precargados con los defaults del perfil (`TOPES_RV_PERFIL`, espejo de
  // `TOPES_RV_DEFAULT` del backend) y **a la vista**: la promesa de la feature es que el asesor
  // sepa con qué topes se armó la cartera, no que los adivine. Cambiar de perfil los pisa, por la
  // misma razón que pisa el % de renta variable.
  const [topes, setTopes] = useState<Record<EjeTopeRv, string>>(() =>
    topesComoTexto(TOPES_RV_PERFIL['moderado']),
  )

  function fijarTope(eje: EjeTopeRv, valor: string) {
    // Vacío se deja pasar tal cual (apaga el eje); con número se acota a 1..100 acá mismo, que es
    // el rango que el backend valida (`gt=0, le=100`): mandar un 150 para que vuelva un 422 sería
    // hacerle dar la vuelta entera a un error que se ve en el input.
    const limpio = valor.trim() === '' ? '' : String(Math.min(100, Math.max(1, Number(valor) || 1)))
    setTopes((previos) => ({ ...previos, [eje]: limpio }))
  }

  const mutacion = useArmadoAsistido()

  // Misma consulta que la grilla: React Query la comparte por clave, así que esto no agrega un
  // pedido. Orden alfabético como orden de presentación, **nunca** como escala de riesgo — la
  // calificación es texto libre de calificadoras distintas y no hay equivalencia entre sus escalas
  // (mismo criterio que `FiltrosGrilla` y que el docstring de `filtros.ts`).
  const consultaUniverso = useEspeciesUniverso()
  const calificacionesDisponibles = useMemo(() => {
    const especies = consultaUniverso.data ?? []
    const valores = [
      ...new Set(especies.map((e) => e.calificacion).filter((c): c is string => c !== null)),
    ].sort()
    const hayNoInformada = especies.some((e) => e.calificacion === null)
    return { valores, hayNoInformada }
  }, [consultaUniverso.data])

  // Las periodicidades que el universo tiene hoy, ordenadas de la que paga más seguido a la que
  // paga menos: acá el orden **sí** es del dominio y no de presentación —mensual cobra antes que
  // semestral, y eso es un hecho del cronograma, no un juicio como sí lo sería ordenar
  // calificaciones—. Una frecuencia que no aparece en el universo no se ofrece: un botón que
  // siempre devuelve cero no es un filtro.
  const periodicidadesDisponibles = useMemo(() => {
    const presentes = new Set(
      (consultaUniverso.data ?? [])
        .map((e) => e.periodicidad)
        .filter((p): p is string => p !== null),
    )
    return ORDEN_PERIODICIDAD.filter((p) => presentes.has(p))
  }, [consultaUniverso.data])

  // Cuántos CEDEARs declaran el dato de cada eje. Es la misma consulta que usa el bloque de renta
  // variable de más abajo —React Query la comparte por clave, así que no agrega un pedido— y sirve
  // para una sola cosa: **decir en el campo mismo cuando un tope no va a acotar nada**. Hoy `pais`
  // está en `null` para todo el universo hasta que corra la siembra del curado, y un tope que el
  // asesor configura y que en silencio no mide nada es peor que no tenerlo (regla 1: el faltante
  // se declara).
  const cedears = useRentaVariable('cedear')
  const coberturaPorEje = useMemo(() => {
    const especies = cedears.data ?? []
    const declaran = (tiene: (e: (typeof especies)[number]) => boolean) => especies.filter(tiene).length
    return {
      total: especies.length,
      // Desde F-079 el tope "rubro" mide `sector_codigo` y no `sic_oficina` (ver el docstring de
      // `TopesRv.max_pct_rubro` en `schemaArmado.ts`): la cobertura sube de 866 a 870 especies
      // (medido 28/08/2026) porque `sector_codigo` es aritmética sobre `sic_codigo` y no depende
      // de las 3 oficinas ambiguas que quedaban sin `sic_oficina` resuelto.
      rubro: declaran((e) => e.sector_codigo !== null),
      pais: declaran((e) => e.pais !== null),
      // El eje geográfico de un ETF es el que declara su nombre; el de una empresa, el país
      // curado. Cualquiera de los dos alcanza para que la posición compute contra el tope.
      region: declaran((e) => e.region !== null || e.region_etf !== null),
      moneda: declaran((e) => e.moneda_cotizacion !== null),
      mercado: declaran((e) => e.mercado_origen !== null),
    } satisfies Record<EjeTopeRv | 'total', number>
  }, [cedears.data])

  function alternarPeriodicidad(valor: string) {
    const activa = filtros.periodicidades.includes(valor)
    fijarFiltros({
      ...filtros,
      periodicidades: activa
        ? filtros.periodicidades.filter((p) => p !== valor)
        : [...filtros.periodicidades, valor],
    })
  }

  function alternarCalificacion(valor: string) {
    const activa = filtros.calificaciones.includes(valor)
    fijarFiltros({
      ...filtros,
      calificaciones: activa
        ? filtros.calificaciones.filter((c) => c !== valor)
        : [...filtros.calificaciones, valor],
    })
  }

  const montoValido = Number.isFinite(montoTotal) && montoTotal > 0

  const presetTematico = presetPorId(tematica === '' ? null : tematica)

  function armar() {
    if (!montoValido) return
    mutacion.mutate({
      monto: montoTotal,
      moneda,
      cobertura,
      perfil,
      horizonte,
      pct_rv: pctRv,
      // Las dos formas de acotar la renta variable, y **nunca las dos a la vez**: mandar
      // `rubro_rv` junto con un `filtro_rv.rubros` distinto es 422 del lado del backend, a
      // propósito (`normalizar_filtro_rv`). Una temática de un solo rubro sigue viajando por el
      // campo viejo, que el backend pliega adentro del filtro; una temática multidimensional
      // —metales preciosos— viaja como filtro y deja `rubro_rv` en `null`.
      rubro_rv: presetTematico?.filtroRv === undefined ? (presetTematico?.rubroRv ?? null) : null,
      ...(presetTematico?.filtroRv === undefined
        ? {}
        : {
            filtro_rv: filtroRvABackend(
              presetTematico.filtroRv,
              presetTematico.modoFiltroRv ?? 'interseccion',
            ),
          }),
      // Los cinco ejes, siempre: el backend no hace merge parcial contra los defaults del perfil
      // —`topes_rv` presente significa "exactamente esto"—, así que omitir un eje lo apagaría en
      // vez de dejarle su default. El objeto que se manda es literalmente lo que muestra el panel.
      topes_rv: topesDesdeTexto(topes),
      // El piso de la grilla es el piso del armado: se manda el mismo número, y sin piso no se
      // manda el campo (el backend ya trata la ausencia como 0).
      ...(filtros.tirMin === '' ? {} : { min_rend: Number(filtros.tirMin) }),
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

        <CampoSelect
          etiqueta="Moneda de referencia"
          valor={moneda}
          onChange={(valor) => setMoneda(valor as ParametrosArmadoAsistido['moneda'])}
          opciones={MONEDAS.map((m) => ({ valor: m.valor, texto: m.etiqueta }))}
        />

        <CampoSelect
          etiqueta="Objetivo de cobertura"
          valor={cobertura}
          onChange={(valor) => setCobertura(valor as ParametrosArmadoAsistido['cobertura'])}
          opciones={COBERTURAS.map((c) => ({ valor: c.valor, texto: c.etiqueta }))}
        />

        <CampoSelect
          etiqueta="Perfil"
          valor={perfil}
          onChange={(valor) => setPerfil(valor as ParametrosArmadoAsistido['perfil'])}
          opciones={PERFILES.map((p) => ({ valor: p.valor, texto: p.etiqueta }))}
        />

        <CampoSelect
          etiqueta="Horizonte"
          valor={horizonte}
          onChange={(valor) => setHorizonte(valor as ParametrosArmadoAsistido['horizonte'])}
          opciones={HORIZONTES.map((h) => ({ valor: h.valor, texto: h.etiqueta }))}
        />

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

        {/* El complemento del anterior, en modo lectura: son el mismo número visto de los dos
            lados, y tener los dos editables obligaría a decidir cuál gana cuando no suman 100. */}
        <Campo etiqueta="% renta fija">
          <span
            className="mono"
            style={{ ...estiloInput, minWidth: 76, display: 'inline-block', color: 'var(--dim)' }}
          >
            {100 - pctRv}
          </span>
        </Campo>

        {/* Es el mismo `filtros.tirMin` que la barra de la grilla, escrito desde acá: el armado
            automático y la oferta que el asesor ve al lado no pueden contradecirse. Rotulado
            distinto a propósito ("rendimiento mínimo" acá, "TIR mín." en la barra) porque son dos
            accesos al mismo número en la misma pantalla, y dos etiquetas idénticas se leerían como
            dos filtros que se pisan. */}
        <Campo etiqueta="Rendimiento mínimo RF (%)">
          <input
            type="number"
            inputMode="decimal"
            step={0.5}
            value={filtros.tirMin}
            onChange={(e) => fijarFiltros({ ...filtros, tirMin: e.target.value })}
            placeholder="sin piso"
            style={{ ...estiloInput, minWidth: 76 }}
          />
        </Campo>

        <Campo etiqueta="Plazo máx. RF (años)">
          <input
            type="number"
            inputMode="decimal"
            min={0}
            step={1}
            value={filtros.vencimientoMax}
            onChange={(e) => fijarFiltros({ ...filtros, vencimientoMax: e.target.value })}
            placeholder="sin tope"
            style={{ ...estiloInput, minWidth: 76 }}
          />
        </Campo>

        <CampoSelect
          etiqueta="Temática (CEDEARs)"
          valor={tematica}
          onChange={setTematica}
          opciones={[
            { valor: '', texto: 'sin temática' },
            ...PRESETS_TEMATICOS.filter(filtraRentaVariable).map((preset) => ({
              valor: preset.id,
              texto: preset.etiqueta,
            })),
          ]}
        />

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
            ? `Los bonos se arman sobre el ${100 - pctRv}% restante; los CEDEARs se eligen por liquidez, respetando los topes de abajo.`
            : 'Sin renta variable: la cartera se arma entera con renta fija.'}
        </p>

        {/* Qué precargó la temática, a la vista y no sólo como tooltip del select. Las temáticas
            multidimensionales —metales preciosos— no se pueden leer del nombre: hay que decir qué
            entra y qué queda afuera, que es justamente para lo que existe la nota del preset. */}
        {presetTematico !== null && (
          <p
            style={{ flexBasis: '100%', margin: 0, fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}
          >
            {presetTematico.etiqueta}: {presetTematico.nota}
          </p>
        )}
      </div>

      {/* Los cinco topes de diversificación del bloque de renta variable — F-078.

          **Inputs numéricos y no sliders**: el design system no tiene ninguno (cero usos de
          `type="range"` en todo el repo) y un rango con `min`/`max` sobre un `<input type="number">`
          dice lo mismo, se lee a simple vista y se puede tipear. Un tope de diversificación es un
          número que el asesor defiende ante el cliente, no un gesto de arrastre.

          El porcentaje es **sobre el bloque de renta variable**, no sobre la cartera: es la unidad
          en la que el armador reparte los cupos. */}
      <fieldset
        style={{
          border: '1px solid var(--lin)',
          borderRadius: 4,
          padding: '8px 12px 10px',
          margin: 0,
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          alignItems: 'flex-start',
        }}
      >
        <legend
          style={{
            fontSize: 9.5,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--dim)',
            padding: '0 4px',
          }}
        >
          Topes de renta variable
        </legend>

        {EJES_TOPE_RV.map((eje) => (
          <CampoTope
            key={eje}
            eje={eje}
            valor={topes[eje]}
            onCambio={(valor) => fijarTope(eje, valor)}
            declaran={coberturaPorEje[eje]}
            total={coberturaPorEje.total}
          />
        ))}

        <p style={{ flexBasis: '100%', margin: 0, fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>
          Máximo que puede pesar una misma categoría dentro del bloque de renta variable. Vienen
          precargados con los del perfil <strong>{perfil}</strong>; cambiar de perfil los vuelve a
          poner. <strong>Un campo vacío apaga ese tope</strong> y el eje deja de acotar. Lo que se
          incumple se declara con una alerta en el bloque de renta variable — no bloquea el armado.
        </p>

        {/* La moneda viene apagada de fábrica y eso necesita explicación: un campo vacío entre
            cuatro llenos se lee como un olvido. */}
        <p style={{ flexBasis: '100%', margin: 0, fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>
          La moneda arranca sin tope en los tres perfiles: 276 de los 286 CEDEARs que cotizan en
          dólares son la hermana MEP o cable de un papel que ya cotiza en pesos (medido el
          28/08/2026), así que acotarla forzaría a comprar el mismo papel dos veces por dos
          ventanillas. Es forma de liquidación, no exposición. Se puede encender a mano.
        </p>
      </fieldset>

      {/* Cada cuánto cobra el cliente. Sale del cronograma contractual de cada emisión, no de
          contar pagos en la ventana de doce meses: son dos preguntas distintas y el filtro de
          `pagos` de la barra de la grilla sigue contestando la segunda. */}
      {periodicidadesDisponibles.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 6 }}>
          <span
            className="rotulo"
            style={{ fontSize: 9.5, letterSpacing: '0.08em', textTransform: 'uppercase', marginRight: 2 }}
          >
            Paga cupón
          </span>
          {periodicidadesDisponibles.map((valor) => (
            <BotonDeFiltro
              key={valor}
              etiqueta={valor}
              activa={filtros.periodicidades.includes(valor)}
              onClick={() => alternarPeriodicidad(valor)}
            />
          ))}
        </div>
      )}

      {/* La calificación se filtra por coincidencia exacta y nunca se ordena por riesgo: son
          escalas de calificadoras distintas, sin equivalencia entre sí (regla 7 — el riesgo es un
          vector, no un número). Sin ninguna marcada, no filtra. */}
      {calificacionesDisponibles.valores.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: 6 }}>
          <span
            className="rotulo"
            style={{ fontSize: 9.5, letterSpacing: '0.08em', textTransform: 'uppercase', marginRight: 2 }}
          >
            Calificación RF
          </span>
          {calificacionesDisponibles.valores.map((valor) => (
            <BotonDeFiltro
              key={valor}
              etiqueta={valor}
              activa={filtros.calificaciones.includes(valor)}
              onClick={() => alternarCalificacion(valor)}
            />
          ))}
          {calificacionesDisponibles.hayNoInformada && (
            <BotonDeFiltro
              etiqueta="sin calificar"
              activa={filtros.calificaciones.includes(CALIFICACION_NO_INFORMADA)}
              onClick={() => alternarCalificacion(CALIFICACION_NO_INFORMADA)}
            />
          )}
        </div>
      )}

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
            {mutacion.data.pct_rv_aplicado}%: no hubo CEDEARs que cumplieran. El resto quedó en
            renta fija — mirá las alertas de abajo.
          </p>
        )}

      {mutacion.isSuccess && <AlertasCalendario alertas={mutacion.data.alertas} />}
    </div>
  )
}

/** Cómo se lee cada eje en pantalla, con la fuente entre paréntesis donde el nombre solo no
 *  alcanza. `Sector` repite deliberadamente la etiqueta del picker del bloque de renta variable:
 *  es el mismo campo (`sector_codigo`) desde F-079, y llamarlo distinto sugeriría dos taxonomías.
 *  El nombre interno del eje sigue siendo `rubro` (`EJES_TOPE_RV`, `max_pct_rubro`): es el
 *  contrato con el backend, no cambia con la migración — sólo el rótulo que ve el asesor. */
const ETIQUETA_EJE_TOPE: Record<EjeTopeRv, string> = {
  rubro: 'Máx. % por sector (SIC)',
  pais: 'Máx. % por país',
  region: 'Máx. % por región',
  moneda: 'Máx. % por moneda',
  mercado: 'Máx. % por mercado',
}

/** Los defaults del perfil pasados a lo que muestran los inputs: número a texto, `null` a vacío. */
function topesComoTexto(topes: TopesRv): Record<EjeTopeRv, string> {
  const salida = {} as Record<EjeTopeRv, string>
  for (const eje of EJES_TOPE_RV) {
    const valor = topes[CAMPO_TOPE_RV[eje]]
    salida[eje] = valor === null ? '' : String(valor)
  }
  return salida
}

/** El camino de vuelta, para el request: vacío a `null` (eje apagado), texto a número. Devuelve
 *  siempre los cinco campos — ver el comentario de `armar()` sobre por qué el backend no mergea. */
function topesDesdeTexto(topes: Record<EjeTopeRv, string>): TopesRv {
  const salida = {} as TopesRv
  for (const eje of EJES_TOPE_RV) {
    const texto = topes[eje].trim()
    salida[CAMPO_TOPE_RV[eje]] = texto === '' ? null : Number(texto)
  }
  return salida
}

/**
 * Un tope, con la cobertura del dato debajo.
 *
 * La línea de cobertura es lo que evita el peor estado posible de esta feature: un tope configurado,
 * aplicado y que en silencio no mide nada porque al universo le falta el dato del eje. Hoy es
 * literalmente el caso de `país`, que está en `null` para todos los papeles hasta que corra la
 * siembra del curado. Decirlo en el campo mismo —y no sólo en la alerta que vuelve después del
 * armado— es la diferencia entre un faltante declarado y una pantalla que miente por omisión.
 */
function CampoTope({
  eje,
  valor,
  onCambio,
  declaran,
  total,
}: {
  eje: EjeTopeRv
  valor: string
  onCambio: (valor: string) => void
  /** Cuántos CEDEARs del universo declaran el dato de este eje. */
  declaran: number
  /** Cuántos CEDEARs tiene el universo. `0` = todavía no se trajo. */
  total: number
}) {
  const sinDatoEnElEje = total > 0 && declaran === 0
  const parcial = total > 0 && declaran > 0 && declaran < total
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxWidth: 190 }}>
      <Campo etiqueta={ETIQUETA_EJE_TOPE[eje]}>
        <input
          type="number"
          inputMode="numeric"
          min={1}
          max={100}
          step={5}
          value={valor}
          onChange={(e) => onCambio(e.target.value)}
          placeholder="sin tope"
          style={{ ...estiloInput, minWidth: 76 }}
        />
      </Campo>
      {sinDatoEnElEje && (
        <span style={{ fontSize: 10, color: 'var(--ac2)', textWrap: 'pretty' }}>
          ninguno de los {total} papeles declara este dato todavía: el tope no va a acotar nada, y
          el armado lo dice con la alerta <span className="mono">rv_tope_sin_dato_en_eje</span>
        </span>
      )}
      {parcial && (
        <span style={{ fontSize: 10, color: 'var(--dim)' }}>
          lo declaran {declaran} de {total} papeles; el resto no computa contra el tope
        </span>
      )}
    </div>
  )
}

/** Un valor de un filtro multiselect como toggle (calificación, periodicidad). `aria-pressed` y no
 *  un checkbox porque el conjunto filtra la vista, no es un formulario que se envía. */
function BotonDeFiltro({
  etiqueta,
  activa,
  onClick,
}: {
  etiqueta: string
  activa: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={activa}
      style={{
        font: 'inherit',
        fontSize: 11,
        padding: '3px 8px',
        borderRadius: 3,
        border: `1px solid ${activa ? 'var(--ac)' : 'var(--lin)'}`,
        background: activa ? 'var(--sel)' : 'transparent',
        color: activa ? 'var(--tx)' : 'var(--dim)',
        cursor: 'pointer',
      }}
    >
      {etiqueta}
    </button>
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
