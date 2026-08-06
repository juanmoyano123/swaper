-- F-007 · De cuándo es cada mitad de la fila de precios.
--
-- Una fila de `precios` junta dos cosas con frecuencias distintas: el precio y el volumen salen de
-- la rueda de BYMA, que cambia todo el tiempo, y la TIR, la duración, la paridad, la convexidad y
-- el valor residual salen del informe de IAMC, que se publica una vez por día y llega por subida
-- manual. `capturado_en` fecha la primera mitad; esta columna fecha la segunda.
--
-- Sin esto el universo se vaciaba solo. Como la vista `resumen` arma cada fila con la fila de
-- precios más reciente, la primera corrida que no tuviera informe a mano dejaba la TIR nula para
-- todo el universo aunque siguiera persistida en las filas anteriores — y "refrescar precios sin
-- volver a consultar IAMC" es exactamente lo que F-008 va a hacer varias veces por rueda.
--
-- Conservar la métrica del último informe conocido no es presentar el dato de ayer como el de hoy,
-- porque la fila dice de qué informe salió. Sin esta columna sí lo sería, y por eso las dos cosas
-- van juntas: se conserva el valor **y** se rotula su fecha.
--
-- Rollback: supabase/rollbacks/20260806191950_f007_fecha_metricas_down.sql

ALTER TABLE public.precios ADD COLUMN fecha_metricas date;

COMMENT ON COLUMN public.precios.fecha_metricas IS
    'Fecha del informe de IAMC del que salieron tir, duration, paridad, convexidad y '
    'residual_value. Distinta de capturado_en, que es el instante de la rueda de BYMA del que '
    'salió el precio: las dos cosas de la misma fila tienen frecuencias distintas (el informe es '
    'diario y el precio intradiario) y por eso se rotulan por separado. Nula cuando la fila no '
    'tiene métricas de IAMC.';
