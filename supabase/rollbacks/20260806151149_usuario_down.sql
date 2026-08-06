-- Rollback de 20260806151149_usuario.sql
--
-- Deshace SOLO las tablas de usuario. Las cinco tablas de mercado quedan intactas: ningún DROP de
-- este archivo las nombra, y las policies e índices se van solos con sus tablas.
--
-- Aplicar con execute_sql (no con apply_migration: un rollback no es una migración nueva).

DROP TABLE public.propuestas;
DROP TABLE public.posiciones;   -- antes que carteras: la FK apunta para ese lado
DROP TABLE public.carteras;

DELETE FROM supabase_migrations.schema_migrations WHERE version = '20260806151149';
