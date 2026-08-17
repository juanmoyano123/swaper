-- Valor técnico y residual, calculados — para saber si un bono ya amortizó y si cotiza caro o
-- barato contra su propio valor técnico (pedido del 17/08/2026).
--
-- `residual_value` ya existía en `precios` (venía de IAMC, pausado, NULL en todo el universo) y
-- ya se exponía en la vista como `residualValue`. Lo que agrega esta migración es la columna
-- nueva `valor_tecnico` y cambia de dónde sale `residual_value`: desde ahora es cálculo propio
-- —residual vigente + cupón corrido, derivado del cronograma contractual persistido en
-- `public.cashflow`— para toda especie de renta fija con cronograma, no sólo IAMC. Ver
-- `app/calendario/cupones.py::componentes_valor_tecnico` y el chequeo de coherencia que la
-- acompaña: 29 de 816 emisiones tienen el residual declarado clavado en 100 mientras amortizan
-- (contradice `100 - Σ capital` de la misma tabla) y para esas el cálculo deja el campo vacío en
-- vez de publicar un valor técnico sobreestimado (alerta `residual_contradictorio`).
--
-- `valor_tecnico` no tiene fuente IAMC equivalente: el informe trae un campo VT, pero
-- `app/ingesta/iamc/parser.py` lo parsea y `armado.py` nunca lo persiste. Cálculo propio es la
-- única fuente que existió nunca para esta columna.
--
-- Rollback: supabase/rollbacks/20260817180000_valor_tecnico_residual_down.sql

ALTER TABLE public.precios ADD COLUMN valor_tecnico numeric;

COMMENT ON COLUMN public.precios.valor_tecnico IS
    'Residual vigente + cupón corrido, cada 100 nominales — el denominador de paridad. Siempre '
    'cálculo propio (`componentes_valor_tecnico`), nunca de IAMC: el campo VT del informe se '
    'parsea y se descarta. NULL en toda corrida anterior a esta migración, en cualquier especie '
    'sin cronograma, en un bono ya vencido, y en las emisiones cuyo residual declarado contradice '
    'la suma de amortizaciones ya pagadas (alerta residual_contradictorio).';

COMMENT ON COLUMN public.precios.residual_value IS
    'Cuánto capital queda vivo hoy, cada 100 nominales. Cálculo propio desde el 17/08/2026 '
    '(`componentes_valor_tecnico`, contractual: no depende de la moneda de cotización, así que se '
    'calcula para toda especie con cronograma aunque no sea calculable por tir/paridad — CER, '
    'moneda cruzada). Antes de esta migración venía de IAMC (pausado) y era NULL en casi todo el '
    'universo; una especie sin cronograma sigue cayendo a esa fuente si IAMC se reactiva. NULL '
    'también en las 29 emisiones con residual declarado incoherente contra la suma de '
    'amortizaciones (alerta residual_contradictorio) — se prefiere vacío antes que un residual '
    'que la propia fuente contradice en la misma tabla.';

-- Al final: CREATE OR REPLACE VIEW sólo admite agregar columnas al final, y los lectores
-- existentes leen por nombre, así que pasar de 29 a 30 columnas no rompe a nadie.
CREATE OR REPLACE VIEW public.resumen
WITH (security_invoker = true) AS
SELECT
    i.ticker,
    i.clase_activo,
    i.tipo_tasa,
    i.subtipo,
    i.underlying,
    i.sector,
    p.tir,
    p.tna,
    p.duration,
    i.maturity,
    i.law,
    i.coupon_currency  AS "couponCurrency",
    i.lamina,
    i.calificacion,
    p.paridad,
    p.residual_value   AS "residualValue",
    p.last_price       AS "lastPrice",
    p.effective_volume AS "effectiveVolume",
    i.revisar,
    i.duplicado,
    i.archivo_origen,
    p.cierre_anterior,
    p.fuente,
    p.precio_apertura,
    p.precio_maximo,
    p.precio_minimo,
    p.vwap,
    p.capturado_en,
    p.fecha_metricas,
    p.valor_tecnico
FROM public.instrumentos i
LEFT JOIN LATERAL (
    SELECT *
    FROM public.precios pr
    WHERE pr.ticker = i.ticker
    ORDER BY pr.capturado_en DESC
    LIMIT 1
) p ON true;
