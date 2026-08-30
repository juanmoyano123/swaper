-- País de la empresa detrás de cada CEDEAR, curado a mano — F-078, fase 3.
--
-- **Por qué una tabla nueva y no la columna `pais` que dejó Yahoo.** Son dos datos distintos con el
-- mismo nombre. El de Yahoo era el domicilio legal del emisor, llegaba en el mismo pedido que el
-- sector y no traía fuente por fila; éste es la economía a la que queda expuesta la plata —lo que
-- el asesor necesita para diversificar— y se investiga papel por papel, con la fuente que lo
-- declara y la fecha en que se verificó. La columna vieja quedó huérfana el 23/08/2026 y la
-- migración 20260828182500 la borra; reciclarla habría mezclado dos semánticas bajo un solo nombre.
--
-- **La clave es el papel, no la especie.** `AAPL`, `AAPLC` y `AAPLD` son el mismo CEDEAR de Apple
-- en pesos, cable y MEP (`app/renta_variable/agrupamiento.py`), y el país es de la empresa: una
-- sola fila lo dice para las tres. Compartirlo entre hermanas no es completar por analogía, es
-- identidad.
--
-- **Sin FK a `instrumentos`, a propósito.** `ticker_papel` es el ticker agrupado y puede no existir
-- como fila propia — un papel que sólo cotiza en su variante D no tiene la especie base listada—, y
-- además el curado puede adelantarse al universo. Mismo criterio que `condiciones_emision`, que
-- tampoco tiene FK justamente para que un curado que el universo todavía no conoce no se pierda.
--
-- **`pais` admite NULL y eso es un valor, no un hueco.** NULL con `fuente` cargada significa "se
-- investigó y no se pudo resolver", que es distinto de no tener fila (nadie lo miró todavía). Las
-- dos cosas se muestran como "sin dato" declarado, pero sólo la segunda es trabajo pendiente.
-- Los ETFs entran acá con `pais` NULL: su eje geográfico es `perfil_renta_variable.region_etf`,
-- que sale del nombre del fondo y no de un país.
--
-- **`pais` es ISO 3166-1 alfa-2**, y leer un estándar publicado no es interpretar un código
-- propietario: es el mismo criterio con el que el proyecto lee `ARS`/`USD` de ISO 4217 y no lee
-- `EXT`, que BYMA no documenta. La región se deriva del país con la subregión M49 de la ONU al
-- leer (`app/renta_variable/regiones.py`) y no se persiste: es derivado y re-derivable, igual que
-- `division_cadena`.
--
-- Rollback: supabase/rollbacks/20260828182000_f078_pais_cedear_down.sql

CREATE TABLE public.pais_cedear (
    ticker_papel text PRIMARY KEY,
    pais         text,
    fuente       text NOT NULL,
    verificado   date NOT NULL,
    cargado_en   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.pais_cedear IS
    'País de la empresa detrás de cada CEDEAR, curado a mano desde data/paises_cedears.csv y '
    'validado antes de cargarse. Una fila por papel agrupado (AAPL, no AAPLD).';

COMMENT ON COLUMN public.pais_cedear.pais IS
    'ISO 3166-1 alfa-2. NULL = se investigó y no se resolvió, o es un ETF (su eje geográfico es '
    'perfil_renta_variable.region_etf). Distinto de no tener fila, que es trabajo pendiente.';

COMMENT ON COLUMN public.pais_cedear.fuente IS
    'Qué declara el país y dónde se leyó. NOT NULL: un país sin fuente no se muestra (regla 11), '
    'y cuando pais es NULL esta columna es la que dice qué se investigó y por qué quedó en duda.';

COMMENT ON COLUMN public.pais_cedear.verificado IS
    'Fecha en que se verificó contra la fuente. Es la fecha del dato, no la de la carga: cargado_en '
    'dice cuándo entró a la base y se mueve en cada resiembra.';

-- Mismo criterio de RLS que `perfil_renta_variable` y que las tablas de mercado (F-002): lectura
-- abierta a cualquier usuario autenticado; el backend escribe por conexión directa como dueño de
-- la tabla, sin pasar por RLS.
ALTER TABLE public.pais_cedear ENABLE ROW LEVEL SECURITY;

CREATE POLICY pais_cedear_lectura ON public.pais_cedear
    FOR SELECT TO authenticated USING (true);
