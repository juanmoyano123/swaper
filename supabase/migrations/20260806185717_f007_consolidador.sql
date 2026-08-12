-- F-007 · Lo que el consolidador necesita guardar y F-002 no previó.
--
-- Cuatro cambios, todos con la misma raíz: al unir las tres fuentes aparecieron datos que las
-- fuentes declaran y el esquema no tenía dónde poner. Ninguna columna nueva lleva CHECK de
-- dominio, porque el vocabulario es de la fuente y la fuente lo cambia sin avisar; el único
-- dominio que se toca es `coupon_currency`, y para ampliarlo.
--
-- Rollback: supabase/rollbacks/20260806185717_f007_consolidador_down.sql

-- 1. La moneda de pago que declara IAMC no entra en el dominio del CSV curado.
--
-- El CSV curado distingue MEP de CCL —por dónde se cobra el dólar—; el informe de IAMC declara
-- solamente USD o ARS, que es la distinción más gruesa. Traducir USD a MEP sería inventar cuál de
-- las dos: el informe no lo dice. Así que el dominio admite las dos granularidades, cada valor
-- entra tal como su fuente lo declaró, y F-009 refina el grueso al fino cuando siembre el curado.
ALTER TABLE public.instrumentos DROP CONSTRAINT instrumentos_coupon_currency_check;
ALTER TABLE public.instrumentos ADD CONSTRAINT instrumentos_coupon_currency_check
    CHECK (coupon_currency IN ('MEP', 'CCL', 'USD', 'ARS'));

-- 2. Atributos que las fuentes declaran por especie y no tenían columna.
ALTER TABLE public.instrumentos
    ADD COLUMN estructura_cupon   text,
    ADD COLUMN moneda_cotizacion  text,
    ADD COLUMN plazo_liquidacion  text;

COMMENT ON COLUMN public.instrumentos.estructura_cupon IS
    'Tal como lo publica IAMC: Tasa Fija, Cupon Cero, Tasa Variable, Step Up. Sin CHECK a '
    'propósito: es vocabulario de la fuente, no una taxonomía nuestra.';
COMMENT ON COLUMN public.instrumentos.moneda_cotizacion IS
    'denominationCcy de BYMA sin traducir: ARS, USD o EXT. Es la moneda en la que cotiza ESTA '
    'especie, distinta de coupon_currency, que es en la que paga la emisión. La regla de dominio '
    '"nada se compara entre monedas sin normalizar" se apoya en esta columna.';
COMMENT ON COLUMN public.instrumentos.plazo_liquidacion IS
    'settlementType de BYMA sin mapear: 1 o 2. Cuando una especie cotiza en los dos plazos, el '
    'consolidador guarda uno solo y marca duplicado; el plazo guardado es el de esa fila.';

-- 3. IAMC publica convexidad y el Resumen no la tenía.
ALTER TABLE public.precios ADD COLUMN convexidad numeric;

COMMENT ON COLUMN public.precios.convexidad IS
    'De IAMC, por ticker exacto. Como la TIR y la duración: no se propaga a las otras especies de '
    'la emisión, porque depende del precio de cada una.';

-- 4. Qué significa `fuente` ahora que hay un consolidador de verdad.
--
-- El comentario anterior decía que la precedencia se resuelve eligiendo de qué fuente leer y no
-- mezclando fuentes dentro de una misma fila. La primera mitad sigue valiendo y la segunda no
-- podía valer: la vista `resumen` toma UNA fila de precios por ticker (LEFT JOIN LATERAL ...
-- LIMIT 1), así que si BYMA e IAMC escribieran filas separadas la última pisaría a la otra y el
-- Resumen perdería o el precio o la TIR. Lo que sí se sostiene es la disciplina por columna:
-- cada columna tiene una única fuente posible, fijada en código.
COMMENT ON COLUMN public.precios.fuente IS
    'Qué fuentes aportaron a esta fila: byma, iamc o byma+iamc. La precedencia por campo está '
    'fijada en código y cada columna tiene una sola fuente posible: last_price y effective_volume '
    'sólo de BYMA; tir, duration, paridad, convexidad y residual_value sólo de IAMC. La fila es '
    'el resultado consolidado de la corrida, que es lo que la vista resumen necesita leer.';
