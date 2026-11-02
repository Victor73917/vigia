-- VIGÍA · portal ciudadano (fase 7) · proyecto de PRUEBAS, solo reportes ficticios.
--
-- Cualquiera puede enviar un reporte sin cuenta, pero solo a través de la función enviar_reporte: la tabla no se puede
-- leer ni escribir sin sesión. El reporte no guarda nombre, DNI, teléfono, correo ni dirección IP. El ciudadano recibe
-- un código para seguir el estado de su reporte (estado_reporte). El mapa público muestra solo los reportes que un
-- operador verificó, con la ubicación redondeada a unos 1 km (reportes_publicos).
-- Para recibir reportes reales hace falta el titular del banco de datos (Ley 29733), la autorización de la institución
-- y quitar a conciencia la restricción «ficticio = true».

create table if not exists public.reportes (
  id bigint generated always as identity primary key,
  codigo text not null unique default upper(substr(md5(random()::text || clock_timestamp()::text), 1, 10)),
  tipo text not null check (tipo in ('inundacion', 'huaico', 'lluvia_intensa', 'deslizamiento', 'erosion_costera', 'otro')),
  descripcion text not null check (char_length(descripcion) between 10 and 1000),
  ubigeo text not null check (ubigeo ~ '^[0-9]{6}$'),
  departamento text generated always as (left(ubigeo, 2)) stored,
  lat double precision not null check (lat between -18.6 and 0.2),
  lng double precision not null check (lng between -81.6 and -68.4),
  estado text not null default 'recibido' check (estado in ('recibido', 'verificado', 'descartado', 'convertido')),
  incidencia_id bigint references public.incidencias (id),
  nota text check (char_length(nota) <= 500),                     -- nota del operador, visible para el ciudadano con su código
  ficticio boolean not null default true check (ficticio),
  creado timestamptz not null default now(),
  revisado timestamptz,
  revisado_por uuid references public.perfiles (id),
  actualizado timestamptz not null default now()
);
create index if not exists reportes_creado on public.reportes (creado desc);

drop trigger if exists actualizado on public.reportes;
create trigger actualizado before update on public.reportes for each row execute function public.al_cambiar();
drop trigger if exists bitacora on public.reportes;
create trigger bitacora after insert or update or delete on public.reportes for each row execute function public.anotar();

alter table public.reportes enable row level security;
revoke all on public.reportes from anon;
grant select, update on public.reportes to authenticated;

drop policy if exists ver on public.reportes;
create policy ver on public.reportes for select to authenticated using (public.puede_ver(departamento));
drop policy if exists cambiar on public.reportes;
create policy cambiar on public.reportes for update to authenticated
  using (public.puede_editar(departamento)) with check (public.puede_editar(departamento));

-- Envío sin cuenta. Límites para que nadie llene la base: 30 reportes por 10 minutos en todo el país y 5 por distrito.
create or replace function public.enviar_reporte(p_tipo text, p_descripcion text, p_ubigeo text, p_lat double precision, p_lng double precision)
returns text language plpgsql security definer set search_path = '' as $$
declare
  c text;
begin
  if (select count(*) from public.reportes where creado > now() - interval '10 minutes') >= 30 then
    raise exception 'Hay demasiados reportes en este momento. Intenta en unos minutos.';
  end if;
  if (select count(*) from public.reportes where ubigeo = p_ubigeo and creado > now() - interval '10 minutes') >= 5 then
    raise exception 'Ya se recibieron varios reportes de este distrito. Intenta en unos minutos.';
  end if;
  insert into public.reportes (tipo, descripcion, ubigeo, lat, lng)
  values (p_tipo, trim(p_descripcion), p_ubigeo, p_lat, p_lng) returning codigo into c;
  return c;
end $$;

-- Seguimiento con el código: solo el estado, el tipo, las fechas y la nota del operador.
create or replace function public.estado_reporte(p_codigo text)
returns table (estado text, tipo text, ubigeo text, creado timestamptz, revisado timestamptz, nota text)
language sql stable security definer set search_path = '' as $$
  select r.estado, r.tipo, r.ubigeo, r.creado, r.revisado, r.nota from public.reportes r where r.codigo = upper(trim(p_codigo))
$$;

-- Mapa público: reportes verificados de los últimos 7 días, sin descripción y con la ubicación a unos 1 km.
create or replace function public.reportes_publicos()
returns table (tipo text, ubigeo text, lat double precision, lng double precision, creado timestamptz)
language sql stable security definer set search_path = '' as $$
  select r.tipo, r.ubigeo, round(r.lat::numeric, 2)::double precision, round(r.lng::numeric, 2)::double precision, r.creado
    from public.reportes r
   where r.estado in ('verificado', 'convertido') and r.creado > now() - interval '7 days'
   order by r.creado desc limit 500
$$;

-- El operador convierte un reporte en incidencia (security invoker: valen sus reglas por fila).
create or replace function public.convertir_reporte(p_reporte bigint, p_nivel smallint, p_titulo text)
returns bigint language plpgsql set search_path = '' as $$
declare
  r public.reportes;
  i bigint;
begin
  select * into r from public.reportes where id = p_reporte and estado in ('recibido', 'verificado');
  if not found then raise exception 'El reporte no existe, ya se cerró o no tienes permiso'; end if;
  insert into public.incidencias (titulo, tipo, nivel, descripcion, ubigeo, lat, lng)
  values (p_titulo, r.tipo, p_nivel, 'Desde el reporte ciudadano ' || r.codigo || ': ' || r.descripcion, r.ubigeo, r.lat, r.lng)
  returning id into i;
  update public.reportes set estado = 'convertido', incidencia_id = i, revisado = now(), revisado_por = auth.uid() where id = p_reporte;
  return i;
end $$;

revoke execute on function public.enviar_reporte(text, text, text, double precision, double precision),
  public.estado_reporte(text), public.reportes_publicos(), public.convertir_reporte(bigint, smallint, text) from public;
grant execute on function public.enviar_reporte(text, text, text, double precision, double precision),
  public.estado_reporte(text), public.reportes_publicos() to anon, authenticated;
revoke execute on function public.convertir_reporte(bigint, smallint, text) from anon;
grant execute on function public.convertir_reporte(bigint, smallint, text) to authenticated;

do $$ begin
  alter publication supabase_realtime add table public.reportes;
exception when duplicate_object then null; end $$;
