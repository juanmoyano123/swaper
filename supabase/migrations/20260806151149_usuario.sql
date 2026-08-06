-- F-002 · Tablas de usuario: cada asesor ve exclusivamente lo suyo.
--
-- El aislamiento se aplica con Row Level Security en la base, no con filtros del lado del cliente:
-- así un bug en el frontend no puede filtrar la cartera de otro asesor. Construirlo desde la
-- primera tabla es más barato que retrofitearlo sobre datos existentes.
--
-- Rollback: supabase/rollbacks/20260806151149_usuario_down.sql

CREATE TABLE public.carteras (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    nombre         text NOT NULL,
    descripcion    text,
    creado_en      timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.posiciones (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cartera_id    uuid NOT NULL REFERENCES public.carteras (id) ON DELETE CASCADE,

    -- Repetido acá y no sólo en `carteras`: la policy se evalúa por fila y sin esta columna cada
    -- lectura de posiciones tendría que subir a la cartera para saber de quién es.
    user_id       uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,

    ticker        text NOT NULL REFERENCES public.instrumentos (ticker),
    cantidad      numeric NOT NULL,

    -- Nullables: una cartera puede cargarse para analizarla sin conocer el precio de compra.
    precio_compra numeric,
    fecha_compra  date,

    creado_en     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.propuestas (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,

    -- Si se borra la cartera, la propuesta sobrevive huérfana: es el registro de lo que se le
    -- sugirió al cliente y borrarlo por arrastre perdería la historia del asesoramiento.
    cartera_id uuid REFERENCES public.carteras (id) ON DELETE SET NULL,

    estado     text NOT NULL DEFAULT 'borrador',

    -- El contenido de una propuesta —swaps sugeridos, riesgo asumido a cambio, comparativas— lo
    -- define la feature que la genera. Modelarlo en columnas hoy sería adivinar.
    payload    jsonb NOT NULL DEFAULT '{}'::jsonb,

    creado_en  timestamptz NOT NULL DEFAULT now()
);

-- Índices sobre las columnas que evalúa cada policy y sobre las claves foráneas: sin ellos, cada
-- lectura con RLS activa termina en un scan de toda la tabla.
CREATE INDEX carteras_user_id_idx ON public.carteras (user_id);
CREATE INDEX posiciones_user_id_idx ON public.posiciones (user_id);
CREATE INDEX posiciones_cartera_id_idx ON public.posiciones (cartera_id);
CREATE INDEX posiciones_ticker_idx ON public.posiciones (ticker);
CREATE INDEX propuestas_user_id_idx ON public.propuestas (user_id);
CREATE INDEX propuestas_cartera_id_idx ON public.propuestas (cartera_id);

ALTER TABLE public.carteras ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.posiciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.propuestas ENABLE ROW LEVEL SECURITY;

-- Cuatro policies por tabla en vez de una FOR ALL: separar las operaciones deja explícito que
-- INSERT y UPDATE también verifican la fila que se escribe (WITH CHECK), no sólo la que se lee.
-- Sin eso, un asesor podría insertar una fila a nombre de otro.
CREATE POLICY carteras_select ON public.carteras
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY carteras_insert ON public.carteras
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY carteras_update ON public.carteras
    FOR UPDATE TO authenticated
    USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY carteras_delete ON public.carteras
    FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY posiciones_select ON public.posiciones
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY posiciones_insert ON public.posiciones
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY posiciones_update ON public.posiciones
    FOR UPDATE TO authenticated
    USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY posiciones_delete ON public.posiciones
    FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY propuestas_select ON public.propuestas
    FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
CREATE POLICY propuestas_insert ON public.propuestas
    FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY propuestas_update ON public.propuestas
    FOR UPDATE TO authenticated
    USING ((SELECT auth.uid()) = user_id) WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY propuestas_delete ON public.propuestas
    FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);
