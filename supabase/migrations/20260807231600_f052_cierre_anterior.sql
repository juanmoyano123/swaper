-- F-052 · El cierre anterior que BYMA publica y la consolidación descartaba.
--
-- `previousClosingPrice` ya llega normalizado (FilaRueda.precio_cierre_anterior) y se tiraba al
-- persistir. Se guarda porque es dato publicado, no derivado: la variación del monitor se calcula
-- (precio - cierre_anterior) / cierre_anterior sólo donde ambos existen, y donde falta queda
-- vacía y contada — nunca se estima desde el histórico propio de `precios`.
--
-- Rollback: supabase/rollbacks/20260807231600_f052_cierre_anterior_down.sql

ALTER TABLE public.precios ADD COLUMN cierre_anterior numeric;

COMMENT ON COLUMN public.precios.cierre_anterior IS
    'previousClosingPrice de BYMA, en la moneda de cotización de la especie. NULL hasta la '
    'primera corrida posterior a esta migración: las filas históricas no lo tienen y no se '
    'rellena hacia atrás.';

-- La vista se reemplaza agregando la columna AL FINAL: CREATE OR REPLACE VIEW sólo admite
-- columnas nuevas al final, y los lectores existentes (motor incluido) leen por nombre, así que
-- pasar de 21 a 22 columnas no rompe a nadie.
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
    p.cierre_anterior
FROM public.instrumentos i
LEFT JOIN LATERAL (
    SELECT *
    FROM public.precios pr
    WHERE pr.ticker = i.ticker
    ORDER BY pr.capturado_en DESC
    LIMIT 1
) p ON true;
