-- Rollback de 20260828160000_subtipo_desde_curado.sql
--
-- Vacía el subtipo de los soberanos hard-dollar cuya única fuente de ley es el curado, que son
-- exactamente los que completó la migración. Los que tienen `instrumentos.law` propia quedan como
-- están: esos los derivó el backfill anterior y no son asunto de este rollback.
--
-- El subtipo es dato derivado y re-derivable: vaciarlo no pierde nada que la ley no vuelva a dar.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

UPDATE public.instrumentos i
   SET subtipo = NULL
  FROM public.condiciones_emision ce
 WHERE ce.ticker = i.ticker
   AND i.law IS NULL
   AND i.clase_activo = 'bono_soberano'
   AND i.tipo_tasa = 'hard-dollar'
   AND i.subtipo IN ('global', 'bonar')
   AND ce.ley IN ('Ley N.Y.', 'Ley Argentina');

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260828160000';
