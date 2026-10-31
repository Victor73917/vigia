"""Índice territorial nacional del Perú para VIGÍA.

Baja del GeoServer del SENAMHI (capas de cartografía fundamental, fuente INEI) los departamentos,
provincias y distritos con su UBIGEO y su límite simplificado, y los centros poblados con su punto.
Escribe datos/territorio.json y datos/ccpp.json. Los límites casi no cambian: basta correrlo de vez en cuando.

Uso: py -X utf8 territorio.py
"""
import json
import datetime as dt

from recolectar import DATOS, SENAMHI_GEO, bajar, poligonos_simples

ESPACIO = "g_carto_fundamento"
PAGINA = 20000


def capa(nombre, props=None, orden=None):
    """Todas las entidades de una capa, por páginas (el GeoServer corta las respuestas grandes)."""
    feats, inicio = [], 0
    while True:
        url = (f"{SENAMHI_GEO}/{ESPACIO}/ows?service=WFS&version=2.0.0&request=GetFeature&typeNames={ESPACIO}:{nombre}"
               f"&outputFormat=application/json&srsName=EPSG:4326&count={PAGINA}&startIndex={inicio}")
        if props:
            url += "&propertyName=" + ",".join(props)
        if orden:
            url += "&sortBy=" + orden
        lote = bajar(url)["features"]
        feats += lote
        print(f"  {nombre}: {len(feats)}", flush=True)
        if len(lote) < PAGINA:
            return feats
        inicio += PAGINA


def caja(polis):
    xs = [v for p in polis for r in p for v in r[0::2]]
    ys = [v for p in polis for r in p for v in r[1::2]]
    return [min(xs), min(ys), max(xs), max(ys)]


def centroide(polis):
    """Centroide del anillo exterior más grande (fórmula del área)."""
    r = max((p[0] for p in polis), key=len)
    xs, ys = r[0::2], r[1::2]
    a = cx = cy = 0.0
    for i in range(len(xs)):
        k = (i + 1) % len(xs)
        c = xs[i] * ys[k] - xs[k] * ys[i]
        a, cx, cy = a + c, cx + (xs[i] + xs[k]) * c, cy + (ys[i] + ys[k]) * c
    if abs(a) < 1e-12:
        return [round(sum(xs) / len(xs), 3), round(sum(ys) / len(ys), 3)]
    return [round(cx / (3 * a), 3), round(cy / (3 * a), 3)]


def territorios(nombre, campo_id, campo_n, eps):
    salida, gid = [], {}
    for f in capa(nombre):
        p = f["properties"]
        polis = poligonos_simples(f["geometry"], eps=eps, area_min=eps * eps)
        if not polis:  # territorio muy chico para esta tolerancia: se conserva con menos simplificación
            polis = poligonos_simples(f["geometry"], eps=eps / 4, area_min=0)
        if not polis:
            continue
        ubigeo = p[campo_id]
        gid[f["id"].split(".")[-1]] = ubigeo
        salida.append([ubigeo, p[campo_n], [round(v, 3) for v in caja(polis)], centroide(polis), polis])
    salida.sort(key=lambda t: t[0])
    return salida, gid


def main():
    hoy = dt.date.today().isoformat()
    deps, _ = territorios("departamentos", "iddpto", "departamento", 0.01)
    provs, _ = territorios("provincias", "idprov", "provincia", 0.006)
    dists, gid_dist = territorios("distritos", "iddist", "distrito", 0.003)
    datos = {"fuente": "INEI, vía GeoServer IDESEP del SENAMHI (g_carto_fundamento)", "fecha": hoy,
             "formato": "[UBIGEO, nombre, [lng0, lat0, lng1, lat1], [lng, lat], polígonos]",
             "departamentos": deps, "provincias": provs, "distritos": dists}
    (DATOS / "territorio.json").write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    ccpp = []
    for f in capa("centros_poblados", ["nom_poblado", "giddist", "geom"], "nom_poblado"):
        p, g = f["properties"], f.get("geometry")
        ubigeo = gid_dist.get(str(p.get("giddist")))
        if not g or not ubigeo or not p.get("nom_poblado"):
            continue
        x, y = g["coordinates"][:2]
        ccpp.append([p["nom_poblado"].strip(), round(x, 4), round(y, 4), ubigeo])
    ccpp.sort(key=lambda c: (c[0], c[3]))
    datos = {"fuente": "INEI, vía GeoServer IDESEP del SENAMHI (g_carto_fundamento:centros_poblados)", "fecha": hoy,
             "formato": "[nombre, lng, lat, UBIGEO del distrito]", "centros": ccpp}
    (DATOS / "ccpp.json").write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for n in ("territorio.json", "ccpp.json"):
        print(f"{n}: {(DATOS / n).stat().st_size // 1024} KB")
    print(f"{len(deps)} departamentos, {len(provs)} provincias, {len(dists)} distritos, {len(ccpp)} centros poblados")


if __name__ == "__main__":
    main()
