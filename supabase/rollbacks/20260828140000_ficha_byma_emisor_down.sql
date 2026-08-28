-- Rollback de 20260828140000_ficha_byma_emisor.sql
--
-- Quita las dos columnas que agregó. Con ellas se va la denominación traída de la ficha y la marca
-- de "ya se preguntó": la próxima corrida del barrido vuelve a preguntar por todo el universo, que
-- es exactamente el estado anterior a esta migración.
--
-- **Lo que el barrido escribió en `underlying`, `law` y `subtipo` no se toca.** Son columnas que ya
-- existían y cuyo dominio no cambió acá, y lo que hay adentro sale de una fuente viva: borrarlo
-- dejaría el universo con menos emisores de los que tenía antes de esta migración, no con los
-- mismos. Un rollback devuelve el esquema, no des-ingiere el dato.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

ALTER TABLE public.instrumentos
    DROP COLUMN denominacion,
    DROP COLUMN ficha_consultada_en;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260828140000';
