-- Rollback de 20260806185717_f007_consolidador.sql
--
-- Dropea las cuatro columnas nuevas y devuelve el CHECK y el COMMENT al estado de F-002. Ojo con
-- el orden: restaurar el dominio MEP/CCL falla si quedó alguna fila con coupon_currency en 'USD'
-- o 'ARS', que es justamente lo que el consolidador escribe. Por eso el UPDATE que las vacía va
-- primero: son datos regenerables (una corrida los vuelve a traer) y el CHECK no lo es.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

ALTER TABLE public.precios DROP COLUMN convexidad;

ALTER TABLE public.instrumentos
    DROP COLUMN estructura_cupon,
    DROP COLUMN moneda_cotizacion,
    DROP COLUMN plazo_liquidacion;

UPDATE public.instrumentos SET coupon_currency = NULL
 WHERE coupon_currency IN ('USD', 'ARS');

ALTER TABLE public.instrumentos DROP CONSTRAINT instrumentos_coupon_currency_check;
ALTER TABLE public.instrumentos ADD CONSTRAINT instrumentos_coupon_currency_check
    CHECK (coupon_currency IN ('MEP', 'CCL'));

COMMENT ON COLUMN public.precios.fuente IS
    'Qué fuente escribió la fila. La precedencia por campo de F-007 se resuelve eligiendo de qué '
    'fuente leer, no mezclando fuentes dentro de una misma fila.';

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260806185717';
