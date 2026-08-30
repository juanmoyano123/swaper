-- Rollback de 20260828182500_f078_drop_perfil_yahoo.sql
--
-- Recrea las cuatro columnas tal como las declaraba 20260809230000_perfil_renta_variable.sql, y
-- vuelve a poner el COMMENT de la tabla como estaba. **Vuelven vacías, que es como estaban**: las
-- cuatro tenían 0 valores no nulos en las 1.641 filas al momento de borrarlas, y su fuente —Yahoo—
-- se eliminó del proyecto el 23/08/2026, así que no hay nada que restaurar ni de dónde traerlo.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

ALTER TABLE public.perfil_renta_variable
    ADD COLUMN nombre_corto text,
    ADD COLUMN sector       text,
    ADD COLUMN industria    text,
    ADD COLUMN pais         text;

COMMENT ON TABLE public.perfil_renta_variable IS
    'Nombre, sector, industria y país de cada acción/CEDEAR, de Yahoo Finance, poblado por el job '
    'de enriquecimiento. Valores tal como la fuente los declara, sin traducir (regla 11).';

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260828182500';
