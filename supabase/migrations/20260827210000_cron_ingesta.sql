-- Ingesta programada desde la base — 27/08/2026.
--
-- Por qué acá y no en otro lado. Hasta hoy la ingesta "automática" era un `uvicorn --reload` en la
-- notebook del asesor: el scheduler in-process de `backend/app/jobs/scheduler.py` con
-- INGESTA_HABILITADA=true apuntando a esta base. Funcionaba mientras la máquina estuviera prendida,
-- corría a intervalos erráticos (cada `--reload` reinicia el reloj) y **sólo disparaba el refresh**,
-- nunca la matinal — por eso la metadata del universo quedó congelada el 17/08 y las letras
-- entraron sin moneda ni vencimiento.
--
-- Las dos alternativas se descartaron con evidencia:
--   * **Vercel Cron**: el proyecto está en plan Hobby, donde los crons corren una vez por día y sin
--     minuto exacto. Alcanza para la matinal, no para un refresh cada 20 minutos.
--   * **GitHub Actions**: se configuró el 26/08 y no disparó **ninguna** de las ~20 veces que le
--     tocaba el 27/08, con el workflow activo y Actions habilitado. Sus schedules son best-effort.
--
-- pg_cron corre dentro del mismo Postgres que ya está siempre encendido, con granularidad de un
-- minuto y sin depender de ninguna máquina de nadie. El disparo es un HTTP a los endpoints que ya
-- existen, así que la lógica de ingesta no se duplica: la base sólo toca el timbre.
--
-- Los horarios van en UTC porque el server está en UTC (`show timezone`). Argentina es UTC-3 fijo.

create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

-- El secreto NO viaja en el cuerpo del job: `cron.job.command` es texto plano legible por cualquiera
-- con acceso a la base. Se guarda en Vault y se lee en el momento del disparo.
--
-- Se crea por fuera de esta migración (una migración versionada no puede contener el secreto):
--   select vault.create_secret('<valor>', 'cron_secret', 'Credencial del cron de ingesta.');
--
-- Y opcionalmente, para apuntar a otro deploy sin editar esta función:
--   select vault.create_secret('https://otro-host', 'swaper_base_url', '...');

create or replace function public.disparar_corrida_ingesta(p_tipo text)
returns bigint
language plpgsql
security definer
set search_path = public, extensions, vault
as $$
declare
    v_secreto text;
    v_base    text;
    v_request bigint;
begin
    -- Lista blanca explícita: este texto se concatena a una URL, y aunque el origen sea un job
    -- nuestro, una función SECURITY DEFINER no debe confiar en su argumento.
    if p_tipo not in ('matinal', 'refresh') then
        raise exception 'tipo de corrida desconocido: %', p_tipo;
    end if;

    select decrypted_secret into v_secreto from vault.decrypted_secrets where name = 'cron_secret';
    if v_secreto is null then
        raise exception 'falta el secreto cron_secret en Vault: el backend rechazaría el disparo';
    end if;

    select decrypted_secret into v_base from vault.decrypted_secrets where name = 'swaper_base_url';
    v_base := coalesce(v_base, 'https://swaper-snowy.vercel.app');

    -- pg_net es asíncrono: encola el pedido y devuelve su id. No se espera la respuesta a propósito
    -- —una corrida matinal puede tardar minutos y no tiene sentido tener una transacción de la base
    -- esperándola—. La traza de lo que efectivamente pasó la deja el backend en
    -- `public.corridas_ingesta`; acá sólo queda el acuse en `net._http_response`.
    --
    -- El timeout es del lado del cliente: si vence, el backend sigue procesando igual. Se le da a la
    -- matinal el margen del `maxDuration` de Vercel (300 s) menos un colchón.
    select net.http_get(
        url := v_base || '/api/v1/jobs/cron/' || p_tipo,
        headers := jsonb_build_object('Authorization', 'Bearer ' || v_secreto),
        timeout_milliseconds := case when p_tipo = 'matinal' then 280000 else 60000 end
    ) into v_request;

    return v_request;
end;
$$;

comment on function public.disparar_corrida_ingesta(text) is
    'Le pega al endpoint de cron del backend con la credencial guardada en Vault. La usan los jobs '
    'de pg_cron; no está pensada para llamarse a mano salvo para probar.';

-- Nadie más que el dueño de la base la ejecuta: puede disparar una ingesta completa y lee un secreto.
revoke all on function public.disparar_corrida_ingesta(text) from public;
revoke all on function public.disparar_corrida_ingesta(text) from anon, authenticated;

-- Los jobs. `cron.schedule` con un nombre ya existente lo reemplaza, así que esta migración es
-- idempotente y re-aplicarla no duplica disparos.
--
-- 14:30 UTC = 11:30 ART. La matinal trae el universo completo: BYMA, data912, CAFCI y el cronograma.
select cron.schedule(
    'ingesta-matinal',
    '30 14 * * 1-5',
    $cmd$select public.disparar_corrida_ingesta('matinal')$cmd$
);

-- Rueda: 14:00 a 19:40 UTC = 11:00 a 16:40 ART, cada 20 minutos, que es la demora que la API abierta
-- de BYMA declara. Pedir más seguido sería pedir tres veces por hora un dato que se renueva dos y
-- media (mismo criterio que `ingesta_refresh_minutos` en el backend).
select cron.schedule(
    'ingesta-refresh',
    '*/20 14-19 * * 1-5',
    $cmd$select public.disparar_corrida_ingesta('refresh')$cmd$
);

-- El tick de las 17:00 ART, que el rango de arriba no alcanza porque corta a las 19:40 UTC.
select cron.schedule(
    'ingesta-refresh-cierre',
    '0 20 * * 1-5',
    $cmd$select public.disparar_corrida_ingesta('refresh')$cmd$
);
