"""Recolector de VIGÍA.

Descarga datos públicos de vigilancia planetaria y los guarda en
datos/instantanea.js, que la página carga como respaldo cuando no puede
consultar las fuentes en vivo (por ejemplo, dentro de un artefacto de Claude).

Uso:  py recolectar.py
"""

import datetime as dt
import gzip
import html
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:  # el mapa mundial de ECMWF necesita leer GRIB2; sin estas librerías se omite
    import eccodes
    import numpy as np
    from PIL import Image
except ImportError:
    eccodes = np = Image = None

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"
AGENTE = "Mozilla/5.0 (compatible; VIGIA/1.0; monitor de riesgos sin fines de lucro)"
LIMA = dt.timezone(dt.timedelta(hours=-5))
SENAMHI_WEB = "https://www.senamhi.gob.pe"
SENAMHI_GEO = "https://idesep.senamhi.gob.pe/geoserver"
ECMWF = "https://data.ecmwf.int/forecasts"
GIBS = "https://gibs.earthdata.nasa.gov"

LUGARES = [
    # Perú: capitales de región y ciudades de la costa norte
    ("Tumbes", -3.567, -80.451, "PE"), ("Piura", -5.194, -80.632, "PE"),
    ("Sullana", -4.904, -80.685, "PE"), ("Talara", -4.577, -81.272, "PE"),
    ("Chiclayo", -6.771, -79.841, "PE"), ("Trujillo", -8.112, -79.029, "PE"),
    ("Chimbote", -9.075, -78.594, "PE"), ("Cajamarca", -7.164, -78.512, "PE"),
    ("Chachapoyas", -6.231, -77.869, "PE"), ("Moyobamba", -6.034, -76.972, "PE"),
    ("Tarapoto", -6.488, -76.360, "PE"), ("Iquitos", -3.749, -73.253, "PE"),
    ("Huaraz", -9.527, -77.528, "PE"), ("Huánuco", -9.930, -76.242, "PE"),
    ("Cerro de Pasco", -10.683, -76.256, "PE"), ("Pucallpa", -8.379, -74.554, "PE"),
    ("Huancayo", -12.065, -75.204, "PE"), ("Lima", -12.046, -77.043, "PE"),
    ("Callao", -12.057, -77.118, "PE"), ("Huancavelica", -12.787, -74.976, "PE"),
    ("Ica", -14.068, -75.729, "PE"), ("Ayacucho", -13.159, -74.224, "PE"),
    ("Abancay", -13.637, -72.879, "PE"), ("Cusco", -13.532, -71.968, "PE"),
    ("Puerto Maldonado", -12.593, -69.189, "PE"), ("Arequipa", -16.409, -71.537, "PE"),
    ("Puno", -15.840, -70.022, "PE"), ("Moquegua", -17.196, -70.935, "PE"),
    ("Tacna", -18.014, -70.253, "PE"),
    # Ecuador: la otra costa que golpea El Niño
    ("Guayaquil", -2.170, -79.922, "EC"), ("Machala", -3.258, -79.955, "EC"), ("Quito", -0.180, -78.468, "EC"),
]

# Resumen curado del último comunicado oficial leído. El recolector avisa si
# ENFEN publicó uno más reciente para que se actualice este texto.
ENFEN_RESUMEN = {
    "numero": "19-2026",
    "fecha": "2026-10-30",
    "estado": "Alerta de El Niño Costero",
    "titular": "El Niño costero continuaría hasta fines de otoño de 2027",
    "puntos": [
        "Frente a la costa (Niño 1+2) el calentamiento registra su máxima intensidad desde el inicio del evento; mantendría magnitud extraordinaria hasta febrero de 2027 y bajaría gradualmente hasta junio de 2027.",
        "En el Pacífico central (Niño 3.4) lo más probable es que siga con magnitud muy fuerte hasta febrero de 2027 y llegue a condición neutra en junio de 2027.",
        "Lluvias de noviembre de 2026 a enero de 2027 por encima de lo normal en la costa norte, la sierra occidental, la costa central y la sierra central occidental, con episodios de moderada a fuerte intensidad; en el verano de 2027, más intensas y frecuentes en la costa norte.",
        "Caudales superiores a lo normal en los ríos de la costa norte, principalmente Tumbes, Chira, Piura, La Leche y Jequetepeque; desde diciembre también en el Chillón, el Rímac y el Lurín.",
        "Temperatura del aire muy superior a lo habitual en toda la costa, con nuevos récords; nivel del mar por encima de lo normal, con riesgo de inundación y erosión costera ante oleajes anómalos.",
        "Embalses en su mayoría dentro de lo normal; Tinajones (Lambayeque) y Paucarani (Tacna) seguirían con niveles bajos.",
    ],
    "proximo": "2026-11-13",
    "url": "https://enfen.imarpe.gob.pe/",
}


# segundos de espera por descarga; en GitHub Actions se baja (VIGIA_ESPERA) para que una fuente lenta no frene a las demás
ESPERA = float(os.environ.get("VIGIA_ESPERA", "120"))
# El SENAMHI y el ENFEN no responden a los servidores de GitHub. Con VIGIA_PROXY (dirección del Worker de Cloudflare,
# ver nube/puente-peru.js) y VIGIA_PROXY_CLAVE, esas descargas pasan por el Worker; las demás van directo.
PROXY = os.environ.get("VIGIA_PROXY", "").rstrip("/")
PROXY_CLAVE = os.environ.get("VIGIA_PROXY_CLAVE", "")
POR_PROXY = ("idesep.senamhi.gob.pe", "www.senamhi.gob.pe", "enfen.imarpe.gob.pe")


def por_proxy(url):
    if PROXY and urllib.parse.urlsplit(url).hostname in POR_PROXY:
        return PROXY + "/?u=" + urllib.parse.quote(url, safe=""), {"X-Vigia-Clave": PROXY_CLAVE}
    return url, {}


def bajar(url, texto=False, intentos=2, binario=False, rango=None):
    ultimo = None
    for _ in range(intentos):
        try:
            destino, extra = por_proxy(url)
            cab = {"User-Agent": AGENTE, "Accept-Encoding": "gzip", **extra}
            if rango:
                cab["Range"] = f"bytes={rango[0]}-{rango[1]}"
            req = urllib.request.Request(destino, headers=cab)
            with urllib.request.urlopen(req, timeout=ESPERA) as r:
                crudo = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    crudo = gzip.decompress(crudo)
            if binario:
                return crudo
            return crudo.decode("utf-8", "replace") if texto else json.loads(crudo)
        except Exception as e:  # noqa: BLE001 - se informa y se sigue con la siguiente fuente
            ultimo = e
            if getattr(e, "code", None) == 429:  # límite por minuto de Open-Meteo: se espera y se reintenta
                time.sleep(65)
    raise RuntimeError(f"{url}: {ultimo}")


def r(x, n=3):
    return None if x is None else round(float(x), n)
















def oni():
    texto = bajar("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", texto=True)
    filas = []
    for l in texto.splitlines()[1:]:
        c = l.split()
        if len(c) == 4:
            filas.append([c[0], int(c[1]), float(c[2]), float(c[3])])
    return filas


MESES = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def serie_cpc(texto, seccion, meses=36):
    """Una sección (ANOMALY, STANDARDIZED...) de un índice mensual del CPC en ancho fijo: [[año, mes, valor], ...] de los últimos meses."""
    lineas = texto.splitlines()
    i = next(k for k, l in enumerate(lineas) if seccion in l.upper())
    filas = []
    for l in lineas[i + 1:]:
        if re.match(r"^\d{4}", l):
            for m in range(12):
                v = l[4 + 6 * m: 10 + 6 * m].strip()
                if v and float(v) > -999:
                    filas.append([int(l[:4]), m + 1, float(v)])
        elif filas and l.strip() and not l.strip().upper().startswith("YEAR"):
            break
    return filas[-meses:]


def oceano():
    """Indicadores del NOAA CPC que explican El Niño: alisios del Pacífico central (850 hPa), calor en los primeros 300 m
    del Pacífico ecuatorial e Índice de Oscilación del Sur. Mensuales."""
    viento = bajar("https://www.cpc.ncep.noaa.gov/data/indices/cpac850", texto=True)
    calor = bajar("https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ocean/index/heat_content_index.txt", texto=True)
    soi = bajar("https://www.cpc.ncep.noaa.gov/data/indices/soi", texto=True)
    filas_calor = []
    for l in calor.splitlines():
        c = l.split()
        if len(c) == 5 and c[0].isdigit():
            filas_calor.append([int(c[0]), int(c[1]), float(c[2]), float(c[3]), float(c[4])])
    return {
        "alisios": {"anomalia": serie_cpc(viento, "ANOMALY"), "estandar": serie_cpc(viento, "STANDARDIZED")},
        "calor": filas_calor[-36:],
        "soi": serie_cpc(soi, "STANDARDIZED"),
        "fuentes": {
            "alisios": "https://www.cpc.ncep.noaa.gov/data/indices/cpac850",
            "calor": "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ocean/index/heat_content_index.txt",
            "soi": "https://www.cpc.ncep.noaa.gov/data/indices/soi",
        },
    }


def nino_semanal():
    texto = bajar("https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for", texto=True)
    filas = []
    for l in texto.splitlines():
        m = re.match(r"\s*(\d{2})([A-Z]{3})(\d{4})\s+(.*)", l)
        if not m:
            continue
        nums = re.findall(r"-?\d+\.\d", m.group(4))
        if len(nums) != 8:
            continue
        fecha = f"{m.group(3)}-{MESES[m.group(2)]:02d}-{m.group(1)}"
        filas.append([fecha] + [float(x) for x in nums])
    # fecha, n12 tsm, n12 anom, n3 tsm, n3 anom, n34 tsm, n34 anom, n4 tsm, n4 anom
    return filas


def clima_lugares():
    lat = ",".join(str(l[1]) for l in LUGARES)
    lng = ",".join(str(l[2]) for l in LUGARES)
    url = ("https://api.open-meteo.com/v1/forecast?latitude=" + lat + "&longitude=" + lng +
           "&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,cloud_cover"
           "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max"
           "&models=ecmwf_ifs&timezone=auto&forecast_days=7")
    d = bajar(url)
    out = []
    for (nombre, la, lo, pais), c in zip(LUGARES, d):
        cur, day = c["current"], c["daily"]
        out.append({
            "n": nombre, "lat": la, "lng": lo, "pais": pais, "tz": c.get("timezone"),
            "ahora": {"t": cur["temperature_2m"], "hr": cur["relative_humidity_2m"], "pp": cur["precipitation"],
                      "wc": cur["weather_code"], "v": cur["wind_speed_10m"], "nub": cur["cloud_cover"], "hora": cur["time"]},
            "dias": [[day["time"][i], day["weather_code"][i], day["temperature_2m_max"][i], day["temperature_2m_min"][i],
                      day["precipitation_sum"][i], day["precipitation_probability_max"][i]] for i in range(len(day["time"]))],
        })
    return out


MESES_ES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                         "septiembre", "octubre", "noviembre", "diciembre"], 1)}
MESES_ES["setiembre"] = 9


def fecha_es(s):
    """«30 octubre 2026», «30 de octubre de 2026» o «30 Octubre, 2026» -> 2026-10-30 (None si no se entiende)."""
    m = re.search(r"(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+),?\s+(?:de\s+|del\s+)?(\d{4})", s or "", re.I)
    if not m or m.group(2).lower() not in MESES_ES:
        return None
    return f"{m.group(3)}-{MESES_ES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def leer_comunicado_enfen(pdf):
    """Del PDF del comunicado oficial: número, fecha, estado del sistema de alerta, titular y fecha del próximo.
    Solo lo que se puede leer sin interpretar; el resumen en puntos se escribe a mano (ENFEN_RESUMEN)."""
    import io
    from pypdf import PdfReader
    texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]
    i = next(k for k, l in enumerate(lineas) if re.match(r"COMUNICADO OFICIAL ENFEN N", l, re.I))
    numero = re.search(r"(\d+\s*-\s*\d{4})", lineas[i]).group(1).replace(" ", "")
    fecha = fecha_es(lineas[i + 1])
    # la línea del estado lleva pegada la llamada a la nota técnica («Alerta de El Niño Costero1»)
    estado = re.sub(r"^Estado del sistema de alerta:\s*", "", re.sub(r"\d+$", "", lineas[i + 2]).strip(), flags=re.I)
    if not re.match(r"(Alerta|Vigilancia|No activo)", estado, re.I):
        raise RuntimeError(f"no se reconoce el estado del comunicado {numero}: {estado!r}")
    titular = []
    for l in lineas[i + 3:i + 6]:  # el titular va en mayúsculas, en una o dos líneas; algunos comunicados no lo traen
        if l.upper() != l or len(l) < 8 or l.upper() == "RESUMEN EJECUTIVO":
            break
        titular.append(l)
    prox = re.search(r"pr[oó]ximo Comunicado Oficial se emitir[aá] el\s+(?:\w+\s+)?(\d{1,2}\s+de\s+\w+\s+del?\s+\d{4})",
                     re.sub(r"\s+", " ", texto), re.I)
    return {"numero": numero, "fecha": fecha, "estado": estado, "titular": " ".join(titular),
            "proximo": fecha_es(prox.group(1)) if prox else None}


def enfen_ultimo():
    texto = bajar("https://enfen.imarpe.gob.pe/", texto=True)
    plano = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto)))
    m = re.search(r"Comunicado Oficial Enfen N° (\d+-\d{4})\s+[\d.,]+ [KM]B \| (\d+ \w+, \d{4})", plano, re.I)
    info = dict(ENFEN_RESUMEN)
    if not m:
        return info
    info["ultimo_publicado"] = {"numero": m.group(1), "fecha": m.group(2)}
    enlace = re.search(r'href="(https://enfen\.imarpe\.gob\.pe/download/comunicado-oficial-enfen-n-' + m.group(1)
                       + r'/\?wpdmdl=\d+)', texto)
    if enlace:
        info["pdf"] = enlace.group(1)
    if m.group(1) == ENFEN_RESUMEN["numero"] or not enlace:
        return info
    # comunicado nuevo: se publica lo que dice el PDF y se retira el resumen en puntos, que es del anterior
    try:
        leido = leer_comunicado_enfen(bajar(enlace.group(1), binario=True))
    except Exception as e:  # noqa: BLE001 - queda el resumen anterior con el aviso de que hay uno nuevo
        print(f"  enfen      no se pudo leer el PDF del {m.group(1)}: {e}", flush=True)
        return info
    info.update({k: v for k, v in leido.items() if v})
    info.update({"puntos": [], "automatico": True, "resumen_de": ENFEN_RESUMEN["numero"]})
    if not leido.get("fecha"):
        info["fecha"] = fecha_es(m.group(2)) or info["fecha"]
    if not leido.get("proximo"):
        info.pop("proximo", None)
    return info


def limpiar(fragmento):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragmento))).strip()


# ---------- lluvia pronosticada ----------

# Cortes en mm y colores (rojo, verde, azul, opacidad) del mapa de lluvia; deben coincidir con la leyenda de la página
CORTES = {"dia": [2, 5, 10, 20, 35, 50, 75, 100], "semana": [5, 15, 30, 60, 100, 150, 225, 300]}
COLORES_LLUVIA = [(120, 175, 255, 70), (90, 150, 255, 135), (70, 115, 255, 185), (120, 90, 255, 210),
                  (170, 80, 250, 222), (215, 75, 230, 232), (250, 85, 190, 240), (255, 150, 175, 248)]


def corrida_ecmwf():
    """La corrida más reciente de ECMWF IFS (00 o 12 UTC) que ya publicó el paso de 168 horas."""
    ahora = dt.datetime.now(dt.timezone.utc)
    base = ahora.replace(hour=12 if ahora.hour >= 12 else 0, minute=0, second=0, microsecond=0)
    for k in range(6):
        t = base - dt.timedelta(hours=12 * k)
        raiz = f"{ECMWF}/{t:%Y%m%d}/{t:%H}z/ifs/0p25/oper/{t:%Y%m%d%H}0000-{{paso}}h-oper-fc"
        try:
            bajar(raiz.format(paso=168) + ".index", texto=True, intentos=1)
            return t, raiz
        except RuntimeError:
            continue
    raise RuntimeError("ninguna corrida de ECMWF disponible en las últimas 72 horas")


def lluvia_acumulada(raiz, paso):
    """Lluvia total acumulada desde el inicio de la corrida hasta `paso` horas, en mm, con longitudes de -180 a 180."""
    indice = bajar(raiz.format(paso=paso) + ".index", texto=True)
    e = next(json.loads(l) for l in indice.splitlines() if '"param": "tp"' in l)
    msg = bajar(raiz.format(paso=paso) + ".grib2", binario=True, rango=(e["_offset"], e["_offset"] + e["_length"] - 1))
    h = eccodes.codes_new_from_message(msg)
    try:
        ni, nj = eccodes.codes_get(h, "Ni"), eccodes.codes_get(h, "Nj")
        lon0 = eccodes.codes_get(h, "longitudeOfFirstGridPointInDegrees")
        dlon = eccodes.codes_get(h, "iDirectionIncrementInDegrees")
        lat0 = eccodes.codes_get(h, "latitudeOfFirstGridPointInDegrees")
        valores = eccodes.codes_get_values(h).reshape(nj, ni) * 1000.0
    finally:
        eccodes.codes_release(h)
    lons = (lon0 + np.arange(ni) * dlon + 180.0) % 360.0 - 180.0
    valores = valores[:, np.argsort(lons)]
    if lat0 < 0:  # se deja el norte arriba
        valores = valores[::-1]
    return valores


def pintar_lluvia(mm, cortes, ruta):
    clases = np.digitize(np.nan_to_num(mm), cortes).astype(np.uint8)  # 0 = menos que el primer corte
    img = Image.fromarray(clases, mode="P")
    paleta = [0, 0, 0] + [c for rgba in COLORES_LLUVIA for c in rgba[:3]]
    img.putpalette(paleta + [0] * (768 - len(paleta)))
    img.info["transparency"] = bytes([0] + [c[3] for c in COLORES_LLUVIA])
    img.save(ruta, optimize=True)


def anillos_peru():
    """Contorno del Perú (Natural Earth 1:110m, id 604) como anillos lng/lat."""
    topo = json.loads((DATOS / "countries-110m.json").read_text(encoding="utf-8"))
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]

    def arco(k):
        x = y = 0
        pts = []
        for dx, dy in topo["arcs"][k if k >= 0 else ~k]:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        return pts if k >= 0 else pts[::-1]

    geo = next(g for g in topo["objects"]["countries"]["geometries"] if str(g.get("id")) == "604")
    polis = geo["arcs"] if geo["type"] == "MultiPolygon" else [geo["arcs"]]
    return [[p for k in anillo for p in arco(k)] for poli in polis for anillo in poli]


def maximo_en_peru(mm):
    """Lluvia máxima dentro del territorio peruano (máscara rasterizada sobre la grilla de 0.25°)."""
    nj, ni = mm.shape
    mascara = Image.new("L", (ni, nj), 0)
    from PIL import ImageDraw
    dibujo = ImageDraw.Draw(mascara)
    for anillo in anillos_peru():
        dibujo.polygon([((lng + 180) / 360 * ni, (90 - lat) / 180 * (nj - 1)) for lng, lat in anillo], fill=1)
    dentro = np.array(mascara, dtype=bool)
    valores = np.where(dentro, mm, -1)
    j, i = np.unravel_index(np.nanargmax(valores), valores.shape)
    return {"mm": round(float(valores[j, i]), 1), "lat": round(90 - j * 180 / (nj - 1), 2),
            "lng": round(-180 + i * 360 / ni, 2)}


def lluvia_ecmwf():
    if eccodes is None:
        raise RuntimeError("faltan eccodes y numpy (py -m pip install --user eccodes numpy)")
    corrida, raiz = corrida_ecmwf()
    tp = {p: lluvia_acumulada(raiz, p) for p in (24, 48, 72, 168)}
    productos = [("24h", tp[24], 0, 24, "dia"), ("48h", tp[48] - tp[24], 24, 48, "dia"),
                 ("72h", tp[72] - tp[48], 48, 72, "dia"), ("7d", tp[168], 0, 168, "semana")]
    salida = []
    for ident, mm, desde, hasta, escala in productos:
        mm = np.clip(mm, 0, None)
        pintar_lluvia(mm, CORTES[escala], DATOS / f"lluvia-{ident}.png")
        salida.append({"id": ident, "desde": desde, "hasta": hasta, "escala": escala,
                       "archivo": f"datos/lluvia-{ident}.png", "max_peru": maximo_en_peru(mm)})
    return {"corrida": corrida.isoformat().replace("+00:00", "Z"), "modelo": "ECMWF IFS 0.25° (datos abiertos)",
            "cortes": CORTES, "colores": COLORES_LLUVIA, "productos": salida}


def lluvia_satelite():
    """Última imagen de lluvia por satélite (NASA GPM IMERG, media hora) en NASA GIBS."""
    hoy = dt.datetime.now(dt.timezone.utc)
    dominio = bajar(f"{GIBS}/wmts/epsg4326/best/wmts.cgi?SERVICE=WMTS&REQUEST=DescribeDomains&VERSION=1.0.0"
                    f"&LAYER=IMERG_Precipitation_Rate_30min&TILEMATRIXSET=2km"
                    f"&TIME={hoy - dt.timedelta(days=2):%Y-%m-%d}T00:00:00Z/{hoy + dt.timedelta(days=1):%Y-%m-%d}T00:00:00Z",
                    texto=True)
    m = re.search(r"<Domain>[^<]*/([0-9T:\-]+Z)/PT30M</Domain>", dominio)
    if not m:
        raise RuntimeError("GIBS no informó la última hora de IMERG")
    hora = m.group(1)
    png = bajar(f"{GIBS}/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
                f"&LAYERS=IMERG_Precipitation_Rate_30min&CRS=EPSG:4326&BBOX=-90,-180,90,180&WIDTH=2048&HEIGHT=1024"
                f"&FORMAT=image/png&TRANSPARENT=TRUE&TIME={hora}", binario=True)
    (DATOS / "lluvia-imerg.png").write_bytes(png)
    return {"hora": hora, "archivo": "datos/lluvia-imerg.png", "capa": "IMERG_Precipitation_Rate_30min"}


def rdp(puntos, eps):
    """Simplifica una línea (Ramer-Douglas-Peucker) sin recursión."""
    if len(puntos) < 3:
        return puntos
    if puntos[0] == puntos[-1]:  # anillo cerrado: se parte en el punto más lejano del inicio
        x0, y0 = puntos[0]
        k = max(range(len(puntos)), key=lambda i: (puntos[i][0] - x0) ** 2 + (puntos[i][1] - y0) ** 2)
        if 0 < k < len(puntos) - 1:
            return rdp(puntos[:k + 1], eps) + rdp(puntos[k:], eps)[1:]
    guardar = [False] * len(puntos)
    guardar[0] = guardar[-1] = True
    pila = [(0, len(puntos) - 1)]
    while pila:
        a, b = pila.pop()
        (x1, y1), (x2, y2) = puntos[a], puntos[b]
        dx, dy = x2 - x1, y2 - y1
        largo = math.hypot(dx, dy) or 1e-12
        peor, idx = 0.0, None
        for k in range(a + 1, b):
            x, y = puntos[k]
            d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / largo
            if d > peor:
                peor, idx = d, k
        if idx is not None and peor > eps:
            guardar[idx] = True
            pila += [(a, idx), (idx, b)]
    return [p for p, g in zip(puntos, guardar) if g]


def poligonos_simples(geom, eps=0.01, area_min=0.0004):
    """MultiPolygon GeoJSON -> lista de polígonos, cada uno lista de anillos [lng, lat, lng, lat, ...] redondeados."""
    polis = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    salida = []
    for poli in polis:
        anillos = []
        for anillo in poli:
            pts = rdp([(p[0], p[1]) for p in anillo], eps)
            area = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2
            if len(pts) >= 4 and area >= area_min:
                anillos.append([round(v, 3) for p in pts for v in p])
        if anillos:
            salida.append(anillos)
    return salida


NIVELES = {"Nivel 1": 1, "Nivel 2": 2, "Nivel 3": 3, "Nivel 4": 4}
NIVEL_COLOR = {"VERDE": 1, "AMARILLO": 2, "NARANJA": 3, "ROJO": 4}


def wfs_senamhi(espacio, capa, extra=""):
    url = (f"{SENAMHI_GEO}/{espacio}/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames={espacio}:{capa}"
           f"&outputFormat=application/json&srsName=EPSG:4326{extra}")
    return bajar(url)


def avisos_senamhi():
    """Avisos meteorológicos nacionales vigentes o por empezar, con su texto oficial y las zonas de cada día."""
    pagina = bajar(f"{SENAMHI_WEB}/?p=aviso-meteorologico", texto=True)
    hoy = dt.datetime.now(LIMA).date()
    avisos = []
    for fila in re.findall(r"<tr>(.*?)</tr>", pagina, re.S):
        celdas = re.findall(r"<td[^>]*>(.*?)</td>", fila, re.S)
        enlace = re.search(r"p=aviso-meteorologico-(?:detalle|vigente)&a=(\d{4})&b=(\d+)", fila)
        if len(celdas) != 7 or not enlace:
            continue
        nro = re.match(r"(\d+)\s*(?:\((\w+)\))?", limpiar(celdas[1]))
        try:
            emision, inicio, fin = (dt.date.fromisoformat(limpiar(c)) for c in celdas[2:5])
        except ValueError:
            continue
        if fin < hoy or not nro:
            continue
        titulo = limpiar(celdas[0])
        avisos.append({
            "numero": int(nro.group(1)), "anio": int(enlace.group(1)), "id": int(enlace.group(2)),
            "titulo": titulo, "emision": emision.isoformat(), "inicio": inicio.isoformat(), "fin": fin.isoformat(),
            "duracion": limpiar(celdas[5]), "nivel": NIVEL_COLOR.get(limpiar(celdas[6]).upper(), 0),
            "lluvia": bool(re.search(r"PRECIPITACI|LLUVIA|NEVADA|GRANIZO", titulo, re.I)),
            "url": f"{SENAMHI_WEB}/?p=aviso-meteorologico-detalle&a={enlace.group(1)}&b={enlace.group(2)}&c=00&d=SENA",
        })
    if not avisos:
        return {"avisos": [], "pagina": f"{SENAMHI_WEB}/?p=aviso-meteorologico"}
    # una página de detalle trae una pestaña por cada aviso activo, con su texto oficial
    detalle = bajar(avisos[0]["url"], texto=True)
    for a in avisos:
        m = re.search(rf'id="tabs-{a["numero"]}{a["anio"]}"(.*?)(?:<div class="tab-content"|id="tabs-\d+")', detalle, re.S)
        texto = limpiar(m.group(1)) if m else ""
        i = texto.find("El SENAMHI informa")
        a["texto"] = texto[i:] if i >= 0 else ""
        a["dias"] = []
        if not a["lluvia"]:
            continue
        dias = (dt.date.fromisoformat(a["fin"]) - dt.date.fromisoformat(a["inicio"])).days + 1
        for mapa in range(1, dias + 1):
            capa = wfs_senamhi("g_aviso", "view_aviso", f"&viewparams=qry:{a['numero']}_{mapa}_{a['anio']}")
            zonas = []
            for f in capa.get("features", []):
                nivel = NIVELES.get(f["properties"].get("nivel"), 0)
                if nivel >= 2 and f.get("geometry"):
                    zonas.append({"nivel": nivel, "poligonos": poligonos_simples(f["geometry"])})
            fecha = (dt.date.fromisoformat(a["inicio"]) + dt.timedelta(days=mapa - 1)).isoformat()
            a["dias"].append({"fecha": fecha, "nivel": max([z["nivel"] for z in zonas], default=1), "zonas": zonas})
    avisos.sort(key=lambda a: (not a["lluvia"], -a["nivel"], a["inicio"]))
    return {"avisos": avisos, "pagina": f"{SENAMHI_WEB}/?p=aviso-meteorologico"}


def quebradas_senamhi():
    """Aviso de corto plazo ante posible activación de quebradas (huaicos) y los distritos que cubre."""
    url = f"{SENAMHI_WEB}/main.php?dp=lima&p=aviso-activacion-quebrada"
    pagina = bajar(url, texto=True)
    i = pagina.find('id="nav-aviso"')
    panel = limpiar(pagina[i:i + 5000]) if i >= 0 else ""
    pestana = re.search(r"Aviso\s+(\d+)\s*-\s*(\d{4})", limpiar(pagina[pagina.find("nav-aviso-tab"):][:400]))
    nro = re.search(r"N[°º]\s*(\d+)\s*-\s*(\d{4})", panel)
    # la página también muestra un comunicado viejo: solo vale si la pestaña y el panel coinciden
    if not (pestana and nro and pestana.groups() == nro.groups()):
        raise RuntimeError("no se reconoció el aviso de quebradas vigente")
    nivel = re.search(r"NIVEL\s+(AMARILLO|NARANJA|ROJO)", panel)
    ini = re.search(r"Fecha de inicio:\s*\w+\s+(\d{1,2})\s+(\w+)\s+(\d{4})\s*-\s*(\d{1,2}):(\d{2})", panel)
    dur = re.search(r"Duración:\s*(\d+)\s*hrs", panel)
    texto = re.search(r"(Ante el pronóstico de lluvias.*?quebradas\.)", panel)
    inicio = None
    if ini and ini.group(2).lower() in MESES_ES:
        inicio = dt.datetime(int(ini.group(3)), MESES_ES[ini.group(2).lower()], int(ini.group(1)),
                             int(ini.group(4)), int(ini.group(5)), tzinfo=LIMA).isoformat()
    capa = wfs_senamhi("g_acti_quebrada", "view_av_activ_qdra", "&propertyName=nivel,fecha,nombdep,nombprov,nombdist,geom")
    distritos = []
    for f in capa.get("features", []):
        p, g = f["properties"], f.get("geometry")
        nivel_d = NIVELES.get(p.get("nivel"), 0)
        if nivel_d < 2 or not g:
            continue
        anillo = (g["coordinates"][0][0] if g["type"] == "MultiPolygon" else g["coordinates"][0])
        lng = sum(q[0] for q in anillo) / len(anillo)
        lat = sum(q[1] for q in anillo) / len(anillo)
        distritos.append([round(lat, 3), round(lng, 3), nivel_d, p.get("nombdep"), p.get("nombprov"), p.get("nombdist")])
    return {"numero": int(nro.group(1)), "anio": int(nro.group(2)), "nivel": NIVEL_COLOR.get(nivel.group(1), 0) if nivel else 0,
            "inicio": inicio, "horas": int(dur.group(1)) if dur else 24, "texto": texto.group(1) if texto else "",
            "url": url, "distritos": distritos}


def probabilidad_lluvia():
    """Probabilidad de lluvia por umbrales con los 51 escenarios del conjunto de ECMWF, para las ciudades del Perú."""
    pe = [l for l in LUGARES if l[3] == "PE"]
    url = ("https://ensemble-api.open-meteo.com/v1/ensemble?latitude=" + ",".join(str(l[1]) for l in pe) +
           "&longitude=" + ",".join(str(l[2]) for l in pe) +
           "&daily=precipitation_sum&models=ecmwf_ifs025&forecast_days=7&timezone=America/Lima")
    datos = bajar(url)
    salida = {}
    for (nombre, *_), d in zip(pe, datos):
        salida[nombre] = resumir_conjunto(d["daily"])
    return salida


def resumir_conjunto(diario):
    claves = [k for k in diario if k.startswith("precipitation_sum")]
    dias = []
    for i, fecha in enumerate(diario["time"]):
        v = sorted(x for x in (diario[k][i] for k in claves) if x is not None)
        if not v:
            continue
        q = lambda p: round(v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))], 1)
        prob = lambda u: round(100 * sum(x >= u for x in v) / len(v))
        dias.append([fecha, q(0.1), q(0.5), q(0.9), prob(10), prob(20), prob(50), len(v)])
    return dias  # fecha, p10, mediana, p90, P≥10 mm, P≥20 mm, P≥50 mm, escenarios


# ---------- zona de operaciones norte (Tumbes, Piura, Lambayeque) ----------

_CACHE = {}  # resultados de esta corrida que otras fuentes reutilizan
DEP_NORTE = {"24": "TUMBES", "20": "PIURA", "14": "LAMBAYEQUE", "13": "LA LIBERTAD", "06": "CAJAMARCA"}
AERODROMOS = [("SPME", "Tumbes"), ("SPYL", "Talara"), ("SPUR", "Piura"), ("SPHI", "Chiclayo"), ("SPRU", "Trujillo"), ("SPJR", "Cajamarca")]
CAJA_TERMICA = (-20.0, -90.0, 5.0, -65.0)  # lat mín, lng mín, lat máx, lng máx


def sin_tildes(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").upper()) if unicodedata.category(c) != "Mn").strip()


def dentro(x, y, anillos):
    adentro = False
    for r in anillos:
        j = len(r) - 2
        for i in range(0, len(r), 2):
            xi, yi, xj, yj = r[i], r[i + 1], r[j], r[j + 1]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                adentro = not adentro
            j = i
    return adentro


def wfs_cql(espacio, capa, cql, props=None):
    import urllib.parse
    extra = "&CQL_FILTER=" + urllib.parse.quote(cql)
    if props:
        extra += "&propertyName=" + ",".join(props)
    return wfs_senamhi(espacio, capa, extra)


def zona_norte():
    deps = list(DEP_NORTE.values())
    en_deps = lambda campo: f"{campo} IN ({','.join(repr(d) for d in deps)})"
    provs = {f["properties"]["idprov"]: f["properties"]["provincia"] for f in wfs_cql(
        "g_carto_fundamento", "provincias", " OR ".join(f"idprov LIKE '{k}%'" for k in DEP_NORTE), ["idprov", "provincia"])["features"]}
    capa = wfs_cql("g_carto_fundamento", "distritos", " OR ".join(f"iddist LIKE '{k}%'" for k in DEP_NORTE))
    avisos = [a for a in _CACHE.get("avisos", {}).get("avisos", []) if a.get("lluvia")]
    quebradas = {}
    for d in _CACHE.get("quebradas", {}).get("distritos", []):
        clave = (sin_tildes(d[3]), sin_tildes(d[5]))
        quebradas[clave] = max(quebradas.get(clave, 0), d[2])
    distritos = []
    for f in capa["features"]:
        p = f["properties"]
        ubigeo, dep = p["iddist"], DEP_NORTE[p["iddist"][:2]]
        polis = poligonos_simples(f["geometry"], eps=0.002, area_min=0.00001)
        if not polis:
            continue
        mayor = max((poli[0] for poli in polis), key=len)
        xs, ys = mayor[0::2], mayor[1::2]
        # centroide del anillo mayor (fórmula del área) y puntos de muestra para cruzar con los avisos
        a = cx = cy = 0.0
        for i in range(len(xs)):
            k = (i + 1) % len(xs)
            c = xs[i] * ys[k] - xs[k] * ys[i]
            a, cx, cy = a + c, cx + (xs[i] + xs[k]) * c, cy + (ys[i] + ys[k]) * c
        lng, lat = (cx / (3 * a), cy / (3 * a)) if abs(a) > 1e-12 else (sum(xs) / len(xs), sum(ys) / len(ys))
        paso = max(1, len(xs) // 24)
        muestras = [(lng, lat)] + [(xs[i], ys[i]) for i in range(0, len(xs), paso)]
        afect = {}
        for av in avisos:
            for dia in av["dias"]:
                nivel = 0
                for z in dia["zonas"]:
                    if z["nivel"] > nivel and any(dentro(x, y, poli) for poli in z["poligonos"] for x, y in muestras):
                        nivel = z["nivel"]
                if nivel >= 2:
                    afect[dia["fecha"]] = max(afect.get(dia["fecha"], 0), nivel)
        area_km2 = abs(a) / 2 * (111.32 ** 2) * math.cos(math.radians(lat))
        distritos.append({
            "id": ubigeo, "n": p["distrito"], "cap": p.get("capital"), "prov": provs.get(ubigeo[:4], ""), "dep": dep,
            "lat": round(lat, 4), "lng": round(lng, 4), "km2": round(area_km2), "poligonos": polis,
            "afect": afect, "quebrada": quebradas.get((dep, sin_tildes(p["distrito"])), 0),
        })
    por_id = {d["id"]: d for d in distritos}
    por_nombre = {(d["dep"], sin_tildes(d["n"])): d for d in distritos}
    for d in distritos:
        d["exp"] = {"pob": 0, "viv": 0, "ccpp": 0, "eess": 0, "iiee": 0, "alumnos": 0, "vias_km": 0.0}
    # exposición calculada por el SENAMHI para el aviso de quebradas vigente
    ccpp = []
    for f in wfs_cql("g_acti_quebrada", "ccpp_filter", en_deps("nomb_dep"),
                     ["arnombre", "nomb_dep", "nomb_dist", "ubigeo", "pob_total", "viv_total", "nivel", "n_inund", "n_mm", "latitud", "longitud"])["features"]:
        q = f["properties"]
        d = por_id.get(str(q.get("ubigeo"))) or por_nombre.get((q.get("nomb_dep"), sin_tildes(q.get("nomb_dist"))))
        if d:
            d["exp"]["pob"] += int(q.get("pob_total") or 0)
            d["exp"]["viv"] += int(q.get("viv_total") or 0)
            d["exp"]["ccpp"] += 1
        ccpp.append([round(float(q["latitud"]), 4), round(float(q["longitud"]), 4), q.get("arnombre"), d["id"] if d else None,
                     int(q.get("pob_total") or 0), int(q.get("viv_total") or 0), int(q.get("nivel") or 0), q.get("n_inund"), q.get("n_mm")])
    eess = []
    for f in wfs_cql("g_acti_quebrada", "eess_filter", en_deps("departamen"),
                     ["departamen", "distrito", "estubigeo", "nombre_del", "categoria", "nivel", "latitud", "longitud"])["features"]:
        q = f["properties"]
        d = por_id.get(str(q.get("estubigeo"))) or por_nombre.get((q.get("departamen"), sin_tildes(q.get("distrito"))))
        if d:
            d["exp"]["eess"] += 1
        eess.append([round(float(q["latitud"]), 4), round(float(q["longitud"]), 4), q.get("nombre_del"), q.get("categoria"),
                     d["id"] if d else None, int(q.get("nivel") or 0)])
    iiee = []
    for f in wfs_cql("g_acti_quebrada", "iiee_filter", en_deps("nombdep"),
                     ["nombdep", "nombdist", "iddistrito", "cenedu", "talumno", "nivel", "latitud", "longitud"])["features"]:
        q = f["properties"]
        d = por_id.get(str(q.get("iddistrito"))) or por_nombre.get((q.get("nombdep"), sin_tildes(q.get("nombdist"))))
        if d:
            d["exp"]["iiee"] += 1
            d["exp"]["alumnos"] += int(q.get("talumno") or 0)
        iiee.append([round(float(q["latitud"]), 4), round(float(q["longitud"]), 4), q.get("cenedu"), int(q.get("talumno") or 0),
                     d["id"] if d else None, int(q.get("nivel") or 0)])
    for capa_vial in ("vial_nacional_filter", "vial_departamental_filter", "vial_vecinal_filter"):
        for f in wfs_cql("g_acti_quebrada", capa_vial, en_deps("nombdep"), ["nombdep", "nombdist", "longitud"])["features"]:
            q = f["properties"]
            d = por_nombre.get((q.get("nombdep"), sin_tildes(q.get("nombdist"))))
            if d:
                d["exp"]["vias_km"] = round(d["exp"]["vias_km"] + float(q.get("longitud") or 0) / 1000, 1)  # el SENAMHI la da en metros
    # lluvia de los próximos 7 días en el centro de cada distrito (ECMWF 9 km) y probabilidades del conjunto
    hres, ens = [], []
    for i in range(0, len(distritos), 100):  # en lotes, para respetar los límites de Open-Meteo
        lote = distritos[i:i + 100]
        la_l = ",".join(str(d["lat"]) for d in lote)
        lo_l = ",".join(str(d["lng"]) for d in lote)
        h = bajar("https://api.open-meteo.com/v1/forecast?latitude=" + la_l + "&longitude=" + lo_l +
                  "&daily=precipitation_sum,precipitation_probability_max&models=ecmwf_ifs&timezone=America/Lima&forecast_days=7")
        e = bajar("https://ensemble-api.open-meteo.com/v1/ensemble?latitude=" + la_l + "&longitude=" + lo_l +
                  "&daily=precipitation_sum&models=ecmwf_ifs025&timezone=America/Lima&forecast_days=7")
        hres += h if isinstance(h, list) else [h]
        ens += e if isinstance(e, list) else [e]
        time.sleep(3)
    for d, h, e in zip(distritos, hres, ens):
        d["lluvia"] = [[t, mm] for t, mm in zip(h["daily"]["time"], h["daily"]["precipitation_sum"])]
        d["conjunto"] = resumir_conjunto(e["daily"])
    return {"departamentos": deps, "distritos": distritos, "ccpp": ccpp, "eess": eess, "iiee": iiee,
            "quebrada_aviso": {k: _CACHE.get("quebradas", {}).get(k) for k in ("numero", "anio", "inicio", "horas", "nivel")}}


def aerodromos():
    ids = ",".join(i for i, _ in AERODROMOS)
    metar = {}
    for m in bajar(f"https://aviationweather.gov/api/data/metar?ids={ids}&format=json&hours=3"):
        if m["icaoId"] not in metar or m.get("obsTime", 0) > metar[m["icaoId"]].get("obsTime", 0):
            metar[m["icaoId"]] = m  # el más reciente
    taf = {t["icaoId"]: t for t in bajar(f"https://aviationweather.gov/api/data/taf?ids={ids}&format=json")}
    salida = []
    for icao, ciudad in AERODROMOS:
        m, t = metar.get(icao), taf.get(icao)
        salida.append({"icao": icao, "ciudad": ciudad, "nombre": (m or t or {}).get("name"), "lat": (m or {}).get("lat"),
                       "lng": (m or {}).get("lon"), "metar": m, "taf": {"raw": t["rawTAF"], "emitido": t.get("issueTime")} if t else None})
    return salida


def termica():
    """Última imagen infrarroja (banda 13) de GOES-East sobre el norte de Sudamérica, vía NASA GIBS."""
    hoy = dt.datetime.now(dt.timezone.utc)
    dominio = bajar(f"{GIBS}/wmts/epsg4326/best/wmts.cgi?SERVICE=WMTS&REQUEST=DescribeDomains&VERSION=1.0.0"
                    f"&LAYER=GOES-East_ABI_Band13_Clean_Infrared&TILEMATRIXSET=2km"
                    f"&TIME={hoy - dt.timedelta(days=1):%Y-%m-%d}T00:00:00Z/{hoy + dt.timedelta(days=1):%Y-%m-%d}T00:00:00Z", texto=True)
    finales = re.findall(r"/([0-9T:\-]+Z)/PT10M", dominio)
    if not finales:
        raise RuntimeError("GIBS no informó la última hora de GOES-East")
    hora = max(finales)
    # la última imagen a veces aún no está completa: se retrocede hasta encontrar una con contenido
    t = dt.datetime.fromisoformat(hora.replace("Z", "+00:00"))
    for _ in range(6):
        h = t.strftime("%Y-%m-%dT%H:%M:%SZ")
        img = bajar(f"{GIBS}/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0&LAYERS=GOES-East_ABI_Band13_Clean_Infrared"
                    f"&CRS=EPSG:4326&BBOX={CAJA_TERMICA[0]},{CAJA_TERMICA[1]},{CAJA_TERMICA[2]},{CAJA_TERMICA[3]}&WIDTH=1200&HEIGHT=1200"
                    f"&FORMAT=image/jpeg&TIME={h}", binario=True)
        if len(img) > 60000:
            (DATOS / "termica.jpg").write_bytes(img)
            return {"hora": h, "archivo": "datos/termica.jpg", "caja": CAJA_TERMICA}
        t -= dt.timedelta(minutes=10)
    raise RuntimeError("sin imagen térmica reciente con contenido")


GLM = "https://noaa-goes19.s3.amazonaws.com"
CAJA_PERU = (-81.6, -18.6, -68.4, 0.2)


def rayos(minutos=60):
    """Rayos detectados por el GLM (Geostationary Lightning Mapper) del GOES-19 sobre el Perú en la última hora.
    El GLM publica un archivo cada 20 segundos en el bucket abierto de la NOAA; se usan los destellos con buena
    calidad (flash_quality_flag 0) dentro del contorno del país."""
    import io
    from concurrent.futures import ThreadPoolExecutor
    import h5py
    ahora = dt.datetime.now(dt.timezone.utc)
    desde = ahora - dt.timedelta(minutes=minutos)
    claves = []
    for h in sorted({desde.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=k) for k in range(minutos // 60 + 2)}):
        if h > ahora:
            continue
        token = ""
        while True:
            xml = bajar(f"{GLM}/?list-type=2&prefix=GLM-L2-LCFA/{h:%Y/%j/%H}/" + token, texto=True)
            for k in re.findall(r"<Key>([^<]+\.nc)</Key>", xml):
                ini = dt.datetime.strptime(re.search(r"_s(\d{13})", k).group(1), "%Y%j%H%M%S").replace(tzinfo=dt.timezone.utc)
                if ini >= desde:
                    claves.append((ini, k))
            sig = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
            if not sig:
                break
            token = "&continuation-token=" + urllib.parse.quote(sig.group(1), safe="")
    if not claves:
        raise RuntimeError("el GLM no tiene archivos de la última hora")
    anillos = [[c for p in a for c in p] for a in anillos_peru()]
    x0, y0, x1, y1 = CAJA_PERU

    def leer(par):
        ini, k = par
        try:
            f = h5py.File(io.BytesIO(bajar(f"{GLM}/{k}", binario=True, intentos=3)), "r")
        except Exception:  # noqa: BLE001 - un archivo de 20 s perdido se cuenta aparte
            return None
        la, lo, q = f["flash_lat"][:], f["flash_lon"][:], f["flash_quality_flag"][:]
        m = (q == 0) & (lo > x0) & (lo < x1) & (la > y0) & (la < y1)
        edad = round((ahora - ini).total_seconds() / 60)
        return [[round(float(x), 3), round(float(y), 3), edad] for x, y in zip(lo[m], la[m]) if dentro(float(x), float(y), anillos)]

    with ThreadPoolExecutor(8) as pool:
        partes = list(pool.map(leer, claves))
    # una tormenta da cientos de destellos: se agrupan en celdas de 0,05° (unos 5 km) con su cantidad y el más reciente
    celdas = {}
    for x, y, edad in (p for parte in partes if parte for p in parte):
        k = (math.floor(x / 0.05), math.floor(y / 0.05))
        n, e = celdas.get(k, (0, edad))
        celdas[k] = (n + 1, min(e, edad))
    return {
        "desde": min(c[0] for c in claves).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hasta": (max(c[0] for c in claves) + dt.timedelta(seconds=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "archivos": len(claves), "perdidos": sum(1 for p in partes if p is None),
        "total": sum(n for n, _ in celdas.values()),
        # [lng, lat del centro de la celda, destellos, minutos desde el más reciente hasta la hora de la corrida]
        "celdas": sorted(([round((i + 0.5) * 0.05, 3), round((j + 0.5) * 0.05, 3), n, e] for (i, j), (n, e) in celdas.items()), key=lambda c: c[3]),
        "fuente": "NOAA GOES-19 GLM L2 (noaa-goes19 en AWS)",
    }


# ---------- cuencas, ríos y caudales del norte ----------

CAJA_NORTE = (-81.5, -9.0, -77.6, -3.3)  # lng mín, lat mín, lng máx, lat máx: de Tumbes a La Libertad y Cajamarca
CAJA_IMAGEN = (-81.45, -7.25, -78.65, -3.35)  # recuadro de la imagen satelital detallada de la zona
FLOOD = "https://flood-api.open-meteo.com/v1/flood"


def area_km2(anillo_plano):
    xs, ys = anillo_plano[0::2], anillo_plano[1::2]
    a = sum(xs[i] * ys[i - 1] - xs[i - 1] * ys[i] for i in range(len(xs))) / 2
    return abs(a) * 111.32 ** 2 * math.cos(math.radians(sum(ys) / len(ys)))


def caudal_salida(codigo, candidatos):
    """Celda de GloFAS con más caudal entre puntos de los ríos de la cuenca: el cauce principal cerca de la salida.
    Se guarda en datos/salidas.json para no repetir la búsqueda en cada actualización."""
    cache_ruta = DATOS / "salidas.json"
    cache = json.loads(cache_ruta.read_text(encoding="utf-8")) if cache_ruta.exists() else {}
    if codigo in cache:
        return tuple(cache[codigo])
    if not candidatos:
        return None
    paso = max(1, len(candidatos) // 60)
    lote = candidatos[::paso][:60]
    d = bajar(f"{FLOOD}?latitude={','.join(str(p[0]) for p in lote)}&longitude={','.join(str(p[1]) for p in lote)}"
              "&daily=river_discharge&past_days=30&forecast_days=7")
    d = d if isinstance(d, list) else [d]
    mejor, mejor_media = None, -1
    for (la, lo), r in zip(lote, d):
        v = [q for q in r["daily"]["river_discharge"] if q is not None]
        media = sum(v) / len(v) if v else -1
        if media > mejor_media:
            mejor, mejor_media = (la, lo), media
    if mejor:
        cache[codigo] = mejor
        cache_ruta.write_text(json.dumps(cache), encoding="utf-8")
    time.sleep(2)
    return mejor


def historia_caudal(la, lo, desde="1984-01-01"):
    """Máximos anuales desde 1984. Es la consulta más pesada para los límites de Open-Meteo (unas mil llamadas
    por río), así que se guarda en datos/historias.json y se renueva cada 60 días."""
    ruta = DATOS / "historias.json"
    cache = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    clave = f"{la},{lo}"
    if clave in cache and (dt.date.today() - dt.date.fromisoformat(cache[clave]["fecha"])).days < 60:
        return cache[clave]["historia"]
    h = _historia_caudal(la, lo, desde)
    if h:
        cache[clave] = {"fecha": dt.date.today().isoformat(), "historia": h}
        ruta.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return h


def _historia_caudal(la, lo, desde="1984-01-01"):
    hoy = dt.date.today()
    d = bajar(f"{FLOOD}?latitude={la}&longitude={lo}&daily=river_discharge&start_date={desde}&end_date={hoy - dt.timedelta(days=1)}")
    maximos = {}
    for t, q in zip(d["daily"]["time"], d["daily"]["river_discharge"]):
        if q is not None and (t[:4] not in maximos or q > maximos[t[:4]][0]):
            maximos[t[:4]] = (q, t)
    anuales = sorted(v[0] for k, v in maximos.items() if k != str(hoy.year))
    if not anuales:
        return {}
    pct = lambda p: round(anuales[min(len(anuales) - 1, int(p * (len(anuales) - 1) + 0.5))], 1)
    record = max(maximos.values())
    top = sorted(maximos.values(), reverse=True)[:5]
    return {"mediana_max_anual": pct(0.5), "p90_max_anual": pct(0.9), "record": round(record[0], 1), "record_fecha": record[1],
            "mayores": [[round(q, 1), t] for q, t in top], "anios": len(anuales)}


def pronostico_caudal(la, lo):
    d = bajar(f"{FLOOD}?latitude={la}&longitude={lo}&daily=river_discharge,river_discharge_median,river_discharge_p25,"
              "river_discharge_p75,river_discharge_max&past_days=10&forecast_days=30")["daily"]
    claves = ["river_discharge", "river_discharge_median", "river_discharge_p25", "river_discharge_p75", "river_discharge_max"]
    return [[t] + [None if d[k][i] is None else round(d[k][i], 1) for k in claves] for i, t in enumerate(d["time"])]


MODELOS = ["ecmwf_ifs", "gfs_seamless", "icon_seamless", "ukmo_seamless", "gem_seamless", "jma_seamless", "meteofrance_seamless"]
MALLA = {"la0": -9.5, "lo0": -81.5, "paso": 0.5, "filas": 23, "cols": 10}  # norte del Perú y Ecuador


def multimodelo():
    """Lluvia cada 3 horas en las próximas 72, de siete modelos globales (ECMWF, GFS, ICON, UKMO, GEM, JMA, ARPEGE)
    vía Open-Meteo, en una malla de 0,5°. La página arma con ellos el escenario probable (mediana) y el pesimista."""
    m = MALLA
    pts = [(round(m["la0"] + m["paso"] * i, 2), round(m["lo0"] + m["paso"] * j, 2)) for i in range(m["filas"]) for j in range(m["cols"])]
    d = bajar("https://api.open-meteo.com/v1/forecast?latitude=" + ",".join(str(p[0]) for p in pts) +
              "&longitude=" + ",".join(str(p[1]) for p in pts) + "&hourly=precipitation&models=" + ",".join(MODELOS) +
              "&forecast_days=4&timezone=UTC")
    d = d if isinstance(d, list) else [d]
    horas = d[0]["hourly"]["time"]
    ahora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:00")
    i0 = max(0, next((i for i, t in enumerate(horas) if t >= ahora), 0) // 3 * 3)
    pasos = min(24, (len(horas) - i0) // 3)
    lluvia = {}
    for mod in MODELOS:
        k = "precipitation_" + mod
        lluvia[mod] = [[round(sum(x or 0 for x in p["hourly"][k][i0 + 3 * s:i0 + 3 * s + 3]) * 10) for p in d] for s in range(pasos)]
    return {"inicio": horas[i0] + ":00Z", "paso_h": 3, "malla": m, "modelos": MODELOS, "lluvia": lluvia}


# ríos de Ecuador sin cuencas dibujadas: solo el punto de GloFAS cerca de su curso bajo
RIOS_EC = {"Guayas": (-2.05, -79.85), "Babahoyo": (-1.80, -79.53), "Daule": (-1.86, -79.98), "Vinces / Quevedo": (-1.03, -79.47),
           "Esmeraldas": (0.90, -79.67), "Portoviejo": (-1.06, -80.46), "Chone": (-0.69, -80.10), "Jubones": (-3.25, -79.80)}


def rios_ecuador():
    salida = []
    for n, (la, lo) in RIOS_EC.items():
        cand = [(round(la + 0.05 * a, 3), round(lo + 0.05 * b, 3)) for a in range(-2, 3) for b in range(-2, 3)]
        p = caudal_salida("EC-" + n, cand)
        if not p:
            continue
        # historia desde 2005: la consulta desde 1984 pesa demasiado para el límite horario de Open-Meteo
        salida.append({"n": n, "pais": "EC", "salida": list(p), "caudal": pronostico_caudal(*p), "historia": historia_caudal(*p, desde="2005-01-01")})
        time.sleep(1)
    return salida


def ensamble_rios():
    """Los 50 escenarios de GloFAS (y el de control) a 10 días en la salida de cada río: con ellos la página calcula
    la probabilidad de pasar la crecida de 2, 5 y 20 años, como GloFAS y Google Flood Hub."""
    puntos = [(c["codigo"], c["salida"]) for c in (_CACHE.get("cuencas") or {}).get("cuencas", []) if c.get("salida")]
    puntos += [("EC-" + r["n"], r["salida"]) for r in (_CACHE.get("rios_ec") or [])]
    if not puntos:
        return None
    d = bajar(f"{FLOOD}?latitude={','.join(str(x[1][0]) for x in puntos)}&longitude={','.join(str(x[1][1]) for x in puntos)}"
              "&daily=river_discharge&ensemble=true&forecast_days=10")
    d = d if isinstance(d, list) else [d]
    redondo = lambda q: None if q is None else (round(q) if q >= 20 else round(q, 1))
    por = {}
    for (k, _), r in zip(puntos, d):
        x = r["daily"]
        claves = [c for c in x if c.startswith("river_discharge")]
        por[k] = [[redondo(x[c][i]) for c in claves] for i in range(len(x["time"]))]
    return {"fechas": d[0]["daily"]["time"], "rios": por}


# ---------- ríos del resto del Perú: un punto de control de GloFAS por cuenca ----------
# Las cuencas y las intercuencas con nombre de la ANA (Marañón, Huallaga, Ucayali, Apurímac, Madre de Dios…); las del
# norte ya las calcula cuencas_norte con su red de ríos. El límite de Open-Meteo no deja armar todo en una corrida:
# cada corrida busca algunos puntos de control y algunas series históricas nuevas, y los guarda para las siguientes.
RIOS_PE_SALIDAS = 12      # cuencas nuevas por corrida donde se busca el punto de control (60 consultas cada una)
RIOS_PE_HISTORIAS = 4     # series nuevas desde 2005 por corrida (unas 550 consultas cada una)
RIOS_PE_SEGUNDOS = 240    # tope de tiempo para la parte lenta (búsquedas e historias)


def unidades_peru():
    """Cuencas e intercuencas con nombre de todo el Perú, con su contorno simplificado. Cambian poco: se guardan
    en datos/unidades.json y se vuelven a pedir cada 90 días."""
    ruta = DATOS / "unidades.json"
    if ruta.exists():
        u = json.loads(ruta.read_text(encoding="utf-8"))
        if (dt.date.today() - dt.date.fromisoformat(u["fecha"])).days < 90:
            return u["unidades"]
    capa = wfs_senamhi("g_carto_fundamento", "cuencas", "&propertyName=codigo,nombre,orden,nivel1,geom")
    salida = []
    for f in capa["features"]:
        p, g = f["properties"], f.get("geometry")
        n = (p.get("nombre") or "").strip()
        if not g or p.get("orden") == 999 or n.startswith(("Lago", "Interna")) or re.fullmatch(r"Intercuenca \d+", n):
            continue
        polis = poligonos_simples(g, eps=0.003, area_min=0.0005)
        km2 = round(sum(area_km2(poli[0]) for poli in polis)) if polis else 0
        if not polis or (n.startswith("Intercuenca") and km2 < 500):  # tramos diminutos de un río grande: no lo representan
            continue
        salida.append({"codigo": p["codigo"], "n": n.replace("Cuenca ", "").replace("Intercuenca ", "").replace("Huallga", "Huallaga"),
                       "tipo": "intercuenca" if n.startswith("Intercuenca") else "cuenca",
                       "vertiente": {"1": "Pacífico", "0": "Titicaca"}.get(p.get("nivel1"), "Amazonas"),  # Pfafstetter: 1, 4 y 0
                       "km2": km2, "poligonos": polis})
    ruta.write_text(json.dumps({"fecha": dt.date.today().isoformat(), "unidades": salida}, ensure_ascii=False), encoding="utf-8")
    return salida


def nombres_cauce(n):
    """Nombres de río que buscar en la red del IGN: «Alto Marañón I» → Marañón; «Quilca - Vitor - Chili» → los tres."""
    n = re.sub(r"\b(Alto|Medio|Bajo|I{1,3}|IV|V)\b", " ", n.replace("De Las", "Las").replace("De la", "La"))
    return [p.strip() for p in re.split(r"\s+-\s+|-", n) if len(p.strip()) >= 4]


def dist_borde(x, y, polis):
    m = 9.0
    for p in polis:
        for anillo in p:
            for k in range(0, len(anillo) - 2, 2):
                ax, ay, bx, by = anillo[k], anillo[k + 1], anillo[k + 2], anillo[k + 3]
                dx, dy = bx - ax, by - ay
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy or 1e-12)))
                m = min(m, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return m


def candidatos_cauce(u, n=60):
    """Puntos del río que da nombre a la cuenca (red hídrica del IGN: líneas y, para los ríos anchos, sus márgenes),
    dentro de ella y lo más lejos posible de su borde: así la celda de GloFAS con más caudal es la de ese río cerca
    de su salida, y no la del río grande al que desemboca."""
    dentro_ = []
    for nombre in nombres_cauce(u["n"]):
        comodin = re.sub(r"[aeiouáéíóúüñ]", "_", nombre.lower())  # el IGN y la ANA no siempre tildan igual
        patron = re.compile(r"\b" + re.escape(sin_tildes(nombre).lower()) + r"\b")
        for capa_ign in ("rios_linea_ign", "rios_area_ign"):
            capa = wfs_cql("g_carto_fundamento", capa_ign, f"nombre ILIKE '%{comodin}%'", ["nombre", "geom"])
            for f in capa["features"]:
                g = f.get("geometry")
                if not g or not patron.search(sin_tildes(f["properties"].get("nombre") or "").lower()):
                    continue
                if g["type"] in ("Polygon", "MultiPolygon"):
                    lineas = [anillo for poli in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]) for anillo in poli]
                else:
                    lineas = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
                for linea in lineas:
                    for x, y in rdp([(q[0], q[1]) for q in linea], 0.003):
                        if any(dentro(x, y, p) for p in u["poligonos"]):
                            dentro_.append((round(y, 3), round(x, 3), dist_borde(x, y, u["poligonos"])))
    pts = []
    for margen in (0.05, 0.03, 0.015, 0):  # el margen más amplio que deje al menos tres puntos
        pts = sorted({(la, lo) for la, lo, d in dentro_ if d >= margen})
        if len(pts) >= 3:
            break
    return pts[::max(1, len(pts) // n)][:n]


def salida_por_cauce(codigo, candidatos, cache):
    """Celda de GloFAS con más caudal medio en 14 días entre los candidatos. Las cuencas sin cauce con nombre o sin
    caudal (endorreicas o fuera de la red de GloFAS) se anotan para no volver a buscarlas."""
    if not candidatos:
        cache[codigo] = "sin"
        return None, 0
    d = bajar(f"{FLOOD}?latitude={','.join(str(p[0]) for p in candidatos)}&longitude={','.join(str(p[1]) for p in candidatos)}"
              "&daily=river_discharge&past_days=13&forecast_days=1")
    d = d if isinstance(d, list) else [d]
    mejor, media_mejor = None, 0
    for (la, lo), x in zip(candidatos, d):
        v = [q for q in x["daily"]["river_discharge"] if q is not None]
        media = sum(v) / len(v) if v else 0
        if media > media_mejor:
            mejor, media_mejor = [la, lo], media
    cache[codigo] = mejor if mejor and media_mejor >= 0.1 else "sin"  # casi sin caudal: fuera de la red de GloFAS
    return (mejor if cache[codigo] != "sin" else None), media_mejor


def rios_peru():
    t0 = time.time()
    unidades = unidades_peru()
    norte = {c["codigo"] for c in (_CACHE.get("cuencas") or {}).get("cuencas", []) if c.get("salida")}
    ruta_s = DATOS / "salidas.json"
    salidas = json.loads(ruta_s.read_text(encoding="utf-8")) if ruta_s.exists() else {}
    ruta_h = DATOS / "historias.json"
    nuevas_s = nuevas_h = 0
    rios = []
    for u in unidades:
        if u["codigo"] in norte:
            continue
        s = salidas.get(u["codigo"])
        if s is None and nuevas_s < RIOS_PE_SALIDAS and time.time() - t0 < RIOS_PE_SEGUNDOS:
            try:
                s, media = salida_por_cauce(u["codigo"], candidatos_cauce(u), salidas)
                nuevas_s += 1
                print(f"    {u['n']}: punto de control {s} ({media:.1f} m³/s de media)", flush=True)
                ruta_s.write_text(json.dumps(salidas), encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                print(f"    {u['n']}: sin punto de control ({str(e)[:90]})", flush=True)
                s = None
        if not s or s == "sin":
            continue
        rio = {k: u[k] for k in ("codigo", "n", "tipo", "vertiente", "km2")}
        rio["salida"] = s
        cache_h = json.loads(ruta_h.read_text(encoding="utf-8")) if ruta_h.exists() else {}
        if f"{s[0]},{s[1]}" in cache_h:
            rio["historia"] = historia_caudal(*s, desde="2005-01-01")
        elif nuevas_h < RIOS_PE_HISTORIAS and time.time() - t0 < RIOS_PE_SEGUNDOS:
            try:
                rio["historia"] = historia_caudal(*s, desde="2005-01-01")
                nuevas_h += 1
            except Exception as e:  # noqa: BLE001
                print(f"    {u['n']}: sin historia ({str(e)[:90]})", flush=True)
        rios.append(rio)
    # pronóstico de todos los puntos en lotes: una consulta por cada 40 ríos
    claves = ["river_discharge", "river_discharge_median", "river_discharge_p25", "river_discharge_p75", "river_discharge_max"]
    for i in range(0, len(rios), 40):
        lote = rios[i:i + 40]
        try:
            d = bajar(f"{FLOOD}?latitude={','.join(str(x['salida'][0]) for x in lote)}&longitude={','.join(str(x['salida'][1]) for x in lote)}"
                      f"&daily={','.join(claves)}&past_days=10&forecast_days=30")
            d = d if isinstance(d, list) else [d]
            for x, r_ in zip(lote, d):
                y = r_["daily"]
                x["caudal"] = [[t] + [None if y[k][j] is None else round(y[k][j], 1) for k in claves] for j, t in enumerate(y["time"])]
        except Exception as e:  # noqa: BLE001
            print(f"    pronóstico de ríos {i}-{i + len(lote)}: {str(e)[:90]}", flush=True)
    faltan_s = sum(1 for u in unidades if u["codigo"] not in norte and salidas.get(u["codigo"]) is None)
    print(f"    {len(rios)} ríos con punto de control · {sum(1 for x in rios if x.get('historia'))} con historia · "
          f"{faltan_s} cuencas por buscar", flush=True)
    return {"rios": rios, "unidades": len([u for u in unidades if u["codigo"] not in norte]), "por_buscar": faltan_s,
            "fuente": "ANA (unidades hidrográficas, GeoServer del SENAMHI) y GloFAS v4 de Copernicus vía Open-Meteo"}


def mundo_gdacs():
    """Desastres activos en el mundo según GDACS (ONU y Comisión Europea): inundaciones, ciclones y sequías de nivel
    naranja o rojo de las últimas tres semanas."""
    desde = (dt.date.today() - dt.timedelta(days=21)).isoformat()
    d = bajar(f"https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=FL;TC;DR&fromDate={desde}")
    return [resumir_gdacs(f) for f in d.get("features", []) if f["properties"].get("todate", "")[:10] >= desde]


def resumir_gdacs(f):
    p = f["properties"]
    lng, lat = f["geometry"]["coordinates"][:2]
    return {"tipo": p["eventtype"], "nivel": p["alertlevel"], "n": p["name"], "paises": p.get("country", ""), "desde": p["fromdate"][:10],
            "hasta": p["todate"][:10], "actual": bool(p.get("iscurrent")), "lat": round(lat, 3), "lng": round(lng, 3),
            "detalle": (p.get("severitydata") or {}).get("severitytext", ""), "url": (p.get("url") or {}).get("report", "")}


def lluvia_cuenca(polis):
    """Lluvia diaria media sobre la cuenca (ECMWF 9 km) en 7 días, con unos 25 puntos repartidos."""
    xs = [x for p in polis for r in p for x in r[0::2]]
    ys = [y for p in polis for r in p for y in r[1::2]]
    pts, n = [], 6
    for i in range(n):
        for j in range(n):
            x = min(xs) + (i + 0.5) * (max(xs) - min(xs)) / n
            y = min(ys) + (j + 0.5) * (max(ys) - min(ys)) / n
            if any(dentro(x, y, p) for p in polis):
                pts.append((round(y, 3), round(x, 3)))
    if not pts:
        return []
    d = bajar("https://api.open-meteo.com/v1/forecast?latitude=" + ",".join(str(p[0]) for p in pts) +
              "&longitude=" + ",".join(str(p[1]) for p in pts) + "&daily=precipitation_sum&models=ecmwf_ifs&timezone=America/Lima&forecast_days=7")
    d = d if isinstance(d, list) else [d]
    tiempos = d[0]["daily"]["time"]
    return [[t, round(sum((r["daily"]["precipitation_sum"][i] or 0) for r in d) / len(d), 1)] for i, t in enumerate(tiempos)]


def cuencas_norte():
    lo0, la0, lo1, la1 = CAJA_NORTE
    capa = wfs_senamhi("g_carto_fundamento", "cuencas", f"&BBOX={la0},{lo0},{la1},{lo1},urn:ogc:def:crs:EPSG::4326")  # WFS 2.0: latitud primero
    salida = []
    for f in capa["features"]:
        p = f["properties"]
        if p.get("orden") == 999 or not p.get("nombre", "").startswith("Cuenca"):
            continue
        polis = poligonos_simples(f["geometry"], eps=0.003, area_min=0.0005)
        if not polis:
            continue
        salida.append({"codigo": p["codigo"], "n": p["nombre"].replace("Cuenca ", ""), "vertiente": "Pacífico" if p.get("nivel1") == "1" else "Amazonas",
                       "km2": round(sum(area_km2(poli[0]) for poli in polis)), "poligonos": polis})
    rios = rios_norte(salida)
    _CACHE["rios"] = rios
    for i, cuenca in enumerate(salida):
        if cuenca["vertiente"] != "Pacífico":  # se calculan las que bajan a la costa de Tumbes, Piura y Lambayeque
            continue
        candidatos = [(round(r[3][k + 1], 3), round(r[3][k], 3)) for r in rios if r[2] == i and r[1] == 1 for k in range(0, len(r[3]), 2)]
        try:  # si Open-Meteo frena una cuenca, las demás siguen
            punto = caudal_salida(cuenca["codigo"], candidatos)
            if punto:
                cuenca["salida"] = punto
                cuenca["historia"] = historia_caudal(*punto)
                cuenca["caudal"] = pronostico_caudal(*punto)
            cuenca["lluvia"] = lluvia_cuenca(cuenca["poligonos"])
        except Exception as e:  # noqa: BLE001
            print(f"    {cuenca['n']}: sin caudal ({str(e)[:90]})")
        time.sleep(1)
        print(f"    {cuenca['n']}: {cuenca['km2']} km², salida {cuenca.get('salida')}")
    return {"cuencas": salida, "fuente": "SENAMHI/ANA (unidades hidrográficas), GloFAS v4 de Copernicus vía Open-Meteo"}


def rios_norte(cuencas):
    lo0, la0, lo1, la1 = CAJA_NORTE
    capa = wfs_senamhi("g_carto_fundamento", "rios_linea_ign", f"&BBOX={la0},{lo0},{la1},{lo1},urn:ogc:def:crs:EPSG::4326&propertyName=nombre,rasgo_prin,rasgo_secu,geom")
    rios = []
    for f in capa["features"]:
        p, g = f["properties"], f.get("geometry")
        if not g:
            continue
        tipo = (p.get("rasgo_prin") or "").lower()
        if not (tipo.startswith("rio") or tipo.startswith("brazo") or (p.get("nombre") and tipo == "quebrada")):
            continue
        lineas = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
        for linea in lineas:
            pts = rdp([(q[0], q[1]) for q in linea], 0.0004)
            if len(pts) < 2:
                continue
            mx, my = pts[len(pts) // 2]
            c = next((i for i, cu in enumerate(cuencas) if any(dentro(mx, my, poli) for poli in cu["poligonos"])), -1)
            rios.append([p.get("nombre") or "", 1 if tipo.startswith("rio") else 0, c, [round(v, 4) for q in pts for v in q]])
    # los ríos anchos (Piura, Chira, Tumbes…) el IGN los dibuja como polígono en vez de línea: se toman sus márgenes
    area = wfs_senamhi("g_carto_fundamento", "rios_area_ign", f"&BBOX={la0},{lo0},{la1},{lo1},urn:ogc:def:crs:EPSG::4326&propertyName=nombre,geom")
    for f in area["features"]:
        g = f.get("geometry")
        if not g:
            continue
        for poli in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            for anillo in poli:
                pts = rdp([(q[0], q[1]) for q in anillo], 0.00015)
                if len(pts) < 3:
                    continue
                mx, my = pts[len(pts) // 2]
                c = next((i for i, cu in enumerate(cuencas) if any(dentro(mx, my, pl) for pl in cu["poligonos"])), -1)
                rios.append([f["properties"].get("nombre") or "", 1, c, [round(v, 4) for q in pts for v in q]])
    return rios


def imagen_zona():
    """Imagen Sentinel-2 sin nubes (EOX, 2024) de la zona norte, para el acercamiento."""
    lo0, la0, lo1, la1 = CAJA_IMAGEN
    alto = 3600
    ancho = round(alto * (lo1 - lo0) / (la1 - la0) * math.cos(math.radians((la0 + la1) / 2)) / math.cos(math.radians((la0 + la1) / 2)))
    img = bajar(f"https://tiles.maps.eox.at/wms?service=WMS&request=GetMap&version=1.1.1&layers=s2cloudless-2024&styles=&srs=EPSG:4326"
                f"&bbox={lo0},{la0},{lo1},{la1}&width={ancho}&height={alto}&format=image/jpeg", binario=True)
    if len(img) < 100000:
        raise RuntimeError("EOX devolvió una imagen vacía")
    (DATOS / "zona-s2.jpg").write_bytes(img)
    return {"archivo": "datos/zona-s2.jpg", "caja": CAJA_IMAGEN, "atribucion": "Sentinel-2 cloudless 2024 de EOX IT Services (contiene datos Copernicus Sentinel modificados), CC BY-NC-SA 4.0"}


# ---------- emergencias reportadas por el COEN-INDECI ----------

INDECI_FEED = "https://portal.indeci.gob.pe/emergencias/feed/"
PELIGROS_NINO = re.compile(r"LLUVIA|INUNDACI|HUAICO|DESLIZAMIENTO|DESBORDE|EROSI[OÓ]N|ANIEGO|TORMENTA|PRECIPITACI|DETRITOS|DERRUMBE", re.I)
NUMEROS = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10}
DANOS = {"fallecidos": r"fallecid", "desaparecidos": r"desaparecid", "heridos": r"herid", "damnificados": r"damnificad", "afectados": r"afectad"}


def cifras_danos(texto):
    """Cifras de personas por tipo de daño cuando el COEN las escribe en el texto: «dos (02) personas fallecidas».
    Las tablas de daños no se leen: al pasar el PDF a texto sus columnas se mezclan y las cifras quedarían cruzadas."""
    t = re.sub(r"\s+", " ", texto)
    res = {}
    for clave, raiz in DANOS.items():
        valores = []
        for m in re.finditer(rf"(?:\((\d+)\)|(\d+)|\b({'|'.join(NUMEROS)})\b)\s*(?:\(\d+\)\s*)?personas?\s+{raiz}", t, re.I):
            valores.append(int(m.group(1) or m.group(2) or NUMEROS[m.group(3).lower()]))
        if valores:
            res[clave] = max(valores)
    return res


def leer_reporte_indeci(enlace, cache):
    if enlace in cache and "victimas" in cache[enlace]:
        return cache[enlace]
    import io
    import pypdf
    pagina = bajar(enlace, texto=True)
    pdf = re.search(r"""href=["'](https://portal\.indeci\.gob\.pe/wp-content/uploads/[^"']+?\.pdf)["']""", pagina, re.I)
    info = {"pdf": urllib.parse.quote(html.unescape(pdf.group(1)), safe=":/%") if pdf else None}
    if pdf:
        datos = bajar(info["pdf"], binario=True)
        texto = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(datos)).pages)
        plano = re.sub(r"\s+", " ", texto)
        hechos = re.search(r"HECHOS:?(.*?)(?:2\.\s*UBICACI|UBICACI)", plano, re.I)
        evaluacion = re.search(r"EVALUACI[OÓ]N DE DA[ÑN]OS:?(.*?)(?:Nota:|Fuente:|3\.2|4\.\s)", plano, re.I)
        info.update({
            "hechos": hechos.group(1).strip()[:900] if hechos else "",
            "danos": evaluacion.group(1).strip()[:900] if evaluacion else "",
            "sin_victimas": bool(re.search(r"no se reportaron da[ñn]os a la vida y (la )?salud", plano, re.I)),
            "cifras": cifras_danos(plano),
            # el COEN solo pone en la tabla las columnas con datos: si aparece FALLECIDO es que hubo fallecidos (la cifra se lee en el PDF)
            "victimas": sorted({v for v, raiz in (("fallecidos", "FALLECID"), ("desaparecidos", "DESAPARECID"), ("heridos", "LESIONAD|HERID"))
                                if re.search(raiz, (evaluacion.group(1) if evaluacion else ""), re.I)}),
            # frases sobre víctimas, para leerlas tal cual (las cifras de tabla no son fiables al extraerlas)
            "citas": [m.group(0).strip()[:220] for m in re.finditer(r"[^.•]*\b(fallecid|desaparecid|herid|sin vida)\w*[^.•]*", plano, re.I)
                      if not re.search(r"no se reportaron|DAÑOS MATERIALES|UBICACI", m.group(0), re.I)][:4],
        })
    cache[enlace] = info
    time.sleep(0.5)
    return info


def distritos_emergencia(r, zona):
    """Distritos de la zona donde ocurrió la emergencia. Primero el lugar del título (el distrito, o todos los de la
    provincia); si el título nombra un centro poblado o una región, el «distrito de X» que citan los hechos.
    No basta con que los hechos nombren un distrito: a veces es el de una carretera o el de un pueblo vecino."""
    deps = [d for d in zona if d["dep"] == r["dep"]]
    lugar = sin_tildes(r["lugar"])
    if r["ambito"].startswith("provincia"):
        return [d["id"] for d in deps if sin_tildes(d["prov"]) == lugar]
    if r["ambito"].startswith("distrito"):
        ids = [d["id"] for d in deps if re.search(rf"\b{re.escape(sin_tildes(d['n']))}\b", lugar)]
        if ids:
            return ids
    hechos = sin_tildes(r.get("hechos", ""))
    citados = re.findall(r"DISTRITOS? (?:Y PROVINCIA )?DE ([A-ZÑ ]+?)(?=,|\.| PROVINCIA| Y | EN |$)", hechos)
    return [d["id"] for d in deps if sin_tildes(d["n"]) in {c.strip() for c in citados}]


def emergencias_indeci(dias=30):
    """Emergencias por lluvias, inundaciones y huaicos en la zona norte, según los reportes del COEN-INDECI."""
    import email.utils
    deps = set(DEP_NORTE.values())
    limite = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=dias)
    grupos = {}
    for pagina in range(1, 150):
        xml = bajar(INDECI_FEED + (f"?paged={pagina}" if pagina > 1 else ""), texto=True)
        items = re.findall(r"<item>(.*?)</item>", xml, re.S)
        if not items:
            break
        viejos = 0
        for it in items:
            titulo = re.sub(r"\s+", " ", html.unescape(re.search(r"<title>(.*?)</title>", it, re.S).group(1))).strip()
            fecha = email.utils.parsedate_to_datetime(re.search(r"<pubDate>(.*?)</pubDate>", it).group(1))
            if fecha < limite:
                viejos += 1
                continue
            cola = titulo.rsplit(")", 1)[-1].strip()
            partes = re.split(r"\s+[–-]\s+", cola)
            if len(partes) < 2:
                continue
            dep = sin_tildes(partes[-1])
            m = re.match(r"(.*?)\s+EN\s+(?:EL|LA|LOS|LAS)\s+(DISTRITOS?|PROVINCIAS?|DEPARTAMENTO|REGI[OÓ]N|CENTRO POBLADO)\s+DE\s+(.*)$", " - ".join(partes[:-1]), re.I)
            if dep not in deps or not m or not PELIGROS_NINO.search(m.group(1)):
                continue
            tipo = re.search(r"(REPORTE COMPLEMENTARIO|REPORTE PRELIMINAR|INFORME DE EMERGENCIA)\s*N\.?\s*[°º]?\s*(\d+)", titulo, re.I)
            clave = (sin_tildes(m.group(1)), sin_tildes(m.group(3)), dep)
            registro = {"evento": m.group(1).strip().capitalize(), "ambito": m.group(2).lower(), "lugar": m.group(3).strip(), "dep": dep,
                        "fecha": fecha.isoformat(), "titulo": titulo, "reporte": f"{tipo.group(1).capitalize()} N° {tipo.group(2)}" if tipo else "",
                        "enlace": re.search(r"<link>(.*?)</link>", it).group(1).strip()}
            if clave not in grupos or registro["fecha"] > grupos[clave]["fecha"]:
                grupos[clave] = registro
        if viejos == len(items):
            break
        time.sleep(0.4)
    cache_ruta = DATOS / "indeci_cache.json"
    cache = json.loads(cache_ruta.read_text(encoding="utf-8")) if cache_ruta.exists() else {}
    zona = _CACHE.get("zona", {}).get("distritos", [])
    lista = sorted(grupos.values(), key=lambda r: r["fecha"], reverse=True)[:90]
    for r in lista:
        try:
            r.update(leer_reporte_indeci(r["enlace"], cache))
        except Exception as e:  # noqa: BLE001 - el reporte queda con su título y enlace
            r["error"] = str(e)[:120]
        r["distritos"] = distritos_emergencia(r, zona)
    cache_ruta.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return {"dias": dias, "emergencias": lista, "fuente": INDECI_FEED}


def fronteras():
    """Convierte el TopoJSON de Natural Earth (110m) en líneas lng/lat sin repetir arcos."""
    topo = json.loads((DATOS / "countries-110m.json").read_text(encoding="utf-8"))
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    lineas = []
    for arco in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arco:
            x += dx
            y += dy
            pts += [round(x * sx + tx, 2), round(y * sy + ty, 2)]
        lineas.append(pts)
    return lineas


# Fuentes que solo responden desde el Perú: las baja la PC del usuario (--peru) y las sube a la rama datos-peru;
# GitHub Actions las lee de ahí (datos/peru.json) y no intenta bajarlas (VIGIA_SALTAR).
FUENTES_PERU = ("avisos", "quebradas", "enfen")
PERU_JSON = DATOS / "peru.json"


def fusionar_peru(viejo):
    """Usa los datos de datos/peru.json cuando son más nuevos que los de la instantánea anterior."""
    if not PERU_JSON.exists():
        return
    try:
        peru = json.loads(PERU_JSON.read_text(encoding="utf-8"))
    except ValueError:
        return
    viejo.setdefault("estado", {})
    for clave, v in peru.get("fuentes", {}).items():
        if v.get("estado") and v["estado"] > (viejo["estado"].get(clave) or ""):
            viejo[clave] = v["datos"]
            viejo["estado"][clave] = v["estado"]
            print(f"  {clave:10s} desde la PC ({v['estado']})", flush=True)


def main():
    """Sin argumentos baja todas las fuentes; con nombres (p. ej. «cuencas emergencias») solo esas y conserva el resto.
    Con --peru además escribe datos/peru.json con las fuentes que solo responden desde el Perú."""
    DATOS.mkdir(exist_ok=True)
    args = sys.argv[1:]
    modo_peru = "--peru" in args
    solo = {a for a in args if not a.startswith("--")} - set(os.environ.get("VIGIA_SALTAR", "").split())
    if args and not solo:
        solo = {"ninguna"}  # todo lo pedido se salta: solo se fusiona lo que llegó de la PC
    fuentes = {
        "oni": oni, "nino": nino_semanal,
        "clima": clima_lugares, "enfen": enfen_ultimo,
        "ecmwf": lluvia_ecmwf, "imerg": lluvia_satelite, "avisos": avisos_senamhi,
        "quebradas": quebradas_senamhi, "conjunto": probabilidad_lluvia,
        "zona": zona_norte, "aerodromos": aerodromos, "termica": termica, "rayos": rayos,
        "emergencias": emergencias_indeci, "cuencas": cuencas_norte, "imagen_zona": imagen_zona,
        "multimodelo": multimodelo, "rios_ec": rios_ecuador, "ensamble": ensamble_rios, "mundo": mundo_gdacs, "oceano": oceano,
        "rios_pe": rios_peru,
    }
    datos = {"generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "estado": {}}
    previo = DATOS / "instantanea.js"
    viejo = {}
    if previo.exists():
        try:
            viejo = json.loads(previo.read_text(encoding="utf-8").split("=", 1)[1].rstrip().rstrip(";"))
        except (ValueError, IndexError):
            viejo = {}
    if not modo_peru:
        fusionar_peru(viejo)
    saltar = set(os.environ.get("VIGIA_SALTAR", "").split())
    for clave, fn in fuentes.items():
        if not solo and clave in saltar:  # corrida completa en GitHub: estas fuentes llegan desde la PC
            if clave in viejo:
                datos[clave] = viejo[clave]
                datos["estado"][clave] = viejo.get("estado", {}).get(clave)
                _CACHE[clave] = viejo[clave]
            continue
        if solo and clave not in solo:
            if clave in viejo:
                datos[clave] = viejo[clave]
                datos["estado"][clave] = viejo.get("estado", {}).get(clave)
                _CACHE[clave] = viejo[clave]
            continue
        t0 = time.time()
        try:
            datos[clave] = fn()
            datos["estado"][clave] = datos["generado"]
            n = len(datos[clave]) if isinstance(datos[clave], list) else "ok"
            print(f"  {clave:10s} {n} ({time.time() - t0:.0f} s)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  {clave:10s} FALLÓ en {time.time() - t0:.0f} s: {e}", flush=True)
            if clave in viejo:  # se conserva el dato anterior y su fecha
                datos[clave] = viejo[clave]
                datos["estado"][clave] = viejo.get("estado", {}).get(clave)
        if clave in datos:
            _CACHE[clave] = datos[clave]
    if "enfen" in datos:
        ult = datos["enfen"].get("ultimo_publicado", {}).get("numero")
        if ult and ult != ENFEN_RESUMEN["numero"]:
            print(f"  AVISO: ENFEN publicó el comunicado {ult}; actualiza ENFEN_RESUMEN.")
    js = "window.VIGIA_INSTANTANEA = " + json.dumps(datos, ensure_ascii=False, separators=(",", ":")) + ";\n"
    previo.write_text(js, encoding="utf-8")
    if modo_peru:
        fuentes_ok = {k: {"datos": datos[k], "estado": datos["estado"].get(k)} for k in FUENTES_PERU if k in datos and datos["estado"].get(k)}
        PERU_JSON.write_text(json.dumps({"generado": datos["generado"], "fuentes": fuentes_ok}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"  peru.json  {', '.join(fuentes_ok)}", flush=True)
    try:  # los ríos van en un archivo aparte: son muchos puntos y cambian poco
        if solo and "cuencas" not in solo:
            print("  rios       sin cambios (se conservan los de la corrida anterior)")
            raise StopIteration
        rios = _CACHE.get("rios") or rios_norte(datos.get("cuencas", {}).get("cuencas", []))
        rios = [r for r in rios if r[2] >= 0 and r[0]]  # solo ríos con nombre dentro de las cuencas: lo demás no aporta
        (DATOS / "rios.js").write_text("window.VIGIA_RIOS = " + json.dumps(rios, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
        print(f"  rios       {len(rios)}")
    except StopIteration:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"  rios       FALLÓ: {e}")
    (DATOS / "fronteras.js").write_text(
        "window.VIGIA_FRONTERAS = " + json.dumps(fronteras(), separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Listo: {previo} ({len(js) // 1024} KB)")


if __name__ == "__main__":
    sys.exit(main())
