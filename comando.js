/* VIGÍA · centro de comando (fase 6).
   Solo se publica en el sitio de pruebas y solo con un proyecto Supabase configurado (construir.py). Todos los datos son
   ficticios: la base rechaza cualquier fila sin «ficticio = true». La seguridad no depende de esta página: las reglas por
   fila de la base (nube/supabase/001_esquema.sql) deciden qué ve y qué cambia cada usuario, y exigen la verificación en
   dos pasos. Aquí no hay claves privadas: la dirección y la clave pública del proyecto llegan en window.VIGIA_NUBE. */
(() => {
  'use strict';
  const NUBE = window.VIGIA_NUBE;
  if (!NUBE) return;
  const listo = new Promise(r => window.VIGIA_EXT ? r() : addEventListener('vigia:ext', r, { once: true }));

  const TIPOS = { inundacion: 'Inundación', huaico: 'Huaico', lluvia_intensa: 'Lluvia intensa', deslizamiento: 'Deslizamiento', erosion_costera: 'Erosión costera', otro: 'Otro' };
  const NIVELES = { 1: ['Bajo', 'amarillo'], 2: ['Medio', 'naranja'], 3: ['Alto', 'rojo'], 4: ['Crítico', 'rojo'] };
  const ESTADOS = { abierta: 'Abierta', en_atencion: 'En atención', cerrada: 'Cerrada' };
  const ESTADOS_MIS = { en_curso: 'En curso', cumplida: 'Cumplida', cancelada: 'Cancelada' };
  const ESTADOS_REC = { disponible: 'Disponible', asignado: 'Asignado', mantenimiento: 'En mantenimiento' };
  const TIPOS_REC = { brigada: 'Brigada', vehiculo: 'Vehículo', embarcacion: 'Embarcación', maquinaria: 'Maquinaria', equipo: 'Equipo' };
  const ROLES = { lector: 'Lector', operador: 'Operador', supervisor: 'Supervisor' };

  const ESTADOS_REP = { recibido: 'Recibido, sin revisar', verificado: 'Verificado por un operador', descartado: 'Descartado', convertido: 'Convertido en incidencia' };
  // números oficiales verificados en gob.pe (PNP: gob.pe/institucion/pnp/contacto-y-numeros-de-emergencias; SAMU: gob.pe/1013)
  const EMERGENCIAS = [['105', 'Policía Nacional'], ['116', 'Bomberos'], ['106', 'SAMU (emergencias médicas)'], ['115', 'Defensa Civil']];

  let X, sb, yo = null, canal = null, recarga = null, eligiendo = null;
  const D = { inc: [], rec: [], mis: [], mr: [], bit: [], per: [], rep: [] };
  const V = { filtro: 'activas', sel: null, nueva: null, error: '' };
  const R = { borrador: { tipo: 'inundacion' }, enviado: null, seguimiento: null, publicos: [] };
  const cuerpoRep = () => document.getElementById('reportarCuerpo');
  const cuerpo = () => document.getElementById('comandoCuerpo');
  const e = s => X.esc(s ?? '');
  const puedeEditar = () => yo && (yo.rol === 'operador' || yo.rol === 'supervisor');
  const nomDep = id => X.titulo(X.TERR?.departamentos.find(d => d[0] === id)?.[1] || id);
  const nomDist = ub => { const t = X.TERR?.distritos.find(d => d[0] === ub); return t ? `${X.titulo(t[1])} · ${nomDep(ub.slice(0, 2))}` : ub; };
  const hace = t => { const m = Math.round((Date.now() - Date.parse(t)) / 60000); return m < 60 ? `hace ${Math.max(1, m)} min` : m < 2880 ? `hace ${Math.round(m / 60)} h` : `hace ${Math.round(m / 1440)} días`; };
  const chipNivel = n => `<span class="nivel-chip" style="--c:var(--${NIVELES[n]?.[1] || 'tinta-3'})">${NIVELES[n]?.[0] || n}</span>`;
  const ficticio = '<span class="cmd-ficticio" title="Dato inventado para probar el sistema">FICTICIO</span>';

  const estilo = document.createElement('style');
  estilo.textContent = `
    .cmd-sesion{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;justify-content:space-between;font-size:12.5px;color:var(--tinta-2);margin:4px 0 10px}
    .cmd-ficticio{display:inline-block;font:700 10px/1.5 system-ui,sans-serif;letter-spacing:.06em;color:#ffd9b0;background:#5a1d00;border:1px solid #ff8a3d;border-radius:4px;padding:0 5px;vertical-align:middle}
    .cmd-aviso{border:1px solid #ff8a3d;background:rgba(255,138,61,.08);border-radius:8px;padding:8px 10px;font-size:12.5px;margin:0 0 10px}
    .cmd-form{display:grid;gap:8px;margin:8px 0 12px}
    .cmd-form label{display:grid;gap:3px;font-size:12px;color:var(--tinta-2)}
    .cmd-form input,.cmd-form select,.cmd-form textarea{font:inherit;font-size:14px;color:var(--tinta);background:var(--fondo-2,rgba(255,255,255,.04));border:1px solid var(--borde,rgba(255,255,255,.15));border-radius:6px;padding:7px 9px}
    .cmd-form .fila{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .cmd-error{color:var(--rojo);font-size:12.5px;margin:6px 0}
    .cmd-qr{background:#fff;padding:8px;border-radius:8px;width:180px;height:180px}
    .cmd-lista{display:grid;gap:6px;margin:6px 0 12px}
    .cmd-inc{display:grid;grid-template-columns:auto 1fr auto;gap:2px 8px;align-items:center;text-align:left;width:100%;background:transparent;border:1px solid var(--borde,rgba(255,255,255,.12));border-radius:8px;padding:7px 9px;color:inherit;cursor:pointer}
    .cmd-inc[aria-current="true"]{border-color:var(--sodio)}
    .cmd-inc small{grid-column:2/4;color:var(--tinta-2)}
    .cmd-det{border:1px solid var(--sodio);border-radius:8px;padding:10px;margin:0 0 12px}
    .cmd-det h3{margin:0 0 4px}
    .cmd-rec{display:flex;gap:6px;align-items:center;font-size:13px}
    .cmd-bit{font-size:12px;color:var(--tinta-2);display:grid;gap:3px}
    .cmd-bit b{color:var(--tinta)}`;
  document.head.appendChild(estilo);

  /* ---------- sesión y verificación en dos pasos ---------- */
  async function iniciar() {
    await listo;
    X = window.VIGIA_EXT;
    if (!window.supabase?.createClient) { cuerpo().innerHTML = '<p class="vacio">No se pudo cargar la librería de Supabase.</p>'; return; }
    sb = window.supabase.createClient(NUBE.url, NUBE.anon, { auth: { persistSession: true, autoRefreshToken: true } });
    X.cargarTerritorio();
    sb.auth.onAuthStateChange(ev => { if (ev === 'SIGNED_OUT') salir(false); });
    addEventListener('vigia:comando', pintar);
    addEventListener('vigia:reportar', pintarReportar);
    pintar();
    pintarReportar();
    cargarPublicos();
    setInterval(cargarPublicos, 5 * 60000);
  }

  async function pintar() {
    if (!sb) return;
    const { data: { session } } = await sb.auth.getSession();
    if (!session) return formEntrar();
    const { data: aal } = await sb.auth.mfa.getAuthenticatorAssuranceLevel();
    if (aal?.currentLevel !== 'aal2') return aal?.nextLevel === 'aal2' ? formCodigo() : formEnrolar();
    if (!yo) await cargarTodo();
    panel();
  }

  function formEntrar() {
    cuerpo().innerHTML = `
      <div class="cmd-aviso">Entorno de pruebas: todas las incidencias, recursos y misiones son <b>ficticios</b>. No registres datos reales ni personales.</div>
      <form class="cmd-form" id="cmdEntrar" autocomplete="on">
        <label>Correo<input type="email" name="correo" autocomplete="username" required></label>
        <label>Contraseña<input type="password" name="clave" autocomplete="current-password" required></label>
        <div class="fila"><button class="btn prim" type="submit">Entrar</button><small>Los usuarios los crea un supervisor; no hay registro abierto.</small></div>
        <p class="cmd-error" role="alert">${e(V.error)}</p>
      </form>`;
    V.error = '';
    document.getElementById('cmdEntrar').onsubmit = async ev => {
      ev.preventDefault();
      const f = new FormData(ev.target);
      const { error } = await sb.auth.signInWithPassword({ email: String(f.get('correo')).trim(), password: String(f.get('clave')) });
      if (error) { V.error = 'Correo o contraseña incorrectos.'; return formEntrar(); }
      pintar();
    };
  }

  async function formEnrolar() {
    const { data: fs } = await sb.auth.mfa.listFactors();
    for (const f of fs?.all || []) if (f.status !== 'verified') await sb.auth.mfa.unenroll({ factorId: f.id });
    const { data, error } = await sb.auth.mfa.enroll({ factorType: 'totp', friendlyName: 'VIGIA ' + new Date().toISOString().slice(0, 10) });
    if (error) { cuerpo().innerHTML = `<p class="cmd-error">No se pudo iniciar la verificación en dos pasos: ${e(error.message)}</p>${botonSalir()}`; enlazarSalir(); return; }
    cuerpo().innerHTML = `
      <p>Para entrar al centro de comando hace falta la <b>verificación en dos pasos</b>. Escanea este código con una aplicación de autenticación (Google Authenticator, Microsoft Authenticator u otra) y escribe el código de 6 dígitos que muestra.</p>
      <img class="cmd-qr" src="${e(data.totp.qr_code)}" alt="Código QR para la aplicación de autenticación">
      <p><small>Si no puedes escanearlo, escribe esta clave en la aplicación: <code>${e(data.totp.secret)}</code></small></p>
      <form class="cmd-form" id="cmdVerificar" autocomplete="off">
        <label>Código de 6 dígitos<input name="codigo" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required autocomplete="one-time-code"></label>
        <div class="fila"><button class="btn prim" type="submit">Verificar</button>${botonSalir()}</div>
        <p class="cmd-error" role="alert"></p>
      </form>`;
    enlazarSalir();
    document.getElementById('cmdVerificar').onsubmit = async ev => {
      ev.preventDefault();
      const { error: err } = await sb.auth.mfa.challengeAndVerify({ factorId: data.id, code: new FormData(ev.target).get('codigo') });
      if (err) { ev.target.querySelector('.cmd-error').textContent = 'Código incorrecto o vencido. Prueba con el siguiente.'; return; }
      pintar();
    };
  }

  async function formCodigo() {
    const { data: fs } = await sb.auth.mfa.listFactors();
    const f = fs?.totp?.[0];
    if (!f) return formEnrolar();
    cuerpo().innerHTML = `
      <form class="cmd-form" id="cmdCodigo" autocomplete="off">
        <label>Código de tu aplicación de autenticación<input name="codigo" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required autocomplete="one-time-code"></label>
        <div class="fila"><button class="btn prim" type="submit">Verificar</button>${botonSalir()}</div>
        <p class="cmd-error" role="alert"></p>
      </form>`;
    enlazarSalir();
    document.getElementById('cmdCodigo').onsubmit = async ev => {
      ev.preventDefault();
      const { error } = await sb.auth.mfa.challengeAndVerify({ factorId: f.id, code: new FormData(ev.target).get('codigo') });
      if (error) { ev.target.querySelector('.cmd-error').textContent = 'Código incorrecto o vencido.'; return; }
      pintar();
    };
  }

  const botonSalir = () => '<button class="btn" type="button" data-cmd-salir>Cerrar sesión</button>';
  function enlazarSalir() { for (const b of cuerpo().querySelectorAll('[data-cmd-salir]')) b.onclick = () => sb.auth.signOut(); }
  function salir(repintar = true) {
    yo = null; Object.keys(D).forEach(k => { D[k] = []; }); V.sel = null; V.nueva = null;
    if (canal) { sb.removeChannel(canal); canal = null; }
    capaMapa();
    if (repintar) pintar(); else formEntrar();
  }

  /* ---------- datos ---------- */
  async function cargarTodo() {
    const { data: { user } } = await sb.auth.getUser();
    const [per, inc, rec, mis, mr, bit, rep] = await Promise.all([
      sb.from('perfiles').select('*').order('correo'),
      sb.from('incidencias').select('*').order('creado', { ascending: false }),
      sb.from('recursos').select('*').order('departamento').order('nombre'),
      sb.from('misiones').select('*').order('creado', { ascending: false }),
      sb.from('mision_recursos').select('*'),
      sb.from('bitacora').select('*').order('momento', { ascending: false }).limit(40),
      sb.from('reportes').select('*').in('estado', ['recibido', 'verificado']).order('creado', { ascending: false }).limit(100),
    ]);
    const err = [per, inc, rec, mis, mr, bit, rep].find(r => r.error);
    if (err) V.error = err.error.message;
    D.per = per.data || []; D.inc = inc.data || []; D.rec = rec.data || []; D.mis = mis.data || []; D.mr = mr.data || []; D.bit = bit.data || []; D.rep = rep.data || [];
    yo = D.per.find(p => p.id === user.id) || { id: user.id, correo: user.email, rol: 'lector', departamentos: [] };
    if (!canal) {
      canal = sb.channel('comando');
      for (const t of ['incidencias', 'recursos', 'misiones', 'reportes']) canal.on('postgres_changes', { event: '*', schema: 'public', table: t }, () => { clearTimeout(recarga); recarga = setTimeout(async () => { await cargarTodo(); panel(); }, 600); });
      canal.subscribe();
    }
    capaMapa();
  }

  async function hacer(promesa, ok) {
    const { error } = await promesa;
    if (error) { X.avisoToast(`<b>No se pudo guardar</b><br><small>${e(error.message)}</small>`, 9000, 'error'); return false; }
    if (ok) X.avisoToast(ok, 5000, 'info');
    await cargarTodo(); panel();
    return true;
  }

  /* ---------- panel ---------- */
  function panel() {
    const activas = D.inc.filter(i => i.estado !== 'cerrada'), lista = V.filtro === 'activas' ? activas : D.inc.filter(i => i.estado === 'cerrada');
    const sinAlcance = yo.rol !== 'supervisor' && !yo.departamentos.length;
    const sel = D.inc.find(i => i.id === V.sel);
    cuerpo().innerHTML = `
      <div class="cmd-sesion"><span>${e(yo.correo)} · <b>${ROLES[yo.rol]}</b> · ${yo.rol === 'supervisor' ? 'todo el país' : yo.departamentos.map(nomDep).join(', ') || 'sin departamentos'}</span>${botonSalir()}</div>
      <div class="cmd-aviso">Entorno de pruebas: todo lo que ves aquí es ${ficticio}. No registres datos reales ni personales.</div>
      ${V.error ? `<p class="cmd-error">${e(V.error)}</p>` : ''}
      ${sinAlcance ? '<p class="vacio">Tu usuario todavía no tiene departamentos asignados. Pide a un supervisor que te los asigne.</p>' : ''}
      <div class="kpis">
        <div class="kpi"><small>Incidencias abiertas</small><b>${D.inc.filter(i => i.estado === 'abierta').length}</b><span>sin misión todavía</span></div>
        <div class="kpi"><small>En atención</small><b>${D.inc.filter(i => i.estado === 'en_atencion').length}</b><span>con misión en curso</span></div>
        <div class="kpi"><small>Recursos disponibles</small><b>${D.rec.filter(r => r.estado === 'disponible').length}</b><span>de ${D.rec.length}</span></div>
        <div class="kpi"><small>Misiones en curso</small><b>${D.mis.filter(m => m.estado === 'en_curso').length}</b><span>${D.mis.length} en total</span></div>
      </div>
      ${puedeEditar() ? (V.nueva ? formNueva() : '<p><button class="btn prim" type="button" data-cmd-nueva>+ Nueva incidencia</button></p>') : ''}
      ${sel ? detalle(sel) : ''}
      ${bandeja()}
      <h3>Incidencias</h3>
      <div class="fila-botones" role="group" aria-label="Filtrar incidencias">
        <button class="btn${V.filtro === 'activas' ? ' prim' : ''}" type="button" data-cmd-filtro="activas">Activas (${activas.length})</button>
        <button class="btn${V.filtro === 'cerradas' ? ' prim' : ''}" type="button" data-cmd-filtro="cerradas">Cerradas (${D.inc.length - activas.length})</button>
      </div>
      <div class="cmd-lista">${lista.map(i => `
        <button class="cmd-inc" type="button" data-cmd-inc="${i.id}" aria-current="${i.id === V.sel}">${chipNivel(i.nivel)}<b>${e(i.titulo)}</b><span>${ESTADOS[i.estado]}</span>
          <small>${TIPOS[i.tipo]} · ${e(nomDist(i.ubigeo))} · ${hace(i.creado)}</small></button>`).join('') || '<p class="vacio">Ninguna.</p>'}</div>
      <h3>Recursos</h3>
      <table class="tabla"><thead><tr><th>Recurso</th><th>Base</th><th>Estado</th></tr></thead><tbody>${D.rec.map(r => `
        <tr><td><b>${e(r.nombre)}</b><small>${TIPOS_REC[r.tipo]} · ${e(nomDep(r.departamento))}</small></td><td>${e(r.base || '–')}</td><td>${ESTADOS_REC[r.estado]}${puedeEditar() && r.estado !== 'asignado' ? `<br><button class="btn" type="button" data-cmd-mant="${r.id}">${r.estado === 'mantenimiento' ? 'Marcar disponible' : 'A mantenimiento'}</button>` : ''}</td></tr>`).join('') || '<tr><td colspan="3" class="vacio">Sin recursos a la vista.</td></tr>'}</tbody></table>
      ${yo.rol === 'supervisor' ? usuarios() : ''}
      ${D.bit.length ? `<h3>Bitácora</h3><div class="cmd-bit">${D.bit.map(b => `<div><b>${X.fmt(Date.parse(b.momento), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</b> · ${e(b.correo || 'carga de datos ficticios')} · ${e(b.accion)} en ${e(b.tabla)} #${e(b.fila)}${resumenCambio(b)}</div>`).join('')}</div><p class="meta">La bitácora la escribe la base de datos; nadie puede editarla ni borrarla.</p>` : ''}`;
    enlazar();
  }

  function resumenCambio(b) {
    if (b.accion !== 'update' || !b.antes || !b.despues) return '';
    const cs = ['estado', 'nivel', 'rol', 'departamentos'].filter(k => JSON.stringify(b.antes[k]) !== JSON.stringify(b.despues[k]));
    return cs.length ? ': ' + cs.map(k => `${k} ${e(JSON.stringify(b.antes[k]))} → ${e(JSON.stringify(b.despues[k]))}`).join(', ') : '';
  }

  function formNueva() {
    const n = V.nueva;
    return `<form class="cmd-form cmd-det" id="cmdNueva" autocomplete="off">
      <h3>Nueva incidencia ${ficticio}</h3>
      <label>Título<input name="titulo" maxlength="140" required value="${e(n.titulo || '[FICTICIO] ')}"></label>
      <div class="fila">
        <label>Tipo<select name="tipo">${Object.entries(TIPOS).map(([k, t]) => `<option value="${k}"${n.tipo === k ? ' selected' : ''}>${t}</option>`).join('')}</select></label>
        <label>Nivel<select name="nivel">${Object.entries(NIVELES).map(([k, [t]]) => `<option value="${k}"${String(n.nivel) === k ? ' selected' : ''}>${t}</option>`).join('')}</select></label>
      </div>
      <label>Descripción<textarea name="descripcion" rows="3" maxlength="2000">${e(n.descripcion || '')}</textarea></label>
      <div class="fila"><button class="btn" type="button" data-cmd-ubicar>${eligiendo ? 'Toca el mapa…' : 'Ubicar en el mapa'}</button><span>${n.ubigeo ? e(nomDist(n.ubigeo)) : '<small>Sin ubicación</small>'}</span></div>
      <div class="fila"><button class="btn prim" type="submit"${n.ubigeo ? '' : ' disabled'}>Guardar</button><button class="btn" type="button" data-cmd-cancelar>Cancelar</button></div>
    </form>`;
  }

  function detalle(i) {
    const mis = D.mis.filter(m => m.incidencia_id === i.id);
    const libres = D.rec.filter(r => r.estado === 'disponible' && r.departamento === i.departamento);
    return `<div class="cmd-det">
      <h3>${e(i.titulo)} ${ficticio}</h3>
      <p>${chipNivel(i.nivel)} ${TIPOS[i.tipo]} · <b>${ESTADOS[i.estado]}</b> · ${e(nomDist(i.ubigeo))} · registrada ${hace(i.creado)}</p>
      ${i.descripcion ? `<p>${e(i.descripcion)}</p>` : ''}
      <div class="fila-botones"><button class="btn" type="button" data-cmd-ir>Ver en el mapa</button>
        ${puedeEditar() ? Object.entries(ESTADOS).filter(([k]) => k !== i.estado).map(([k, t]) => `<button class="btn" type="button" data-cmd-estado="${k}">${k === 'cerrada' ? 'Cerrar' : 'Pasar a ' + t.toLowerCase()}</button>`).join('') : ''}
        <button class="btn" type="button" data-cmd-cerrar-det>Ocultar</button></div>
      <h4>Misiones</h4>
      ${mis.map(m => `<div class="cmd-rec"><b>${e(m.titulo)}</b> · ${ESTADOS_MIS[m.estado]} · ${D.mr.filter(x => x.mision_id === m.id).map(x => e(D.rec.find(r => r.id === x.recurso_id)?.nombre || '#' + x.recurso_id)).join(', ') || 'sin recursos'}
        ${puedeEditar() && m.estado === 'en_curso' ? `<button class="btn" type="button" data-cmd-fin="${m.id}" data-fin="cumplida">Cumplida</button><button class="btn" type="button" data-cmd-fin="${m.id}" data-fin="cancelada">Cancelar</button>` : ''}</div>`).join('') || '<p class="vacio">Sin misiones.</p>'}
      ${puedeEditar() && i.estado !== 'cerrada' ? `<form class="cmd-form" id="cmdMision" autocomplete="off">
        <label>Nueva misión<input name="titulo" maxlength="140" required value="[FICTICIO] "></label>
        ${libres.length ? libres.map(r => `<label class="cmd-rec"><input type="checkbox" name="rec" value="${r.id}"> ${e(r.nombre)} <small>${TIPOS_REC[r.tipo]} · ${e(r.base || '')}</small></label>`).join('') : `<p class="vacio">No hay recursos disponibles en ${e(nomDep(i.departamento))}.</p>`}
        <div class="fila"><button class="btn prim" type="submit">Crear misión</button></div></form>` : ''}
    </div>`;
  }

  // reportes ciudadanos sin cerrar: el operador los verifica, los descarta o los convierte en incidencia
  function bandeja() {
    if (!D.rep.length) return '<h3>Reportes ciudadanos</h3><p class="vacio">Ningún reporte pendiente.</p>';
    return `<h3>Reportes ciudadanos (${D.rep.length})</h3><div class="cmd-lista">${D.rep.map(r => `
      <div class="cmd-det" data-cmd-rep="${r.id}"><p><b>${TIPOS[r.tipo]}</b> · ${e(nomDist(r.ubigeo))} · ${hace(r.creado)} · ${ESTADOS_REP[r.estado]} ${ficticio}</p>
        <p>${e(r.descripcion)}</p><p class="meta">Código ${e(r.codigo)} · sin datos de contacto</p>
        ${puedeEditar() ? `<div class="fila-botones">
          <button class="btn" type="button" data-rep-ir>Ver en el mapa</button>
          ${r.estado === 'recibido' ? '<button class="btn" type="button" data-rep-estado="verificado">Verificar</button>' : ''}
          <button class="btn" type="button" data-rep-estado="descartado">Descartar</button>
          <select data-rep-nivel aria-label="Nivel de la incidencia">${Object.entries(NIVELES).map(([k, [t]]) => `<option value="${k}"${k === '2' ? ' selected' : ''}>${t}</option>`).join('')}</select>
          <button class="btn prim" type="button" data-rep-convertir>Convertir en incidencia</button></div>` : ''}
      </div>`).join('')}</div>`;
  }

  function usuarios() {
    return `<h3>Usuarios</h3>
      <p class="meta">Los usuarios se crean en Supabase (Authentication). Aquí se asigna su rol y sus departamentos (códigos del INEI separados por comas, por ejemplo 20, 24).</p>
      <table class="tabla"><thead><tr><th>Usuario</th><th>Rol</th><th>Departamentos</th></tr></thead><tbody>${D.per.map(p => `
        <tr data-cmd-per="${e(p.id)}"><td>${e(p.correo)}</td>
          <td><select data-cmd-rol${p.id === yo.id ? ' disabled title="No puedes cambiar tu propio rol"' : ''}>${Object.entries(ROLES).map(([k, t]) => `<option value="${k}"${p.rol === k ? ' selected' : ''}>${t}</option>`).join('')}</select></td>
          <td><input data-cmd-deps value="${e(p.departamentos.join(', '))}" size="10" aria-label="Departamentos de ${e(p.correo)}"${p.id === yo.id ? ' disabled' : ''}></td></tr>`).join('')}</tbody></table>`;
  }

  function enlazar() {
    const c = cuerpo();
    enlazarSalir();
    c.querySelectorAll('[data-cmd-filtro]').forEach(b => { b.onclick = () => { V.filtro = b.dataset.cmdFiltro; panel(); }; });
    c.querySelectorAll('[data-cmd-inc]').forEach(b => { b.onclick = () => { V.sel = Number(b.dataset.cmdInc); panel(); irA(D.inc.find(i => i.id === V.sel)); }; });
    c.querySelector('[data-cmd-nueva]')?.addEventListener('click', () => { V.nueva = { nivel: 2, tipo: 'inundacion' }; panel(); });
    c.querySelector('[data-cmd-cerrar-det]')?.addEventListener('click', () => { V.sel = null; panel(); });
    c.querySelector('[data-cmd-ir]')?.addEventListener('click', () => irA(D.inc.find(i => i.id === V.sel)));
    c.querySelectorAll('[data-cmd-estado]').forEach(b => { b.onclick = () => hacer(sb.from('incidencias').update({ estado: b.dataset.cmdEstado }).eq('id', V.sel), 'Estado actualizado'); });
    c.querySelectorAll('[data-cmd-fin]').forEach(b => { b.onclick = () => hacer(sb.rpc('cerrar_mision', { p_mision: Number(b.dataset.cmdFin), p_estado: b.dataset.fin }), 'Misión cerrada y recursos liberados'); });
    c.querySelectorAll('[data-cmd-mant]').forEach(b => { b.onclick = () => { const r = D.rec.find(x => x.id === Number(b.dataset.cmdMant)); hacer(sb.from('recursos').update({ estado: r.estado === 'mantenimiento' ? 'disponible' : 'mantenimiento' }).eq('id', r.id)); }; });
    const fm = c.querySelector('#cmdMision');
    if (fm) fm.onsubmit = ev => {
      ev.preventDefault();
      const f = new FormData(fm), recs = f.getAll('rec').map(Number);
      if (!recs.length) { X.avisoToast('Elige al menos un recurso disponible', 5000, 'info'); return; }
      hacer(sb.rpc('crear_mision', { p_incidencia: V.sel, p_titulo: conMarca(f.get('titulo')), p_recursos: recs }), 'Misión creada');
    };
    const fn = c.querySelector('#cmdNueva');
    if (fn) {
      const guardarBorrador = () => { const f = new FormData(fn); Object.assign(V.nueva, { titulo: f.get('titulo'), tipo: f.get('tipo'), nivel: Number(f.get('nivel')), descripcion: f.get('descripcion') }); };
      fn.querySelector('[data-cmd-cancelar]').onclick = () => { V.nueva = null; eligiendo = null; panel(); };
      fn.querySelector('[data-cmd-ubicar]').onclick = () => { guardarBorrador(); panel(); ubicar(p => { Object.assign(V.nueva, p); X.abrirVista('comando'); panel(); }, panel); };
      fn.onsubmit = async ev => {
        ev.preventDefault(); guardarBorrador();
        const n = V.nueva;
        const ok = await hacer(sb.from('incidencias').insert({ titulo: conMarca(n.titulo), tipo: n.tipo, nivel: n.nivel, descripcion: n.descripcion || null, ubigeo: n.ubigeo, lat: n.lat, lng: n.lng, creado_por: yo.id }), 'Incidencia registrada');
        if (ok) { V.nueva = null; panel(); }
      };
    }
    c.querySelectorAll('[data-cmd-rep]').forEach(caja => {
      const r = D.rep.find(x => x.id === Number(caja.dataset.cmdRep));
      caja.querySelector('[data-rep-ir]')?.addEventListener('click', () => irA(r));
      caja.querySelectorAll('[data-rep-estado]').forEach(b => { b.onclick = () => hacer(sb.from('reportes').update({ estado: b.dataset.repEstado, revisado: new Date().toISOString(), revisado_por: yo.id }).eq('id', r.id), b.dataset.repEstado === 'verificado' ? 'Reporte verificado: ya aparece en el mapa público' : 'Reporte descartado'); });
      const conv = caja.querySelector('[data-rep-convertir]');
      if (conv) conv.onclick = () => hacer(sb.rpc('convertir_reporte', { p_reporte: r.id, p_nivel: Number(caja.querySelector('[data-rep-nivel]').value), p_titulo: conMarca(`${TIPOS[r.tipo]} reportado en ${X.titulo(X.TERR?.distritos.find(d => d[0] === r.ubigeo)?.[1] || r.ubigeo)}`) }), 'Reporte convertido en incidencia');
    });
    c.querySelectorAll('[data-cmd-per]').forEach(tr => {
      const id = tr.dataset.cmdPer, rol = tr.querySelector('[data-cmd-rol]'), deps = tr.querySelector('[data-cmd-deps]');
      const guardar = () => {
        const lista = deps.value.split(/[\s,;]+/).filter(Boolean);
        if (lista.some(d => !/^[0-9]{2}$/.test(d))) { X.avisoToast('Los departamentos van como códigos de 2 dígitos del INEI (por ejemplo 20 para Piura)', 7000, 'info'); return; }
        hacer(sb.from('perfiles').update({ rol: rol.value, departamentos: lista }).eq('id', id), 'Usuario actualizado');
      };
      rol.onchange = guardar; deps.onchange = guardar;
    });
  }

  // los datos de esta página son siempre de prueba: el título lleva la marca aunque se borre al escribirlo
  const conMarca = s => { const t = String(s || '').trim(); return /\[FICTICIO\]/i.test(t) ? t : '[FICTICIO] ' + t; };

  /* ---------- mapa ---------- */
  function irA(i) { if (i) X.G?.irA?.(i.lat, i.lng, 40); }

  // elegir un punto del Perú en el mapa; listo recibe { lat, lng, ubigeo }, fallo repinta el formulario
  function ubicar(listo, fallo) {
    const map = X.G?.mapa;
    if (!map) { X.avisoToast('El mapa no está disponible (globo de respaldo): no se puede ubicar el punto', 7000, 'info'); return; }
    eligiendo = true; fallo();
    X.avisoToast('Toca el mapa donde ocurre', 6000, 'info');
    if (matchMedia('(max-width: 899px)').matches) document.getElementById('mapa')?.scrollIntoView?.();
    map.getCanvas().style.cursor = 'crosshair';
    map.once('click', ev => {
      eligiendo = null; map.getCanvas().style.cursor = '';
      const { lat, lng } = ev.lngLat, t = X.distritoPeruEn(lat, lng);
      if (!t) { X.avisoToast('Ese punto no está dentro de un distrito del Perú', 6000, 'info'); fallo(); return; }
      listo({ lat: +lat.toFixed(5), lng: +lng.toFixed(5), ubigeo: t[0] });
    });
  }

  /* ---------- portal ciudadano: reportar sin cuenta ---------- */
  function pintarReportar() {
    const c = cuerpoRep();
    if (!c || !sb) return;
    const b = R.borrador, s = R.seguimiento;
    c.innerHTML = `
      <div class="cmd-aviso"><b>Si hay personas en peligro, llama ya:</b> ${EMERGENCIAS.map(([n, t]) => `<a href="tel:${n}"><b>${n}</b></a> ${t}`).join(' · ')}.
        Este portal no reemplaza a esos números ni al COEN-INDECI.</div>
      <div class="cmd-aviso">Entorno de pruebas: lo que envíes aquí es un reporte ${ficticio} para probar el sistema. Nadie lo atenderá en la realidad.</div>
      ${R.enviado ? `<div class="cmd-det"><h3>Reporte enviado</h3><p>Tu código de seguimiento es <b style="font-size:20px;letter-spacing:.08em">${e(R.enviado)}</b>. Guárdalo: con él puedes ver más abajo si un operador lo revisó.</p><button class="btn" type="button" data-rep-otro>Enviar otro reporte</button></div>` : `
      <form class="cmd-form" id="repForm" autocomplete="off">
        <label>¿Qué está pasando?<select name="tipo">${Object.entries(TIPOS).map(([k, t]) => `<option value="${k}"${b.tipo === k ? ' selected' : ''}>${t}</option>`).join('')}</select></label>
        <label>Cuéntalo en pocas palabras (de 10 a 1 000 letras)<textarea name="descripcion" rows="4" maxlength="1000" required>${e(b.descripcion || '')}</textarea></label>
        <p class="meta">No escribas nombres, DNI, teléfonos ni direcciones exactas. VIGÍA no pide ni guarda datos personales.</p>
        <div class="fila"><button class="btn" type="button" data-rep-ubicar>${eligiendo ? 'Toca el mapa…' : 'Ubicar en el mapa'}</button>
          ${navigator.geolocation ? '<button class="btn" type="button" data-rep-gps>Usar mi ubicación</button>' : ''}
          <span>${b.ubigeo ? e(nomDist(b.ubigeo)) : '<small>Sin ubicación</small>'}</span></div>
        <label class="cmd-rec"><input type="checkbox" name="acepto" required> Entiendo que es una prueba y que mi reporte es ficticio</label>
        <div class="fila"><button class="btn prim" type="submit"${b.ubigeo ? '' : ' disabled'}>Enviar reporte</button></div>
        <p class="cmd-error" role="alert">${e(b.error || '')}</p>
      </form>`}
      <h3>Seguir un reporte</h3>
      <form class="cmd-form" id="repSeguir" autocomplete="off"><div class="fila">
        <input name="codigo" maxlength="10" placeholder="Código de 10 letras y números" aria-label="Código de seguimiento" value="${e(s?.codigo || '')}">
        <button class="btn" type="submit">Consultar</button></div></form>
      ${s ? (s.fila ? `<p><b>${ESTADOS_REP[s.fila.estado]}</b> · ${TIPOS[s.fila.tipo]} en ${e(nomDist(s.fila.ubigeo))} · enviado ${hace(s.fila.creado)}${s.fila.revisado ? ` · revisado ${hace(s.fila.revisado)}` : ''}${s.fila.nota ? `<br>Nota: ${e(s.fila.nota)}` : ''}</p>` : '<p class="vacio">No hay ningún reporte con ese código.</p>') : ''}
      <h3>Reportes verificados en el mapa</h3>
      <p class="meta">${R.publicos.length} en los últimos 7 días. Solo se muestran los que revisó un operador, sin descripción y con la ubicación aproximada (unos 1 km).</p>`;
    enlazarReportar();
  }

  function enlazarReportar() {
    const c = cuerpoRep(), f = c.querySelector('#repForm');
    c.querySelector('[data-rep-otro]')?.addEventListener('click', () => { R.enviado = null; R.borrador = { tipo: 'inundacion' }; pintarReportar(); });
    c.querySelector('#repSeguir').onsubmit = async ev => {
      ev.preventDefault();
      const codigo = String(new FormData(ev.target).get('codigo') || '').trim().toUpperCase();
      if (!codigo) return;
      const { data, error } = await sb.rpc('estado_reporte', { p_codigo: codigo });
      R.seguimiento = { codigo, fila: error ? null : data?.[0] };
      pintarReportar();
    };
    if (!f) return;
    const guardar = () => { const d = new FormData(f); Object.assign(R.borrador, { tipo: d.get('tipo'), descripcion: d.get('descripcion') }); };
    const puesto = p => { Object.assign(R.borrador, p, { error: '' }); X.abrirVista('reportar'); pintarReportar(); };
    f.querySelector('[data-rep-ubicar]').onclick = () => { guardar(); ubicar(puesto, pintarReportar); };
    f.querySelector('[data-rep-gps]')?.addEventListener('click', () => {
      guardar();
      navigator.geolocation.getCurrentPosition(pos => {
        const { latitude: lat, longitude: lng } = pos.coords, t = X.distritoPeruEn(lat, lng);
        if (!t) { R.borrador.error = 'Tu ubicación no está dentro de un distrito del Perú. Ubícalo en el mapa.'; pintarReportar(); return; }
        puesto({ lat: +lat.toFixed(5), lng: +lng.toFixed(5), ubigeo: t[0] });
      }, () => { R.borrador.error = 'No se pudo obtener tu ubicación. Ubícalo en el mapa.'; pintarReportar(); }, { timeout: 15000 });
    });
    f.onsubmit = async ev => {
      ev.preventDefault(); guardar();
      const b = R.borrador, texto = String(b.descripcion || '').trim();
      if (texto.length < 10) { b.error = 'Escribe al menos 10 letras.'; pintarReportar(); return; }
      const { data, error } = await sb.rpc('enviar_reporte', { p_tipo: b.tipo, p_descripcion: /\[FICTICIO\]/i.test(texto) ? texto : '[FICTICIO] ' + texto, p_ubigeo: b.ubigeo, p_lat: b.lat, p_lng: b.lng });
      if (error) { b.error = error.message.includes('demasiados') || error.message.includes('varios') ? error.message : 'No se pudo enviar. Revisa los datos e intenta otra vez.'; pintarReportar(); return; }
      R.enviado = data; R.seguimiento = { codigo: data, fila: null };
      pintarReportar();
    };
  }

  async function cargarPublicos() {
    const { data, error } = await sb.rpc('reportes_publicos');
    if (error) return;
    R.publicos = data || [];
    capaPublicos();
    if (!document.getElementById('p-reportar')?.hidden) pintarReportar();
  }

  function capaPublicos() {
    const map = X?.G?.mapa;
    if (!map) { if (!X?.G) setTimeout(capaPublicos, 3000); return; } // el mapa carga después (en una pestaña oculta, recién al mostrarla)
    const datos = { type: 'FeatureCollection', features: R.publicos.map(r => ({ type: 'Feature', properties: { t: TIPOS[r.tipo] }, geometry: { type: 'Point', coordinates: [r.lng, r.lat] } })) };
    if (map.getSource('rep-pub')) { map.getSource('rep-pub').setData(datos); return; }
    map.addSource('rep-pub', { type: 'geojson', data: datos });
    map.addLayer({ id: 'rep-pub', type: 'circle', source: 'rep-pub', paint: {
      'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': X.COL.lluvia, 'circle-stroke-width': 2.5,
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 4, 10, 9] } });
  }

  function capaMapa() {
    const map = X?.G?.mapa;
    if (!map) { if (X && !X.G && yo) setTimeout(capaMapa, 3000); return; }
    const fs = D.inc.filter(i => i.estado !== 'cerrada').map(i => ({ type: 'Feature', properties: { id: i.id, n: i.nivel, t: i.titulo }, geometry: { type: 'Point', coordinates: [i.lng, i.lat] } }));
    const datos = { type: 'FeatureCollection', features: fs };
    if (map.getSource('cmd-inc')) { map.getSource('cmd-inc').setData(datos); return; }
    map.addSource('cmd-inc', { type: 'geojson', data: datos });
    map.addLayer({ id: 'cmd-inc', type: 'circle', source: 'cmd-inc', paint: {
      'circle-color': ['match', ['get', 'n'], 1, X.COL.amarillo, 2, X.COL.naranja, X.COL.rojo],
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, ['+', 4, ['get', 'n']], 10, ['+', 8, ['*', 2, ['get', 'n']]]],
      'circle-stroke-color': '#FFFFFF', 'circle-stroke-width': 2, 'circle-opacity': 0.95 } });
    map.on('click', 'cmd-inc', ev => {
      if (eligiendo) return;
      V.sel = ev.features[0].properties.id; X.abrirVista('comando'); panel();
    });
    map.on('mouseenter', 'cmd-inc', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'cmd-inc', () => { map.getCanvas().style.cursor = ''; });
  }

  iniciar();
})();
