"""Arma index.html (página completa para abrir en el navegador) a partir de vigia.html.

vigia.html es el contenido tal como se publica en Claude, que pone su propio
<!doctype>, <head> y <body>. Para abrirlo fuera de Claude hace falta ese esqueleto,
y para la web pública también la descripción y la vista previa al compartir el enlace.

Con --paquete además arma la carpeta publicar/ y vigia-web.zip para subir a Netlify.
"""

import base64
import hashlib
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
# dirección pública; en GitHub Actions la fija la variable VIGIA_SITIO
SITIO = os.environ.get("VIGIA_SITIO", "https://vigia-pe.netlify.app").rstrip("/")
# VIGIA_PRUEBAS=1 arma el sitio de pruebas (rama desarrollo): sin indexar y con una marca visible
PRUEBAS = os.environ.get("VIGIA_PRUEBAS") == "1"
MARCA_PRUEBAS = ('<meta name="robots" content="noindex,nofollow">'
                 '<style>.marca-pruebas{position:fixed;left:50%;bottom:6px;transform:translateX(-50%);z-index:40;pointer-events:none;'
                 'background:#5a1d00;color:#ffd9b0;border:1px solid #ff8a3d;border-radius:999px;padding:3px 12px;'
                 'font:600 11px/1.4 system-ui,sans-serif;letter-spacing:.04em}</style>')
# Centro de comando (fase 6): solo en el sitio de pruebas y con un proyecto Supabase configurado. La dirección y la clave
# pública (anon) no son secretas: van en el navegador por diseño y las tablas las protegen las reglas por fila.
NUBE_URL = os.environ.get("VIGIA_SUPABASE_URL", "").strip().rstrip("/")
NUBE_ANON = os.environ.get("VIGIA_SUPABASE_ANON", "").strip()
NUBE = PRUEBAS and bool(re.fullmatch(r"https://[a-z0-9]{10,40}\.supabase\.co", NUBE_URL)) and bool(re.fullmatch(r"[A-Za-z0-9._-]{20,400}", NUBE_ANON))
# Analista IA (fase 8): la función «analista» de Supabase necesita la clave de Anthropic con crédito. Apagado mientras
# no haya presupuesto; con VIGIA_ANALISTA=1 (variable de GitHub ANALISTA) se muestra la pestaña en el sitio de pruebas.
ANALISTA = NUBE and os.environ.get("VIGIA_ANALISTA") == "1"
if PRUEBAS and (NUBE_URL or NUBE_ANON) and not NUBE:
    print("AVISO: VIGIA_SUPABASE_URL o VIGIA_SUPABASE_ANON no tienen el formato esperado; el centro de comando no se incluye")
DESCRIPCION = ("El Niño Costero en el norte del Perú: lluvias, crecidas de ríos, emergencias y "
               "distritos a atender primero. Datos públicos de ENFEN, SENAMHI, INDECI, GloFAS y ECMWF.")
ICONO = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
         "%3Crect width='32' height='32' rx='7' fill='%2303060D'/%3E"
         "%3Ccircle cx='16' cy='16' r='9.5' fill='none' stroke='%23FFB547' stroke-width='2.2'/%3E"
         "%3Ccircle cx='16' cy='16' r='4.6' fill='%23FFB547'/%3E%3C/svg%3E")
ESQUELETO = (
    '<!doctype html><html lang="es"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    f'<meta name="description" content="{DESCRIPCION}">'
    '<meta name="theme-color" content="#03060D">'
    f'<link rel="icon" href="{ICONO}">'
    '<meta property="og:type" content="website">'
    '<meta property="og:locale" content="es_PE">'
    '<meta property="og:title" content="VIGÍA · El Niño Costero en el norte del Perú">'
    f'<meta property="og:description" content="{DESCRIPCION}">'
    f'<meta property="og:url" content="{SITIO}/">'
    f'<meta property="og:image" content="{SITIO}/vista-previa.jpg">'
    '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
    '<meta name="twitter:card" content="summary_large_image">'
    "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
    "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>"
    f'<script>window.VIGIA_SITIO = "{SITIO}";</script>'
    + (MARCA_PRUEBAS if PRUEBAS else "")
    + (f'<script>window.VIGIA_NUBE = {{ url: "{NUBE_URL}", anon: "{NUBE_ANON}", analista: {"true" if ANALISTA else "false"} }};</script>'
       '<script src="lib/supabase-js@2.45.4/supabase.js" defer></script>'
       '<script src="comando.js" defer></script>' if NUBE else "")
    + "</head><body>\n"
    + ('<div class="marca-pruebas" role="note">ENTORNO DE PRUEBAS · no usar para decisiones</div>\n' if PRUEBAS else "")
)
CABECERAS = """/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
/tex/*
  Cache-Control: public, max-age=604800
/datos/zona-s2.jpg
  Cache-Control: public, max-age=604800
"""
PUBLICAR = ["index.html", "legal.html", "vista-previa.jpg", "datos/instantanea.js", "datos/fronteras.js", "datos/rios.js",
            "datos/lluvia-24h.png", "datos/lluvia-48h.png", "datos/lluvia-72h.png", "datos/lluvia-7d.png",
            "datos/lluvia-imerg.png", "datos/termica.jpg", "datos/territorio.json", "datos/ccpp.json", "tex/tierra-dia.jpg", "tex/tierra-noche.jpg", "tex/agua.jpg",
            # bibliotecas propias (librerias.py): el mapa y el globo de respaldo
            "lib/maplibre-gl@6.14.0/maplibre-gl.mjs", "lib/maplibre-gl@6.14.0/maplibre-gl-worker.mjs", "lib/maplibre-gl@6.14.0/maplibre-gl.css",
            "lib/three@0.185.1/three.module.js", "lib/three@0.185.1/three.core.js", "lib/three@0.185.1/OrbitControls.js",
            "lib/three@0.185.1/LineSegments2.js", "lib/three@0.185.1/LineSegmentsGeometry.js", "lib/three@0.185.1/LineMaterial.js"]


if NUBE:
    PUBLICAR += ["comando.js", "lib/supabase-js@2.45.4/supabase.js"]


# Política de seguridad de contenido (fase 9). GitHub Pages no permite cabeceras, así que va como <meta>.
# Solo se cargan scripts propios (MapLibre, three.js y Supabase van en lib/, ver librerias.py) y los scripts en línea cuyo hash calcula
# este programa; los datos solo se piden a las fuentes que usa VIGÍA. Si se agrega una fuente nueva, va en esta lista.
FUENTES_EN_VIVO = ("https://api.open-meteo.com https://ensemble-api.open-meteo.com https://flood-api.open-meteo.com "
                   "https://gibs.earthdata.nasa.gov https://www.gdacs.org")
TESELAS = "https://server.arcgisonline.com https://*.basemaps.cartocdn.com https://gibs.earthdata.nasa.gov"


def politica(html):
    hashes = sorted({"'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode("utf-8")).digest()).decode() + "'"
                     for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)})
    nube = f" {NUBE_URL} wss://{NUBE_URL.split('//', 1)[1]}" if NUBE else ""
    return ("default-src 'self'; "
            f"script-src 'self' {' '.join(hashes)}; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            f"img-src 'self' data: blob: {TESELAS}; "
            f"connect-src 'self' {FUENTES_EN_VIVO} {TESELAS}{nube}; "
            "worker-src 'self' blob:; child-src blob:; frame-src 'none'; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; upgrade-insecure-requests")


def construir():
    contenido = (BASE / "vigia.html").read_text(encoding="utf-8")
    html = ESQUELETO + contenido + "\n</body></html>\n"
    meta = (f'<meta http-equiv="Content-Security-Policy" content="{politica(html)}">'
            '<meta name="referrer" content="strict-origin-when-cross-origin">')
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">' + meta, 1)
    (BASE / "index.html").write_text(html, encoding="utf-8", newline="\n")
    print("index.html listo")


def empaquetar():
    destino = BASE / "publicar"
    # se sobrescriben los archivos en vez de borrar la carpeta: OneDrive suele tenerla bloqueada
    for viejo in destino.rglob("*") if destino.exists() else []:
        if viejo.is_file() and viejo.relative_to(destino).as_posix() not in PUBLICAR + ["_headers", "_redirects"]:
            viejo.unlink()
    for rel in PUBLICAR:
        (destino / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASE / rel, destino / rel)
    (destino / "_headers").write_text(CABECERAS, encoding="utf-8")
    # Netlify reenvía /awc/ a NOAA para leer los METAR y TAF en vivo (NOAA no permite leerlos directo desde el navegador)
    (destino / "_redirects").write_text("/awc/*  https://aviationweather.gov/api/data/:splat  200\n", encoding="utf-8")
    zip_ruta = BASE / "vigia-web.zip"
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(destino.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(destino).as_posix())
    print(f"{zip_ruta.name} listo ({zip_ruta.stat().st_size // 1024} KB) con {len(PUBLICAR) + 1} archivos")


if __name__ == "__main__":
    construir()
    if "--paquete" in sys.argv:
        empaquetar()
