-- Rollback de 20260823230000_f057_fci.sql
--
-- Borra las dos tablas del FCI y devuelve el CHECK de `corridas_ingesta.tipo` a su forma original
-- (sólo 'matinal' y 'refresh'). No toca ninguna otra tabla: nada tiene FK hacia `fci` ni hacia
-- `fci_planilla`.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

ALTER TABLE public.corridas_ingesta DROP CONSTRAINT corridas_ingesta_tipo_check;
ALTER TABLE public.corridas_ingesta ADD CONSTRAINT corridas_ingesta_tipo_check
    CHECK (tipo IN ('matinal', 'refresh'));

DROP TABLE IF EXISTS public.fci_planilla;
DROP TABLE IF EXISTS public.fci;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260823230000';
