-- Perfil de empresa para acciones y CEDEARs — Etapa 4 del rediseño del armador.
--
-- El listado de renta variable (F-052, `app/renta_variable/`) no trae nombre de la empresa, sector,
-- industria ni país: `EspecieRentaVariable` sólo tiene lo que publica BYMA. Ese dato existe en la
-- ficha individual (F-053, Yahoo Finance, `app/externos/yahoo.py`), pedido on-demand ticker por
-- ticker cuando el asesor abre la ficha. Para poder filtrar el armador y el bloque de renta variable
-- por rubro o por empresa hace falta que ese dato esté disponible en el LISTADO, no sólo en la
-- ficha — y Yahoo limita por IP (429 medido el 08/08/2026, ver el docstring de `yahoo.py`), así que
-- pedirlo en vivo por cada fila de una grilla de ~750 tickers no es viable.
--
-- Se persiste acá, poblado por un job de enriquecimiento disparable a mano
-- (`POST /api/v1/jobs/perfiles-renta-variable`, `app/renta_variable/enriquecimiento.py`) en vez de
-- pedirse on-demand: el perfil de una empresa cambia lento (nombre, sector, país), así que una
-- corrida esporádica alcanza, y el job corta al primer 429 en vez de insistir contra el límite.
--
-- Rollback: supabase/rollbacks/20260809230000_perfil_renta_variable_down.sql

CREATE TABLE public.perfil_renta_variable (
    ticker         text PRIMARY KEY REFERENCES public.instrumentos (ticker) ON DELETE CASCADE,

    nombre_corto   text,
    nombre_largo   text,
    sector         text,
    industria      text,
    pais           text,

    -- Los cinco de arriba llegan juntos, en el mismo pedido a Yahoo (ClienteYahoo.
    -- perfil_de_empresa) — un solo origen y una sola fecha para toda la fila, no uno por campo
    -- como `condiciones_emision` (que sí mezcla curaciones de distintas pasadas).
    fuente         text NOT NULL,
    capturado_en   timestamptz NOT NULL
);

COMMENT ON TABLE public.perfil_renta_variable IS
    'Nombre, sector, industria y país de cada acción/CEDEAR, de Yahoo Finance, poblado por el job '
    'de enriquecimiento. Valores tal como la fuente los declara, sin traducir (regla 11).';

-- Mismo criterio de RLS que las tablas de mercado (F-002): lectura abierta a cualquier usuario
-- autenticado; el backend escribe por conexión directa como dueño de la tabla, sin pasar por RLS.
ALTER TABLE public.perfil_renta_variable ENABLE ROW LEVEL SECURITY;

CREATE POLICY perfil_renta_variable_lectura ON public.perfil_renta_variable
    FOR SELECT TO authenticated USING (true);
