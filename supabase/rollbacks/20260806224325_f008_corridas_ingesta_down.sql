-- Rollback de 20260806224325_f008_corridas_ingesta.sql
--
-- Sólo borra la tabla del job de F-008: no toca `instrumentos`, `precios`, `puntas` ni `cashflow`,
-- que son de F-002/F-007 y no tienen ninguna dependencia hacia acá.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

DROP TABLE IF EXISTS public.corridas_ingesta;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260806224325';
