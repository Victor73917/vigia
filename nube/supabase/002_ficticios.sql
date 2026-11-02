-- VIGÍA · centro de comando · DATOS FICTICIOS para el proyecto de pruebas.
-- Ninguna de estas incidencias, recursos ni misiones existe. Los títulos llevan «[FICTICIO]» y la página los marca.
-- Los distritos (UBIGEO del INEI) y sus coordenadas son reales para que el mapa y las reglas por departamento se
-- puedan probar. Se puede volver a ejecutar: borra los datos ficticios anteriores y los vuelve a cargar.
-- Se ejecuta como dueño de la base (sin reglas por fila); la bitácora registra la carga sin usuario.

begin;

delete from public.mision_recursos;
delete from public.misiones where ficticio;
delete from public.incidencias where ficticio;
delete from public.recursos where ficticio;

insert into public.incidencias (titulo, tipo, nivel, estado, descripcion, ubigeo, lat, lng, creado_por, creado) values
  ('[FICTICIO] Desborde del dren Sullana en Castilla', 'inundacion', 3, 'en_atencion', 'Ejercicio: agua en calles de dos asentamientos humanos. Dato inventado para probar el sistema.', '200104', -5.196, -80.612, null, now() - interval '20 hours'),
  ('[FICTICIO] Huaico en quebrada de Huarmaca', 'huaico', 4, 'en_atencion', 'Ejercicio: vía departamental bloqueada. Dato inventado para probar el sistema.', '200304', -5.569, -79.523, null, now() - interval '14 hours'),
  ('[FICTICIO] Lluvia intensa en Catacaos', 'lluvia_intensa', 2, 'abierta', 'Ejercicio: viviendas de adobe con filtraciones. Dato inventado para probar el sistema.', '200105', -5.266, -80.677, null, now() - interval '6 hours'),
  ('[FICTICIO] Aniego en Veintiséis de Octubre', 'inundacion', 2, 'abierta', 'Ejercicio. Dato inventado para probar el sistema.', '200115', -5.182, -80.687, null, now() - interval '3 hours'),
  ('[FICTICIO] Crecida del río Tumbes', 'inundacion', 3, 'abierta', 'Ejercicio: el río sube cerca de la defensa ribereña. Dato inventado para probar el sistema.', '240101', -3.567, -80.452, null, now() - interval '9 hours'),
  ('[FICTICIO] Erosión costera en Zarumilla', 'erosion_costera', 1, 'abierta', 'Ejercicio. Dato inventado para probar el sistema.', '240301', -3.468, -80.274, null, now() - interval '30 hours'),
  ('[FICTICIO] Deslizamiento en vía de Tambo Grande', 'deslizamiento', 2, 'cerrada', 'Ejercicio ya atendido. Dato inventado para probar el sistema.', '200114', -4.927, -80.343, null, now() - interval '3 days'),
  ('[FICTICIO] Inundación en Chiclayo', 'inundacion', 2, 'abierta', 'Ejercicio. Dato inventado para probar el sistema.', '140101', -6.771, -79.840, null, now() - interval '5 hours'),
  ('[FICTICIO] Lluvia intensa en Trujillo', 'lluvia_intensa', 1, 'abierta', 'Ejercicio. Dato inventado para probar el sistema.', '130101', -8.112, -79.029, null, now() - interval '2 hours'),
  ('[FICTICIO] Huaico en Lurigancho-Chosica', 'huaico', 3, 'abierta', 'Ejercicio. Dato inventado para probar el sistema.', '150118', -11.936, -76.698, null, now() - interval '1 hour'),
  ('[FICTICIO] Desborde en Punchana', 'inundacion', 2, 'abierta', 'Ejercicio. Dato inventado para probar el sistema.', '160108', -3.727, -73.243, null, now() - interval '7 hours');

insert into public.recursos (nombre, tipo, departamento, base, estado) values
  ('[FICTICIO] Brigada de rescate 1', 'brigada', '20', 'Piura', 'asignado'),
  ('[FICTICIO] Brigada de rescate 2', 'brigada', '20', 'Sullana', 'disponible'),
  ('[FICTICIO] Camión cisterna', 'vehiculo', '20', 'Piura', 'disponible'),
  ('[FICTICIO] Retroexcavadora', 'maquinaria', '20', 'Chulucanas', 'asignado'),
  ('[FICTICIO] Motobomba de achique', 'equipo', '20', 'Castilla', 'asignado'),
  ('[FICTICIO] Bote de rescate', 'embarcacion', '24', 'Tumbes', 'disponible'),
  ('[FICTICIO] Brigada de rescate 3', 'brigada', '24', 'Tumbes', 'disponible'),
  ('[FICTICIO] Camioneta 4x4', 'vehiculo', '14', 'Chiclayo', 'mantenimiento'),
  ('[FICTICIO] Brigada de rescate 4', 'brigada', '14', 'Chiclayo', 'disponible'),
  ('[FICTICIO] Cargador frontal', 'maquinaria', '15', 'Chosica', 'disponible'),
  ('[FICTICIO] Bote fluvial', 'embarcacion', '16', 'Iquitos', 'disponible');

insert into public.misiones (incidencia_id, titulo, estado, creado_por, creado)
select id, '[FICTICIO] Achique y evacuación preventiva', 'en_curso', null, now() - interval '18 hours'
  from public.incidencias where titulo like '%Castilla%' and ficticio;
insert into public.misiones (incidencia_id, titulo, estado, creado_por, creado)
select id, '[FICTICIO] Limpieza de la vía y rescate', 'en_curso', null, now() - interval '12 hours'
  from public.incidencias where titulo like '%Huarmaca%' and ficticio;
insert into public.misiones (incidencia_id, titulo, estado, creado_por, creado, cerrado)
select id, '[FICTICIO] Despeje de la vía', 'cumplida', null, now() - interval '3 days', now() - interval '2 days'
  from public.incidencias where titulo like '%Tambo Grande%' and ficticio;

insert into public.mision_recursos (mision_id, recurso_id)
select m.id, r.id from public.misiones m, public.recursos r
 where (m.titulo like '%Achique%' and r.nombre in ('[FICTICIO] Brigada de rescate 1', '[FICTICIO] Motobomba de achique'))
    or (m.titulo like '%Limpieza%' and r.nombre = '[FICTICIO] Retroexcavadora');

commit;
