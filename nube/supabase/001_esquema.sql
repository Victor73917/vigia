-- VIGÍA · centro de comando · esquema del proyecto de PRUEBAS (vigia-pruebas, Supabase, São Paulo)
--
-- Solo admite datos ficticios: cada tabla con datos operativos tiene la restricción «ficticio = true».
-- Para un proyecto con datos reales hay que retirar esa restricción a conciencia, con el titular de los datos
-- definido (Ley 29733) y la autorización de la institución.
--
-- Acceso (reglas por fila, RLS):
--   · nadie sin sesión ve nada (la clave pública del navegador no abre ninguna tabla por sí sola);
--   · con sesión, todo exige la verificación en dos pasos (nivel aal2 del token);
--   · lector: ve sus departamentos; operador: además crea y cambia incidencias y misiones de sus departamentos;
--     supervisor: todo el país, crea recursos y asigna roles;
--   · la bitácora la escriben los disparadores, nadie la puede editar ni borrar.
--
-- Se puede volver a ejecutar: crea lo que falta y reemplaza funciones y reglas.

-- ---------- roles y perfiles ----------
do $$ begin
  create type public.rol_vigia as enum ('lector', 'operador', 'supervisor');
exception when duplicate_object then null; end $$;

create table if not exists public.perfiles (
  id uuid primary key references auth.users (id) on delete cascade,
  correo text not null,
  nombre text,
  rol public.rol_vigia not null default 'lector',
  departamentos text[] not null default '{}',   -- códigos INEI de 2 dígitos; el supervisor ve todo el país
  creado timestamptz not null default now()
);

-- cada usuario nuevo de Auth recibe un perfil de lector sin departamentos: no ve nada hasta que un supervisor lo habilite
create or replace function public.nuevo_perfil() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.perfiles (id, correo) values (new.id, lower(new.email)) on conflict (id) do nothing;
  return new;
end $$;
drop trigger if exists al_crear_usuario on auth.users;
create trigger al_crear_usuario after insert on auth.users for each row execute function public.nuevo_perfil();
-- usuarios creados antes de este esquema
insert into public.perfiles (id, correo) select id, lower(email) from auth.users on conflict (id) do nothing;

create or replace function public.mi_rol() returns public.rol_vigia
language sql stable security definer set search_path = '' as $$
  select rol from public.perfiles where id = auth.uid()
$$;
create or replace function public.mis_departamentos() returns text[]
language sql stable security definer set search_path = '' as $$
  select coalesce((select departamentos from public.perfiles where id = auth.uid()), '{}')
$$;
create or replace function public.mfa_ok() returns boolean
language sql stable set search_path = '' as $$
  select coalesce(auth.jwt() ->> 'aal', '') = 'aal2'
$$;
create or replace function public.puede_ver(dep text) returns boolean
language sql stable set search_path = '' as $$
  select public.mfa_ok() and (public.mi_rol() = 'supervisor' or dep = any (public.mis_departamentos()))
$$;
create or replace function public.puede_editar(dep text) returns boolean
language sql stable set search_path = '' as $$
  select public.puede_ver(dep) and public.mi_rol() in ('operador', 'supervisor')
$$;

-- ---------- datos operativos ----------
create table if not exists public.incidencias (
  id bigint generated always as identity primary key,
  titulo text not null check (char_length(titulo) between 3 and 140),
  tipo text not null check (tipo in ('inundacion', 'huaico', 'lluvia_intensa', 'deslizamiento', 'erosion_costera', 'otro')),
  nivel smallint not null check (nivel between 1 and 4),            -- 1 bajo · 2 medio · 3 alto · 4 crítico
  estado text not null default 'abierta' check (estado in ('abierta', 'en_atencion', 'cerrada')),
  descripcion text check (char_length(descripcion) <= 2000),
  ubigeo text not null check (ubigeo ~ '^[0-9]{6}$'),
  departamento text generated always as (left(ubigeo, 2)) stored,
  lat double precision not null check (lat between -18.6 and 0.2),
  lng double precision not null check (lng between -81.6 and -68.4),
  ficticio boolean not null default true check (ficticio),
  creado_por uuid references public.perfiles (id) default auth.uid(),
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now()
);

create table if not exists public.recursos (
  id bigint generated always as identity primary key,
  nombre text not null check (char_length(nombre) between 3 and 120),
  tipo text not null check (tipo in ('brigada', 'vehiculo', 'embarcacion', 'maquinaria', 'equipo')),
  departamento text not null check (departamento ~ '^[0-9]{2}$'),
  base text,
  estado text not null default 'disponible' check (estado in ('disponible', 'asignado', 'mantenimiento')),
  ficticio boolean not null default true check (ficticio),
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now()
);

create table if not exists public.misiones (
  id bigint generated always as identity primary key,
  incidencia_id bigint not null references public.incidencias (id),
  departamento text not null,                                      -- copiado de la incidencia por un disparador
  titulo text not null check (char_length(titulo) between 3 and 140),
  estado text not null default 'en_curso' check (estado in ('en_curso', 'cumplida', 'cancelada')),
  ficticio boolean not null default true check (ficticio),
  creado_por uuid references public.perfiles (id) default auth.uid(),
  creado timestamptz not null default now(),
  cerrado timestamptz,
  actualizado timestamptz not null default now()
);

create table if not exists public.mision_recursos (
  mision_id bigint not null references public.misiones (id),
  recurso_id bigint not null references public.recursos (id),
  primary key (mision_id, recurso_id)
);

create table if not exists public.bitacora (
  id bigint generated always as identity primary key,
  momento timestamptz not null default now(),
  usuario uuid,
  correo text,
  tabla text not null,
  fila text not null,
  accion text not null,
  departamento text,
  antes jsonb,
  despues jsonb
);
create index if not exists bitacora_momento on public.bitacora (momento desc);

create or replace function public.al_cambiar() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.actualizado := now();
  return new;
end $$;
drop trigger if exists actualizado on public.incidencias;
create trigger actualizado before update on public.incidencias for each row execute function public.al_cambiar();
drop trigger if exists actualizado on public.recursos;
create trigger actualizado before update on public.recursos for each row execute function public.al_cambiar();
drop trigger if exists actualizado on public.misiones;
create trigger actualizado before update on public.misiones for each row execute function public.al_cambiar();

create or replace function public.departamento_de_mision() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  select departamento into new.departamento from public.incidencias where id = new.incidencia_id;
  return new;
end $$;
drop trigger if exists departamento on public.misiones;
create trigger departamento before insert or update of incidencia_id on public.misiones
  for each row execute function public.departamento_de_mision();

-- bitácora: quién cambió qué y cuándo. security definer para escribir aunque el usuario no tenga permiso sobre la tabla
create or replace function public.anotar() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  fila jsonb := to_jsonb(coalesce(new, old));
begin
  insert into public.bitacora (usuario, correo, tabla, fila, accion, departamento, antes, despues)
  values (auth.uid(), (select correo from public.perfiles where id = auth.uid()), tg_table_name,
          coalesce(fila ->> 'id', fila ->> 'mision_id' || '/' || (fila ->> 'recurso_id')), lower(tg_op),
          coalesce(fila ->> 'departamento', (select departamento from public.misiones where id = (fila ->> 'mision_id')::bigint)),
          case when tg_op <> 'INSERT' then to_jsonb(old) end, case when tg_op <> 'DELETE' then to_jsonb(new) end);
  return null;
end $$;
do $$ declare t text; begin
  foreach t in array array['incidencias', 'recursos', 'misiones', 'mision_recursos', 'perfiles'] loop
    execute format('drop trigger if exists bitacora on public.%I', t);
    execute format('create trigger bitacora after insert or update or delete on public.%I for each row execute function public.anotar()', t);
  end loop;
end $$;

-- ---------- reglas por fila ----------
alter table public.perfiles enable row level security;
alter table public.incidencias enable row level security;
alter table public.recursos enable row level security;
alter table public.misiones enable row level security;
alter table public.mision_recursos enable row level security;
alter table public.bitacora enable row level security;

revoke all on public.perfiles, public.incidencias, public.recursos, public.misiones, public.mision_recursos, public.bitacora from anon;
grant select, update on public.perfiles to authenticated;
grant select, insert, update on public.incidencias, public.recursos, public.misiones to authenticated;
grant select, insert on public.mision_recursos to authenticated;
grant select on public.bitacora to authenticated;

drop policy if exists ver_propio on public.perfiles;
create policy ver_propio on public.perfiles for select to authenticated
  using (id = auth.uid() or (public.mfa_ok() and public.mi_rol() = 'supervisor'));
drop policy if exists supervisor_edita on public.perfiles;
create policy supervisor_edita on public.perfiles for update to authenticated
  using (public.mfa_ok() and public.mi_rol() = 'supervisor')
  with check (public.mfa_ok() and public.mi_rol() = 'supervisor');

drop policy if exists ver on public.incidencias;
create policy ver on public.incidencias for select to authenticated using (public.puede_ver(departamento));
drop policy if exists crear on public.incidencias;
create policy crear on public.incidencias for insert to authenticated
  with check (public.puede_editar(left(ubigeo, 2)) and creado_por = auth.uid());
drop policy if exists cambiar on public.incidencias;
create policy cambiar on public.incidencias for update to authenticated
  using (public.puede_editar(departamento)) with check (public.puede_editar(left(ubigeo, 2)));

drop policy if exists ver on public.recursos;
create policy ver on public.recursos for select to authenticated using (public.puede_ver(departamento));
drop policy if exists crear on public.recursos;
create policy crear on public.recursos for insert to authenticated with check (public.mfa_ok() and public.mi_rol() = 'supervisor');
drop policy if exists cambiar on public.recursos;
create policy cambiar on public.recursos for update to authenticated
  using (public.puede_editar(departamento)) with check (public.puede_editar(departamento));

drop policy if exists ver on public.misiones;
create policy ver on public.misiones for select to authenticated using (public.puede_ver(departamento));
drop policy if exists crear on public.misiones;
create policy crear on public.misiones for insert to authenticated
  with check (public.puede_editar((select departamento from public.incidencias i where i.id = incidencia_id)) and creado_por = auth.uid());
drop policy if exists cambiar on public.misiones;
create policy cambiar on public.misiones for update to authenticated
  using (public.puede_editar(departamento)) with check (public.puede_editar(departamento));

drop policy if exists ver on public.mision_recursos;
create policy ver on public.mision_recursos for select to authenticated
  using (exists (select 1 from public.misiones m where m.id = mision_id and public.puede_ver(m.departamento)));
drop policy if exists crear on public.mision_recursos;
create policy crear on public.mision_recursos for insert to authenticated
  with check (exists (select 1 from public.misiones m where m.id = mision_id and public.puede_editar(m.departamento)));

drop policy if exists ver on public.bitacora;
create policy ver on public.bitacora for select to authenticated
  using (public.mfa_ok() and (public.mi_rol() = 'supervisor' or (public.mi_rol() = 'operador' and departamento = any (public.mis_departamentos()))));

-- ---------- operaciones en un solo paso ----------
-- Crear una misión: la misión, sus recursos (que deben estar disponibles) y la incidencia pasa a «en atención».
-- security invoker: valen las mismas reglas por fila que si se hiciera a mano.
create or replace function public.crear_mision(p_incidencia bigint, p_titulo text, p_recursos bigint[])
returns bigint language plpgsql set search_path = '' as $$
declare
  m bigint;
  n int;
begin
  update public.recursos set estado = 'asignado' where id = any (p_recursos) and estado = 'disponible';
  get diagnostics n = row_count;
  if n <> coalesce(array_length(p_recursos, 1), 0) then
    raise exception 'Algún recurso no está disponible o no tienes permiso sobre él';
  end if;
  insert into public.misiones (incidencia_id, titulo) values (p_incidencia, p_titulo) returning id into m;
  insert into public.mision_recursos (mision_id, recurso_id) select m, unnest(p_recursos);
  update public.incidencias set estado = 'en_atencion' where id = p_incidencia and estado = 'abierta';
  return m;
end $$;

-- Cerrar una misión (cumplida o cancelada) y liberar sus recursos.
create or replace function public.cerrar_mision(p_mision bigint, p_estado text)
returns void language plpgsql set search_path = '' as $$
begin
  if p_estado not in ('cumplida', 'cancelada') then raise exception 'Estado de cierre no válido'; end if;
  update public.misiones set estado = p_estado, cerrado = now() where id = p_mision and estado = 'en_curso';
  if not found then raise exception 'La misión no está en curso o no tienes permiso'; end if;
  update public.recursos set estado = 'disponible'
    where id in (select recurso_id from public.mision_recursos where mision_id = p_mision) and estado = 'asignado';
end $$;

revoke execute on function public.crear_mision(bigint, text, bigint[]), public.cerrar_mision(bigint, text) from public, anon;
grant execute on function public.crear_mision(bigint, text, bigint[]), public.cerrar_mision(bigint, text) to authenticated;

-- ---------- tiempo real (respeta las mismas reglas por fila) ----------
do $$ declare t text; begin
  foreach t in array array['incidencias', 'recursos', 'misiones'] loop
    begin
      execute format('alter publication supabase_realtime add table public.%I', t);
    exception when duplicate_object then null;
    end;
  end loop;
end $$;
