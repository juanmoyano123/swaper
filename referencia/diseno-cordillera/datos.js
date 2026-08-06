// Universo de instrumentos y motor de cálculo compartido por las 5 alternativas.
// Datos de mercado de ejemplo (rueda del 05/08/2026), plausibles pero no reales.
// Convención: precios y cupones expresados cada 100 de valor nominal (VN).
// null = dato no disponible. Nunca se estima: la interfaz debe mostrar "s/d".

export const SEGMENTOS = [
  { id: 'hard',   nom: 'Dólar hard',    unidad: 'TIR en USD',            eje: 'TIR (%) anual en dólares' },
  { id: 'cer',    nom: 'CER',           unidad: 'tasa real s/ inflación', eje: 'Tasa real (%) sobre CER' },
  { id: 'fija',   nom: 'Tasa fija $',   unidad: 'TNA en pesos',          eje: 'TNA (%) en pesos' },
  { id: 'dlk',    nom: 'Dólar linked',  unidad: 'TIR devengada en USD',  eje: 'TIR (%) dólar linked' },
  { id: 'badlar', nom: 'Badlar',        unidad: 'margen s/ Badlar',      eje: 'Margen (bps) sobre Badlar' },
  { id: 'tamar',  nom: 'Tamar',         unidad: 'margen s/ Tamar',       eje: 'Margen (bps) sobre Tamar' },
];

export const MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];

const rf = (o) => ({ clase: 'RF', ...o });

export const RENTA_FIJA = [
  // ── Soberanos ley Nueva York ──────────────────────────────────────────────
  rf({ id:'GD29', tickers:{ars:'GD29',mep:'GD29D',cable:'GD29C'}, emisor:'República Argentina', tipo:'Soberano', ley:'Nueva York', seg:'hard', estructura:'Step up', tasa:1.00, freq:'Semestral', meses:[1,7], cuponAnual:1.00, amort:[{mes:1,pct:10},{mes:7,pct:10}], precios:{ars:82150,mep:68.90,cable:67.95}, tir:9.8, dm:1.9, vto:2029, lamina:1, paridad:71.4, vt:96.5, residual:60, convexidad:4.1, vidaProm:1.8, volumen:41_820_000, puntas:{c:68.75,v:69.05}, ultimo:68.90, varDia:0.42 }),
  rf({ id:'GD30', tickers:{ars:'GD30',mep:'GD30D',cable:'GD30C'}, emisor:'República Argentina', tipo:'Soberano', ley:'Nueva York', seg:'hard', estructura:'Step up', tasa:0.75, freq:'Semestral', meses:[1,7], cuponAnual:0.75, amort:[{mes:1,pct:8},{mes:7,pct:8}], precios:{ars:85300,mep:71.55,cable:70.60}, tir:10.5, dm:2.6, vto:2030, lamina:1, paridad:68.2, vt:104.9, residual:76, convexidad:7.8, vidaProm:2.4, volumen:96_450_000, puntas:{c:71.40,v:71.70}, ultimo:71.55, varDia:0.61 }),
  rf({ id:'GD35', tickers:{ars:'GD35',mep:'GD35D',cable:'GD35C'}, emisor:'República Argentina', tipo:'Soberano', ley:'Nueva York', seg:'hard', estructura:'Step up', tasa:4.125, freq:'Semestral', meses:[1,7], cuponAnual:4.125, amort:[], precios:{ars:74900,mep:62.80,cable:61.95}, tir:10.2, dm:6.9, vto:2035, lamina:1, paridad:62.8, vt:100.0, residual:100, convexidad:58.2, vidaProm:7.6, volumen:112_300_000, puntas:{c:62.65,v:62.95}, ultimo:62.80, varDia:-0.35 }),
  rf({ id:'GD38', tickers:{ars:'GD38',mep:'GD38D',cable:'GD38C'}, emisor:'República Argentina', tipo:'Soberano', ley:'Nueva York', seg:'hard', estructura:'Step up', tasa:5.00, freq:'Semestral', meses:[1,7], cuponAnual:5.00, amort:[{mes:1,pct:4.55},{mes:7,pct:4.55}], precios:{ars:87600,mep:73.45,cable:72.50}, tir:9.6, dm:6.1, vto:2038, lamina:1, paridad:73.5, vt:99.9, residual:100, convexidad:47.9, vidaProm:6.9, volumen:58_910_000, puntas:{c:73.30,v:73.60}, ultimo:73.45, varDia:0.18 }),
  rf({ id:'GD41', tickers:{ars:'GD41',mep:'GD41D',cable:'GD41C'}, emisor:'República Argentina', tipo:'Soberano', ley:'Nueva York', seg:'hard', estructura:'Step up', tasa:3.875, freq:'Semestral', meses:[1,7], cuponAnual:3.875, amort:[], precios:{ars:69200,mep:58.05,cable:57.20}, tir:9.9, dm:7.4, vto:2041, lamina:1, paridad:58.1, vt:99.9, residual:100, convexidad:66.4, vidaProm:9.1, volumen:33_270_000, puntas:{c:57.90,v:58.20}, ultimo:58.05, varDia:-0.12 }),
  // ── Soberanos ley Argentina ───────────────────────────────────────────────
  rf({ id:'AL30', tickers:{ars:'AL30',mep:'AL30D',cable:'AL30C'}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'hard', estructura:'Step up', tasa:0.75, freq:'Semestral', meses:[1,7], cuponAnual:0.75, amort:[{mes:1,pct:8},{mes:7,pct:8}], precios:{ars:81900,mep:68.70,cable:67.80}, tir:11.6, dm:2.5, vto:2030, lamina:1, paridad:65.5, vt:104.9, residual:76, convexidad:7.4, vidaProm:2.4, volumen:148_600_000, puntas:{c:68.55,v:68.85}, ultimo:68.70, varDia:0.72 }),
  rf({ id:'AE38', tickers:{ars:'AE38',mep:'AE38D',cable:'AE38C'}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'hard', estructura:'Step up', tasa:5.00, freq:'Semestral', meses:[1,7], cuponAnual:5.00, amort:[{mes:1,pct:4.55},{mes:7,pct:4.55}], precios:{ars:84100,mep:70.50,cable:69.60}, tir:10.4, dm:6.0, vto:2038, lamina:1, paridad:70.6, vt:99.9, residual:100, convexidad:45.1, vidaProm:6.9, volumen:44_050_000, puntas:{c:70.35,v:70.65}, ultimo:70.50, varDia:0.24 }),
  // ── Subsoberanos (provinciales) ───────────────────────────────────────────
  rf({ id:'BA37D', tickers:{ars:'BA37',mep:'BA37D',cable:'BA37C'}, emisor:'Provincia de Buenos Aires', tipo:'Subsoberano', ley:'Nueva York', seg:'hard', estructura:'Step up', tasa:5.25, freq:'Semestral', meses:[3,9], cuponAnual:5.25, amort:[{mes:3,pct:4.0},{mes:9,pct:4.0}], precios:{ars:88400,mep:74.15,cable:73.20}, tir:11.1, dm:4.8, vto:2037, lamina:1, paridad:74.2, vt:99.9, residual:88, convexidad:29.6, vidaProm:5.4, volumen:12_940_000, puntas:{c:73.95,v:74.35}, ultimo:74.15, varDia:0.31 }),
  rf({ id:'CO27D', tickers:{ars:'CO27',mep:'CO27D',cable:'CO27C'}, emisor:'Provincia de Córdoba', tipo:'Subsoberano', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:6.99, freq:'Semestral', meses:[6,12], cuponAnual:6.99, amort:[{mes:6,pct:16.7},{mes:12,pct:16.7}], precios:{ars:110300,mep:92.55,cable:91.40}, tir:9.4, dm:1.6, vto:2027, lamina:1, paridad:92.6, vt:100.0, residual:50, convexidad:3.2, vidaProm:1.4, volumen:8_310_000, puntas:{c:92.35,v:92.75}, ultimo:92.55, varDia:0.09 }),
  rf({ id:'NDT27', tickers:{ars:'NDT27',mep:'NDT7D',cable:'NDT7C'}, emisor:'Provincia del Neuquén', tipo:'Subsoberano', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:8.50, freq:'Trimestral', meses:[2,5,8,11], cuponAnual:8.50, amort:[{mes:5,pct:12.5},{mes:11,pct:12.5}], precios:{ars:114700,mep:96.25,cable:95.10}, tir:8.9, dm:1.9, vto:2028, lamina:1, paridad:96.3, vt:100.0, residual:62.5, convexidad:4.4, vidaProm:1.7, volumen:5_620_000, puntas:{c:96.05,v:96.45}, ultimo:96.25, varDia:0.14 }),
  rf({ id:'CHSG2', tickers:{ars:'CHSG2',mep:'CHSD2',cable:'CHSC2'}, emisor:'Provincia del Chubut', tipo:'Subsoberano', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:7.75, freq:'Semestral', meses:[4,10], cuponAnual:7.75, amort:[{mes:4,pct:12.5},{mes:10,pct:12.5}], precios:{ars:106800,mep:89.60,cable:88.50}, tir:10.8, dm:2.2, vto:2030, lamina:1, paridad:89.7, vt:99.9, residual:75, convexidad:6.1, vidaProm:2.0, volumen:2_180_000, puntas:{c:89.30,v:89.90}, ultimo:89.60, varDia:-0.22 }),
  rf({ id:'SA26D', tickers:{ars:'SA26',mep:'SA26D',cable:'SA26C'}, emisor:'Provincia de Salta', tipo:'Subsoberano', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:9.125, freq:'Semestral', meses:[3,9], cuponAnual:9.125, amort:[{mes:9,pct:33.3}], precios:{ars:120400,mep:101.05,cable:99.85}, tir:8.2, dm:1.1, vto:2027, lamina:1, paridad:101.1, vt:100.0, residual:33.3, convexidad:1.8, vidaProm:0.9, volumen:1_460_000, puntas:{c:100.80,v:101.30}, ultimo:101.05, varDia:0.05 }),
  // ── Obligaciones negociables ──────────────────────────────────────────────
  rf({ id:'YMCJO', tickers:{ars:'YMCJO',mep:'YMCJD',cable:'YMCJC'}, emisor:'YPF S.A.', tipo:'ON', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:8.75, freq:'Semestral', meses:[2,8], cuponAnual:8.75, amort:[], precios:{ars:122600,mep:102.90,cable:101.70}, tir:8.1, dm:3.6, vto:2031, lamina:1000, paridad:102.9, vt:100.0, residual:100, convexidad:15.2, vidaProm:4.4, volumen:18_730_000, puntas:{c:102.70,v:103.10}, ultimo:102.90, varDia:0.11 }),
  rf({ id:'YFCJO', tickers:{ars:'YFCJO',mep:'YFCJD',cable:'YFCJC'}, emisor:'YPF Luz', tipo:'ON', ley:'Argentina', seg:'hard', estructura:'Tasa fija', tasa:7.50, freq:'Semestral', meses:[5,11], cuponAnual:7.50, amort:[], precios:{ars:117200,mep:98.35,cable:97.20}, tir:8.4, dm:3.1, vto:2030, lamina:1000, paridad:98.4, vt:100.0, residual:100, convexidad:11.7, vidaProm:3.6, volumen:6_950_000, puntas:{c:98.15,v:98.55}, ultimo:98.35, varDia:0.08 }),
  rf({ id:'TLC1O', tickers:{ars:'TLC1O',mep:'TLC1D',cable:'TLC1C'}, emisor:'Telecom Argentina', tipo:'ON', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:9.50, freq:'Semestral', meses:[1,7], cuponAnual:9.50, amort:[], precios:{ars:126900,mep:106.50,cable:105.25}, tir:7.9, dm:3.9, vto:2031, lamina:1000, paridad:106.5, vt:100.0, residual:100, convexidad:17.9, vidaProm:4.8, volumen:9_420_000, puntas:{c:106.25,v:106.75}, ultimo:106.50, varDia:-0.06 }),
  rf({ id:'PNDCO', tickers:{ars:'PNDCO',mep:'PNDCD',cable:'PNDCC'}, emisor:'Pan American Energy', tipo:'ON', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:8.50, freq:'Semestral', meses:[3,9], cuponAnual:8.50, amort:[], precios:{ars:124100,mep:104.15,cable:102.95}, tir:7.6, dm:4.2, vto:2032, lamina:1000, paridad:104.2, vt:100.0, residual:100, convexidad:20.4, vidaProm:5.2, volumen:14_180_000, puntas:{c:103.95,v:104.35}, ultimo:104.15, varDia:0.15 }),
  rf({ id:'MRCAO', tickers:{ars:'MRCAO',mep:'MRCAD',cable:'MRCAC'}, emisor:'Mastellone Hermanos', tipo:'ON', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:10.95, freq:'Semestral', meses:[4,10], cuponAnual:10.95, amort:[{mes:10,pct:25}], precios:{ars:128300,mep:107.65,cable:106.40}, tir:9.2, dm:2.1, vto:2029, lamina:1000, paridad:107.7, vt:100.0, residual:75, convexidad:5.6, vidaProm:2.3, volumen:3_640_000, puntas:{c:107.35,v:107.95}, ultimo:107.65, varDia:0.27 }),
  rf({ id:'GNCXO', tickers:{ars:'GNCXO',mep:'GNCXD',cable:'GNCXC'}, emisor:'Generación Mediterránea', tipo:'ON', ley:'Argentina', seg:'hard', estructura:'Tasa fija', tasa:11.25, freq:'Semestral', meses:[5,11], cuponAnual:11.25, amort:[{mes:11,pct:33.3}], precios:{ars:125400,mep:105.20,cable:104.00}, tir:10.6, dm:1.7, vto:2028, lamina:1000, paridad:105.2, vt:100.0, residual:66.7, convexidad:3.9, vidaProm:1.6, volumen:2_910_000, puntas:{c:104.85,v:105.55}, ultimo:105.20, varDia:-0.31 }),
  rf({ id:'AEC1O', tickers:{ars:'AEC1O',mep:'AEC1D',cable:'AEC1C'}, emisor:'Aeropuertos Argentina 2000', tipo:'ON', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:8.50, freq:'Trimestral', meses:[2,5,8,11], cuponAnual:8.50, amort:[{mes:5,pct:10},{mes:11,pct:10}], precios:{ars:121800,mep:102.20,cable:101.05}, tir:8.3, dm:2.8, vto:2031, lamina:1000, paridad:102.2, vt:100.0, residual:80, convexidad:9.8, vidaProm:3.1, volumen:7_260_000, puntas:{c:102.00,v:102.40}, ultimo:102.20, varDia:0.19 }),
  rf({ id:'VSCRO', tickers:{ars:'VSCRO',mep:'VSCRD',cable:'VSCRC'}, emisor:'Vista Energy', tipo:'ON', ley:'Nueva York', seg:'hard', estructura:'Tasa fija', tasa:7.625, freq:'Semestral', meses:[6,12], cuponAnual:7.625, amort:[], precios:{ars:119600,mep:100.35,cable:99.20}, tir:7.5, dm:4.6, vto:2035, lamina:1000, paridad:100.4, vt:100.0, residual:100, convexidad:24.1, vidaProm:5.9, volumen:11_050_000, puntas:{c:100.15,v:100.55}, ultimo:100.35, varDia:0.04 }),
  rf({ id:'CP17O', tickers:{ars:'CP17O',mep:'CP17D',cable:'CP17C'}, emisor:'Compañía Gral. de Combustibles', tipo:'ON', ley:'Argentina', seg:'hard', estructura:'Tasa fija', tasa:9.75, freq:'Trimestral', meses:[3,6,9,12], cuponAnual:9.75, amort:[{mes:12,pct:20}], precios:{ars:123500,mep:103.65,cable:102.45}, tir:9.1, dm:2.4, vto:2030, lamina:1000, paridad:103.7, vt:100.0, residual:80, convexidad:7.2, vidaProm:2.6, volumen:1_980_000, puntas:{c:103.30,v:104.00}, ultimo:103.65, varDia:0.12 }),
  rf({ id:'IRCFO', tickers:{ars:'IRCFO',mep:'IRCFD',cable:'IRCFC'}, emisor:'IRSA', tipo:'ON', ley:'Argentina', seg:'hard', estructura:'Tasa fija', tasa:8.75, freq:'Semestral', meses:[3,9], cuponAnual:8.75, amort:[], precios:{ars:121000,mep:101.55,cable:100.40}, tir:8.6, dm:3.3, vto:2032, lamina:1000, paridad:101.6, vt:100.0, residual:100, convexidad:13.4, vidaProm:3.9, volumen:2_450_000, puntas:{c:101.25,v:101.85}, ultimo:101.55, varDia:-0.09 }),
  rf({ id:'CRCEO', tickers:{ars:'CRCEO',mep:'CRCED',cable:'CRCEC'}, emisor:'Cresud', tipo:'ON', ley:'Argentina', seg:'hard', estructura:'Tasa fija', tasa:9.00, freq:'Semestral', meses:[4,10], cuponAnual:9.00, amort:[], precios:{ars:120200,mep:100.90,cable:99.75}, tir:8.8, dm:2.9, vto:2031, lamina:1000, paridad:100.9, vt:100.0, residual:100, convexidad:10.9, vidaProm:3.4, volumen:null, puntas:{c:100.40,v:101.40}, ultimo:100.90, varDia:null }),
  rf({ id:'LOC3O', tickers:{ars:'LOC3O',mep:'LOC3D',cable:'LOC3C'}, emisor:'Loma Negra', tipo:'ON', ley:'Argentina', seg:'hard', estructura:'Step up', tasa:7.00, freq:'Semestral', meses:[6,12], cuponAnual:7.00, amort:[], precios:{ars:116400,mep:97.65,cable:96.55}, tir:8.0, dm:3.0, vto:2031, lamina:1000, paridad:97.7, vt:100.0, residual:100, convexidad:null, vidaProm:3.5, volumen:890_000, puntas:{c:97.20,v:98.10}, ultimo:97.65, varDia:0.02 }),
  rf({ id:'PECFO', tickers:{ars:'PECFO',mep:'PECFD',cable:'PECFC'}, emisor:'Petroquímica Comodoro Rivadavia', tipo:'ON', ley:'Argentina', seg:'hard', estructura:'Tasa fija', tasa:8.00, freq:'Trimestral', meses:[1,4,7,10], cuponAnual:8.00, amort:[{mes:7,pct:12.5}], precios:{ars:118900,mep:99.75,cable:98.60}, tir:8.7, dm:2.3, vto:2030, lamina:1000, paridad:99.8, vt:100.0, residual:87.5, convexidad:6.4, vidaProm:2.5, volumen:1_320_000, puntas:{c:99.40,v:100.10}, ultimo:99.75, varDia:0.07 }),
  // ── CER ───────────────────────────────────────────────────────────────────
  rf({ id:'TZXD6', tickers:{ars:'TZXD6',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'cer', estructura:'Cupón cero', tasa:0, freq:'Al vencimiento', meses:[12], cuponAnual:0, amort:[{mes:12,pct:100}], precios:{ars:1_486.50,mep:null,cable:null}, tir:6.4, dm:0.4, vto:2026, lamina:1, paridad:99.1, vt:1500.2, residual:100, convexidad:0.3, vidaProm:0.4, volumen:9_820_000_000, puntas:{c:1485.00,v:1488.00}, ultimo:1486.50, varDia:0.21 }),
  rf({ id:'TZX27', tickers:{ars:'TZX27',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'cer', estructura:'Cupón cero', tasa:0, freq:'Al vencimiento', meses:[6], cuponAnual:0, amort:[{mes:6,pct:100}], precios:{ars:1_142.80,mep:null,cable:null}, tir:7.9, dm:1.6, vto:2027, lamina:1, paridad:97.4, vt:1173.1, residual:100, convexidad:2.9, vidaProm:1.6, volumen:6_140_000_000, puntas:{c:1141.50,v:1144.00}, ultimo:1142.80, varDia:-0.14 }),
  rf({ id:'TX31', tickers:{ars:'TX31',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'cer', estructura:'Tasa fija + CER', tasa:2.00, freq:'Semestral', meses:[3,9], cuponAnual:2.00, amort:[{mes:3,pct:5},{mes:9,pct:5}], precios:{ars:928.40,mep:null,cable:null}, tir:9.2, dm:3.8, vto:2031, lamina:1, paridad:92.8, vt:1000.4, residual:90, convexidad:17.2, vidaProm:4.1, volumen:2_390_000_000, puntas:{c:926.00,v:930.50}, ultimo:928.40, varDia:0.33 }),
  // ── Tasa fija en pesos ────────────────────────────────────────────────────
  rf({ id:'S30J6', tickers:{ars:'S30J6',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'fija', estructura:'Cupón cero (Lecap)', tasa:0, freq:'Al vencimiento', meses:[6], cuponAnual:0, amort:[{mes:6,pct:100}], precios:{ars:158.90,mep:null,cable:null}, tir:31.4, dm:0.9, vto:2027, lamina:1, paridad:null, vt:null, residual:100, convexidad:1.1, vidaProm:0.9, volumen:41_200_000_000, puntas:{c:158.70,v:159.10}, ultimo:158.90, varDia:0.18 }),
  rf({ id:'T17O6', tickers:{ars:'T17O6',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'fija', estructura:'Cupón cero (Boncap)', tasa:0, freq:'Al vencimiento', meses:[10], cuponAnual:0, amort:[{mes:10,pct:100}], precios:{ars:139.25,mep:null,cable:null}, tir:29.8, dm:0.2, vto:2026, lamina:1, paridad:null, vt:null, residual:100, convexidad:0.1, vidaProm:0.2, volumen:63_800_000_000, puntas:{c:139.15,v:139.35}, ultimo:139.25, varDia:0.09 }),
  rf({ id:'TO28', tickers:{ars:'TO28',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'fija', estructura:'Tasa fija', tasa:19.00, freq:'Semestral', meses:[4,10], cuponAnual:19.00, amort:[{mes:10,pct:50}], precios:{ars:104.60,mep:null,cable:null}, tir:33.2, dm:1.3, vto:2028, lamina:1, paridad:null, vt:null, residual:100, convexidad:2.4, vidaProm:1.4, volumen:4_710_000_000, puntas:{c:104.30,v:104.90}, ultimo:104.60, varDia:-0.26 }),
  // ── Dólar linked ──────────────────────────────────────────────────────────
  rf({ id:'TZVD6', tickers:{ars:'TZVD6',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'dlk', estructura:'Cupón cero', tasa:0, freq:'Al vencimiento', meses:[12], cuponAnual:0, amort:[{mes:12,pct:100}], precios:{ars:1_398.20,mep:null,cable:null}, tir:1.9, dm:0.4, vto:2026, lamina:1, paridad:99.4, vt:1406.5, residual:100, convexidad:0.3, vidaProm:0.4, volumen:5_270_000_000, puntas:{c:1396.00,v:1400.50}, ultimo:1398.20, varDia:0.44 }),
  rf({ id:'D31M7', tickers:{ars:'D31M7',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'dlk', estructura:'Cupón cero', tasa:0, freq:'Al vencimiento', meses:[3], cuponAnual:0, amort:[{mes:3,pct:100}], precios:{ars:1_312.60,mep:null,cable:null}, tir:3.6, dm:0.6, vto:2027, lamina:1, paridad:98.2, vt:1336.7, residual:100, convexidad:0.6, vidaProm:0.6, volumen:2_840_000_000, puntas:{c:1310.00,v:1315.00}, ultimo:1312.60, varDia:0.29 }),
  // ── Badlar / Tamar ────────────────────────────────────────────────────────
  rf({ id:'PBY26', tickers:{ars:'PBY26',mep:null,cable:null}, emisor:'Provincia de Buenos Aires', tipo:'Subsoberano', ley:'Argentina', seg:'badlar', estructura:'Badlar + margen', tasa:5.50, freq:'Trimestral', meses:[2,5,8,11], cuponAnual:34.20, amort:[{mes:5,pct:25},{mes:11,pct:25}], precios:{ars:102.30,mep:null,cable:null}, tir:null, dm:0.7, vto:2027, lamina:1, paridad:null, vt:null, residual:50, convexidad:null, vidaProm:0.8, volumen:1_640_000_000, puntas:{c:102.00,v:102.60}, ultimo:102.30, varDia:0.11 }),
  rf({ id:'BDC28', tickers:{ars:'BDC28',mep:null,cable:null}, emisor:'Provincia de Córdoba', tipo:'Subsoberano', ley:'Argentina', seg:'badlar', estructura:'Badlar + margen', tasa:4.00, freq:'Trimestral', meses:[1,4,7,10], cuponAnual:32.70, amort:[{mes:7,pct:20}], precios:{ars:99.80,mep:null,cable:null}, tir:null, dm:0.9, vto:2028, lamina:1, paridad:null, vt:null, residual:80, convexidad:null, vidaProm:1.1, volumen:null, puntas:{c:99.30,v:100.30}, ultimo:99.80, varDia:null }),
  rf({ id:'M31G6', tickers:{ars:'M31G6',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'tamar', estructura:'Tamar + margen', tasa:2.25, freq:'Trimestral', meses:[2,5,8,11], cuponAnual:30.90, amort:[{mes:8,pct:100}], precios:{ars:101.40,mep:null,cable:null}, tir:null, dm:0.5, vto:2027, lamina:1, paridad:null, vt:null, residual:100, convexidad:null, vidaProm:0.5, volumen:12_900_000_000, puntas:{c:101.20,v:101.60}, ultimo:101.40, varDia:0.16 }),
  rf({ id:'TTM27', tickers:{ars:'TTM27',mep:null,cable:null}, emisor:'República Argentina', tipo:'Soberano', ley:'Argentina', seg:'tamar', estructura:'Tamar + margen', tasa:1.75, freq:'Trimestral', meses:[3,6,9,12], cuponAnual:30.40, amort:[{mes:12,pct:100}], precios:{ars:100.70,mep:null,cable:null}, tir:null, dm:0.8, vto:2027, lamina:1, paridad:null, vt:null, residual:100, convexidad:null, vidaProm:0.8, volumen:7_450_000_000, puntas:{c:100.50,v:100.90}, ultimo:100.70, varDia:-0.08 }),
];

const rv = (o) => ({ clase: 'RV', seg: 'rv', ...o });

// Renta variable: sin TIR, sin duración, sin cupones. El equivalente de calendario
// son las fechas de presentación de balances trimestrales (`balances`).
export const RENTA_VARIABLE = [
  rv({ id:'GGAL', tipo:'Acción', tickers:{ars:'GGAL',mep:'GGALD',cable:'GGALC'}, emisor:'Grupo Financiero Galicia', industria:'Bancos', precios:{ars:9_840,mep:8.25,cable:8.14}, balances:[2,5,8,11], lamina:1, volumen:38_400_000_000, puntas:{c:9825,v:9855}, ultimo:9840, varDia:1.64, apertura:9700, max:9880, min:9690, cierreAnt:9681, ordenes:4_182, dividendo:'Anual (abr)' }),
  rv({ id:'YPFD', tipo:'Acción', tickers:{ars:'YPFD',mep:'YPFDD',cable:'YPFDC'}, emisor:'YPF S.A.', industria:'Energía', precios:{ars:44_150,mep:37.00,cable:36.55}, balances:[3,5,8,11], lamina:1, volumen:29_100_000_000, puntas:{c:44050,v:44250}, ultimo:44150, varDia:-0.82, apertura:44500, max:44700, min:43900, cierreAnt:44515, ordenes:3_004, dividendo:'s/d' }),
  rv({ id:'PAMP', tipo:'Acción', tickers:{ars:'PAMP',mep:'PAMPD',cable:'PAMPC'}, emisor:'Pampa Energía', industria:'Energía', precios:{ars:6_720,mep:5.63,cable:5.56}, balances:[3,5,8,11], lamina:1, volumen:21_800_000_000, puntas:{c:6710,v:6730}, ultimo:6720, varDia:0.91, apertura:6650, max:6745, min:6640, cierreAnt:6659, ordenes:2_741, dividendo:'Anual (may)' }),
  rv({ id:'BMA', tipo:'Acción', tickers:{ars:'BMA',mep:'BMAD',cable:'BMAC'}, emisor:'Banco Macro', industria:'Bancos', precios:{ars:13_950,mep:11.70,cable:11.55}, balances:[3,5,8,11], lamina:1, volumen:14_600_000_000, puntas:{c:13920,v:13980}, ultimo:13950, varDia:1.12, apertura:13800, max:14000, min:13780, cierreAnt:13795, ordenes:1_960, dividendo:'Anual (abr)' }),
  rv({ id:'TXAR', tipo:'Acción', tickers:{ars:'TXAR',mep:'TXARD',cable:'TXARC'}, emisor:'Ternium Argentina', industria:'Materiales', precios:{ars:1_082,mep:0.91,cable:0.90}, balances:[2,4,7,10], lamina:1, volumen:6_300_000_000, puntas:{c:1080,v:1084}, ultimo:1082, varDia:-1.36, apertura:1098, max:1101, min:1078, cierreAnt:1097, ordenes:1_204, dividendo:'Anual (may)' }),
  rv({ id:'LOMA', tipo:'Acción', tickers:{ars:'LOMA',mep:'LOMAD',cable:'LOMAC'}, emisor:'Loma Negra', industria:'Materiales', precios:{ars:2_945,mep:2.47,cable:2.44}, balances:[3,5,8,11], lamina:1, volumen:4_120_000_000, puntas:{c:2938,v:2952}, ultimo:2945, varDia:0.44, apertura:2930, max:2960, min:2925, cierreAnt:2932, ordenes:842, dividendo:'s/d' }),
  rv({ id:'CRES', tipo:'Acción', tickers:{ars:'CRES',mep:'CRESD',cable:'CRESC'}, emisor:'Cresud', industria:'Agro', precios:{ars:2_186,mep:1.83,cable:1.81}, balances:[2,5,9,11], lamina:1, volumen:2_890_000_000, puntas:{c:2180,v:2192}, ultimo:2186, varDia:0.28, apertura:2178, max:2198, min:2172, cierreAnt:2180, ordenes:611, dividendo:'Anual (oct)' }),
  rv({ id:'ALUA', tipo:'Acción', tickers:{ars:'ALUA',mep:'ALUAD',cable:'ALUAC'}, emisor:'Aluar', industria:'Materiales', precios:{ars:1_318,mep:1.11,cable:1.09}, balances:[2,5,8,11], lamina:1, volumen:null, puntas:{c:1312,v:1324}, ultimo:1318, varDia:null, apertura:1315, max:1326, min:1310, cierreAnt:1318, ordenes:null, dividendo:'s/d' }),
  rv({ id:'AAPL', tipo:'CEDEAR', tickers:{ars:'AAPL',mep:'AAPLD',cable:'AAPLC'}, emisor:'Apple Inc. (CEDEAR, ratio 20:1)', industria:'Tecnología', precios:{ars:16_480,mep:13.82,cable:13.65}, balances:[2,5,8,11], lamina:1, volumen:9_700_000_000, puntas:{c:16450,v:16510}, ultimo:16480, varDia:0.63, apertura:16400, max:16530, min:16380, cierreAnt:16377, ordenes:2_310, dividendo:'Trimestral' }),
  rv({ id:'GOOGL', tipo:'CEDEAR', tickers:{ars:'GOOGL',mep:'GOOGLD',cable:'GOOGLC'}, emisor:'Alphabet Inc. (CEDEAR, ratio 58:1)', industria:'Tecnología', precios:{ars:11_240,mep:9.42,cable:9.30}, balances:[2,4,7,10], lamina:1, volumen:7_140_000_000, puntas:{c:11220,v:11260}, ultimo:11240, varDia:1.08, apertura:11150, max:11280, min:11130, cierreAnt:11120, ordenes:1_884, dividendo:'Trimestral' }),
  rv({ id:'KO', tipo:'CEDEAR', tickers:{ars:'KO',mep:'KOD',cable:'KOC'}, emisor:'Coca-Cola Co. (CEDEAR, ratio 5:1)', industria:'Consumo', precios:{ars:8_960,mep:7.51,cable:7.42}, balances:[2,4,7,10], lamina:1, volumen:3_260_000_000, puntas:{c:8945,v:8975}, ultimo:8960, varDia:0.21, apertura:8940, max:8980, min:8930, cierreAnt:8941, ordenes:1_042, dividendo:'Trimestral' }),
  rv({ id:'BRKB', tipo:'CEDEAR', tickers:{ars:'BRKB',mep:'BRKBD',cable:'BRKBC'}, emisor:'Berkshire Hathaway (CEDEAR, ratio 30:1)', industria:'Financiero', precios:{ars:19_720,mep:16.53,cable:16.33}, balances:[2,5,8,11], lamina:1, volumen:2_480_000_000, puntas:{c:19680,v:19760}, ultimo:19720, varDia:0.37, apertura:19650, max:19790, min:19630, cierreAnt:19647, ordenes:730, dividendo:'No paga' }),
];

export const UNIVERSO = [...RENTA_FIJA, ...RENTA_VARIABLE];
export const porId = Object.fromEntries(UNIVERSO.map(i => [i.id, i]));

export const NUMEROS_DEL_DIA = [
  { rot:'Dólar MEP',      val:'$1.192,40', var:0.38,  fuente:'AL30 / AL30D' },
  { rot:'Dólar cable',    val:'$1.207,90', var:0.44,  fuente:'AL30 / AL30C' },
  { rot:'Canje MEP/CCL',  val:'1,30%',     var:0.06,  fuente:'AL30D / AL30C' },
  { rot:'Mayor volumen',  val:'AL30D',     var:0.72,  fuente:'US$ 148,6 M operados' },
  { rot:'Mayor subida',   val:'NDT27',     var:1.41,  fuente:'96,25 vs 94,91' },
  { rot:'Mayor baja',     val:'GNCXO',     var:-0.31, fuente:'105,20 vs 105,53' },
];

// ── Motor de cálculo ────────────────────────────────────────────────────────

/**
 * Puntas (compra/venta) de la ESPECIE operada en esa moneda. Cada moneda es un
 * ticker distinto con su propio book: nunca se reusa el book de otra especie.
 * Devuelve null cuando esa especie no cotiza (la interfaz debe mostrar "s/d").
 */
export function puntasDe(inst, mon = 'mep') {
  const px = inst.precios[mon];
  if (px == null || !inst.tickers[mon]) return null;
  if (Math.abs(px - inst.ultimo) < 1e-9) return inst.puntas;
  const sp = mon === 'cable' ? 0.0070 : mon === 'ars' ? 0.0040 : 0.0045;
  const d = mon === 'ars' && px > 1000 ? 0 : 2;
  const red = (v) => Number(v.toFixed(d));
  return { c: red(px * (1 - sp / 2)), v: red(px * (1 + sp / 2)) };
}

/** Precio del instrumento en la moneda de operación elegida. null si no cotiza ahí. */
export const precio = (inst, mon = 'mep') => inst.precios[mon] ?? null;
export const ticker = (inst, mon = 'mep') => inst.tickers[mon] ?? null;

/**
 * Resuelve una cartera: reparte `monto` según pesos deseados, redondea el valor
 * nominal hacia abajo al múltiplo de la lámina mínima y devuelve el peso REAL.
 * posiciones: [{id, peso}] con peso en %.
 */
export function resolver(posiciones, monto, mon = 'mep') {
  const filas = posiciones.map(p => {
    const inst = porId[p.id];
    const px = precio(inst, mon);
    if (px == null) return { ...p, inst, px: null, vn: 0, invertido: 0, sinCotizar: true };
    const objetivo = monto * (p.peso / 100);
    const lam = inst.lamina || 1;
    const vnBruto = objetivo / (px / 100);
    const vn = Math.floor(vnBruto / lam) * lam;
    const invertido = vn * px / 100;
    return { ...p, inst, px, vn, invertido, sinCotizar: false };
  });
  const invertido = filas.reduce((a, f) => a + f.invertido, 0);
  filas.forEach(f => { f.pesoReal = invertido ? (f.invertido / invertido) * 100 : 0; });
  const rfFilas = filas.filter(f => f.inst.clase === 'RF' && f.invertido > 0);
  const invRF = rfFilas.reduce((a, f) => a + f.invertido, 0);
  const pesoRV = invertido ? (invertido - invRF) / invertido * 100 : 0;
  // TIR y duración ponderadas SOLO dentro del segmento dólar hard: no se promedian
  // rendimientos de distinta naturaleza (regla 1). Los demás segmentos se informan aparte.
  const hard = rfFilas.filter(f => f.inst.seg === 'hard' && f.inst.tir != null);
  const invHard = hard.reduce((a, f) => a + f.invertido, 0);
  const tirHard = invHard ? hard.reduce((a, f) => a + f.inst.tir * f.invertido, 0) / invHard : null;
  const dmHard = invHard ? hard.reduce((a, f) => a + f.inst.dm * f.invertido, 0) / invHard : null;
  const otrosSeg = [...new Set(rfFilas.filter(f => f.inst.seg !== 'hard').map(f => f.inst.seg))];

  const meses = MESES.map((nom, i) => {
    const m = i + 1;
    const renta = [], amortiz = [];
    rfFilas.forEach(f => {
      const { inst, vn } = f;
      if (inst.meses.includes(m) && inst.cuponAnual > 0) {
        const pagos = inst.meses.length;
        const monto = vn * (inst.cuponAnual / 100) / pagos * (inst.residual / 100);
        if (monto > 0) renta.push({ id: inst.id, tk: ticker(inst, mon), monto });
      }
      (inst.amort || []).forEach(a => {
        if (a.mes === m) amortiz.push({ id: inst.id, tk: ticker(inst, mon), monto: vn * a.pct / 100 });
      });
    });
    const balances = filas.filter(f => f.inst.clase === 'RV' && f.inst.balances.includes(m))
      .map(f => ({ id: f.inst.id, tk: ticker(f.inst, mon) }));
    return {
      mes: m, nom, renta, amortiz, balances,
      totalRenta: renta.reduce((a, r) => a + r.monto, 0),
      totalAmort: amortiz.reduce((a, r) => a + r.monto, 0),
    };
  });
  const rentaAnual = meses.reduce((a, m) => a + m.totalRenta, 0);
  const picoRenta = Math.max(1e-9, ...meses.map(m => m.totalRenta));
  const cubiertos = meses.filter(m => m.totalRenta > 0).length;
  const vacios = meses.filter(m => m.totalRenta === 0).map(m => m.nom);
  const prom = rentaAnual / 12;
  // Dispersión del calendario: 0 = perfectamente parejo, 1 = todo en un mes.
  const gini = rentaAnual > 0
    ? meses.reduce((a, m) => a + Math.abs(m.totalRenta - prom), 0) / (2 * rentaAnual) * (12 / 11)
    : 0;

  return {
    filas, invertido, monto, mon, meses, rentaAnual, picoRenta, cubiertos, vacios,
    parejo: Math.round((1 - gini) * 100),
    rentaSobreInvertido: invertido ? rentaAnual / invertido * 100 : 0,
    pesoRF: 100 - pesoRV, pesoRV, tirHard, dmHard, otrosSeg,
    sumaPesos: posiciones.reduce((a, p) => a + p.peso, 0),
    remanente: monto - invertido,
  };
}

// ── Formato (es-AR) ─────────────────────────────────────────────────────────
const nf = (d) => new Intl.NumberFormat('es-AR', { minimumFractionDigits: d, maximumFractionDigits: d });
export const n0 = (v) => v == null ? 's/d' : nf(0).format(v);
export const n1 = (v) => v == null ? 's/d' : nf(1).format(v);
export const n2 = (v) => v == null ? 's/d' : nf(2).format(v);
export const usd = (v, d = 2) => v == null ? 's/d' : 'US$ ' + nf(d).format(v);
export const ars = (v, d = 0) => v == null ? 's/d' : '$ ' + nf(d).format(v);
export const pct = (v, d = 1) => v == null ? 's/d' : nf(d).format(v) + '%';
export const compacto = (v) => {
  if (v == null) return 's/d';
  const a = Math.abs(v);
  if (a >= 1e9) return nf(1).format(v / 1e9) + ' MM';
  if (a >= 1e6) return nf(1).format(v / 1e6) + ' M';
  if (a >= 1e3) return nf(0).format(v / 1e3) + ' mil';
  return nf(0).format(v);
};

// ── Carteras de ejemplo ─────────────────────────────────────────────────────

/** Cartera que trae el cliente: concentrada en enero y julio, el problema típico. */
export const CARTERA_HEREDADA = [
  { id:'AL30',  peso:22 }, { id:'GD30',  peso:18 }, { id:'GD35', peso:14 },
  { id:'TLC1O', peso:12 }, { id:'PECFO', peso:8 },
  { id:'GGAL',  peso:14 }, { id:'AAPL',  peso:12 },
];

/** Borrador que el sistema propone cuando se declara un objetivo de renta mensual. */
export const CARTERA_PROPUESTA = [
  { id:'YMCJO', peso:12 }, { id:'PNDCO', peso:11 }, { id:'MRCAO', peso:10 },
  { id:'YFCJO', peso:10 }, { id:'VSCRO', peso:9 },  { id:'AEC1O', peso:9 },
  { id:'GD38',  peso:8 },  { id:'CO27D', peso:7 },
  { id:'GGAL',  peso:8 },  { id:'PAMP',  peso:6 },  { id:'AAPL', peso:6 }, { id:'BRKB', peso:4 },
];

export const CLIENTES = [
  { id:'gv', nom:'Graciela Vázquez', perfil:'Conservador', monto:100_000, moneda:'USD', horizonte:'5 años',
    objetivo:'Renta mensual estable en dólares para complementar jubilación',
    cubrir:['Devaluación', 'Inflación local', 'Riesgo soberano'],
    evitar:['Ley Argentina en más del 20%'], objetivoMensual:550, tieneCartera:true },
  { id:'mf', nom:'Fideicomiso Marbella', perfil:'Moderado', monto:450_000, moneda:'USD', horizonte:'3 años',
    objetivo:'Preservar capital con flujo trimestral previsible',
    cubrir:['Devaluación','Riesgo soberano'], evitar:['Provinciales'], objetivoMensual:3_200, tieneCartera:false },
  { id:'ha', nom:'Hernán Aguirre', perfil:'Agresivo declarado', monto:60_000, moneda:'USD', horizonte:'8 años',
    objetivo:'Crecimiento con piso de renta; acepta 40% renta variable',
    cubrir:['Inflación local'], evitar:[], objetivoMensual:350, tieneCartera:true },
];
