// Puente de VIGÍA en Cloudflare Workers.
// El SENAMHI y el ENFEN no responden a los servidores de GitHub Actions. El recolector (recolectar.py, variable VIGIA_PROXY)
// les pide esas páginas a este Worker, que las trae desde la red de Cloudflare y las devuelve tal cual.
// No guarda nada. Solo atiende a quien envía la clave (secreto CLAVE del Worker = secreto VIGIA_PROXY_CLAVE de GitHub)
// y solo hacia los sitios de PERMITIDOS, para no convertirse en un proxy abierto.
// Prueba sin clave: GET /estado responde si el Worker llega al SENAMHI y al ENFEN.

const PERMITIDOS = new Set(['idesep.senamhi.gob.pe', 'www.senamhi.gob.pe', 'senamhi.gob.pe', 'enfen.imarpe.gob.pe']);
const AGENTE = 'Mozilla/5.0 (compatible; VIGIA/1.0; monitor de riesgos sin fines de lucro; +https://victor73917.github.io/vigia)';

// sigue las redirecciones a mano para no salir nunca de los sitios permitidos
async function traer(url, init = {}) {
  let destino = new URL(url);
  for (let i = 0; i < 5; i++) {
    if (destino.protocol !== 'https:' && destino.protocol !== 'http:') throw new Error('protocolo no permitido');
    if (!PERMITIDOS.has(destino.hostname)) throw new Error('destino no permitido: ' + destino.hostname);
    const r = await fetch(destino, { ...init, headers: { 'user-agent': AGENTE, ...(init.headers || {}) }, redirect: 'manual' });
    if (r.status >= 300 && r.status < 400 && r.headers.get('location')) { destino = new URL(r.headers.get('location'), destino); continue; }
    return r;
  }
  throw new Error('demasiadas redirecciones');
}

// compara dos textos sin filtrar tiempos: la clave nunca se compara carácter a carácter con salida temprana
function iguales(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export default {
  async fetch(req, env) {
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
      return Response.json({ colo: req.cf?.colo, resultados: out });
    }
    if (!env.CLAVE || !iguales(req.headers.get('x-vigia-clave') || '', env.CLAVE)) return new Response('no autorizado', { status: 401 });
    if (req.method !== 'GET') return new Response('solo GET', { status: 405 });
    const u = url.searchParams.get('u');
    if (!u) return new Response('falta el parámetro u', { status: 400 });
    try {
      const rango = req.headers.get('range');
      const r = await traer(u, rango ? { headers: { range: rango } } : {});
      return new Response(r.body, { status: r.status, headers: { 'content-type': r.headers.get('content-type') || 'application/octet-stream' } });
    } catch (e) {
      return new Response('error: ' + (e.message || e), { status: 502 });
    }
  },
};
