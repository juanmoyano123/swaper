DROP INDEX IF EXISTS public.carteras_user_id_snapshot_en_idx;
ALTER TABLE public.carteras ALTER COLUMN user_id DROP DEFAULT;
ALTER TABLE public.carteras
    DROP COLUMN IF EXISTS snapshot,
    DROP COLUMN IF EXISTS snapshot_en,
    DROP COLUMN IF EXISTS resumen,
    DROP COLUMN IF EXISTS monto,
    DROP COLUMN IF EXISTS moneda_referencia,
    DROP COLUMN IF EXISTS origen;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260810193636';
