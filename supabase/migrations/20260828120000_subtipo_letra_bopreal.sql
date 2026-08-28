-- Subtipo: la subclasificación de lo que hoy cae todo junto bajo `bono_soberano` (28/08/2026).
--
-- `subtipo` existía desde `20260806151113_mercado.sql` con el dominio `('global','bonar')`, que
-- sólo distingue soberanos hard-dollar por legislación. Con la incorporación del panel `lebacs` de
-- BYMA a la ingesta —199 especies, ver `app/ingesta/byma/cliente.py`— entran las letras del Tesoro,
-- y el Bopreal ya estaba adentro desde siempre bajo `tipo_tasa='bopreal'`. Los cuatro son riesgo
-- soberano y ninguno era distinguible en pantalla.
--
-- **Esto no toca `clase_activo` ni la concentración.** El Bopreal lo emite el BCRA y no el Tesoro,
-- pero a efectos de tope por emisor sigue bajo la clave única `SOBERANO_AR` (regla 4 del dominio):
-- `app/concentracion/riesgo.py` no se modifica. El subtipo es visualización y filtro, nada más.
--
-- El backfill es determinístico sobre datos ya declarados y persistidos —`tipo_tasa`, que viene del
-- `type` del cronograma, y `law`, del dato curado de F-009—: no completa ningún hueco, sólo
-- re-expresa como subtipo lo que otra columna ya dice. Es el espejo exacto de `subtipo_en_corrida`
-- y `subtipo_de` en `app/ingesta/consolidacion/clasificacion.py`; si una de las dos cambia, la otra
-- también.
--
-- `letra` **no se backfillea**: sale del panel que trajo la especie, y el panel no queda persistido
-- en ninguna columna. Lo escribe la primera corrida de ingesta con `lebacs` habilitado. Derivarlo
-- acá desde el ticker sería reconstruir el emisor cortando strings, que es el antecedente de los
-- 121 tickers inventados (regla 1).
--
-- Rollback: supabase/rollbacks/20260828120000_subtipo_letra_bopreal_down.sql

ALTER TABLE public.instrumentos DROP CONSTRAINT instrumentos_subtipo_check;

ALTER TABLE public.instrumentos ADD CONSTRAINT instrumentos_subtipo_check
    CHECK (subtipo IN ('global', 'bonar', 'letra', 'bopreal'));

COMMENT ON COLUMN public.instrumentos.subtipo IS
    'Subclase dentro del riesgo soberano, vocabulario cerrado: letra | bonar | global | bopreal. '
    'NULL = sin subclase declarada, que es el caso de toda la renta fija no soberana y de los '
    'soberanos cuya ley no consta. `letra` la escribe la ingesta cuando la especie viene del panel '
    'lebacs de BYMA y el cronograma la declara del Tesoro (una letra provincial no lleva subtipo). '
    '`bopreal` sale de tipo_tasa. `bonar`/`global` salen de law. No afecta la concentración: el '
    'Bopreal lo emite el BCRA pero sigue bajo la clave SOBERANO_AR (regla 4 del dominio).';

-- Backfill. Sólo filas con `subtipo IS NULL`: lo ya escrito no se pisa.
UPDATE public.instrumentos
SET subtipo = 'bopreal'
WHERE subtipo IS NULL
  AND clase_activo = 'bono_soberano'
  AND tipo_tasa = 'bopreal';

UPDATE public.instrumentos
SET subtipo = CASE law WHEN 'Ley N.Y.' THEN 'global' WHEN 'Ley Argentina' THEN 'bonar' END
WHERE subtipo IS NULL
  AND clase_activo = 'bono_soberano'
  AND tipo_tasa = 'hard-dollar'
  AND law IS NOT NULL;
