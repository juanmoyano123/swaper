-- Rollback de 20260806151113_mercado.sql
--
-- Deshace SOLO lo que creó esa migración. Ojo: es el único down que borra datos de mercado, y por
-- eso corre último. Si están aplicadas las migraciones de usuario o la vista, este script falla en
-- vez de arrastrarlas: `posiciones` referencia `instrumentos` y la vista lee de las dos tablas.
-- Ese orden forzado es deliberado — hay que decidir explícitamente tirar abajo lo de arriba.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

DROP TABLE public.condiciones_emision;
DROP TABLE public.cashflow;
DROP TABLE public.puntas;
DROP TABLE public.precios;   -- antes que instrumentos: la FK apunta para ese lado
DROP TABLE public.instrumentos;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260806151113';
