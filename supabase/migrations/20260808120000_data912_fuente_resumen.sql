-- Experimento data912 · La procedencia del precio, visible en la vista viva.
--
-- `precios.fuente` ya existía y ya distinguía byma / iamc / calculo, pero la vista `resumen` nunca
-- la exponía (verificado: la columna se pierde en el `SELECT` explícito de F-052). Con el overlay
-- de data912 (`app/ingesta/consolidacion/overlay.py`) el vocabulario crece: un precio puede venir
-- de data912 porque la especie operó en la sesión del payload, o arrastrado de una sesión anterior
-- de fecha que la fuente no declara — y esa segunda situación es justo la que la regla 11 del
-- dominio exige rotular, no ocultar. Sin la columna en la vista, el monitor no tiene con qué armar
-- la nota de cobertura ni la ficha con qué mostrar la procedencia por especie.
--
-- No se agrega ninguna columna nueva a `precios`: sólo se actualiza el vocabulario documentado y
-- se expone lo que ya existía. Migración aditiva y segura para `develop`, que no la lee.
--
-- Rollback: supabase/rollbacks/20260808120000_data912_fuente_resumen_down.sql

COMMENT ON COLUMN public.precios.fuente IS
    'Qué fuentes aportaron a esta fila: data912, data912-arrastre o byma, compuesto con +calculo '
    '/ +iamc. data912 y data912-arrastre son el experimento de fuente primaria (rama '
    'experimento/data912): data912 significa que la especie operó en la sesión que trajo el '
    'payload; data912-arrastre, que el precio es el último cierre conocido de una fecha que la '
    'fuente no declara. byma es el respaldo cuando data912 no tiene la especie o no tiene precio '
    'utilizable. La precedencia por campo sigue fijada en código: last_price y effective_volume '
    'de la fuente que ganó el overlay; tir, duration, paridad, convexidad y residual_value sólo '
    'de IAMC o del cálculo propio. La fila es el resultado consolidado de la corrida.';

-- La columna nueva va AL FINAL: CREATE OR REPLACE VIEW sólo admite agregar columnas al final, y
-- los lectores existentes leen por nombre, así que pasar de 22 a 23 columnas no rompe a nadie.
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
