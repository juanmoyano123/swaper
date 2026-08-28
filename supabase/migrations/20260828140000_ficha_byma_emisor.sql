-- Las dos columnas que necesita el barrido de emisores contra la ficha técnica de BYMA (28/08/2026).
--
-- El problema que resuelve: de las 4.761 filas de `instrumentos`, sólo 742 tienen emisor. Las dos
-- fuentes que lo traían se apagaron —el CSV curado de F-009 no tiene origen vivo y la ingesta de
-- IAMC se eliminó el 26/08/2026—, y un instrumento cuyo emisor no se conoce no se puede analizar.
-- La ficha técnica de BYMA (`app/externos/byma_ficha.py`) lo publica por especie.
--
-- **`ficha_consultada_en` es la marca de "ya se preguntó", y es la columna que hace que el job
-- avance.** Sin ella, cada corrida volvería a preguntar por las mismas especies que la fuente no
-- cubre y los pendientes no bajarían nunca: es el mismo error que ya costó nueve tandas de 100
-- papeles para bajar los pendientes de la SEC de 1.539 a 1.536 (13/08/2026, documentado en
-- `app/renta_variable/clasificacion.py`). Con valor y los campos vacíos significa **"se preguntó y
-- la fuente no lo tiene"**, que es un dato en sí mismo y no un hueco.
--
-- ISIN, tipo de garantía, montos nominal y residual y las fechas de emisión y vencimiento vienen en
-- la misma respuesta y **quedan afuera a propósito**: cada uno necesita su propia verificación
-- contra la fuente antes de mostrarse, y agregarlos "ya que la respuesta los trae" es cómo un dato
-- sin verificar termina en pantalla.
--
-- Rollback: supabase/rollbacks/20260828140000_ficha_byma_emisor_down.sql

ALTER TABLE public.instrumentos
    ADD COLUMN denominacion text,
    ADD COLUMN ficha_consultada_en timestamptz;

COMMENT ON COLUMN public.instrumentos.denominacion IS
    'Cómo la ficha técnica de BYMA nombra a la emisión ("Clase XXXI", "BONOS DE LA REPÚBLICA '
    'ARGENTINA ... STEP UP 2030"), tal cual la declara la fuente. NULL = la fuente no la publica.';

COMMENT ON COLUMN public.instrumentos.ficha_consultada_en IS
    'Cuándo se le preguntó por esta especie a la ficha técnica de BYMA. Con valor y `underlying`, '
    '`law` o `denominacion` vacíos significa "se preguntó y la fuente no lo tiene" — no es un '
    'hueco pendiente. Es lo que impide que el barrido vuelva a preguntar por siempre lo mismo; '
    'vaciarla reabre la pregunta para esas especies.';
