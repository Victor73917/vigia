# Fuentes de lluvia pronosticada: qué se evaluó y qué se usa

Investigación del 26 de octubre de 2026. Cada fuente se probó de verdad: descarga, formato, fecha de los datos y si el navegador puede leerla directamente (CORS).

## Las que VIGÍA usa

| Fuente | Qué aporta | Quién la publica | Cada cuánto | Cómo llega a VIGÍA |
|---|---|---|---|---|
| **Avisos meteorológicos** | Avisos oficiales de lluvia (amarillo, naranja, rojo), con su texto y las zonas de cada día | SENAMHI | Cuando se emiten, casi a diario | Recolector: tabla de la web + GeoServer WFS `g_aviso:view_aviso` (un mapa por día) |
| **Activación de quebradas** | Aviso de corto plazo por huaicos, distrito por distrito (3 154 distritos el 25 de octubre) | SENAMHI | Diario, vigencia de 24 h | Recolector: página del aviso + WFS `g_acti_quebrada:view_av_activ_qdra` |
| **ECMWF IFS 0,25°, datos abiertos** | Mapa mundial de lluvia: próximas 24 h, de 24 a 48 h, de 48 a 72 h y 7 días | Centro Europeo (ECMWF), licencia CC BY 4.0 | Corridas de las 00 y 12 UTC | Recolector: descarga solo el campo de lluvia (unos 400 KB por paso) y lo pinta en PNG |
| **ECMWF IFS 9 km vía Open-Meteo** | Lluvia por día en 75 ciudades y en cualquier punto que toques | ECMWF, servido por Open-Meteo | Cada 6 h | En vivo desde el navegador (tiene CORS) |
| **Conjunto ECMWF (51 escenarios) vía Open-Meteo** | Probabilidad de 10, 20 y 50 mm por día, y el rango probable | ECMWF ENS | Cada 6 h | En vivo desde el navegador |
| **NASA GPM IMERG (media hora)** | Lluvia que ya cayó, vista por satélite, en todo el planeta | NASA, vía GIBS | Cada 30 min, con unas 6 h de retraso | En vivo: GIBS dice cuál es la última imagen y el navegador la pide |

**Por qué este orden:** lo oficial en el Perú son los avisos del SENAMHI, y VIGÍA los muestra primero y sin cambiarlos. ECMWF es el modelo global con mejor desempeño y desde octubre de 2025 sus datos son abiertos; sirve para ver dónde y cuánto, pero no reemplaza un aviso. El conjunto de 51 escenarios evita dar un solo número como si fuera seguro. IMERG permite comparar lo pronosticado con lo que de verdad llovió.

## Evaluadas y no usadas (todavía)

| Fuente | Por qué no |
|---|---|
| SENAMHI · «Predicción numérica PP 24/48/72 h» (WMS `g_03_05`) | Es su modelo de lluvia en cuadrícula, pero el servicio no informa la fecha de la corrida. No hay forma de saber si el mapa es de hoy. Pedirle al SENAMHI que la publique. |
| SENAMHI · «Peligro de movimientos en masa por lluvias intensas 24-168 h» (WMS `g_04_08`) | Mismo problema: sin fecha. |
| SENAMHI · umbrales de precipitación (211 estaciones) | Lluvia medida cada hora frente a su umbral. Es observación, no pronóstico, y los campos (`pp`, `pp_acum`, `umbral`, `umb_acum`) no están documentados. Buen siguiente paso. |
| SENAMHI · SONICS y SILVIA (pronóstico hidrológico) | Tienen pronóstico por día, pero no encontré qué significa cada nivel. |
| SENAMHI · «Probabilidad de ocurrencia PP» | Es un pronóstico estacional (inferior, normal o superior), no de días. |
| CAP del SENAMHI | No existe. El SENAMHI aparece en el directorio de la OMM (`pe-senamhi`), pero sin feed. |
| NOAA GFS | Menor desempeño que ECMWF. Su acceso OpenDAP ya no responde y el GRIB necesita el mismo trabajo que ECMWF. |
| GloFAS (Copernicus) | Pronostica caudales de ríos, no lluvia. Las salidas por punto en el Perú piden registro. Sería el paso siguiente para los ríos Tumbes, Chira y Piura que menciona el ENFEN. |
| CHIRPS-GEFS (UC Santa Barbara) | Acumulados de 5 a 15 días pensados para sequía y agricultura, en GeoTIFF. No sirve para avisos de corto plazo. |
| RainViewer, OpenWeatherMap, Windy, Meteoblue | Comerciales, con clave, o con poca cobertura de radar en el Perú. |

## Qué está en vivo y qué no

| Dónde se abre | En vivo | Se renueva al actualizar o publicar |
|---|---|---|
| Web pública y `Abrir VIGIA.bat` | Lluvia por ciudad y por punto (ECMWF 9 km), probabilidades, satélite IMERG | Avisos y quebradas del SENAMHI, mapas ECMWF |
| Artefacto de Claude | Nada (el visor bloquea conexiones externas) | Todo |

El SENAMHI no deja que el navegador lea sus datos (no tiene CORS) y, según el proyecto avisos-pe, bloquea conexiones desde el extranjero y desde servidores en la nube como GitHub. Por eso hoy pasan por `recolectar.py`, que corre en esta computadora en el Perú. Para tenerlos en vivo en la web haría falta un pequeño servicio intermedio. Un Worker de Cloudflare con tarea programada es la opción más probada: el proyecto peru-alerta-lluvia confirma que el SENAMHI le responde.

## Detalles técnicos verificados

- Cada aviso del SENAMHI tiene **un mapa por día**: `viewparams=qry:{número}_{día}_{año}`. Los niveles se superponen: un punto en rojo también está en naranja y en amarillo.
- El filtro espacial del servidor del SENAMHI **no es confiable**. VIGÍA descarga las zonas y decide en el navegador si un punto cae dentro.
- La página de avisos de quebradas también muestra un comunicado de 2020. VIGÍA solo acepta el aviso si el número de la pestaña y el del panel coinciden.
- Para leer el GRIB2 de ECMWF, `recolectar.py` usa `eccodes` y `numpy`. Se instalan una vez con `py -m pip install --user eccodes numpy`. Sin ellas, el recolector omite el mapa mundial y sigue con lo demás.

## Referencias que ayudaron

- [avisos-pe](https://github.com/osrcmap/avisos-pe) y su RESEARCH.md: cómo publica el SENAMHI sus avisos (verificado el 17 de octubre de 2026).
- [peru-alerta-lluvia](https://github.com/renzodamgo/peru-alerta-lluvia): capas WFS del SENAMHI y su acceso desde Cloudflare.
- [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data), [Open-Meteo ECMWF](https://open-meteo.com/en/docs/ecmwf-api), [Open-Meteo Ensemble](https://open-meteo.com/en/docs/ensemble-api), [NASA IMERG](https://gpm.nasa.gov/data/imerg).
