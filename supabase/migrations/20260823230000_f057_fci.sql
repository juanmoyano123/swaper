-- FCI en el monitor, con la planilla diaria de CAFCI como fuente — F-057.
--
-- CAFCI publica `GET https://api.pub.cafci.org.ar/pb_get`, sin token: un XLSX de ~950 KB, una fila
-- por fondo × clase (4.251 filas medidas el 23/08/2026), agrupadas en 39 secciones por tipo de
-- renta × moneda. No hay parámetro de fecha —el endpoint siempre devuelve el último día hábil—, así
-- que no hay serie que pedir: cada corrida trae el snapshot completo del día.
--
-- Decisión del dueño del producto (23/08/2026): no se acumulan planillas. Cada corrida de la
-- ingesta (`app/ingesta/cafci/`) borra `fci` entero y vuelve a insertar, en una sola transacción —
-- mismo criterio que la poda por-ticker de `precios`, llevado a la tabla completa porque acá no hay
-- histórico que conservar. Nada tiene FK hacia `fci`: las carteras congelan su propio snapshot en
-- jsonb (`carteras.mercado`), así que un fondo que desaparece de la planilla de un día para el otro
-- no deja nada huérfano.
--
-- `codigo_cafci` (columna U de la planilla) es la PK: es único por fondo×clase, a diferencia de
-- `codigo_cnv` (columna S), que agrupa a todas las clases del mismo fondo padre.
--
-- `vcp` se publica **por cada mil cuotapartes** (el encabezado de la fuente dice literalmente
-- "Valor (mil cuotapartes)"): se guarda tal como la fuente lo declara, sin dividir por mil acá —
-- quien valúe una posición divide, y el comentario de columna lo deja escrito para que no se
-- repita el error de tratarlo como valor por cuotaparte.
--
-- `fci_planilla` es un singleton (una sola fila, forzada por la PK booleana) con los atributos del
-- snapshot completo: la fecha de la planilla sale del nombre del archivo que declara el
-- `content-disposition` (`20260821_Planilla_Diaria_A.xlsx`), no de ninguna columna — y las fechas
-- base de las variaciones mensual/anual/12 meses, que la fuente embebe en el propio encabezado
-- ("Variacion cuotaparte % / 31/07/26"), se leen por posición y se guardan como dato en vez de
-- hardcodearse en el código, porque cambian cada corrida.
--
-- Rollback: supabase/rollbacks/20260823230000_f057_fci_down.sql

CREATE TABLE public.fci (
    codigo_cafci            text PRIMARY KEY,

    fondo                   text NOT NULL,
    codigo_cnv              text,
    seccion                 text NOT NULL,
    tipo_renta              text NOT NULL,
    moneda                  text NOT NULL,
    region                  text,
    horizonte               text,

    fecha_vcp               date,
    vcp                     numeric,
    vcp_anterior            numeric,

    var_diaria_pct          numeric,
    var_mes_pct             numeric,
    var_anio_pct            numeric,
    var_12m_pct             numeric,

    cuotapartes             numeric,
    cuotapartes_anterior    numeric,
    patrimonio              numeric,
    patrimonio_anterior     numeric,
    market_share            numeric,

    gerente                 text,
    depositaria              text,
    calificacion            text,
    calificado              text,
    tipo_dinero             text,

    comision_ingreso        numeric,
    honorarios_adm_sg       numeric,
    honorarios_adm_sd       numeric,
    gastos_ord_gestion      numeric,
    comision_rescate        numeric,
    comision_transferencia  numeric,
    honorarios_exito        numeric,

    moneda_fondo            text,
    plazo_liq               integer,
    minimo_inversion        numeric,

    fuente                  text NOT NULL DEFAULT 'cafci',
    capturado_en            timestamptz NOT NULL
);

COMMENT ON TABLE public.fci IS
    'Fondos comunes de inversión, una fila por fondo×clase, de la planilla diaria pública de '
    'CAFCI. Se reescribe entera en cada corrida (wipe-and-replace transaccional): no acumula '
    'historia, decisión del dueño del producto del 23/08/2026.';
COMMENT ON COLUMN public.fci.vcp IS
    'Valor de cuotaparte publicado por la fuente POR CADA MIL CUOTAPARTES, tal como CAFCI lo '
    'declara. Quien valúe una posición contra `cuotapartes` divide por 1000 antes de multiplicar.';
COMMENT ON COLUMN public.fci.fecha_vcp IS
    'La fecha de la columna "Fecha" de la planilla, por fila: no siempre coincide con la fecha de '
    'la planilla (`fci_planilla.fecha_planilla`) — hay fondos que dejaron de reportar y conservan '
    'una fecha vieja. NULL en las filas donde la fuente no la publica (medido: 7 de 4.251).';
COMMENT ON COLUMN public.fci.moneda IS
    'Columna "Moneda" de la sección: ARS, USD o USB. USB es código propietario de CAFCI, no ISO '
    '4217 — se muestra tal cual, nunca se traduce ni se convierte (regla 11).';
COMMENT ON COLUMN public.fci.moneda_fondo IS
    'Columna "Moneda Fondo", distinta de `moneda` y que puede no coincidir con ella. Las dos se '
    'ingieren y la discrepancia se declara donde exista; no se elige una como la correcta.';
COMMENT ON COLUMN public.fci.plazo_liq IS
    'Columna "Plazo Liq." cruda. Además de 0-10 trae centinelas sin documentar (999, 9999, 99999, '
    '-1): se guardan tal cual, y quien los muestre deja vacío el espacio de "días para rescatar" '
    'cuando no son un plazo interpretable.';
COMMENT ON COLUMN public.fci.calificacion IS
    'NULL significa "no informada", no "sin calificación": la fuente cubre el 47% de las filas.';

ALTER TABLE public.fci ENABLE ROW LEVEL SECURITY;

CREATE POLICY fci_lectura ON public.fci
    FOR SELECT TO authenticated USING (true);

CREATE TABLE public.fci_planilla (
    id                      boolean PRIMARY KEY DEFAULT true CHECK (id),

    fecha_planilla          date NOT NULL,
    fecha_cierre_anterior   date,
    fecha_base_mes          date,
    fecha_base_anio         date,
    fecha_base_12m          date,

    total_filas             integer NOT NULL,
    capturado_en            timestamptz NOT NULL
);

COMMENT ON TABLE public.fci_planilla IS
    'Los hechos del snapshot completo de la planilla de CAFCI (una sola fila, PK booleana): de '
    'qué fecha es, y las fechas base que declaran los encabezados de variación mensual/anual/12 '
    'meses. Se reescribe junto con `fci` en cada corrida.';
COMMENT ON COLUMN public.fci_planilla.fecha_planilla IS
    'Del nombre del archivo que declara el content-disposition (ej. 20260821_Planilla_Diaria_A. '
    'xlsx), no de ninguna columna de la planilla: es lo único que la fuente declara sobre sí misma.';

ALTER TABLE public.fci_planilla ENABLE ROW LEVEL SECURITY;

CREATE POLICY fci_planilla_lectura ON public.fci_planilla
    FOR SELECT TO authenticated USING (true);

-- El job manual de F-057 (`POST /jobs/fci`) registra su propia corrida en `corridas_ingesta`
-- (F-008), que hoy sólo admite 'matinal' y 'refresh'. Se amplía el CHECK en vez de crear una tabla
-- aparte: es la misma auditoría (hora, duración, filas, alertas) que ya sirve a la barra de estado.
ALTER TABLE public.corridas_ingesta DROP CONSTRAINT corridas_ingesta_tipo_check;
ALTER TABLE public.corridas_ingesta ADD CONSTRAINT corridas_ingesta_tipo_check
    CHECK (tipo IN ('matinal', 'refresh', 'fci'));
