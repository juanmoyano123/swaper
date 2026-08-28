-- Rollback de 20260828120000_subtipo_letra_bopreal.sql
--
-- Vacía los dos subtipos que esta migración habilitó (`letra` y `bopreal`), restaura el CHECK
-- anterior —`('global','bonar')`— y quita el comentario de la columna, que antes no tenía
-- (verificado contra la base real el 28/08/2026: `col_description` devolvía NULL).
--
-- El orden importa: con filas en `letra`/`bopreal` el CHECK viejo no se puede volver a poner.
--
-- **Las filas que el backfill dejó en `global`/`bonar` no se tocan.** Son valores que el CHECK
-- viejo ya aceptaba y que salen de `law`, un dato persistido y estable: borrarlas dejaría la
-- columna peor de lo que estaba antes de esta migración, no igual. `letra` y `bopreal` sí se
-- vacían porque el dominio al que vuelve la columna no los admite; los dos son derivados y
-- re-derivables —`bopreal` desde `tipo_tasa`, `letra` desde el panel de la próxima ingesta—, así
-- que no se pierde nada que no se pueda volver a calcular.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

UPDATE public.instrumentos SET subtipo = NULL WHERE subtipo IN ('letra', 'bopreal');

ALTER TABLE public.instrumentos DROP CONSTRAINT instrumentos_subtipo_check;

ALTER TABLE public.instrumentos ADD CONSTRAINT instrumentos_subtipo_check
    CHECK (subtipo IN ('global', 'bonar'));

COMMENT ON COLUMN public.instrumentos.subtipo IS NULL;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260828120000';
