-- F-002 · Vista `resumen`: el contrato del motor, servido desde el esquema nuevo.
--
-- Reproduce exactamente las 21 columnas de la hoja `Resumen` de universo_consolidado.xlsx
-- (COLUMNAS_RESUMEN en tools/consolidar_universo.py), en el mismo orden y con los mismos nombres,
-- incluidos los que vienen en camelCase de la fuente original. Los módulos que hoy leen el Excel
-- pasan a leer esta vista sin cambiar una línea de su lógica.
--
-- Las columnas estáticas salen de `instrumentos` y las del día, del último snapshot de `precios`.
--
-- Rollback: supabase/rollbacks/20260806151206_vista_resumen_down.sql

CREATE VIEW public.resumen
WITH (security_invoker = true) AS  -- evalúa RLS con el usuario que consulta, no con el dueño
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
-- LATERAL y no un GROUP BY: para cada instrumento toma la fila completa del snapshot más reciente,
-- así las métricas del día vienen todas del mismo momento y no mezcladas entre capturas. El LEFT
-- conserva los instrumentos que todavía no cotizaron: aparecen con las métricas vacías, que es el
-- estado real, en vez de desaparecer del universo.
LEFT JOIN LATERAL (
    SELECT *
    FROM public.precios pr
    WHERE pr.ticker = i.ticker
    ORDER BY pr.capturado_en DESC
    LIMIT 1
) p ON true;

COMMENT ON VIEW public.resumen IS
    'Contrato de lectura del motor: las 21 columnas de la hoja Resumen. Ver docs/esquema-datos.md.';
