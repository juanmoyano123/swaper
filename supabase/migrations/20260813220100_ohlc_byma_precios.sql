-- El OHLC de BYMA que la consolidación descartaba.
--
-- BYMA publica `openingPrice`, `tradingHighPrice`, `tradingLowPrice` y `vwap` en cada renglón, y
-- `byma/normalizacion.py` ya los lee (`FilaRueda.precio_apertura/precio_maximo/precio_minimo/
-- vwap`) — pero `consolidacion/armado.py` nunca los ponía en la fila de `precios`, así que se
-- tiraban. Son el máximo y el mínimo del día que la ficha de renta variable le pedía a Yahoo
-- Finance sin necesidad: ya nos llegan.
--
-- **Siempre son de BYMA, aunque `precios.fuente` diga data912.** El overlay
-- (`consolidacion/overlay.py`, `CAMPOS_PISADOS`) pisa el último precio, las puntas y las
-- operaciones con lo que trae data912, pero no toca apertura/máximo/mínimo/vwap: no están en su
-- lista de campos pisados, y las filas que llegan sólo por data912 (`_agregar_solo_data912`) no
-- traen ninguno de los cuatro. Leer la procedencia de estos cuatro campos desde `fuente` sería un
-- error — por eso queda dicho acá y en el `COMMENT ON COLUMN`.
--
-- Rollback: supabase/rollbacks/20260813220100_ohlc_byma_precios_down.sql

ALTER TABLE public.precios ADD COLUMN precio_apertura numeric;
ALTER TABLE public.precios ADD COLUMN precio_maximo numeric;
ALTER TABLE public.precios ADD COLUMN precio_minimo numeric;
ALTER TABLE public.precios ADD COLUMN vwap numeric;

COMMENT ON COLUMN public.precios.precio_apertura IS
    'openingPrice de BYMA, en la moneda de cotización de la especie. Siempre de BYMA: el overlay '
    'de data912 no lo pisa. NULL hasta la primera corrida posterior a esta migración y en toda '
    'fila cuyo precio vino sólo de data912; no se rellena hacia atrás ni se deriva.';

COMMENT ON COLUMN public.precios.precio_maximo IS
    'tradingHighPrice de BYMA, en la moneda de cotización de la especie. Siempre de BYMA: el '
    'overlay de data912 no lo pisa. Mismas condiciones de NULL que precio_apertura.';

COMMENT ON COLUMN public.precios.precio_minimo IS
    'tradingLowPrice de BYMA, en la moneda de cotización de la especie. Siempre de BYMA: el '
    'overlay de data912 no lo pisa. Mismas condiciones de NULL que precio_apertura.';

COMMENT ON COLUMN public.precios.vwap IS
    'vwap de BYMA (precio promedio ponderado por volumen de la rueda), en la moneda de cotización '
    'de la especie. Siempre de BYMA: el overlay de data912 no lo pisa. Mismas condiciones de NULL '
    'que precio_apertura. Un VWAP de 0 se guarda como NULL (regla del módulo: la especie no operó, '
    'no cotizó a cero).';

-- Las cuatro van AL FINAL: CREATE OR REPLACE VIEW sólo admite agregar columnas al final, y los
-- lectores existentes leen por nombre, así que pasar de 23 a 27 columnas no rompe a nadie.
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
    p.vwap
FROM public.instrumentos i
LEFT JOIN LATERAL (
    SELECT *
    FROM public.precios pr
    WHERE pr.ticker = i.ticker
    ORDER BY pr.capturado_en DESC
    LIMIT 1
) p ON true;
