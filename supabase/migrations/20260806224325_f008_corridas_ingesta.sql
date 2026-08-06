-- F-008 · Registro auditable de cada corrida del job de ingesta.
--
-- El job programado (matinal completa y refrescos intra-rueda) necesita dejar rastro de cada
-- pasada: hora de inicio, duración, filas por fuente y alertas emitidas. Es la base de la barra de
-- estado del dato que F-013 va a construir, y hoy no hay dónde guardar eso — las tablas de
-- `public.precios` y `public.puntas` sólo saben "cuál es el último dato", no "cuándo corrió el
-- job que lo trajo y si salió completo".
--
-- `filas_por_fuente` y `alertas` son jsonb en vez de columnas propias por fuente porque las
-- fuentes involucradas cambian según el tipo de corrida (la matinal trae byma/iamc/docta, el
-- refresh sólo byma) y las alertas ya son una lista de longitud variable en todo el resto del
-- backend (`app/ingesta/alertas.py`); tipar cada campo a mano acá duplicaría ese contrato.
--
-- Rollback: supabase/rollbacks/20260806224325_f008_corridas_ingesta_down.sql

CREATE TABLE public.corridas_ingesta (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- 'matinal': BYMA + IAMC + Docta + consolidación. 'refresh': sólo precios y puntas de BYMA.
    tipo             text NOT NULL CHECK (tipo IN ('matinal', 'refresh')),

    iniciado_en      timestamptz NOT NULL,
    finalizado_en    timestamptz NOT NULL,
    duracion_ms      integer NOT NULL,

    -- Total de filas traídas por cada fuente que participó en la corrida. Ej.: {"byma": 3204,
    -- "iamc": 512, "docta": 6111} en una matinal, {"byma": 3204} en un refresh.
    filas_por_fuente jsonb NOT NULL DEFAULT '{}',

    -- Las alertas de los snapshots de cada fuente más las de la consolidación y la escritura, en
    -- la misma forma que devuelve `Alerta.como_dict()` — codigo, mensaje, severidad, accion
    -- requerida y detalle.
    alertas          jsonb NOT NULL DEFAULT '[]',

    -- 'completa': ninguna fuente falló. 'parcial': al menos una aportó algo pero no todas — se
    -- persistió lo que llegó y se declaró lo que no, como pide el GIVEN/WHEN/THEN de F-008.
    -- 'fallida': la corrida corrió pero ninguna fuente aportó una fila.
    estado           text NOT NULL CHECK (estado IN ('completa', 'parcial', 'fallida')),

    creado_en        timestamptz NOT NULL DEFAULT now()
);

-- La consulta que alimenta la barra de estado pide las últimas N corridas por hora de inicio.
CREATE INDEX corridas_ingesta_iniciado_en_idx ON public.corridas_ingesta (iniciado_en DESC);

COMMENT ON TABLE public.corridas_ingesta IS
    'Historial de corridas del job de F-008: matinal (BYMA+IAMC+Docta+consolidación) y refresh '
    '(sólo precios y puntas de BYMA). Alimenta la barra de estado del dato de F-013.';

-- Mismo criterio de RLS que las tablas de mercado (F-002): lectura abierta a cualquier usuario
-- autenticado, sin policies de escritura porque el backend escribe por conexión directa como
-- dueño de la tabla, que no pasa por RLS.
ALTER TABLE public.corridas_ingesta ENABLE ROW LEVEL SECURITY;

CREATE POLICY corridas_ingesta_lectura ON public.corridas_ingesta
    FOR SELECT TO authenticated USING (true);
