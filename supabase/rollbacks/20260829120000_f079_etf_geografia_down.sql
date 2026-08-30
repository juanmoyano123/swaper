-- Rollback de 20260829120000_f079_etf_geografia.sql
--
-- Borra la tabla entera. **Lo que se pierde es la carga, no el curado**: la fuente de verdad es
-- `data/etfs_geografia.csv`, versionado en el repo, y `POST /api/v1/jobs/sembrar-geografia-etfs`
-- la reconstruye completa sin pedirle nada a ninguna fuente externa. La política de RLS cae con
-- la tabla; no hace falta borrarla aparte.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

DROP TABLE IF EXISTS public.etf_geografia;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260829120000';
