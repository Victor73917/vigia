"""Bibliotecas de terceros que VIGÍA sirve desde su propio sitio (hallazgo H-05 de la auditoría 4).

Antes se cargaban desde jsDelivr: si esa CDN entregaba un archivo alterado, la página lo ejecutaba. Ahora se guardan
en lib/ con versión fija y la huella SHA-256 del archivo original queda escrita aquí abajo.

  py librerias.py            comprueba que los archivos de lib/ son los originales (más el cambio de abajo)
  py librerias.py --bajar    los vuelve a bajar de jsDelivr, verifica la huella y los guarda en lib/

Único cambio: los complementos de three.js importan 'three' (nombre de paquete) y el navegador no sabe resolverlo
sin un mapa de importación; se reescribe a './three.module.js', que está en la misma carpeta.
Para cambiar de versión: actualizar la dirección y la huella, correr con --bajar y probar el sitio de pruebas.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

LIB = Path(__file__).resolve().parent / "lib"
CDN = "https://cdn.jsdelivr.net/npm/"
# destino en lib/: (origen en npm, huella SHA-256 del original)
ARCHIVOS = {
    "maplibre-gl@6.14.0/maplibre-gl.mjs": ("maplibre-gl@6.14.0/dist/maplibre-gl.mjs", "244d36122c1398da3a8259817cc6d71e04321afe6404f32606b4b6c6cc4f26fb"),
    "maplibre-gl@6.14.0/maplibre-gl-worker.mjs": ("maplibre-gl@6.14.0/dist/maplibre-gl-worker.mjs", "5f1e2f0e1624082b7e88a06e4c86085992b0f8c02929801e552f3f7a119856a9"),
    "maplibre-gl@6.14.0/maplibre-gl.css": ("maplibre-gl@6.14.0/dist/maplibre-gl.css", "bacba6a85a867fcf602f2ff88331b8acf7edf3fbd063a519888cfbff39970193"),
    "three@0.185.1/three.module.js": ("three@0.185.1/build/three.module.js", "bbf5ed13fe4373f5bd38b14ea8e62e9f157327da5638edc6d3863e08b167c9c7"),
    "three@0.185.1/three.core.js": ("three@0.185.1/build/three.core.js", "3718df126d69c125362a03340913204470d8c50238605150e57f808840fb7759"),
    "three@0.185.1/OrbitControls.js": ("three@0.185.1/examples/jsm/controls/OrbitControls.js", "faabb4e8dfd9235ee4a9fd7c9a3d75f90f1689dbd4944bd6fd32117dacec5f93"),
    "three@0.185.1/LineSegments2.js": ("three@0.185.1/examples/jsm/lines/LineSegments2.js", "fcbc20f576e88343cea12131f49b7003d7ab44ede422fcb694e567456022f7a0"),
    "three@0.185.1/LineSegmentsGeometry.js": ("three@0.185.1/examples/jsm/lines/LineSegmentsGeometry.js", "471f0a954a0c9c59d3d151392f424142a9164a722802f63b371971378a84a1b1"),
    "three@0.185.1/LineMaterial.js": ("three@0.185.1/examples/jsm/lines/LineMaterial.js", "d4517001f9d7b3e885ea5baa930de0077351e885db52ef4565cde4c7dd17eb23"),
    "supabase-js@2.45.4/supabase.js": ("@supabase/supabase-js@2.45.4/dist/umd/supabase.js", "8596965fe918e656600a1b568d3a168f5c0d3d22a600886bb6f44a6555db01e7"),
}
COMPLEMENTOS = ("OrbitControls.js", "LineSegments2.js", "LineSegmentsGeometry.js", "LineMaterial.js")


def ajustar(destino, crudo):
    if destino.endswith(COMPLEMENTOS):
        texto = crudo.decode("utf-8")
        assert "from 'three';" in texto, destino
        crudo = texto.replace("from 'three';", "from './three.module.js';").encode("utf-8")
    return crudo


def original(destino, guardado):
    """Deshace el único cambio para comparar la huella con la del archivo publicado en npm."""
    if destino.endswith(COMPLEMENTOS):
        return guardado.decode("utf-8").replace("from './three.module.js';", "from 'three';").encode("utf-8")
    return guardado


def main():
    bajar = "--bajar" in sys.argv
    malos = 0
    for destino, (origen, huella) in ARCHIVOS.items():
        ruta = LIB / destino
        if bajar:
            req = urllib.request.Request(CDN + origen, headers={"User-Agent": "VIGIA-librerias"})
            with urllib.request.urlopen(req, timeout=60) as r:
                crudo = r.read()
            h = hashlib.sha256(crudo).hexdigest()
            if huella and h != huella:
                print(f"DISTINTO  {destino}: jsDelivr entregó {h}, se esperaba {huella}. No se guarda.")
                malos += 1
                continue
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(ajustar(destino, crudo))
            print(f"bajado    {destino}  {h}")
        else:
            if not ruta.exists():
                print(f"FALTA     {destino}")
                malos += 1
                continue
            h = hashlib.sha256(original(destino, ruta.read_bytes())).hexdigest()
            ok = huella is None or h == huella
            malos += not ok
            print(f"{'ok' if ok else 'DISTINTO':9s} {destino}  {h}")
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
