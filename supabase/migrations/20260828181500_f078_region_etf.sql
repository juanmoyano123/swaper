-- Geografía declarada por el nombre oficial de un ETF — F-078, fase 1.
--
-- `perfil_renta_variable.estrategia_etf` ya guarda qué idea arma el portafolio de un fondo, leída
-- del nombre que publica BYMA (`app/renta_variable/etfs.py`). De los 123 papeles con estrategia,
-- 27 la tienen `geografico`: el nombre nombra un país o una región y hoy ese dato se pierde en una
-- sola palabra ("Geográfico") que no dice *cuál*. Para filtrar el mission control de F-078 por
-- geografía hace falta el token, no la categoría.
--
-- **Columna y no derivación al vuelo** por la misma razón que `estrategia_etf`: el nombre vive en
-- esta tabla, el listado la lee con un LEFT JOIN, y re-parsear ~1.600 nombres en cada request de
-- monitor es trabajo repetido en un backend serverless con pool de 5 conexiones.
--
-- Se escribe donde se escribe `estrategia_etf` —`perfiles.py::SQL_UPSERT_SEC`, llamado desde
-- `clasificacion.py`— y se rellena sin tocar la SEC con `POST /api/v1/jobs/reclasificar-etfs`, que
-- la re-deriva del `nombre_largo` ya persistido.
--
-- **El valor es el token del nombre, sin traducir** (regla 11): `EAFE` se guarda `EAFE`, no
-- "Europa, Australasia y Lejano Oriente". Es un vocabulario distinto del de la región curada por
-- país (`pais_cedear` + subregión M49), y conviven a propósito: unificarlos sería traducir.
--
-- Rollback: supabase/rollbacks/20260828181500_f078_region_etf_down.sql

ALTER TABLE public.perfil_renta_variable ADD COLUMN region_etf text;

COMMENT ON COLUMN public.perfil_renta_variable.region_etf IS
    'Geografía que declara el nombre oficial del fondo, tal como aparece en el nombre (China, '
    'EAFE, Latin America). NULL = el papel no es un fondo, o su nombre no nombra ninguna '
    'geografía. Nunca se traduce ni se completa por el índice que el fondo replica (regla 11).';
