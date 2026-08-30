-- Geografía curada por ETF (índice que sigue + alcance declarado por su emisor + país ISO si es
-- mono-país) — F-079, D3 / fase 2.
--
-- **Por qué una tabla nueva y no una columna en `perfil_renta_variable`.** Mismo criterio que
-- `pais_cedear` (F-078): es dato curado por-papel, investigado uno por uno, con fuente y fecha
-- propias de cada fila. `perfil_renta_variable` es lo que la SEC y BYMA publican; esto es un
-- curado editorial que un humano valida antes de cargarse, y vive aparte por la misma razón que
-- ya separó `pais_cedear` de la columna vieja de Yahoo.
--
-- **Qué es `alcance`.** La definición del ÍNDICE que el fondo sigue, tal como la declara el
-- emisor de ese índice (MSCI, FTSE, S&P) — no nuestra interpretación de qué mercados toca hoy.
-- "Acciones de gran y mediana capitalización de mercados desarrollados, excluyendo EE.UU. y
-- Canadá" para MSCI EAFE es lo que MSCI publica sobre su propio índice, no una lectura nuestra de
-- su composición.
--
-- **Por qué `pais` es NULL para la mayoría.** Un ETF geográfico casi siempre sigue un índice
-- multi-país (MSCI ACWI, MSCI Emerging Markets, MSCI Europe...), y **no se cura su composición
-- completa de países**: esa composición cambia con cada rebalanceo del índice, y mostrarla como
-- si fuera estable sería la misma lección que llevó a pausar el consumo de IAMC
-- (`IAMC_HABILITADO=false`, ver CLAUDE.md) — un dato que envejece en silencio al lado de un
-- precio de hoy. `pais` sólo se completa para el puñado de fondos mono-país (iShares MSCI Japan,
-- iShares MSCI South Korea, iShares China Large-Cap), donde no hay composición que envejezca
-- porque el fondo es, por definición, un solo país.
--
-- **Sin FK a `instrumentos`**, mismo criterio que `pais_cedear`: `ticker_papel` es el papel post-
-- agrupamiento (el ticker base, sin sufijo C/D de liquidación) y puede no calzar 1:1 con
-- `instrumentos.ticker`, además de que el curado puede adelantarse al universo.
--
-- Rollback: supabase/rollbacks/20260829120000_f079_etf_geografia_down.sql

CREATE TABLE public.etf_geografia (
    ticker_papel text PRIMARY KEY,
    indice       text NOT NULL,
    alcance      text NOT NULL,
    pais         text NULL,
    fuente       text NOT NULL,
    verificado   date NOT NULL,
    cargado_en   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.etf_geografia IS
    'Geografía curada por ETF (F-079, D3): qué índice sigue y qué alcance declara el emisor de '
    'ese índice, desde data/etfs_geografia.csv, validado antes de cargarse. Tabla propia y no '
    'columna en perfil_renta_variable: dato curado por-papel con fuente y fecha por fila, mismo '
    'criterio que pais_cedear (F-078).';

COMMENT ON COLUMN public.etf_geografia.indice IS
    'El índice que el ETF sigue (ej. "MSCI EAFE Index"), tal como lo nombra su emisor.';

COMMENT ON COLUMN public.etf_geografia.alcance IS
    'Definición del ÍNDICE según su propio emisor (MSCI, FTSE, S&P...), en español y corto — no '
    'nuestra interpretación de qué mercados toca hoy. No es la composición de países del índice.';

COMMENT ON COLUMN public.etf_geografia.pais IS
    'ISO 3166-1 alfa-2, sólo cuando el fondo es de un solo país (ej. iShares MSCI Japan → JP). '
    'NULL para todo fondo multi-país: NO se cura su composición completa porque envejece con '
    'cada rebalanceo del índice — misma lección que pausó el consumo de IAMC.';

COMMENT ON COLUMN public.etf_geografia.fuente IS
    'Qué declara el índice/alcance y dónde se leyó. NOT NULL: un dato sin fuente no se muestra '
    '(regla 11).';

COMMENT ON COLUMN public.etf_geografia.verificado IS
    'Fecha en que se verificó contra la fuente. Es la fecha del dato, no la de la carga: '
    'cargado_en dice cuándo entró a la base y se mueve en cada resiembra.';

-- Mismo criterio de RLS que `pais_cedear`: lectura abierta a cualquier usuario autenticado; el
-- backend escribe por conexión directa como dueño de la tabla, sin pasar por RLS.
ALTER TABLE public.etf_geografia ENABLE ROW LEVEL SECURITY;

CREATE POLICY etf_geografia_lectura ON public.etf_geografia
    FOR SELECT TO authenticated USING (true);
