-- VIGÍA · analista IA (fase 8) · tope diario de preguntas para todo el sitio.
-- La función de Supabase «analista» (nube/supabase/functions/analista) lo consulta con la clave de servicio antes de
-- llamar a Claude; si el cupo del día se acabó, no llama. No guarda las preguntas ni quién las hizo: solo la cuenta.

create table if not exists public.analista_uso (
  dia date primary key,
  preguntas integer not null default 0
);
alter table public.analista_uso enable row level security;
revoke all on public.analista_uso from anon, authenticated;

-- Suma una pregunta al día de hoy (hora de Lima) si queda cupo. Devuelve cuántas quedan después, o -1 si no había cupo.
create or replace function public.usar_analista(p_limite integer)
returns integer language plpgsql security definer set search_path = '' as $$
declare
  hoy date := (now() at time zone 'America/Lima')::date;
  n integer;
begin
  insert into public.analista_uso (dia, preguntas) values (hoy, 0) on conflict (dia) do nothing;
  update public.analista_uso set preguntas = preguntas + 1 where dia = hoy and preguntas < p_limite returning preguntas into n;
  if n is null then return -1; end if;
  return p_limite - n;
end $$;

revoke execute on function public.usar_analista(integer) from public, anon, authenticated;
grant execute on function public.usar_analista(integer) to service_role;
