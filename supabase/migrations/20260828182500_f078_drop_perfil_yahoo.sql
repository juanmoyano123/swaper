-- Se van las cuatro columnas que dejó Yahoo — F-078, fase 3.
--
-- `perfil_renta_variable` nació el 09/08/2026 con lo que traía `ClienteYahoo.perfil_de_empresa`:
-- `nombre_corto`, `nombre_largo`, `sector`, `industria`, `pais`. El 23/08/2026 se eliminó Yahoo del
-- proyecto y el job de clasificación pasó a la SEC, que escribe otras columnas. `nombre_largo`
-- sobrevivió porque la SEC y la tabla de CEDEARs de BYMA lo siguen escribiendo; las otras cuatro
-- quedaron huérfanas: nadie las escribe, nadie las lee y están vacías en las 1.641 filas (medido el
-- 28/08/2026: `count(nombre_corto) = count(sector) = count(industria) = count(pais) = 0`).
--
-- Se verificó que no queda lector antes de borrarlas: `lectura.py::COLUMNAS_PERFIL` no las nombra,
-- `perfiles.py::SQL_UPSERT_SEC` tampoco, y no hay ningún `SELECT *` sobre esta tabla en el backend.
--
-- **Se borran en vez de dejarse.** Una columna vacía llamada `pais` al lado de una tabla nueva
-- `pais_cedear` es una trampa: el próximo que busque el país del CEDEAR va a encontrar la columna
-- antes que la tabla, y va a leer NULLs creyendo que el curado no cargó. El rubro que sí existe se
-- llama `sic_oficina` y sale de la SEC; `sector` acá no es un sinónimo suyo, es un campo muerto.
--
-- Rollback: supabase/rollbacks/20260828182500_f078_drop_perfil_yahoo_down.sql

ALTER TABLE public.perfil_renta_variable
    DROP COLUMN nombre_corto,
    DROP COLUMN sector,
    DROP COLUMN industria,
    DROP COLUMN pais;

COMMENT ON TABLE public.perfil_renta_variable IS
    'Nombre, actividad (SIC), eslabón de la cadena, estrategia y geografía de fondo, ratio de '
    'conversión y mercado de origen de cada acción/CEDEAR. Escrita por el job de clasificación '
    'contra la SEC y la tabla de CEDEARs de BYMA. Valores tal como la fuente los declara, sin '
    'traducir (regla 11). El país de la empresa NO vive acá: está curado en public.pais_cedear.';
