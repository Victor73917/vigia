"""Prueba automática de navegación de VIGÍA en un Chromium sin ventana.

Abre la página armada (por defecto publicar/ servida en http://127.0.0.1:8765/) con ?prueba y comprueba:
- que la vista inicial muestre todo el Perú;
- que cada departamento, provincia, distrito y centro poblado de la lista quede entero dentro del área libre del mapa
  y que la dirección cambie a su UBIGEO;
- que la búsqueda tolere errores de escritura y nombres alternativos;
- que un UBIGEO inexistente avise en vez de fallar en silencio.

Termina con código 1 si algo falla, para que GitHub Actions no publique.
Uso: python pruebas/navegacion.py [url]
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/").rstrip("/") + "/"
PERU = [-81.4, -18.4, -68.6, -0.1]
# casos de cobertura en todas las regiones (no indican que estén afectados)
CASOS = [
    ("departamento", "piura"), ("departamento", "tumbes"), ("departamento", "lambayeque"), ("departamento", "la libertad"),
    ("departamento", "ancash"), ("departamento", "lima"), ("departamento", "ica"), ("departamento", "arequipa"),
    ("departamento", "cajamarca"), ("departamento", "amazonas"), ("departamento", "san martin"), ("departamento", "loreto"),
    ("departamento", "ucayali"), ("departamento", "cusco"), ("departamento", "puno"), ("departamento", "callao"),
    ("departamento", "madre de dios"), ("provincia", "chiclayo"), ("provincia", "maynas"), ("provincia", "huancayo"),
    ("distrito", "la union"), ("distrito", "iquitos"), ("distrito", "juliaca"), ("distrito", "nasca"),
    ("distrito", "tarapoto"), ("distrito", "yarinacocha"), ("distrito", "chachapoyas"),
]
# lo escrito y el nombre que debe aparecer entre las opciones
ESCRITURA = [("lambayeke", "Lambayeque"), ("arekipa", "Arequipa"), ("huancaio", "Huancayo"), ("cuzco", "Cusco"),
             ("nazca", "Nasca"), ("chiclallo", "Chiclayo"), ("moyobanba", "Moyobamba")]

ESPERA_JS = """async () => {
  const G = VIGIA_PRUEBA.G;
  await new Promise(r => setTimeout(r, 300));
  for (let i = 0; i < 60 && G.estadoCamara().volando; i++) await new Promise(r => setTimeout(r, 250));
  await new Promise(r => setTimeout(r, 250));
}"""
CAJA_JS = """o => { if (o.caja) return o.caja; const a = [180, 90, -180, -90];
  for (const d of (o.poligonos ? [o] : (o.distritos || []))) for (const p of d.poligonos || []) for (const an of p)
    for (let i = 0; i < an.length; i += 2) { a[0] = Math.min(a[0], an[i]); a[2] = Math.max(a[2], an[i]); a[1] = Math.min(a[1], an[i + 1]); a[3] = Math.max(a[3], an[i + 1]); }
  return a; }"""


def esperar_mapa(pagina):
    pagina.wait_for_function("window.VIGIA_PRUEBA && VIGIA_PRUEBA.G", timeout=90_000)
    pagina.evaluate("VIGIA_PRUEBA.cargarTerritorio()")
    pagina.wait_for_timeout(3500)


def main():
    fallas, filas = [], []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pagina = nav.new_page(viewport={"width": 1366, "height": 800})
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        pagina.goto(URL + "?prueba", wait_until="domcontentloaded")
        esperar_mapa(pagina)
        motor = pagina.evaluate("document.querySelector('#mapa') && !document.querySelector('#mapa').hidden ? 'MapLibre' : 'globo'")
        filas.append(f"motor del mapa: {motor}")

        r = pagina.evaluate(f"VIGIA_PRUEBA.G.cajaEnPantalla({json.dumps(PERU)})")
        filas.append(f"vista inicial Perú: {r}")
        if not r["dentro"]:
            fallas.append("la vista inicial no muestra todo el Perú")

        for tipo, clave in CASOS:
            res = pagina.evaluate(f"""async () => {{
              const P = VIGIA_PRUEBA, e = P.indice().find(x => x.tipo === {json.dumps(tipo)} && x.clave === {json.dumps(clave)});
              if (!e) return {{ falta: true }};
              P.consultar(e.obj.n, e);
              await ({ESPERA_JS})();
              return {{ ...P.G.cajaEnPantalla(({CAJA_JS})(e.obj)), id: e.obj.id, url: location.search }};
            }}""")
            filas.append(f"{tipo} {clave}: {res}")
            if res.get("falta"):
                fallas.append(f"{tipo} {clave}: no está en el índice")
            elif not res["dentro"]:
                fallas.append(f"{tipo} {clave}: queda fuera del área libre del mapa")
            elif f"lugar={res['id']}" not in res["url"]:
                fallas.append(f"{tipo} {clave}: la dirección no tiene su UBIGEO {res['id']}")

        cc = pagina.evaluate("async () => (await VIGIA_PRUEBA.buscarCcpp('Pedregal, Piura')).map(e => e.obj.dist)")
        filas.append(f"centro poblado «Pedregal, Piura»: {cc[:3]}")
        if not cc:
            fallas.append("no encuentra el centro poblado Pedregal (Piura)")

        for q, esperado in ESCRITURA:
            ops = pagina.evaluate(f"""async () => {{
              VIGIA_PRUEBA.consultar({json.dumps(q)}); await new Promise(r => setTimeout(r, 1200));
              return [...document.querySelectorAll('#respuesta:not([hidden]) [data-opcion] b')].map(b => b.textContent);
            }}""")
            filas.append(f"«{q}» → {ops[:3]}")
            if esperado not in ops:
                fallas.append(f"«{q}» no ofrece {esperado}")

        pagina.goto(URL + "?prueba&lugar=999999", wait_until="domcontentloaded")
        esperar_mapa(pagina)
        aviso = pagina.evaluate("[...document.querySelectorAll('.aviso-toast')].map(t => t.textContent).join(' ')")
        filas.append(f"UBIGEO 999999: {aviso[:90]}")
        if "999999" not in aviso:
            fallas.append("un UBIGEO inexistente no avisa")

        if errores:
            fallas.append("errores de JavaScript: " + " | ".join(errores[:3]))
        nav.close()

    print("\n".join(filas))
    print(f"\n{len(fallas)} fallas" + (":\n- " + "\n- ".join(fallas) if fallas else ""))
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
