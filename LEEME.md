# VIGÍA · El Niño Costero en el norte del Perú

Un globo 3D con toda la información sobre los lugares que afecta El Niño Costero en la zona norte: Tumbes, Piura, Lambayeque, La Libertad y Cajamarca. Muestra las lluvias, las crecidas de los ríos, las emergencias reportadas y los distritos que conviene atender primero. Está pensado para apoyar las operaciones de auxilio.

- **Prioridad**: los 326 distritos ordenados por **prioridad de atención**. Es un criterio de VIGÍA, no oficial, que suma puntos y explica cada uno:
  - el aviso del SENAMHI para ese día (amarillo 1, naranja 2, rojo 3);
  - una emergencia reportada por el COEN-INDECI en los últimos 30 días (2, más 1 si el reporte menciona víctimas);
  - un río que atraviesa el distrito con crecida pronosticada en 7 días (1, o 2 si la crecida es fuerte o de récord);
  - más de mil personas expuestas a huaicos (1).

  Una prioridad alta es 4 puntos o más, media es 2 o 3, y "vigilar" es 1. La pestaña también trae la exposición ante huaicos (población, salud, colegios y vías), el METAR y TAF de los aeródromos y la imagen térmica de GOES-East.
- **Emergencias**: los reportes del COEN-INDECI por lluvias intensas, inundaciones, huaicos, deslizamientos y derrumbes en la zona.
  - Cada emergencia trae lo que pasó, su enlace al PDF y su ubicación en el globo.
  - Las cifras de fallecidos, desaparecidos o heridos solo se muestran cuando el texto del reporte las escribe. Si la tabla de daños las menciona sin cifra legible, se marca "ver reporte".
- **Ríos**: las cuencas de la ANA y la red de ríos del IGN, del GeoServer del SENAMHI, dibujadas en el globo.
  - Para cada río hay un hidrograma con el caudal de los últimos 10 días y el pronóstico a 30 días de GloFAS (Copernicus), con la mediana y el rango de sus escenarios.
  - Ese pronóstico se compara con la historia del propio río desde 1984: la crecida anual típica, la que llega una vez cada 10 años y el récord.
  - También lista los distritos por donde pasa el cauce principal.
- **Simulación de crecida**: "¿y si llueve más?". Suma al pronóstico la crecida que daría una lluvia extra de 24 horas sobre la cuenca, según el tipo de suelo y el día. Usa el hidrograma unitario triangular del SCS. Es una estimación aproximada, no un pronóstico oficial, y no considera represas.
- **Lluvia**: los avisos del SENAMHI con sus zonas por día, el aviso de activación de quebradas, el mapa de ECMWF, la probabilidad con 51 escenarios y la lluvia por satélite (NASA IMERG). Detalle en [`FUENTES-LLUVIA.md`](FUENTES-LLUVIA.md).
- **El Niño**: el estado oficial del ENFEN, la temperatura del mar en las regiones Niño, la comparación de 2026 con 1997, 2015 y 2023, y el índice ONI.
- **Lugar**: al tocar cualquier punto se ve su distrito, su prioridad, sus emergencias, su río y su cuenca, el pronóstico de 7 días y los avisos que lo cubren.
- **Acercamiento**: el globo se puede acercar hasta unos 10 km de altura.
  - La rueda del ratón o el pellizco acercan hacia el punto señalado, y el doble clic acerca de golpe.
  - El giro se vuelve más lento a medida que bajas, para que el terreno siga al dedo.
  - De cerca aparece la imagen satelital Sentinel-2 sin nubes (EOX). En la web se pide en el momento hasta unos 10 m por píxel.
  - Los ríos, las cuencas y los límites de distrito se dibujan como líneas nítidas.
- **Barra de consultas**: por ejemplo «río Piura», «emergencias en Tumbes», «¿dónde atender primero?», «lluvia mañana en Talara» o «SPUR».
- **Búsqueda y encuadre**: al elegir un distrito, una provincia o un departamento, el mapa encuadra su límite. Si un nombre se repite (por ejemplo «Piura», que es distrito, provincia y departamento), la página pregunta cuál.
  - El lugar elegido queda en la dirección como `?lugar=UBIGEO`: `?lugar=200110` abre La Unión (Piura).
  - El botón «Perú», o la tecla Inicio, vuelve a la vista nacional.
  - Cambiar de capa o de pestaña no mueve la cámara.
- **Mapa** (desde la fase 3): MapLibre GL JS con vista de globo.
  - Mapa base satelital, oscuro o topográfico.
  - Los íconos se agrupan al alejarse.
  - «Opacidad, fuentes y mapa base…» abre el gestor de capas, con la fuente, el tipo de dato y la antigüedad de cada capa.
  - El globo anterior (three.js) se usa dentro de Claude, sin WebGL2 o con `?motor=globo`.
- **Todo el Perú**: se pueden buscar los 1 873 distritos, las 196 provincias, los 25 departamentos y los 127 681 centros poblados del INEI.
  - Para un centro poblado, escribe el departamento o la provincia después de una coma: «Pedregal, Piura».
  - Los límites se renuevan con `py -X utf8 territorio.py`, que escribe `datos/territorio.json` y `datos/ccpp.json`.
- **Analista** (solo dentro de Claude): responde preguntas y redacta un informe de situación con los datos de la página.

VIGÍA no emite alertas. Las oficiales en el Perú son del ENFEN, el SENAMHI, el INDECI y la ANA.

## Alertas, escenarios y asesor

- **Alertas automáticas** (criterio de VIGÍA, no oficial): un río pasa a *alerta* (rojo en el globo) si GloFAS espera que pase su crecida de 2 años o si 30 % de sus 51 escenarios pasan la de 5 años; a *vigilancia* (naranja) si sube 20 % o más en 3 días o si 30 % de los escenarios pasan la de 2 años. Las crecidas de 2, 5 y 20 años (umbrales de GloFAS y Google Flood Hub) salen de la serie de GloFAS: la de 2 años es la mediana de los máximos anuales y las otras de una Gumbel. La lluvia entra en alerta cuando la mediana de 7 modelos da 50 mm en 48 h (o 35 mm en 24 h) en una localidad. También entran las emergencias del COEN de los últimos 3 días. «Avisarme» pide permiso al navegador para avisar de alertas nuevas.
- **Escenarios 72 h**: lluvia cada 3 horas de ECMWF, GFS, ICON, UKMO, GEM, JMA y ARPEGE (Open-Meteo), en una malla de 0,5° del norte del Perú y Ecuador. *Probable* = mediana de los siete; *pesimista* = el segundo más lluvioso. Los ríos se pintan según el caudal que espera GloFAS ese día.
- **Ecuador**: 14 ciudades en las alertas de lluvia y 8 ríos con caudal GloFAS (fuente `rios_ec`).
- **Imagen satelital**: en la web, teselas de Esri World Imagery hasta ~1 km del suelo; dentro de Claude, la instantánea Sentinel-2 de EOX.
- **Desastres en el mundo**: inundaciones, ciclones y sequías activas de GDACS (fuente `mundo`), en el globo y en la pestaña El Niño.
- **Un punto cualquiera**: al tocar el globo, la pestaña Lugar muestra la lluvia de cada uno de los 7 modelos allí.
- **Asesor** (botón «?»): explica cómo usar la página y lleva a cada parte.
- El globo solo se redibuja cuando algo cambia.

## Cómo abrirlo

- **En la web pública**: <https://vigia-pe.netlify.app>. Funciona en cualquier celular o computadora.
  - Los METAR se actualizan cada 5 minutos, el caudal de GloFAS cada 3 horas y la imagen térmica cada 10 minutos.
  - El clima y la lluvia se actualizan cada 30 minutos.
- **Dentro de Claude**: en el enlace del artefacto. Usa la instantánea de datos guardada en `datos/` y trae el Analista.
- **En tu computadora**: doble clic en **`Abrir VIGIA.bat`**. Abre un pequeño servidor local y la misma versión en vivo que la web. Necesita internet.

## Publicación automática en GitHub (reemplaza a Netlify)

El flujo `.github/workflows/publicar.yml` hace solo lo que antes había que hacer a mano:

- **Cada hora** renueva los avisos y quebradas del SENAMHI, las emergencias del INDECI, el ENFEN, los METAR, la imagen térmica, IMERG y GDACS.
- **Cada 6 horas** renueva todas las fuentes.
- En cada corrida arma la página y la publica en GitHub Pages, en <https://victor73917.github.io/vigia>. No cuesta créditos.
- Cada cambio de código que se sube a `main` también se publica.
- Desde la pestaña *Actions* del repositorio se puede correr a mano («Run workflow») y elegir las fuentes.

**Fuentes que solo responden desde el Perú.** Los avisos y quebradas del SENAMHI y el ENFEN no contestan a los servidores de GitHub. Los baja esta PC:

- La tarea programada de Windows «VIGIA datos Peru» corre `subir-peru.bat` a los :05 de cada hora.
- Ese archivo los sube a la rama `datos-peru`, que siempre tiene un solo commit.
- La corrida de GitHub de los :17 los toma de ahí.
- El registro queda en `datos/peru.log`.
- Si la PC está apagada, esos datos se quedan con su última fecha, y la página la muestra.
- Para quitar la tarea: `schtasks /Delete /TN "VIGIA datos Peru" /F`.

Si el recolector avisa que el ENFEN publicó un comunicado nuevo, hay que actualizar a mano `ENFEN_RESUMEN` en `recolectar.py` y subir el cambio.

Puesta en marcha (una sola vez):

1. Crear el repositorio público `vigia` en GitHub, vacío.
2. Desde esta carpeta, subir el código: `git remote add origin https://github.com/USUARIO/vigia.git` y luego `git push -u origin main`. Git abre el navegador para iniciar sesión.
3. En el repositorio, ir a *Settings → Pages → Build and deployment* y elegir **GitHub Actions**.

## Publicar una versión nueva en la web

1. Doble clic en `Actualizar datos.bat` para refrescar la instantánea.
2. En una terminal, dentro de esta carpeta, ejecuta `py construir.py --paquete`. Genera `vigia-web.zip` y la carpeta `publicar/`.
3. En Netlify, entra al proyecto **vigia-pe**, abre *Deploys* y sube `vigia-web.zip`.

Cada publicación gasta créditos del plan gratuito de Netlify, que el proyecto comparte con Pilas. Solo hace falta publicar para renovar estos datos:

- los avisos del SENAMHI;
- las emergencias del INDECI;
- los mapas de ECMWF;
- El Niño y el comunicado del ENFEN.

## Actualizar la instantánea

Doble clic en **`Actualizar datos.bat`**. Necesita Python y las librerías `eccodes`, `numpy` y `pypdf`; si faltan, se instalan con `py -m pip install --user eccodes numpy pypdf`. Descarga todas las fuentes y rearma `index.html`, y tarda varios minutos porque lee los PDF del INDECI y respeta los límites de Open-Meteo.

Para renovar solo algunas fuentes: `py -X utf8 recolectar.py emergencias cuencas` (las demás se conservan). Después, para que el artefacto de Claude muestre los datos nuevos, hay que volver a publicarlo; pídeselo a Claude.

Si `recolectar.py` avisa que el ENFEN publicó un comunicado nuevo, hay que actualizar el resumen `ENFEN_RESUMEN` que está al principio del archivo.

## Archivos

| Archivo | Qué es |
|---|---|
| `vigia.html` | La aplicación (es lo que se publica en Claude) |
| `index.html` | La misma aplicación lista para abrir en el navegador; la arma `construir.py` |
| `recolectar.py` | Descarga las fuentes y escribe `datos/instantanea.js`, `datos/rios.js`, los mapas de lluvia y las imágenes |
| `construir.py` | Arma `index.html` a partir de `vigia.html` y, con `--paquete`, el zip para Netlify |
| `datos/` | Instantánea de datos, ríos, mapas de lluvia, imagen térmica, imagen Sentinel-2 de la zona y fronteras (Natural Earth) |
| `datos/salidas.json`, `datos/indeci_cache.json` | Memoria del recolector: punto de caudal de cada cuenca y reportes del INDECI ya leídos |
| `FUENTES-LLUVIA.md` | Qué fuentes de lluvia se evaluaron, cuáles se usan y por qué |
| `tex/` | Texturas de la Tierra de la NASA (Blue Marble de día, Black Marble de noche) |

## Fuentes

Todas son públicas y gratuitas:

- ENFEN;
- SENAMHI (avisos, quebradas y GeoServer IDESEP con cuencas de la ANA y ríos del IGN);
- COEN-INDECI;
- GloFAS v4 de Copernicus, vía Open-Meteo;
- ECMWF (datos abiertos, CC BY 4.0) y Open-Meteo;
- NOAA (CPC, AWC y GOES-East) y NASA (GPM IMERG y GIBS);
- EOX, con Sentinel-2 cloudless 2024 bajo licencia CC BY-NC-SA 4.0.
