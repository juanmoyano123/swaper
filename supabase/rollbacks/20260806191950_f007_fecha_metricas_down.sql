-- Rollback de 20260806191950_f007_fecha_metricas.sql
--
-- Volver acá deja el universo otra vez expuesto a vaciarse: sin la fecha que las rotula, las
-- métricas de IAMC no se pueden conservar entre corridas sin presentar el dato de un informe como
-- si fuera el de otro. Si se dropea esta columna hay que dejar de arrastrarlas también.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

ALTER TABLE public.precios DROP COLUMN fecha_metricas;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260806191950';
