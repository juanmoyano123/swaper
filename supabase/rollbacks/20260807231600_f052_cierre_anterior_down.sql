-- Rollback de 20260807231600_f052_cierre_anterior.sql
--
-- Recrea la vista con las 21 columnas originales y saca la columna de la tabla.
--
-- `CREATE OR REPLACE VIEW` y no `DROP` + `CREATE`: la migración de subida tampoco dropea la vista
-- (la reemplaza), así que el guardián estructural de `test_migraciones.py` —que sólo cuenta como
-- "creado por esta migración" lo que aparece en un `CREATE TABLE|VIEW` literal— vería un `DROP
-- VIEW public.resumen` acá como si tirara abajo algo que esta migración nunca creó. Revertir en el
-- mismo modo que se avanzó evita esa falsa alarma y de paso es más seguro: no hay una ventana sin
-- la vista entre el DROP y el CREATE.
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
    i.archivo_origen
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

ALTER TABLE public.precios DROP COLUMN cierre_anterior;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260807231600';
