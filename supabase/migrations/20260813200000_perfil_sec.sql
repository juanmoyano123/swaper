-- Clasificación de renta variable desde la SEC y la lista de CEDEARs de BYMA.
--
-- `perfil_renta_variable` ya existía con lo que traía Yahoo (nombre, sector, industria, país) y con
-- `fuente` NOT NULL, así que estaba preparada para más de un origen desde el día uno. Estas columnas
-- son lo que Yahoo no daba y lo que el asesor pidió: a qué se dedica el papel, en qué eslabón de la
-- cadena productiva está, y qué idea arma el portafolio cuando es un fondo.
--
-- **Todas nullable, sin excepción.** La SEC cubre 315 de 427 CEDEARs y sólo 21 de 245 acciones
-- argentinas: la mayoría de las filas va a tener parte de esto vacío, y eso se declara en pantalla
-- en vez de completarse por analogía (regla 1). Las argentinas esperan a la CNV (F-054).

ALTER TABLE public.perfil_renta_variable
    -- El código de actividad tal como lo declara la SEC, sin normalizar: es la llave contra el
    -- catálogo oficial de 444 códigos y contra cualquier auditoría posterior.
    ADD COLUMN sic_codigo text,
    -- El título de la actividad. Viaja junto al código y no se deriva de él: la SEC lo manda en el
    -- mismo pedido, y guardarlo evita que una fila vieja pierda sentido si el catálogo cambia.
    ADD COLUMN sic_titulo text,
    -- La oficina de la SEC que revisa esa industria. Es la agrupación por rubro que hace la propia
    -- fuente — no una que hayamos armado acá.
    ADD COLUMN sic_oficina text,
    -- En qué eslabón de la cadena está la empresa: extracción, manufactura, comercio, servicios.
    -- Sale de la división del SIC Manual (ver `app/externos/sic.py`), que es estructura oficial de
    -- la taxonomía. NULL cuando el código cae en un hueco del manual o no hay código.
    ADD COLUMN division_cadena text,
    -- Qué idea arma el portafolio de un fondo, leída del nombre que publica BYMA. NULL cuando el
    -- papel no es un fondo; `'sin_clasificar'` cuando lo es y su nombre no declara la estrategia.
    ADD COLUMN estrategia_etf text,
    -- De la tabla oficial de CEDEARs de BYMA: cuántos CEDEARs equivalen a una acción del
    -- subyacente, y en qué mercado cotiza ese subyacente. Texto y no numérico porque la fuente lo
    -- publica como razón (`20:1`, `1:3`) y partirlo en dos números es una decisión de presentación,
    -- no de almacenamiento.
    ADD COLUMN ratio_conversion text,
    ADD COLUMN mercado_origen text;

COMMENT ON COLUMN public.perfil_renta_variable.sic_codigo IS
    'Standard Industrial Classification declarado por la SEC. NULL si el papel no tiene CIK.';
COMMENT ON COLUMN public.perfil_renta_variable.division_cadena IS
    'Eslabón de la cadena productiva, derivado del rango del SIC según el SIC Manual (OSHA). '
    'Nunca se aproxima al eslabón más parecido: un código fuera de los rangos queda NULL.';
COMMENT ON COLUMN public.perfil_renta_variable.estrategia_etf IS
    'Idea de armado del fondo, leída del nombre oficial de BYMA. NULL = no es un fondo.';
