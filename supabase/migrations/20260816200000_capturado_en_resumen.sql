-- Relevamiento de confiabilidad de datos (16/08/2026) · Antigüedad del precio, visible en la vista.
--
-- `precios.capturado_en` y `precios.fecha_metricas` ya existían y ya distinguían de cuándo es cada
-- fila, pero la vista `resumen` nunca los exponía. Sin esto, un ticker que dejó de cotizar conserva
-- su última fila para siempre (la poda es por-ticker, no por antigüedad global) y `resumen` la sirve
-- al monitor y al armador sin ninguna marca de que no es de la corrida más reciente — y si esa fila
-- trae métricas de IAMC de antes de la pausa, llegan al frontend sin fecha que las delate.
--
-- Con las dos columnas expuestas, `app/universo/segmentacion.py` puede comparar el `capturado_en`
-- de cada especie contra el máximo del universo leído y declarar las que quedaron atrás como
-- huérfanas (alerta `precio_desactualizado`), en vez de que la antigüedad quede invisible.
--
-- No se agrega ninguna columna nueva a `precios`: sólo se expone lo que ya existía. Migración
-- aditiva y segura para `develop`.
--
-- Rollback: supabase/rollbacks/20260816200000_capturado_en_resumen_down.sql

COMMENT ON COLUMN public.precios.capturado_en IS
    'El instante de la corrida que escribió esta fila. Todas las filas de una misma corrida '
    '(matinal o refresh) comparten exactamente el mismo valor: es el reloj de la corrida, no un '
    'timestamp por ticker. Comparar esta columna contra su máximo en el universo leído es lo que '
    'distingue una especie recién actualizada de una huérfana (dejó de cotizar y conserva su '
    'última fila, por diseño de la poda — ver `persistencia.py::sql_poda`).';

-- Las dos van AL FINAL: CREATE OR REPLACE VIEW sólo admite agregar columnas al final, y los
-- lectores existentes leen por nombre, así que pasar de 27 a 29 columnas no rompe a nadie.
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
