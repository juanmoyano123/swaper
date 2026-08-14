-- Rollback de 20260813220100_ohlc_byma_precios.sql
--
-- Recrea la vista con las 23 columnas previas y saca las cuatro columnas de la tabla.
--
-- `CREATE OR REPLACE VIEW` y no `DROP` + `CREATE`, mismo criterio que los rollbacks anteriores: la
-- migración de subida tampoco dropea la vista, así que el guardián de `test_migraciones.py` no
-- vería acá un `DROP VIEW` de algo que esta migración nunca creó.
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
    p.fuente
FROM public.instrumentos i
LEFT JOIN LATERAL (
    SELECT *
    FROM public.precios pr
    WHERE pr.ticker = i.ticker
    ORDER BY pr.capturado_en DESC
    LIMIT 1
) p ON true;

COMMENT ON VIEW public.resumen IS
    'Contrato de lectura del motor: las 21 columnas de la hoja Resumen. Ver docs/esquema-datos.md.';

ALTER TABLE public.precios DROP COLUMN precio_apertura;
ALTER TABLE public.precios DROP COLUMN precio_maximo;
ALTER TABLE public.precios DROP COLUMN precio_minimo;
ALTER TABLE public.precios DROP COLUMN vwap;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260813220100';
