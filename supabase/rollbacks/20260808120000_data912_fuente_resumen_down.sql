-- Rollback de 20260808120000_data912_fuente_resumen.sql
--
-- Recrea la vista con las 22 columnas de F-052 (sin `fuente`) y restaura el comentario anterior
-- de `precios.fuente`. `CREATE OR REPLACE VIEW` y no `DROP` + `CREATE`, mismo motivo que el
-- rollback de F-052: la migración de subida tampoco dropea la vista, y el guardián estructural de
-- `test_migraciones.py` sólo cuenta como "creado por esta migración" lo que aparece en un `CREATE
-- TABLE|VIEW` literal — un `DROP VIEW` acá se leería como tirar abajo algo que esta migración
-- nunca creó.
--
-- Límite heredado del patrón (ya presente en el rollback de F-052): `CREATE OR REPLACE VIEW` no
-- puede quitar una columna del medio, pero sí puede quitar la última — que es exactamente este
-- caso, `fuente` quedó al final. Si alguna vez hiciera falta un rollback que además reordenara
-- columnas, ahí sí hace falta `DROP VIEW` + `CREATE VIEW` en una transacción vía `execute_sql`.
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
    p.cierre_anterior
FROM public.instrumentos i
LEFT JOIN LATERAL (
    SELECT *
    FROM public.precios pr
    WHERE pr.ticker = i.ticker
    ORDER BY pr.capturado_en DESC
    LIMIT 1
) p ON true;

COMMENT ON COLUMN public.precios.fuente IS
    'Qué fuentes aportaron a esta fila: byma, iamc o byma+iamc. La precedencia por campo está '
    'fijada en código y cada columna tiene una sola fuente posible: last_price y effective_volume '
    'sólo de BYMA; tir, duration, paridad, convexidad y residual_value sólo de IAMC. La fila es '
    'el resultado consolidado de la corrida, que es lo que la vista resumen necesita leer.';

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260808120000';
