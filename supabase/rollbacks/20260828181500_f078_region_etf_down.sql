-- Rollback de 20260828181500_f078_region_etf.sql
--
-- Saca la columna y nada más. `region_etf` es dato derivado del `nombre_largo` que queda en la
-- misma tabla: volver a aplicar la migración y correr `POST /api/v1/jobs/reclasificar-etfs`
-- reconstruye exactamente lo mismo, sin pedirle nada a ninguna fuente externa.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

ALTER TABLE public.perfil_renta_variable DROP COLUMN IF EXISTS region_etf;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260828181500';
