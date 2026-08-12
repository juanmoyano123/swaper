-- Rollback de 20260809230000_perfil_renta_variable.sql
--
-- Sólo borra esta tabla: no toca instrumentos ni ninguna otra tabla de mercado o de renta variable.

DROP TABLE IF EXISTS public.perfil_renta_variable;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260809230000';
