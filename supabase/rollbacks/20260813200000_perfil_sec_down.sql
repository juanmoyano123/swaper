-- Rollback de 20260813200000_perfil_sec.sql
--
-- Saca las siete columnas que agregó y no toca nada más: las de Yahoo (nombre, sector, industria,
-- país) siguen donde estaban, y la tabla misma la creó otra migración.
--
-- Ojo: borrar estas columnas **pierde la clasificación ya traída de la SEC**. Volver a llenarlas es
-- correr el job de nuevo, que son ~315 pedidos a una fuente que no cobra ni bloquea; no es un dato
-- irrecuperable, pero tampoco es gratis en tiempo.

ALTER TABLE public.perfil_renta_variable
    DROP COLUMN IF EXISTS sic_codigo,
    DROP COLUMN IF EXISTS sic_titulo,
    DROP COLUMN IF EXISTS sic_oficina,
    DROP COLUMN IF EXISTS division_cadena,
    DROP COLUMN IF EXISTS estrategia_etf,
    DROP COLUMN IF EXISTS ratio_conversion,
    DROP COLUMN IF EXISTS mercado_origen;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260813200000';
