-- Rollback de 20260827210000_cron_ingesta.sql
--
-- Desprograma los tres jobs y borra la función que dispara las corridas. **La ingesta queda sin
-- ningún disparador automático**: después de correr esto hay que dispararla a mano
-- (POST /api/v1/jobs/corridas/matinal) o volver a programarla en otro lado.
--
-- Qué NO se toca, a propósito:
--   * Las extensiones `pg_cron` y `pg_net` quedan instaladas. Dropearlas se llevaría puesto
--     cualquier otro job o pedido HTTP que alguien haya programado por fuera de esta migración,
--     y son inertes si no hay nada que las use.
--   * El secreto `cron_secret` de Vault queda donde está: se creó por fuera de la migración
--     —una migración versionada no puede contener un secreto— así que tampoco se borra acá.
--     Para sacarlo: `select vault.delete_secret(id) from vault.secrets where name = 'cron_secret';`
--   * `public.corridas_ingesta` y todo lo que escribieron las corridas ya hechas: son datos, no
--     esquema.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

SELECT cron.unschedule('ingesta-matinal');
SELECT cron.unschedule('ingesta-refresh');
SELECT cron.unschedule('ingesta-refresh-cierre');

DROP FUNCTION IF EXISTS public.disparar_corrida_ingesta(text);

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260827210000';
