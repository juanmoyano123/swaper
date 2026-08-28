-- Completa el subtipo de los soberanos cuya ley vive en el curado — 28/08/2026.
--
-- El backfill de `20260828120000_subtipo_letra_bopreal.sql` derivó bonar/global desde
-- `instrumentos.law`, y ahí se le escaparon 42 emisiones. El motivo es que la ley de los soberanos
-- no siempre está en esa columna: buena parte vive en `condiciones_emision`, el CSV curado que se
-- rescató en su momento, y sólo se resuelve al leer (`universo/segmentacion.py::_resolver_ley`).
-- AE38 es el caso testigo: `instrumentos.law` en NULL y `condiciones_emision.ley` en "Ley Argentina".
--
-- Tampoco los alcanzó el barrido de la ficha técnica de BYMA, y por una razón sana: ese job excluye
-- lo que ya tiene emisor efectivo, y a los soberanos la corrida les escribe el emisor en cada
-- matinal. Nunca les pide la ficha, así que nunca les trae la ley.
--
-- Esto no infiere nada: la ley del curado es dato declarado y verificado a mano, y la regla que
-- traduce ley a subtipo es la misma que ya aplica `subtipo_de` — Ley N.Y. es global, Ley Argentina
-- es bonar. Sólo se completa donde el subtipo está vacío: nada se pisa.

UPDATE public.instrumentos i
   SET subtipo = CASE ce.ley
                     WHEN 'Ley N.Y.'      THEN 'global'
                     WHEN 'Ley Argentina' THEN 'bonar'
                 END
  FROM public.condiciones_emision ce
 WHERE ce.ticker = i.ticker
   AND i.subtipo IS NULL
   AND i.clase_activo = 'bono_soberano'
   AND i.tipo_tasa = 'hard-dollar'
   AND ce.ley IN ('Ley N.Y.', 'Ley Argentina');
