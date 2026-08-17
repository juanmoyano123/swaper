-- Rollback de 20260817180000_valor_tecnico_residual.sql
--
-- Recrea la vista con las 29 columnas anteriores (sin `valor_tecnico`), restaura el comentario
-- previo de `residual_value` (fuente IAMC) y quita la columna `valor_tecnico` de `precios`.
-- `CREATE OR REPLACE VIEW` y no `DROP` + `CREATE`, mismo motivo que los rollbacks anteriores de
-- esta vista: el guardián estructural de `test_migraciones.py` sólo cuenta como "creado por esta
-- migración" lo que aparece en un `CREATE TABLE|VIEW` literal.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

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
    p.fecha_metricas
FROM public.instrumentos i
LEFT JOIN LATERAL (
    SELECT *
    FROM public.precios pr
    WHERE pr.ticker = i.ticker
    ORDER BY pr.capturado_en DESC
    LIMIT 1
) p ON true;

-- `residual_value` nunca tuvo un COMMENT propio antes de esta migración (verificado contra la
-- base real el 17/08/2026): se restaura a sin comentario, no se inventa uno.
COMMENT ON COLUMN public.precios.residual_value IS NULL;

ALTER TABLE public.precios DROP COLUMN valor_tecnico;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260817180000';
