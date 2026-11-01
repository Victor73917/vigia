"""Arma index.html (página completa para abrir en el navegador) a partir de vigia.html.

vigia.html es el contenido tal como se publica en Claude, que pone su propio
<!doctype>, <head> y <body>. Para abrirlo fuera de Claude hace falta ese esqueleto,
y para la web pública también la descripción y la vista previa al compartir el enlace.

Con --paquete además arma la carpeta publicar/ y vigia-web.zip para subir a Netlify.
"""

import os
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
PUBLICAR = ["index.html", "vista-previa.jpg", "datos/instantanea.js", "datos/fronteras.js", "datos/rios.js",
            "datos/lluvia-24h.png", "datos/lluvia-48h.png", "datos/lluvia-72h.png", "datos/lluvia-7d.png",
            "datos/lluvia-imerg.png", "datos/termica.jpg", "datos/territorio.json", "datos/ccpp.json", "tex/tierra-dia.jpg", "tex/tierra-noche.jpg", "tex/agua.jpg"]


def construir():
    contenido = (BASE / "vigia.html").read_text(encoding="utf-8")
    (BASE / "index.html").write_text(ESQUELETO + contenido + "\n</body></html>\n", encoding="utf-8")
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
