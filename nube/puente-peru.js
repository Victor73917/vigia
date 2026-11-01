// Puente de VIGÍA en Cloudflare Workers.
// El SENAMHI y el ENFEN no responden a los servidores de GitHub Actions. El recolector (recolectar.py, variable VIGIA_PROXY)
// les pide esas páginas a este Worker, que las trae desde la red de Cloudflare y las devuelve tal cual.
// No guarda nada propio: solo la caché de Cloudflare durante CACHE_S segundos, para no repetir pedidos al SENAMHI.
// Solo atiende las direcciones que usa VIGÍA (permitida), con GET; no es un proxy abierto.
// Si el Worker tiene el secreto CLAVE, además exige la cabecera X-Vigia-Clave (secreto VIGIA_PROXY_CLAVE de GitHub).
// Prueba: GET /estado responde si el Worker llega al SENAMHI y al ENFEN (/estado?estricto: 503 si alguno falla).

const CACHE_S = 600;
const AGENTE = 'Mozilla/5.0 (compatible; VIGIA/1.0; monitor de riesgos sin fines de lucro; +https://victor73917.github.io/vigia)';
const CAPAS_WFS = new Set(['g_aviso', 'g_acti_quebrada', 'g_carto_fundamento']);
const HOSTS = new Set(['idesep.senamhi.gob.pe', 'www.senamhi.gob.pe', 'senamhi.gob.pe', 'enfen.imarpe.gob.pe']);

// las únicas consultas que hace recolectar.py: avisos y quebradas del SENAMHI, sus capas WFS de solo lectura y la portada del ENFEN
function permitida(u) {
  if (u.protocol !== 'https:') return false;
  const p = u.searchParams, pag = p.get('p');
  if (u.hostname === 'enfen.imarpe.gob.pe') return u.pathname === '/' && !u.search;
  if (u.hostname === 'www.senamhi.gob.pe') {
    if (u.pathname === '/') return pag === 'aviso-meteorologico' || pag === 'aviso-meteorologico-detalle';
    if (u.pathname === '/main.php') return pag === 'aviso-activacion-quebrada';
    return false;
  }
  if (u.hostname === 'idesep.senamhi.gob.pe') {
    const m = /^\/geoserver\/([a-z_]+)\/ows$/.exec(u.pathname), pedido = (p.get('request') || '').toLowerCase();
    return !!m && CAPAS_WFS.has(m[1]) && (p.get('service') || '').toUpperCase() === 'WFS' && pedido === 'getfeature';
  }
  return false;
}

// sigue las redirecciones a mano para no salir nunca de los sitios del SENAMHI y el ENFEN
async function traer(url, init = {}) {
  let destino = new URL(url);
  for (let i = 0; i < 5; i++) {
    if (destino.protocol !== 'https:' || !HOSTS.has(destino.hostname)) throw new Error('destino no permitido: ' + destino.hostname);
    const r = await fetch(destino, { ...init, headers: { 'user-agent': AGENTE }, redirect: 'manual' });
    if (r.status >= 300 && r.status < 400 && r.headers.get('location')) { destino = new URL(r.headers.get('location'), destino); continue; }
    return r;
  }
  throw new Error('demasiadas redirecciones');
}

// compara dos textos sin filtrar tiempos
function iguales(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (url.pathname === '/estado') {
      const pruebas = {
        'SENAMHI GeoServer': 'https://idesep.senamhi.gob.pe/geoserver/ows?service=WFS&request=GetCapabilities',
        'SENAMHI web': 'https://www.senamhi.gob.pe/?p=aviso-meteorologico',
        'ENFEN': 'https://enfen.imarpe.gob.pe/',
      };
      const out = {};
      await Promise.all(Object.entries(pruebas).map(async ([n, u]) => {
        const t0 = Date.now();
        try { const r = await traer(u, { signal: AbortSignal.timeout(25000) }); out[n] = { estado: r.status, ms: Date.now() - t0 }; await r.body?.cancel(); }
        catch (e) { out[n] = { error: String(e.message || e), ms: Date.now() - t0 }; }
      }));
      // ?estricto responde 503 si alguna fuente falla, para probarlo desde servicios que solo ven el código HTTP
      const falla = Object.values(out).some(x => x.error || x.estado >= 400);
      return Response.json({ colo: req.cf?.colo, resultados: out }, { status: falla && url.searchParams.has('estricto') ? 503 : 200 });
    }
    if (env.CLAVE && !iguales(req.headers.get('x-vigia-clave') || '', env.CLAVE)) return new Response('no autorizado', { status: 401 });
    if (req.method !== 'GET') return new Response('solo GET', { status: 405 });
    let destino;
    try { destino = new URL(url.searchParams.get('u') || ''); } catch { return new Response('falta el parámetro u', { status: 400 }); }
    if (!permitida(destino)) return new Response('dirección no permitida', { status: 403 });
    const cache = caches.default, clave = new Request(destino.toString());
    const guardada = await cache.match(clave);
    if (guardada) return guardada;
    try {
      const r = await traer(destino);
      const resp = new Response(r.body, { status: r.status, headers: {
        'content-type': r.headers.get('content-type') || 'application/octet-stream',
        'cache-control': r.ok ? `public, max-age=${CACHE_S}` : 'no-store',
      } });
      if (r.ok) ctx.waitUntil(cache.put(clave, resp.clone()));
      return resp;
    } catch (e) {
      return new Response('error: ' + (e.message || e), { status: 502 });
    }
  },
};
