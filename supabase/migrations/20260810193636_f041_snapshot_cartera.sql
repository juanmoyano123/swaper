-- F-041 · La cartera guardada es un snapshot: el estado y los precios del momento van en
-- `snapshot` (jsonb, forma definida y validada por el frontend — mismo criterio que
-- `propuestas.payload`); las columnas nuevas denormalizan lo que el listado muestra,
-- para que listar nunca baje snapshots enteros.
-- Rollback: supabase/rollbacks/20260810193636_f041_snapshot_cartera_down.sql

ALTER TABLE public.carteras
    ADD COLUMN origen            text        NOT NULL CHECK (origen IN ('cargada', 'armador')),
    ADD COLUMN moneda_referencia text        NOT NULL,
    ADD COLUMN monto             numeric     NOT NULL,
    ADD COLUMN resumen           text        NOT NULL,
    ADD COLUMN snapshot_en       timestamptz NOT NULL,
    ADD COLUMN snapshot          jsonb       NOT NULL;

-- PostgREST completa user_id desde el JWT; la policy WITH CHECK sigue verificando la fila.
ALTER TABLE public.carteras ALTER COLUMN user_id SET DEFAULT auth.uid();

-- El listado ordena por fecha de snapshot descendente.
CREATE INDEX carteras_user_id_snapshot_en_idx ON public.carteras (user_id, snapshot_en DESC);
