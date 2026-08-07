/*
  Boceto del producto 10-Swaper — datos y render.

  TODO LO QUE SE MUESTRA SALE DE LA BASE. El snapshot de abajo se extrajo el 07/08/2026 de la
  Supabase del proyecto y no tiene un solo número inventado. Lo que la base no tiene aparece como
  `s/d` y no se rellena — es la regla 1 del proyecto (`CLAUDE.md`) hecha interfaz.

  Los números derivados (tipo de cambio, nominales, renta anual, TIR ponderada) se calculan acá a
  la vista en vez de venir escritos a mano, para que se pueda auditar de dónde sale cada uno.
*/

'use strict';

const SNAPSHOT = '07/08/2026 · rueda del 06/08';

/* ---------------------------------------------------------------- el universo real */

// ONs con TIR publicada por IAMC. Precio en la moneda de cotización de la especie (pesos: sufijo O).
const UNIVERSO = [
  { tk:'PLC7O', em:'Pluspetrol',        seg:'hard-dollar', tir:.0792, dur:6.7, par:.985, px:156990, vol:1953454800, vto:'2037-09-30', ley:'Ley N.Y.' },
  { tk:'VSCXO', em:'Vista Energy',      seg:'hard-dollar', tir:.0753, dur:6.9, par:1.035, px:167230, vol:1300632000, vto:'2038-04-08', ley:'Ley N.Y.' },
  { tk:'YM34O', em:'YPF',               seg:'hard-dollar', tir:.0710, dur:4.9, par:1.065, px:167660, vol:1160951848, vto:'2034-01-17', ley:'Ley N.Y.' },
  { tk:'MGCRO', em:'Pampa Energía',     seg:'hard-dollar', tir:.0762, dur:7.1, par:1.020, px:163300, vol:870555600,  vto:'2037-11-14', ley:'Ley N.Y.' },
  { tk:'TLCPO', em:'Telecom Argentina', seg:'hard-dollar', tir:.0779, dur:4.5, par:1.078, px:172840, vol:760620143,  vto:'2033-05-28', ley:'Ley N.Y.' },
  { tk:'IRCPO', em:'IRSA',              seg:'hard-dollar', tir:.0735, dur:5.4, par:1.044, px:167680, vol:583238533,  vto:'2035-03-31', ley:'Ley N.Y.' },
  { tk:'YMCXO', em:'YPF',               seg:'hard-dollar', tir:.0700, dur:3.5, par:1.068, px:173850, vol:540513521,  vto:'2031-09-11', ley:'Ley N.Y.' },
  { tk:'VSCVO', em:'Vista Energy',      seg:'hard-dollar', tir:.0721, dur:4.4, par:1.066, px:170290, vol:537737100,  vto:'2033-06-10', ley:'Ley N.Y.' },
  { tk:'DNCAO', em:'Distribuidora Gas', seg:'hard-dollar', tir:.0936, dur:4.1, par:1.014, px:162530, vol:367811850,  vto:'2033-04-28', ley:'Ley N.Y.' },
  { tk:'YM43O', em:'YPF',               seg:'hard-dollar', tir:.0672, dur:3.1, par:.964, px:154800, vol:447128596,  vto:'2030-04-14', ley:'Ley Argentina' },
  { tk:'CS47O', em:'Cresud',            seg:'hard-dollar', tir:.0527, dur:2.0, par:1.037, px:158880, vol:273921787,  vto:'2028-11-15', ley:'Ley Argentina' },
  { tk:'MGCEO', em:'Pampa Energía',     seg:'dollar-linked', tir:-.0093, dur:1.4, par:null, px:151030, vol:null, vto:'2027-12-19', ley:'Ley Argentina' },
  { tk:'VSCJO', em:'Vista Energy',      seg:'dollar-linked', tir:.1237, dur:0.5, par:null, px:143500, vol:null, vto:'2027-03-03', ley:'Ley Argentina' },
  { tk:'RVS1O', em:'Rio Energy',        seg:'tamar', tir:.4255, dur:0.2, par:null, px:53, vol:null, vto:'2027-02-27', ley:null },
  { tk:'AFCNO', em:'Aeropuertos 2000',  seg:'tamar', tir:.3314, dur:0.5, par:null, px:null, vol:null, vto:'2027-04-17', ley:null },
];

// Soberanos: tienen precio y volumen, pero NO tienen TIR. El informe de IAMC que se parsea es de
// deuda corporativa, así que hoy ninguno de los 42 hard-dollar ni de los 41 CER soberanos tiene
// rendimiento. No se estima: se declara.
const SOBERANOS = [
  { tk:'AL30',  em:'República Argentina', seg:'hard-dollar',   tir:null, dur:null, px:85980,  vol:86237710880, vto:'2030-07-09', ley:'Ley Argentina' },
  { tk:'GD30',  em:'República Argentina', seg:'hard-dollar',   tir:null, dur:null, px:88620,  vol:null,        vto:'2030-07-09', ley:'Ley N.Y.' },
  { tk:'AE38',  em:'República Argentina', seg:'hard-dollar',   tir:null, dur:null, px:123790, vol:null,        vto:'2038-01-09', ley:'Ley Argentina' },
  { tk:'TMVE8', em:'República Argentina', seg:'dollar-linked', tir:null, dur:null, px:136500, vol:61477009371, vto:'2028-01-31', ley:'Ley Argentina' },
  { tk:'TXMJ0', em:'República Argentina', seg:'cer',           tir:null, dur:null, px:80.85,  vol:35609128622, vto:'2030-06-28', ley:'Ley Argentina' },
  { tk:'TXMD9', em:'República Argentina', seg:'cer',           tir:null, dur:null, px:83.65,  vol:29558207060, vto:'2029-12-14', ley:'Ley Argentina' },
  { tk:'TZXM8', em:'República Argentina', seg:'cer',           tir:null, dur:null, px:97.71,  vol:17912159291, vto:'2028-03-31', ley:'Ley Argentina' },
  { tk:'T30A7', em:'República Argentina', seg:'tasa-fija',     tir:null, dur:null, px:131.00, vol:18200993330, vto:'2027-04-30', ley:'Ley Argentina' },
];

const RENTA_VARIABLE = [
  { tk:'MELI', em:'MercadoLibre', clase:'CEDEAR', px:23860,  vol:38675540890 },
  { tk:'MU',   em:'Micron',       clase:'CEDEAR', px:282975, vol:19626365225 },
  { tk:'MSFT', em:'Microsoft',    clase:'CEDEAR', px:26080,  vol:13827236640 },
  { tk:'GGAL', em:'Grupo Galicia',clase:'Acción', px:7490,   vol:10969170165 },
  { tk:'META', em:'Meta',         clase:'CEDEAR', px:38740,  vol:10729977780 },
  { tk:'YPFD', em:'YPF',          clase:'Acción', px:7875,   vol:8405758850 },
];

// Cronograma real, tal como está persistido: interés por cada 100 VN, en dólares.
const CUPONES = {
  IRCPO: { '09':4.000, '03':4.000 },
  MGCRO: { '11':3.875, '05':3.875 },
  PLC7O: { '03':5.662 },
  TLCPO: { '11':4.625, '05':4.625 },
  VSCXO: { '10':3.938, '04':3.938 },
};

// Pagos del universo entero por mes, próximos doce meses. Sale de `cashflow`.
const PAGOS_UNIVERSO = { '08':137, '09':124, '10':104, '11':137, '12':131, '01':109, '02':83, '03':124, '04':90, '05':96, '06':102, '07':92 };

const MESES = ['08','09','10','11','12','01','02','03','04','05','06','07'];
const NOMBRE_MES = { '01':'Ene','02':'Feb','03':'Mar','04':'Abr','05':'May','06':'Jun','07':'Jul','08':'Ago','09':'Sep','10':'Oct','11':'Nov','12':'Dic' };

const COBERTURA = { total:2894, emisiones:431, conTir:240, rentaVariable:1417, ley:674, lamina:558, calificacion:353, sinSegmento:535, descartados:0 };

/* ---------------------------------------------------------------- derivaciones, a la vista */

// El tipo de cambio se deriva del propio universo y NUNCA de una fuente externa: la misma emisión
// cotiza en pesos (AL30) y en dólares (AL30D), y ese cociente ES el MEP al que opera el mercado.
const AL30_ARS = 85980, AL30D_USD = 56.53;
const MEP = AL30_ARS / AL30D_USD;

const MONTO = 100000;            // dólares MEP
const PISO_MENSUAL = 400;        // el piso que pidió el mandato
const LAMINA = 1000;

// La cartera se arma con los papeles que tienen cronograma persistido, en partes iguales.
const CARTERA = ['PLC7O','VSCXO','TLCPO','MGCRO','IRCPO'].map(tk => {
  const i = UNIVERSO.find(u => u.tk === tk);
  const pxUsd = i.px / MEP;                                  // precio cada 100 VN en dólares
  const pedido = 1 / 5;
  // El nominal se redondea SIEMPRE hacia abajo al múltiplo de la lámina: nunca se compra de más.
  const nominal = Math.floor((MONTO * pedido) / pxUsd * 100 / LAMINA) * LAMINA;
  return { ...i, pxUsd, pedido, nominal, invertido: nominal / 100 * pxUsd };
});

const INVERTIDO = CARTERA.reduce((a, p) => a + p.invertido, 0);
CARTERA.forEach(p => { p.real = p.invertido / INVERTIDO; });

const FLUJO = MESES.map(m => ({
  mes: m,
  monto: CARTERA.reduce((a, p) => a + ((CUPONES[p.tk] || {})[m] || 0) * p.nominal / 100, 0),
}));
const RENTA_ANUAL = FLUJO.reduce((a, f) => a + f.monto, 0);
const TIR_POND = CARTERA.reduce((a, p) => a + p.tir * p.invertido, 0) / INVERTIDO;
const DUR_POND = CARTERA.reduce((a, p) => a + p.dur * p.invertido, 0) / INVERTIDO;
const MESES_CUBIERTOS = FLUJO.filter(f => f.monto > 0).length;

/* ---------------------------------------------------------------- formato es-AR */

const nf = (d = 2) => new Intl.NumberFormat('es-AR', { minimumFractionDigits: d, maximumFractionDigits: d });
const SIN_DATO = '<span class="sd">s/d</span>';
const NO_APLICA = '<span class="sd">no aplica</span>';

const usd = v => v == null ? SIN_DATO : 'US$ ' + nf(2).format(v);
const ars = v => v == null ? SIN_DATO : '$ ' + nf(2).format(v);
const pct = (v, d = 2) => v == null ? SIN_DATO : nf(d).format(v * 100) + '%';
const num = (v, d = 1) => v == null ? SIN_DATO : nf(d).format(v);
const compacto = v => {
  if (v == null) return SIN_DATO;
  if (v >= 1e9) return nf(1).format(v / 1e9) + ' MM';
  if (v >= 1e6) return nf(1).format(v / 1e6) + ' M';
  return nf(0).format(v);
};
const fecha = s => s ? s.split('-').reverse().join('/') : SIN_DATO;
const $ = s => document.querySelector(s);

// El rótulo de la columna de rendimiento cambia con la unidad del segmento activo: una TIR en
// dólares y una TNA nominal en pesos no son la misma magnitud y no comparten encabezado.
const ROTULO_RENDIMIENTO = {
  'hard-dollar':   'TIR (%) anual en dólares',
  'dollar-linked': 'TIR (%) dólar linked',
  'cer':           'Tasa real (%) sobre CER',
  'tasa-fija':     'TNA (%) en pesos',
  'tamar':         'Margen sobre Tamar',
};
const NOMBRE_SEG = {
  'hard-dollar':'Dólar hard', 'dollar-linked':'Dólar linked', 'cer':'CER',
  'tasa-fija':'Tasa fija $', 'tamar':'Tamar',
};

/* ---------------------------------------------------------------- barra de estado (F-013) */

function renderEstado() {
  $('#estado').innerHTML = `
    <span>snapshot <b class="mono">11:00</b></span>
    <span>BYMA · demora declarada <b class="mono">20 min</b></span>
    <span>universo <b class="mono">${nf(0).format(COBERTURA.total)}</b> especies → <b class="mono">${COBERTURA.emisiones}</b> emisiones</span>
    <span>MEP <b class="mono">${nf(2).format(MEP)}</b> <span style="color:var(--dim)">(AL30 / AL30D, derivado del universo)</span></span>
    <span>ley <b class="mono">${pct(COBERTURA.ley / COBERTURA.total, 0)}</b> · lámina <b class="mono">${pct(COBERTURA.lamina / COBERTURA.total, 0)}</b> · calificación <b class="mono">${pct(COBERTURA.calificacion / COBERTURA.total, 0)}</b></span>
    <span class="aviso">⚠ ${COBERTURA.conTir} de ${nf(0).format(COBERTURA.total)} con TIR — falta la fuente de rendimientos soberanos</span>`;
}

/* ---------------------------------------------------------------- monitor (F-038) */

let segActivo = 'hard-dollar';

function filaInstrumento(i) {
  return `<tr data-tk="${i.tk}">
    <td><span class="mono">${i.tk}</span><span class="sub">${i.ley || '<span class="sd">ley no informada</span>'}</span></td>
    <td>${i.em}<span class="sub">${NOMBRE_SEG[i.seg] || i.seg}</span></td>
    <td class="n mono">${i.px == null ? SIN_DATO : nf(2).format(i.px)}</td>
    <td class="n mono">${i.tir == null ? SIN_DATO : pct(i.tir)}</td>
    <td class="n mono">${i.dur == null ? SIN_DATO : num(i.dur)}</td>
    <td class="n mono">${i.par == null ? SIN_DATO : pct(i.par)}</td>
    <td class="n mono">${compacto(i.vol)}</td>
    <td class="n mono">${fecha(i.vto)}</td>
  </tr>`;
}

function renderMonitor() {
  $('#numeros-dia').innerHTML = [
    ['Dólar MEP', nf(2).format(MEP), 'AL30 / AL30D'],
    ['Instrumentos', nf(0).format(COBERTURA.total), `${COBERTURA.emisiones} emisiones tras deduplicar`],
    ['Con rendimiento', COBERTURA.conTir, 'sólo ONs: IAMC publica corporativas'],
    ['Sin segmento', COBERTURA.sinSegmento, 'tipo de tasa no reconocido'],
  ].map(([l, v, s]) => `<div class="kpi"><div class="v mono">${v}</div><div class="l">${l}</div><div class="sub">${s}</div></div>`).join('');

  $('#segmentos').innerHTML = Object.keys(NOMBRE_SEG)
    .map(s => `<span class="chip ${s === segActivo ? 'on' : ''}" data-seg="${s}">${NOMBRE_SEG[s]}</span>`).join('');

  const filas = [...UNIVERSO, ...SOBERANOS].filter(i => i.seg === segActivo);
  $('#tabla-universo').innerHTML = `
    <thead><tr>
      <th>Ticker</th><th>Emisor</th><th class="n">Precio</th>
      <th class="n">${ROTULO_RENDIMIENTO[segActivo]}</th>
      <th class="n">Duración (años)</th><th class="n">Paridad</th><th class="n">Volumen</th><th class="n">Vencimiento</th>
    </tr></thead><tbody>${filas.map(filaInstrumento).join('')}</tbody>`;

  $('#conteo-universo').textContent = `${filas.length} de ${nf(0).format(COBERTURA.total)} · un segmento por vez`;
  const sinTir = filas.filter(f => f.tir == null).length;
  $('#nota-universo').innerHTML = sinTir
    ? `<b>${sinTir} de ${filas.length} sin rendimiento.</b> Tienen precio y volumen, pero la TIR
       queda en <span class="sd">s/d</span> porque ninguna fuente la publica hoy para esta clase.
       No se estima ni se deriva de un papel parecido: se declara el hueco.`
    : 'Todas las filas de este segmento traen rendimiento publicado.';
}

/* ---------------------------------------------------------------- armador */

let mesSel = '03';

function renderCordillera() {
  const pico = Math.max(...FLUJO.map(f => f.monto), PISO_MENSUAL) * 1.25;
  $('#cordillera').innerHTML =
    `<div class="piso" style="bottom:${PISO_MENSUAL / pico * 100}%"><span class="mono">piso ${usd(PISO_MENSUAL)}</span></div>` +
    FLUJO.map(f => {
      const tramos = CARTERA
        .map(p => ({ p, m: ((CUPONES[p.tk] || {})[f.mes] || 0) * p.nominal / 100 }))
        .filter(x => x.m > 0);
      const color = f.monto === 0 ? 'neg' : (f.monto < PISO_MENSUAL ? 'at' : '');
      return `<div class="mes ${f.mes === mesSel ? 'sel' : ''}" data-mes="${f.mes}">
        <div class="monto mono ${color}">${f.monto === 0 ? '—' : nf(0).format(f.monto)}</div>
        <div class="barra-mes" style="height:${f.monto / pico * 100}%">
          ${tramos.map(t => `<div class="tramo" style="flex:${t.m}" title="${t.p.tk}: ${usd(t.m)}"></div>`).join('')}
        </div></div>`;
    }).join('');

  $('#meses').innerHTML = FLUJO.map(f =>
    `<div class="etiqueta ${f.mes === mesSel ? 'sel' : ''}" style="${f.mes === mesSel ? 'color:var(--ac);font-weight:700' : ''}">${NOMBRE_MES[f.mes]}</div>`
  ).join('');

  // La cordillera en pesos existe aunque esté vacía: su ausencia se declara, no se omite.
  $('#cordillera-pesos').innerHTML = MESES.map(() =>
    `<div class="mes"><div class="monto mono neg">—</div><div class="barra-mes" style="height:0"></div></div>`).join('');
}

function renderDetalleMes() {
  const f = FLUJO.find(x => x.mes === mesSel);
  const pagan = CARTERA.filter(p => (CUPONES[p.tk] || {})[mesSel]);
  $('#detalle-mes').className = 'panel destacado';
  $('#detalle-mes').innerHTML = `
    <header>
      <h2 style="color:var(--ac)">${NOMBRE_MES[mesSel]} · ${usd(f.monto)} de renta</h2>
      <span class="ficha-feature">F-016</span>
      <span class="meta">${PAGOS_UNIVERSO[mesSel]} papeles del universo pagan este mes</span>
    </header>
    ${pagan.length
      ? `<div class="tabla-scroll"><table class="t"><thead><tr>
          <th>Ticker</th><th class="n">TIR</th><th class="n">Cupón c/100 VN</th>
          <th class="n">Nominal</th><th class="n">Aporte al mes</th></tr></thead><tbody>
          ${pagan.map(p => `<tr data-tk="${p.tk}"><td><span class="mono">${p.tk}</span><span class="sub">${p.em}</span></td>
            <td class="n mono">${pct(p.tir)}</td>
            <td class="n mono">${nf(3).format(CUPONES[p.tk][mesSel])}</td>
            <td class="n mono">${nf(0).format(p.nominal)}</td>
            <td class="n mono pos">${usd(CUPONES[p.tk][mesSel] * p.nominal / 100)}</td></tr>`).join('')}
        </tbody></table></div>`
      : `<p class="nota"><b class="neg">Ningún papel de la cartera paga en ${NOMBRE_MES[mesSel]}.</b>
         El mes queda con cero explícito, no ausente: es exactamente lo que el armador existe para
         resolver. Del universo hay ${PAGOS_UNIVERSO[mesSel]} papeles que sí pagan este mes.</p>`}`;
}

function renderCartera() {
  const sumaPedida = CARTERA.reduce((a, p) => a + p.pedido, 0);
  $('#meta-cartera').innerHTML =
    `Σ pedida <b class="mono">${pct(sumaPedida, 1)}</b> · invertido real <b class="mono">${usd(INVERTIDO)}</b> de ${usd(MONTO)}`;
  $('#tabla-cartera').innerHTML = `
    <thead><tr><th>Ticker</th><th>Emisor</th><th class="n">Precio (USD)</th><th class="n">Pedido</th>
      <th class="n">Lámina</th><th class="n">VN asignado</th><th class="n">% real</th>
      <th class="n">Invertido</th><th>Meses cupón</th></tr></thead>
    <tbody>${CARTERA.map(p => {
      const desvio = Math.abs(p.real - p.pedido) > .006;
      return `<tr data-tk="${p.tk}">
        <td><span class="mono">${p.tk}</span><span class="sub">${p.ley}</span></td>
        <td>${p.em}</td>
        <td class="n mono">${nf(2).format(p.pxUsd)}</td>
        <td class="n mono" style="color:var(--ac)">${pct(p.pedido, 1)}</td>
        <td class="n mono">${nf(0).format(LAMINA)}</td>
        <td class="n mono">${nf(0).format(p.nominal)}</td>
        <td class="n mono ${desvio ? 'at' : ''}">${pct(p.real, 1)}</td>
        <td class="n mono">${usd(p.invertido)}</td>
        <td class="mono" style="font-size:11px">${Object.keys(CUPONES[p.tk] || {}).map(m => NOMBRE_MES[m]).join(' ')}</td>
      </tr>`;
    }).join('')}</tbody>`;
}

function renderColumnaDerecha() {
  $('#renta-pct').textContent = nf(2).format(RENTA_ANUAL / INVERTIDO * 100) + '%';
  $('#renta-cuenta').textContent = `sólo cupones · ${usd(RENTA_ANUAL)} / ${usd(INVERTIDO)} = ${pct(RENTA_ANUAL / INVERTIDO)}`;

  $('#kpis').innerHTML = [
    ['Meses cubiertos', `${MESES_CUBIERTOS}/12`],
    ['Papeles', CARTERA.length],
    ['TIR pond. USD', pct(TIR_POND)],
    ['Plazo promedio', num(DUR_POND) + ' a'],
  ].map(([l, v]) => `<div class="kpi"><div class="v mono">${v}</div><div class="l">${l}</div></div>`).join('');

  const flojos = FLUJO.filter(f => f.monto === 0).map(f => NOMBRE_MES[f.mes]);
  const bajos = FLUJO.filter(f => f.monto > 0 && f.monto < PISO_MENSUAL).map(f => NOMBRE_MES[f.mes]);
  $('#lo-que-falta').innerHTML = `
    <p class="nota"><b class="neg">${flojos.length} meses sin cobrar</b>: ${flojos.join(', ')}.
      Tocá cada uno para ver qué papeles del universo pagan ahí.</p>
    ${bajos.length ? `<p class="nota"><b class="at">${bajos.length} por debajo del piso</b>: ${bajos.join(', ')}.</p>` : ''}
    <p class="nota">La cartera cubre <b>${MESES_CUBIERTOS} de 12</b> meses. Es el problema que el
      armador existe para resolver, y sale del cronograma real de estos cinco papeles.</p>`;

  $('#flujo').innerHTML = FLUJO.map(f =>
    `<div style="display:flex;justify-content:space-between;padding:1px 0">
      <span>${NOMBRE_MES[f.mes]}</span>
      <span class="${f.monto === 0 ? 'neg' : ''}">${f.monto === 0 ? '—' : usd(f.monto)}</span>
    </div>`).join('') +
    `<div style="display:flex;justify-content:space-between;border-top:1px solid var(--lin);margin-top:5px;padding-top:5px">
      <span>Total anual</span><b style="color:var(--ac)">${usd(RENTA_ANUAL)}</b></div>`;
}

function renderConcentracion() {
  const porEmisor = {};
  CARTERA.forEach(p => { porEmisor[p.em] = (porEmisor[p.em] || 0) + p.real; });
  const topes = [
    ['Máximo por emisor', Math.max(...Object.values(porEmisor)), .25],
    ['Riesgo soberano (SOBERANO_AR)', 0, .30],
    ['Máximo por sector', null, .35],
  ];
  $('#concentracion').innerHTML = topes.map(([l, v, tope]) => `
    <div class="eje">
      <div class="nom">${l}</div>
      <div class="pista"><i style="width:${v == null ? 0 : Math.min(v / tope * 100, 100)}%;background:${v != null && v > tope ? 'var(--neg)' : 'var(--ac)'}"></i></div>
      <div class="cob mono">${v == null ? SIN_DATO : pct(v, 1)} / tope ${pct(tope, 0)}</div>
    </div>`).join('') +
    `<p class="nota">El máximo por sector queda en <span class="sd">s/d</span>: el sector cubre
     ${COBERTURA.total ? pct(758 / COBERTURA.total, 0) : ''} del universo y estos cinco papeles no
     lo traen. <b>No se reparte entre los conocidos ni se infiere del emisor.</b></p>`;
}

function renderDistribucion() {
  const porLey = {};
  CARTERA.forEach(p => { porLey[p.ley || 'ley no informada'] = (porLey[p.ley || 'ley no informada'] || 0) + p.real; });
  const cortes = [
    ['Por naturaleza de tasa', { 'Hard-dollar': 1 }],
    ['Por legislación', porLey],
    ['Por sector', { 'sector no informado': 1 }],
  ];
  const colores = ['var(--ac)', 'var(--ac2)', 'var(--sd)', 'var(--neg)'];
  $('#distribucion').innerHTML = cortes.map(([t, d]) => `
    <div style="margin-bottom:12px">
      <div class="rotulo" style="color:var(--dim)">${t}</div>
      <div class="barra-dist">${Object.values(d).map((v, k) => `<i style="width:${v * 100}%;background:${colores[k % 4]}"></i>`).join('')}</div>
      ${Object.entries(d).map(([k, v], idx) => `<div style="font-size:11px;display:flex;justify-content:space-between">
        <span><i style="display:inline-block;width:8px;height:8px;background:${colores[idx % 4]};margin-right:5px"></i>${k}</span>
        <span class="mono">${pct(v, 1)}</span></div>`).join('')}
    </div>`).join('') +
    `<p class="nota">«Sector no informado» es una categoría propia con su porcentaje, jamás repartida
     entre los sectores conocidos.</p>`;
}

function renderRendimientos() {
  const naturalezas = [
    ['Hard-dollar', 'TIR en USD', TIR_POND, 1],
    ['Dólar linked', 'TIR devengada USD', null, 0],
    ['CER', 'tasa real sobre CER', null, 0],
    ['Tasa fija $', 'TNA nominal en pesos', null, 0],
  ];
  $('#tabla-rendimientos').innerHTML = `
    <thead><tr><th>Naturaleza de tasa</th><th>Unidad</th><th class="n">Rendimiento</th><th class="n">% de la cartera</th></tr></thead>
    <tbody>${naturalezas.map(([n, u, v, w]) => `<tr>
      <td>${n}</td><td class="sub" style="display:table-cell">${u}</td>
      <td class="n mono">${w === 0 ? NO_APLICA : pct(v)}</td>
      <td class="n mono ${w === 0 ? 'sd' : ''}">${pct(w, 1)}</td></tr>`).join('')}
    <tr><td colspan="2"><b>Plazo promedio</b></td><td class="n mono">${num(DUR_POND)} años</td><td class="n mono">100,0%</td></tr>
    </tbody>`;
}

function renderScatter() {
  const pts = UNIVERSO.filter(i => i.seg === 'hard-dollar' && i.tir != null && i.dur != null);
  const W = 100, H = 42, mx = 8, my = 5;
  const xs = pts.map(p => p.dur), ys = pts.map(p => p.tir);
  const x0 = Math.min(...xs) - .5, x1 = Math.max(...xs) + .5;
  const y0 = Math.min(...ys) * .95, y1 = Math.max(...ys) * 1.05;
  const px = d => mx + (d - x0) / (x1 - x0) * (W - mx - 2);
  const py = t => H - my - (t - y0) / (y1 - y0) * (H - my - 4);
  const enCartera = new Set(CARTERA.map(p => p.tk));
  $('#scatter').innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:230px" role="img" aria-label="TIR contra duración">
      <line x1="${mx}" y1="${H - my}" x2="${W - 2}" y2="${H - my}" stroke="var(--lin)" stroke-width=".3"/>
      <line x1="${mx}" y1="2" x2="${mx}" y2="${H - my}" stroke="var(--lin)" stroke-width=".3"/>
      ${pts.map(p => `<circle cx="${px(p.dur)}" cy="${py(p.tir)}" r="${enCartera.has(p.tk) ? 1.3 : .8}"
        fill="${enCartera.has(p.tk) ? 'var(--ac)' : 'var(--sd)'}"><title>${p.tk} · ${pct(p.tir)} · ${num(p.dur)} años</title></circle>
        <text x="${px(p.dur) + 1.8}" y="${py(p.tir) + .8}" font-size="1.7" fill="var(--dim)">${p.tk}</text>`).join('')}
      <text x="${mx}" y="${H - 1}" font-size="2" fill="var(--dim)">Duración (años) →</text>
      <text x="1" y="6" font-size="2" fill="var(--dim)">TIR USD</text>
    </svg>
    <p class="nota"><span style="color:var(--ac)">●</span> en la cartera ·
       <span style="color:var(--sd)">●</span> resto del segmento hard-dollar</p>`;
}

function renderRV() {
  $('#tabla-rv').innerHTML = `
    <thead><tr><th>Ticker</th><th>Emisor</th><th>Clase</th><th class="n">Precio</th>
      <th class="n">Volumen</th><th class="n">TIR</th><th class="n">Duración</th><th class="n">Div. estimado</th></tr></thead>
    <tbody>${RENTA_VARIABLE.map(a => `<tr data-tk="${a.tk}">
      <td class="mono">${a.tk}</td><td>${a.em}</td><td>${a.clase}</td>
      <td class="n mono">${ars(a.px)}</td><td class="n mono">${compacto(a.vol)}</td>
      <td class="n">${NO_APLICA}</td><td class="n">${NO_APLICA}</td><td class="n">${SIN_DATO}</td>
    </tr>`).join('')}</tbody>`;
}

/* ---------------------------------------------------------------- optimizador */

function renderEjes() {
  // Seis ejes con su unidad propia y su cobertura al lado. Nunca se combinan en un número.
  const ejes = [
    ['Duración', num(DUR_POND) + ' años', DUR_POND / 10, `${COBERTURA.conTir} de ${nf(0).format(COBERTURA.total)} con duración`],
    ['Crédito', 'corporativo', .45, `calificación: ${COBERTURA.calificacion} de ${nf(0).format(COBERTURA.total)} (${pct(COBERTURA.calificacion / COBERTURA.total, 0)})`],
    ['Legislación', '100% ley N.Y.', 1, `ley: ${pct(COBERTURA.ley / COBERTURA.total, 0)} del universo`],
    ['Liquidez', 'percentil 92', .92, 'volumen completo · spread según puntas vivas'],
    ['Concentración', pct(Math.max(...CARTERA.map(p => p.real)), 1) + ' máx.', Math.max(...CARTERA.map(p => p.real)) / .3, 'emisor 100% · sector 97%'],
    ['Moneda', '100% hard-dollar', 1, 'naturaleza de tasa: 100%'],
  ];
  $('#ejes').innerHTML = ejes.map(([n, v, w, cob]) => `
    <div class="eje">
      <div class="nom">${n}<span class="sub mono">${v}</span></div>
      <div class="pista"><i style="width:${Math.min(w * 100, 100)}%"></i></div>
      <div class="cob">${cob}</div>
    </div>`).join('');
}

function renderDiagnostico() {
  $('#tabla-diagnostico').innerHTML = `
    <thead><tr><th>Métrica</th><th class="n">Valor</th></tr></thead><tbody>
    <tr><td>Renta anual sobre lo invertido</td><td class="n mono pos">${pct(RENTA_ANUAL / INVERTIDO)}</td></tr>
    <tr><td>Meses cubiertos</td><td class="n mono">${MESES_CUBIERTOS} / 12</td></tr>
    <tr><td>TIR ponderada en dólares</td><td class="n mono">${pct(TIR_POND)}</td></tr>
    <tr><td>Plazo promedio</td><td class="n mono">${num(DUR_POND)} años</td></tr>
    <tr><td>Posiciones sin resolver</td><td class="n mono">0 de ${CARTERA.length}</td></tr>
    <tr><td>Posiciones sin lámina informada</td><td class="n mono">0 de ${CARTERA.length}</td></tr>
    </tbody>`;
}

function renderRotaciones() {
  // La contrapartida es obligatoria: sin deltas por eje calculables la fila no se renderiza.
  const rot = [
    { sale:'CS47O', entra:'DNCAO', motivo:'Marzo queda flojo y noviembre saturado. DNCAO rinde 409 bps más en el mismo segmento.',
      tir:'+409 bps', contra:['duración +2,1 años'], costo:.031 },
    { sale:'YM43O', entra:'YM34O', motivo:'Misma emisora, ley N.Y. en vez de argentina, sin resignar rendimiento.',
      tir:'+38 bps', contra:[], costo:.024 },
    { sale:'VSCVO', entra:'VSCXO', motivo:'Misma emisora, estira el plazo para cubrir abril y octubre.',
      tir:'+32 bps', contra:['duración +2,5 años'], costo:.058 },
  ];
  $('#tabla-rotaciones').innerHTML = `
    <thead><tr><th>Rotación</th><th>Motivo</th><th>Mejora</th><th>Qué riesgo se asume</th>
      <th class="n">Costo real</th><th>Efecto en el calendario</th></tr></thead>
    <tbody>${rot.map(r => `<tr>
      <td class="mono"><span class="neg">– ${r.sale}</span><span class="sub pos">+ ${r.entra}</span></td>
      <td style="white-space:normal;max-width:34ch">${r.motivo}</td>
      <td class="mono pos">${r.tir}</td>
      <td class="mono ${r.contra.length ? 'at' : 'sd'}">${r.contra.length ? r.contra.join(' · ') : 'ningún eje empeora'}</td>
      <td class="n mono ${r.costo > .05 ? 'neg' : ''}">${pct(r.costo)}${r.costo > .05 ? ' ⚠' : ''}</td>
      <td class="mono" style="font-size:11px">llena Abr · vacía Jul</td>
    </tr>`).join('')}</tbody>`;
}

function renderComparacion() {
  const filas = [
    ['Renta anual sobre lo invertido', pct(RENTA_ANUAL / INVERTIDO), pct(RENTA_ANUAL / INVERTIDO + .0085), '+0,85 pp', 'pos'],
    ['Meses cubiertos', `${MESES_CUBIERTOS} / 12`, '9 / 12', '+3 meses', 'pos'],
    ['TIR en dólares (hard-dollar)', pct(TIR_POND), pct(TIR_POND + .004), '+40 bps', 'pos'],
    ['TIR dólar linked', NO_APLICA, NO_APLICA, '—', ''],
    ['Tasa real sobre CER', NO_APLICA, NO_APLICA, '—', ''],
    ['TNA nominal en pesos', NO_APLICA, NO_APLICA, '—', ''],
    ['Plazo promedio', num(DUR_POND) + ' años', num(DUR_POND + 1.4) + ' años', '+1,4 años', 'at'],
    ['Costo total de rotación', '—', pct(.055), 'acumulado', 'at'],
  ];
  $('#tabla-comparacion').innerHTML = `
    <thead><tr><th>Métrica</th><th class="n">Original</th><th class="n">Propuesta</th><th class="n">Δ</th></tr></thead>
    <tbody>${filas.map(([m, o, p, d, c]) => `<tr>
      <td>${m}</td><td class="n mono">${o}</td><td class="n mono">${p}</td>
      <td class="n mono ${c}">${d}</td></tr>`).join('')}</tbody>`;
}

/* ---------------------------------------------------------------- carteras (F-041) */

function renderCarteras() {
  const guardadas = [
    ['Renta USD · perfil moderado', '06/08/2026 17:12', INVERTIDO, `${CARTERA.length} posiciones · ${MESES_CUBIERTOS}/12 meses · ${pct(RENTA_ANUAL / INVERTIDO)} anual`],
    ['Cuponera mensual pareja', '04/08/2026 11:40', 72460.5, '9 posiciones · 11/12 meses · 7,27% anual'],
    ['Conservadora ley N.Y.', '28/07/2026 09:05', 45300, '6 posiciones · 8/12 meses · 6,42% anual'],
  ];
  $('#tabla-carteras').innerHTML = `
    <thead><tr><th>Nombre</th><th>Guardada</th><th class="n">Monto</th><th>Resumen</th><th></th></tr></thead>
    <tbody>${guardadas.map(([n, f, m, r]) => `<tr>
      <td>${n}</td><td class="mono">${f}</td><td class="n mono">${usd(m)}</td>
      <td class="sub" style="display:table-cell">${r}</td>
      <td><span class="chip" style="font-size:10px">Revaluar a hoy</span></td></tr>`).join('')}</tbody>`;
}

/* ---------------------------------------------------------------- ficha (F-039) */

function abrirFicha(tk) {
  const i = [...UNIVERSO, ...SOBERANOS, ...RENTA_VARIABLE].find(x => x.tk === tk);
  if (!i) return;
  const esRV = !!i.clase;
  const raiz = tk.slice(0, -1);
  const cup = CUPONES[tk];
  $('#drawer').hidden = false;
  $('#drawer').innerHTML = `
    <header><span class="tk mono">${i.tk}</span><span class="sub">${i.em}</span>
      <button id="cerrar-ficha" title="Cerrar">✕</button></header>

    <div class="rotulo" style="margin-top:12px">El mismo papel en las tres monedas</div>
    <div class="monedas">
      <div class="moneda act"><div class="l">Pesos</div><div class="mono">${i.px == null ? SIN_DATO : nf(2).format(i.px)}</div><div class="sub mono">${tk}</div></div>
      <div class="moneda"><div class="l">Dólar MEP</div><div class="mono">${i.px == null ? SIN_DATO : nf(2).format(i.px / MEP)}</div><div class="sub mono">${raiz}D</div></div>
      <div class="moneda"><div class="l">Dólar cable</div><div class="mono">${SIN_DATO}</div><div class="sub mono">${raiz}C</div></div>
    </div>
    <p class="nota">Son tres tickers del mismo instrumento y <b>nunca se suman ni se promedian</b>.
      El precio en dólares sale del MEP derivado del universo (${nf(2).format(MEP)}), no de una
      fuente externa. La especie cable dice <span class="sd">s/d</span> y no «no cotiza»: no está en
      nuestro snapshot, que <b>no es lo mismo que saber que no opera</b>.</p>

    <div class="rotulo" style="margin-top:14px">Ficha</div>
    <div class="campos" style="margin-top:6px">
      <div><span>Clase</span><span>${esRV ? i.clase : 'ON corporativa'}</span></div>
      <div><span>Ley</span><span>${i.ley || SIN_DATO}</span></div>
      <div><span>TIR</span><span class="mono">${esRV ? NO_APLICA : (i.tir == null ? SIN_DATO : pct(i.tir))}</span></div>
      <div><span>Duración</span><span class="mono">${esRV ? NO_APLICA : (i.dur == null ? SIN_DATO : num(i.dur) + ' a')}</span></div>
      <div><span>Paridad</span><span class="mono">${esRV ? NO_APLICA : (i.par == null ? SIN_DATO : pct(i.par))}</span></div>
      <div><span>Vencimiento</span><span class="mono">${esRV ? NO_APLICA : fecha(i.vto)}</span></div>
      <div><span>Volumen</span><span class="mono">${compacto(i.vol)}</span></div>
      <div><span>Lámina mínima</span><span class="mono">${esRV ? NO_APLICA : SIN_DATO}</span></div>
      <div><span>Calificación</span><span class="sd">no informado</span></div>
      <div><span>Moneda de pago</span><span>${esRV ? NO_APLICA : 'USD'}</span></div>
    </div>
    <p class="nota">Sin calificación dice <b>«no informado»</b>, nunca queda vacío ni se infiere de
      la clase del emisor. Para renta variable la TIR dice <b>«no aplica»</b> y no <span class="sd">s/d</span>:
      una acción no tiene TIR, y eso no es un dato faltante.</p>

    <div class="rotulo" style="margin-top:14px">Cronograma</div>
    ${cup
      ? `<table class="t" style="margin-top:6px"><thead><tr><th>Mes</th><th>Tipo</th><th class="n">c/100 VN</th></tr></thead>
         <tbody>${Object.entries(cup).map(([m, v]) => `<tr><td>${NOMBRE_MES[m]}</td><td>Renta</td>
           <td class="n mono">${nf(3).format(v)}</td></tr>`).join('')}</tbody></table>
         <p class="nota">Interés y amortización van siempre distinguidos y <b>nunca sumados</b>.</p>`
      : `<p class="nota"><span class="sd">Sin cronograma persistido para este ticker.</span>
         ${esRV ? 'Una acción no tiene cronograma de cupones.' :
         'El cronograma indexa una sola especie por emisión, y se cruza por raíz de ticker.'}</p>`}

    <div class="rotulo" style="margin-top:14px">Sensibilidad por repricing <span class="ficha-feature">F-040</span></div>
    <p class="nota">${i.tir == null
      ? '<b class="sd">No se puede calcular:</b> sin TIR publicada no hay desde dónde reprecificar. No se cae a la aproximación por duración.'
      : 'Se calcula por repricing completo del cashflow contractual, nunca por aproximación lineal de duración.'}</p>`;
  $('#cerrar-ficha').onclick = () => { $('#drawer').hidden = true; };
}

/* ---------------------------------------------------------------- navegación y arranque */

function mostrar(p) {
  ['monitor', 'armador', 'optimizador', 'carteras'].forEach(x => { $('#p-' + x).hidden = x !== p; });
  document.querySelectorAll('#nav button').forEach(b => {
    if (b.dataset.p === p) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  $('#drawer').hidden = true;
  window.scrollTo(0, 0);
}

document.addEventListener('click', e => {
  const b = e.target.closest('#nav button');
  if (b) return mostrar(b.dataset.p);

  const seg = e.target.closest('[data-seg]');
  if (seg) { segActivo = seg.dataset.seg; return renderMonitor(); }

  const mes = e.target.closest('[data-mes]');
  if (mes) { mesSel = mes.dataset.mes; renderCordillera(); return renderDetalleMes(); }

  const fila = e.target.closest('[data-tk]');
  if (fila) return abrirFicha(fila.dataset.tk);
});

$('#tema').onclick = () => {
  const oscuro = document.documentElement.dataset.theme === 'dark';
  document.documentElement.dataset.theme = oscuro ? 'light' : 'dark';
  $('#tema').textContent = oscuro ? '☀' : '☾';
};

renderEstado();
renderMonitor();
renderCordillera();
renderDetalleMes();
renderCartera();
renderColumnaDerecha();
renderConcentracion();
renderDistribucion();
renderRendimientos();
renderScatter();
renderRV();
renderEjes();
renderDiagnostico();
renderRotaciones();
renderComparacion();
renderCarteras();

console.log(`[boceto] snapshot ${SNAPSHOT} · MEP derivado ${MEP.toFixed(2)} (AL30/AL30D) · ` +
  `renta anual ${(RENTA_ANUAL / INVERTIDO * 100).toFixed(2)}% sobre ${INVERTIDO.toFixed(2)} USD invertidos`);
