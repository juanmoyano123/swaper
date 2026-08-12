-- F-002 · Tablas de mercado: el universo es uno solo y es igual para todos los asesores.
--
-- El esquema replica el contrato de salida del motor Python —la hoja `Resumen` de
-- universo_consolidado.xlsx y cashflow_completo.csv— para que los módulos que ya funcionan no se
-- enteren de que la fuente cambió de Excel a PostgreSQL. La correspondencia columna por columna
-- está en docs/esquema-datos.md; romperla es romper el 85% del motor que se reusa.
--
-- Rollback: supabase/rollbacks/20260806151113_mercado_down.sql

-- Identidad y clasificación de cada especie: lo que no cambia con la rueda.
-- Las métricas del día viven en `precios`, no acá.
CREATE TABLE public.instrumentos (
    ticker          text PRIMARY KEY,

    -- Dominios cerrados por el consolidador (SUBMARKET_MAP en tools/consolidar_universo.py).
    -- Acciones y CEDEARs no tienen tipo_tasa: no tienen tasa, y por eso quedan fuera del armador.
    clase_activo    text NOT NULL CHECK (clase_activo IN (
                        'bono_soberano', 'bono_subsoberano', 'on_corporativo', 'accion', 'cedear')),
    tipo_tasa       text CHECK (tipo_tasa IN (
                        'hard-dollar', 'tasa-fija', 'cer', 'dollar-linked', 'badlar', 'tamar',
                        'bopreal')),
    subtipo         text CHECK (subtipo IN ('global', 'bonar')),

    underlying      text,
    sector          text,
    maturity        date,

    -- Atributos de la emisión, no de la especie: si AL30 los tiene, AL30D y AL30C también.
    -- La herencia por raíz de ticker la resuelve F-009 sobre `condiciones_emision`; acá viven los
    -- valores ya efectivos para esta especie. Nullables porque la cobertura es parcial (ley 75%,
    -- calificación 39%) y un dato que falta se muestra faltante, nunca se infiere.
    law             text CHECK (law IN ('Ley Argentina', 'Ley N.Y.')),
    coupon_currency text CHECK (coupon_currency IN ('MEP', 'CCL')),
    lamina          numeric,
    calificacion    text,

    -- Banderas de calidad del consolidador: clase_activo nula y ticker repetido.
    revisar         boolean NOT NULL DEFAULT false,
    duplicado       boolean NOT NULL DEFAULT false,
    archivo_origen  text,

    actualizado_en  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.instrumentos IS
    'Una fila por especie negociable. Contrato: columnas estáticas de la hoja Resumen del motor.';

-- Serie temporal de mercado. Todas las métricas son nullable: sólo 618 de 927 instrumentos
-- cotizan con TIR y duration, y completar el resto sería inventar.
CREATE TABLE public.precios (
    ticker           text NOT NULL REFERENCES public.instrumentos (ticker) ON DELETE CASCADE,

    -- Nombre y tipo fijados por backend/app/db/health.py, que lee el último snapshot de acá.
    capturado_en     timestamptz NOT NULL,

    last_price       numeric,
    tir              numeric,
    tna              numeric,
    duration         numeric,
    paridad          numeric,
    residual_value   numeric,
    effective_volume numeric,

    -- Qué fuente escribió la fila. La precedencia por campo de F-007 se resuelve eligiendo de qué
    -- fuente leer, no mezclando fuentes dentro de una misma fila.
    fuente           text,

    PRIMARY KEY (ticker, capturado_en)
);

-- El health pide max(capturado_en) en cada sondeo de la plataforma: sin este índice sería un scan.
CREATE INDEX precios_capturado_en_idx ON public.precios (capturado_en DESC);

COMMENT ON COLUMN public.precios.last_price IS
    'Precio en la moneda de cotización de la especie, que no es la misma para todas. Nunca dividir '
    'un monto por este valor sin normalizar antes contra el tipo de cambio implícito.';

-- Puntas bid/ask. Tabla aparte de `precios` porque la cadencia y la fuente son distintas.
CREATE TABLE public.puntas (
    ticker       text NOT NULL,
    capturado_en timestamptz NOT NULL,
    px_bid       numeric,
    px_ask       numeric,
    operaciones  integer,
    fuente       text,
    PRIMARY KEY (ticker, capturado_en)
);

CREATE INDEX puntas_capturado_en_idx ON public.puntas (capturado_en DESC);

-- Sin FK a instrumentos a propósito: la fuente de puntas publica tickers que no están en nuestro
-- universo, y descartarlos en la ingesta sería perder dato que mañana puede servir. El join contra
-- el universo lo hace el motor. No agregar la FK "para arreglarlo".
COMMENT ON TABLE public.puntas IS
    'Puntas por especie. Sin FK a instrumentos: la fuente publica tickers fuera del universo.';

-- `spread_pct` no se persiste: es derivado de px_bid/px_ask (tools/mercado.py) y guardar un
-- derivado es tener dos versiones de la misma verdad que se pueden contradecir.

-- Cronograma completo de pagos. Es la piedra fundamental del producto: sin calendario no hay
-- análisis de predecibilidad del cashflow.
CREATE TABLE public.cashflow (
    ticker          text NOT NULL,
    type            text NOT NULL,
    issue_date      date,
    payment_date    date NOT NULL,
    capital         numeric,
    interest_rate   numeric,
    interest_amount numeric,
    residual_value  numeric,
    cash_flow       numeric,

    -- La fuente consolida capital e interés del mismo día en una sola fila: verificado sobre los
    -- 6111 pagos del cashflow actual, cero duplicados. Sirve de clave natural y hace la ingesta de
    -- F-007 un upsert.
    PRIMARY KEY (ticker, payment_date)
);

CREATE INDEX cashflow_payment_date_idx ON public.cashflow (payment_date);

-- `type` queda como texto libre y sin CHECK: es el submarket de la fuente, que agrega categorías
-- nuevas sin avisar, y un instrumento nuevo no debe hacer fallar la ingesta entera.
COMMENT ON TABLE public.cashflow IS
    'Pagos por 100 de valor nominal. Indexa una sola especie por emisión: cruzar por raíz de ticker.';

-- Dato curado del producto, no del mercado. Cada valor viaja con su origen y su fecha en la misma
-- fila: sin eso no se puede auditar de dónde salió ni decidir qué gana ante un conflicto.
CREATE TABLE public.condiciones_emision (
    ticker              text PRIMARY KEY,

    ley                 text,
    ley_origen          text,
    ley_fecha           date,

    moneda_pago         text,
    moneda_pago_origen  text,
    moneda_pago_fecha   date,

    lamina              numeric,
    lamina_origen       text,
    lamina_fecha        date,

    calificacion        text,
    calificacion_origen text,
    calificacion_fecha  date,

    sector              text,
    sector_origen       text,
    sector_fecha        date,

    underlying          text,
    underlying_origen   text,
    underlying_fecha    date,

    actualizado_en      timestamptz NOT NULL DEFAULT now(),

    -- Un valor cargado sin trazabilidad es un dato sin respaldo: la base lo rechaza en vez de
    -- confiar en que el que escribe se acuerde.
    CONSTRAINT ley_trazable CHECK (
        ley IS NULL OR (ley_origen IS NOT NULL AND ley_fecha IS NOT NULL)),
    CONSTRAINT moneda_pago_trazable CHECK (
        moneda_pago IS NULL OR (moneda_pago_origen IS NOT NULL AND moneda_pago_fecha IS NOT NULL)),
    CONSTRAINT lamina_trazable CHECK (
        lamina IS NULL OR (lamina_origen IS NOT NULL AND lamina_fecha IS NOT NULL)),
    CONSTRAINT calificacion_trazable CHECK (
        calificacion IS NULL
        OR (calificacion_origen IS NOT NULL AND calificacion_fecha IS NOT NULL)),
    CONSTRAINT sector_trazable CHECK (
        sector IS NULL OR (sector_origen IS NOT NULL AND sector_fecha IS NOT NULL)),
    CONSTRAINT underlying_trazable CHECK (
        underlying IS NULL OR (underlying_origen IS NOT NULL AND underlying_fecha IS NOT NULL))
);

-- Sin FK a instrumentos: se siembra con 823 tickers curados (F-009) que pueden existir antes de
-- que la ingesta de mercado los vea, y perder una condición de emisión por eso sería irrecuperable.
COMMENT ON TABLE public.condiciones_emision IS
    'Dato curado por especie. Cada valor lleva origen y fecha en la misma fila (CHECK lo exige).';

-- Row Level Security en las tablas de mercado.
--
-- El universo se lee igual para todos los asesores, así que la policy de lectura es abierta a
-- cualquier usuario autenticado. Lo que RLS impide acá es la ESCRITURA: sin policies de INSERT,
-- UPDATE ni DELETE, nadie escribe con la anon key a través de la API pública. El backend escribe
-- por conexión directa como dueño de las tablas, que no pasa por RLS.
ALTER TABLE public.instrumentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.precios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.puntas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cashflow ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.condiciones_emision ENABLE ROW LEVEL SECURITY;

CREATE POLICY instrumentos_lectura ON public.instrumentos
    FOR SELECT TO authenticated USING (true);
CREATE POLICY precios_lectura ON public.precios
    FOR SELECT TO authenticated USING (true);
CREATE POLICY puntas_lectura ON public.puntas
    FOR SELECT TO authenticated USING (true);
CREATE POLICY cashflow_lectura ON public.cashflow
    FOR SELECT TO authenticated USING (true);
CREATE POLICY condiciones_emision_lectura ON public.condiciones_emision
    FOR SELECT TO authenticated USING (true);
