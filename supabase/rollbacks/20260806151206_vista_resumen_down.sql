-- Rollback de 20260806151206_vista_resumen.sql
--
-- La vista no guarda datos: sacarla no pierde nada y las tablas que lee quedan intactas.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

DROP VIEW public.resumen;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260806151206';
