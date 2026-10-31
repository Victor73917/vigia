# VIGÍA · Auditoría, fase 1

Fecha: 31 de octubre de 2026. Versión auditada: la publicada en vigia-pe.netlify.app el 28 de octubre (00:11), que es la misma que `vigia.html` en esta carpeta.

## Cómo se hizo

- Leí el código de búsqueda, cámara, paneles y capas en `vigia.html`. Revisé los datos de `datos/instantanea.js` y la configuración de Netlify en `publicar/`.
- Probé la página en un servidor local, en escritorio y en tamaño de celular (375 × 812).
- La consola no mostró errores.
- **Qué no probé**: un Android o iPhone reales (solo la emulación), la accesibilidad con lector de pantalla, ni el sitio publicado en esta ronda. El código publicado es el mismo que el local.

## Qué es hoy la aplicación

- Es un solo archivo HTML (unas 3 400 líneas) con un globo 3D propio hecho en three.js.
- No tiene backend, base de datos, cuentas ni datos personales.
- Los datos vienen de dos lados:
  - una instantánea que arma `recolectar.py` en tu computadora (SENAMHI, INDECI, ENFEN, distritos y ríos);
  - consultas en vivo desde el navegador (Open-Meteo, GloFAS, GDACS, METAR y GOES).
- Cubre 326 distritos de cinco departamentos: Tumbes, Piura, Lambayeque, La Libertad y Cajamarca.
- Se publica a mano en Netlify. Cada subida gasta unos 15 créditos y quedan 88.

## Problemas encontrados

Los marcados como **Confirmado** los reproduje. Los marcados **Por código** se ven en el código, pero no los ejecuté.

### P-01 · Buscar un lugar aleja la cámara hasta ver el planeta (crítico, confirmado)

- **Componente**: buscador de la pestaña Lugar (`#buscarLugar`) y la función `irALugar`.
- **Pasos**:
  1. Acercar el globo a Piura hasta unos 100 km de altura.
  2. En la pestaña Lugar, escribir «Piura» y pulsar Enter.
- **Observado**: la cámara se aleja hasta mostrar Sudamérica y el Pacífico. Es la vista del planeta.
- **Esperado**: que la cámara encuadre la ciudad o el distrito de Piura.
- **Causa raíz**: `volarA(lat, lng, dist)` recibe la distancia en radios terrestres, con números fijos que se pusieron cuando el globo solo se acercaba hasta unos 1 000 km:
  - `irALugar` usa 2,1 (unos 7 000 km de altura);
  - el buscador superior usa 1,35 para un distrito (unos 2 200 km);
  - usa 1,4 para una provincia y 1,5 para un departamento.

  Hoy el globo baja hasta 1 km, así que cualquier selección hecha desde cerca **aleja** la vista. Hay 20 llamadas a `volarA` con distancias fijas.
- **Solución**: una función `encuadrar(caja, margen)` equivalente a `fitBounds`:
  - calcula la altura con el tamaño real del límite (distrito, provincia o departamento), el ángulo de visión de la cámara y el espacio que dejan libre los paneles;
  - tiene altura mínima y máxima;
  - para un punto sin límite (centro poblado) usa una altura fija de unos 8 a 15 km.

  Todas las llamadas actuales pasan a usarla.
- **Verificación**: prueba automática que, para Piura, Tumbes, Sullana, Talara, Castilla, Catacaos y La Unión, compruebe dos cosas:
  - después del vuelo, la caja del lugar queda entera en pantalla y ocupa al menos el 40 % del ancho libre;
  - la altura final nunca supera la necesaria.

### P-02 · El buscador superior también aleja la vista (crítico, confirmado)

- **Pasos**: acercar el globo a unos 30 km y escribir «Piura» en «Consulta».
- **Observado**: la cámara sube a unos 2 200 km y se ve todo el norte del Perú y el Ecuador.
- **Causa y solución**: las mismas que en P-01. Además, la provincia y el departamento se centran en el promedio de los centros de sus distritos, no en su límite.

### P-03 · Algunos botones devuelven a la vista nacional sin pedirlo (alto, por código)

- **Dónde**:
  - en la pestaña Lluvia, al tocar un día de un aviso (`#avisosLluvia`, `[data-dia]`);
  - al entrar a Lluvia o El Niño desde un enlace interno (`verVista`);
  - al activar la imagen térmica (`#btnTermica`).
- **Observado**: los tres llevan la cámara a (-8, -77) a 2,1 radios, o a 2,2. Se pierde el acercamiento que tenías.
- **Esperado**: que cambiar de capa o de día no mueva la cámara.
- **Solución**: quitar esos vuelos y poner un botón «Vista nacional» para volver a propósito.

### P-04 · Un nombre se elige sin preguntar cuál (alto, confirmado en datos)

- «Piura» es a la vez distrito, provincia y departamento. El buscador elige el distrito sin avisar.
- Diez nombres de distrito se repiten en la zona y el buscador toma uno al azar: Santa Rosa, San José, Bellavista, Salitral, Lagunas, Bambamarca, Bolívar, Pueblo Nuevo, Santa Cruz y La Esperanza.
- **Solución**: si hay más de un resultado, mostrar una lista para elegir, con el tipo y la jerarquía (por ejemplo «Santa Rosa · distrito · Chiclayo, Lambayeque»). La clave interna será el UBIGEO, que los datos ya traen (por ejemplo, La Unión es 200110).

### P-05 · El buscador cubre solo la zona norte (alto, confirmado)

- Hay 326 distritos de 5 departamentos. No hay centros poblados ni el resto del Perú.
- «Talara» funciona como provincia, pero no hay un distrito con ese nombre: la ciudad de Talara está en el distrito de Pariñas.
- **Solución**: un índice territorial nacional:
  - departamentos, provincias y distritos con UBIGEO y su límite simplificado;
  - centros poblados con su punto.
- **Pendiente de verificar**: la fuente y la licencia. Las candidatas son la capa de distritos del GeoServer del SENAMHI, que ya usamos, y los centros poblados del INEI o del IGN. El índice se cargaría por partes, para no hacer más lenta la primera carga.

### P-06 · El panel derecho no sigue a la búsqueda (medio, confirmado)

- **Pasos**: tocar Catacaos en el globo y luego buscar «Piura» arriba.
- **Observado**: la tarjeta de respuesta habla de Piura, pero el panel derecho sigue mostrando la ficha de Catacaos.
- **Solución**: un solo estado `seleccion` (tipo, UBIGEO y caja) que actualicen a la vez el mapa, el panel y la URL. El enlace `?lugar=200110` serviría para compartir.

### P-07 · La tarjeta de respuesta tapa la lista de capas y no se cierra al cambiar de pestaña (medio, confirmado)

- **Solución**: que la respuesta viva dentro del panel contextual, no flotando sobre el mapa.

### P-08 · En el celular, el aviso de alerta nueva tapa el buscador al abrir la página (medio, confirmado)

- Pasa con el tamaño de 375 px.
- **Solución**: mover el aviso abajo, que desaparezca solo y que no tape la barra superior.

### P-09 · El doble clic para acercar también selecciona el distrito (bajo, confirmado)

- El primer clic del doble clic abre la ficha del distrito que está debajo.
- **Solución**: esperar unos 250 ms antes de tratar el clic como selección.

### P-10 · En el celular, los nombres e íconos se amontonan en la vista inicial (bajo, confirmado)

- Pasa en Tumbes, Piura y Chiclayo.
- **Solución**: agrupar los íconos y ocultar los nombres que chocan, según el nivel de acercamiento.

### P-11 · Los datos oficiales solo se renuevan cuando se republica (alto, confirmado)

- La instantánea es del 28 de octubre. El encabezado dice «SENAMHI hace 4 días · INDECI hace 4 días», así que la antigüedad sí se avisa.
- Los avisos del SENAMHI, las emergencias del INDECI y el ENFEN no tienen permiso del navegador para leerse directamente (CORS), y solo se actualizan cuando corro `recolectar.py` y subo un zip a Netlify. Eso gasta créditos.
- El ENFEN anunciaba su comunicado siguiente para el 30 de octubre. La página sigue mostrando el N° 18-2026, cuyo resumen está escrito a mano en el código.
- **Solución**: una tarea programada en un servidor que recolecte los datos cada hora y los publique como JSON, sin volver a subir la página. Es la base de casi todo lo demás (ver la arquitectura más abajo).

### P-12 · Faltan cosas de accesibilidad y teclado (medio, por código)

- Los paneles emergentes (asesor y respuesta) no declaran `role="dialog"` ni manejan el foco.
- Escape solo cierra la respuesta.
- **Pendiente**: revisión con lector de pantalla y medición de contraste.

## Lo que pide el prompt maestro y todavía no existe

| Área | Estado |
|---|---|
| Búsqueda nacional con UBIGEO, provincias y centros poblados | No existe (solo 326 distritos) |
| Encuadre por límites y botón «Vista nacional» | No existe |
| Gestor de capas con opacidad, leyenda, fuente y confianza por capa | Parcial: solo se pueden encender y apagar |
| Ficha de 5 días con amenaza, exposición, vulnerabilidad e incertidumbre | Parcial: 7 días de lluvia con 7 modelos y 51 escenarios; faltan la separación amenaza/exposición/riesgo y la descarga del informe |
| Monitoreo de El Niño | Existe: ENFEN, Niño 1+2 y 3.4, ONI, comparación con 1997, 2015 y 2023. Faltan los vientos alisios y el subsuelo del mar, y la renovación automática del ENFEN |
| Tormentas observadas | Parcial: imagen térmica GOES y lluvia IMERG. **No hay rayos ni radar reales** (no encontré una fuente abierta para el Perú; está por verificar) |
| Carreteras (MTC / Provías) | No existe. Hay que verificar si Provías publica datos que se puedan leer automáticamente |
| Portal ciudadano, DNI, evidencias | No existe. **Necesita backend y una decisión legal** |
| Centro de Comando: roles, bandeja, estados, trazabilidad | No existe. **Necesita backend y autenticación** |
| Matriz de prioridad configurable y explicada | Parcial: «Prioridad de atención» ya explica sus puntos, pero los pesos están fijos en el código |
| Asistente con fuentes y fecha | Parcial: el asesor responde por reglas con datos de la página. El Analista con IA solo funciona dentro de Claude |
| Informes PDF y CSV | No existe |
| Uso sin conexión (PWA) | No existe |

## Recomendación de arquitectura

1. **Mapa**: cambiar el globo three.js propio por **MapLibre GL JS 5**. Ya tiene proyección de globo, así que se conserva el aspecto 3D, y trae de serie lo que hoy tuve que programar a mano:
   - `fitBounds` con margen;
   - capas vectoriales con leyenda y opacidad;
   - agrupación de marcadores;
   - etiquetas sin choques;
   - buen rendimiento en celulares.

   Las capas y los datos actuales se pasan a GeoJSON. Es el cambio más grande de la fase 3. Hasta entonces, P-01 a P-03 se corrigen en el globo actual (fase 2), para no esperar.
2. **Datos**: una tarea programada (GitHub Actions o un servidor pequeño) que corra el recolector cada hora y publique JSON con la fecha de cada fuente. Así deja de hacer falta republicar para tener datos frescos.
3. **Reportes ciudadanos y Centro de Comando**:
   - base de datos PostgreSQL con PostGIS;
   - autenticación con roles y MFA;
   - almacenamiento privado de fotos;
   - registro de auditoría.

   Supabase es una opción que reúne todo eso con seguridad por fila. La alternativa es un servidor propio de la institución. Esto **no puede vivir solo en Netlify** como hoy.
4. **Seguridad hoy**: el riesgo es bajo porque no hay cuentas ni datos personales. Netlify ya envía `nosniff`, `Referrer-Policy` y `Permissions-Policy`. Falta una política de contenido (CSP). Hay 77 `innerHTML`; los textos que vienen de fuentes externas pasan por `esc()`, pero conviene revisarlos uno por uno antes de aceptar texto de ciudadanos.

## Plan por fases

| Fase | Qué incluye | Depende de | Criterio de aceptación |
|---|---|---|---|
| **2. Correcciones críticas** (en el globo actual) | `encuadrar()` por límites; quitar los vuelos automáticos (P-03); botón «Vista nacional»; desambiguación por UBIGEO; un solo estado de selección (P-06); arreglar P-07 a P-09 | Nada | Pruebas 1 a 4 y 17 del prompt, con Piura, Tumbes, Sullana, Talara, Castilla, Catacaos y La Unión, en escritorio y celular |
| **3. Rediseño y capas** | MapLibre GL JS; barra superior, panel izquierdo y panel derecho contextual; gestor de capas con opacidad, fuente y fecha; índice nacional con UBIGEO | Fase 2; fuente de límites nacionales verificada | Pruebas 3 a 5, 15 y 16; carga inicial menor de 3 s en 4G |
| **4. Inteligencia territorial** | Ficha de 5 días (amenaza, exposición e incertidumbre); módulo La Unión con descarga del informe; El Niño con alisios y subsuelo; recolección automática | Fase 3; tarea programada | Pruebas 6 a 8, 15, 18 y 19 |
| **5. Portal ciudadano** | Formulario de celular sin registro obligatorio; borrador sin conexión; fotos con controles; moderación | Backend (decisión D-1); base legal (D-2) | Pruebas 9, 12, 14 y 16 |
| **6. Centro de Comando** | Roles, MFA, bandeja, estados con historial, asignación, prioridad configurable | Fase 5 | Pruebas 10, 11 y 13 |
| **7. Asistente** | Respuestas con fuente, fecha, hechos frente a proyecciones, y límites por rol | Fases 4 a 6 | Prueba 18 |
| **8. Validación** | Pruebas automáticas (Playwright), accesibilidad, seguridad OWASP, documentación | Todas | Las 20 pruebas del prompt |

## Decisiones que necesito de ti

- **D-1 · Backend**: ¿usamos un servicio como Supabase (tiene plan gratuito y uno de pago) o un servidor de tu institución? Sin backend no se pueden hacer las fases 5 y 6.
- **D-2 · Datos personales**: guardar el DNI y los datos de contacto de ciudadanos exige un responsable del banco de datos inscrito ante la Autoridad Nacional de Protección de Datos Personales (Ley 29733). ¿Qué entidad sería la responsable? Hasta tener esa respuesta, el portal ciudadano funcionaría **sin DNI**.
- **D-3 · Publicación**: quedan 88 créditos de Netlify y cada subida gasta unos 15. Con la recolección automática, la página casi no necesitaría republicarse. Otra opción es moverla a otro alojamiento.

## Resultado de la fase 2 (31 de octubre de 2026)

Corregido en `vigia.html`, todavía **sin publicar**:

- **P-01 y P-02**: la nueva función `encuadrar()` calcula la altura con el límite del lugar, el ángulo de la cámara y el espacio libre de paneles. Las 20 llamadas con distancia fija se cambiaron:
  - distrito, provincia, departamento y cuenca se encuadran por su límite;
  - una ciudad baja a 30 km, un aeródromo a 40 km y un punto a 6 km.
- **P-03**: tocar un día de aviso, la imagen térmica o una pestaña ya no mueven la cámara.
- **Vista nacional**: botón «Perú» encima del Asesor, o la tecla Inicio. La vista inicial encuadra la zona crítica: Tumbes, Piura, Lambayeque, La Libertad y Cajamarca.
- **P-04**: si el nombre es de varios territorios, los dos buscadores preguntan cuál, con su UBIGEO. El buscador de Lugar ahora también reconoce distritos, provincias y departamentos.
- **P-06**:
  - un distrito buscado abre su ficha en el panel;
  - una provincia o un departamento pasan el panel a Prioridad, filtrado por su departamento;
  - la dirección guarda `?lugar=UBIGEO`, que sirve para compartir (por ejemplo `?lugar=200110` abre La Unión).
- **P-07**: la tarjeta de respuesta se cierra al cambiar de pestaña.
- **P-08**: en el celular, el aviso de alerta nueva ya no tapa el buscador.
- **P-09**: el doble clic solo acerca, ya no selecciona.

Pruebas que ejecuté en el navegador, en escritorio (800 × 600) y en celular (375 × 812):

- Empezando a 2 km de altura, busqué Piura, Tumbes, Sullana, Talara, Castilla, Catacaos y La Unión. En los 7 casos, y en cada opción de los nombres repetidos, el límite quedó entero en pantalla y la cámara bajó o subió solo lo necesario:
  - distrito de Piura: 70 km;
  - provincia: 479 km;
  - departamento: 1 001 km.
- Antes del cambio, Piura subía a unos 2 200 km o a la vista del planeta.
- Encender y apagar todas las capas, recorrer las 6 pestañas, tocar un día de aviso y la imagen térmica: la altura siguió en 12 km y el lugar elegido se conservó.
- Con el botón «Perú», el país entero queda en pantalla.
- La consola no mostró errores.

Pendiente:

- **P-10**: amontonamiento de íconos. Pasa a la fase 3, con la agrupación de MapLibre.
- **P-11**: recolección automática.
- **P-12**: accesibilidad.
- **P-05**: el índice nacional.
- No probé en un Android ni en un iPhone reales.

## Resultado de la fase 3 (31 de octubre de 2026)

Hecho en `vigia.html`, todavía **sin publicar**:

- **Mapa con MapLibre GL JS 6.14** (proyección de globo). Expone las mismas funciones que el globo anterior, así que el resto de la página no cambió.
  - Las capas son vectoriales: distritos, avisos, ríos, cuencas y límites.
  - La lluvia, la imagen térmica y los escenarios son imágenes reproyectadas a Mercator.
  - Los íconos son los mismos de antes.
  - El globo three.js queda **de respaldo**: dentro de Claude, en archivo local, en equipos sin WebGL2, si MapLibre falla, o con `?motor=globo`.
- **Mapa base configurable**: Satélite (Esri), Oscuro (CARTO/OpenStreetMap) y Topográfico (Esri). Se recuerda en el navegador.
- **Agrupación** de emergencias, quebradas y centros poblados expuestos al alejarse (resuelve P-10). Al tocar un grupo, el mapa se acerca.
- **Gestor de capas** («Opacidad, fuentes y mapa base…»). Para cada capa muestra:
  - encendido;
  - opacidad;
  - fuente;
  - tipo de dato (aviso oficial, reporte oficial, pronóstico de modelo, observación o criterio de VIGÍA);
  - antigüedad;
  - leyenda.
- **Índice territorial nacional** (resuelve P-05), con datos del INEI tomados del GeoServer del SENAMHI y generados con `territorio.py`:
  - `datos/territorio.json`: 25 departamentos, 196 provincias y 1 873 distritos, con UBIGEO y límite (515 KB comprimido);
  - `datos/ccpp.json`: 127 681 centros poblados (1,6 MB comprimido). Solo se descarga si el nombre buscado no es un territorio.

  Fuera de la zona norte, la ficha muestra el pronóstico en vivo y los avisos del SENAMHI, y aclara que ahí no hay prioridad ni exposición.
- **Búsqueda**:
  - Los nombres repetidos en todo el país se preguntan: Castilla, La Unión, Santa Rosa…
  - Para un centro poblado, «Pedregal, Piura» filtra por departamento, provincia o distrito. La zona norte aparece primero.

Pruebas que ejecuté, en Chrome a 1536 × 730:

- Los 7 lugares de prueba, empezando a 2 km del suelo: todos encuadrados y enteros en pantalla.
  - Piura distrito: 56 km.
  - Tumbes: 31 km.
  - Sullana: 80 km.
  - Talara provincia: 162 km.
  - Castilla: 65 km.
  - Catacaos: 144 km.
  - La Unión: 51 km.
- Huancayo (fuera de la zona): pregunta entre provincia y distrito, y encuadra la provincia elegida.
- Centros poblados: «Pedregal» da 45 resultados con la zona norte primero, y «Pedregal, Piura» da 7.
- Capas y pestañas: la cámara quedó igual (12 km y el mismo centro).
- Mapa base y opacidad: cambian.
- Botón «Perú»: el país entero queda en pantalla.
- `?motor=globo`: carga el globo de respaldo.
- La consola no mostró errores.

Corregí un fallo que encontré en las pruebas: el respaldo saltaba al globo si la página se abría en una pestaña en segundo plano.

Pendiente de la fase 3:

- **Prueba en celular**: no la pude hacer, porque el navegador interno no dibujaba con la ventana minimizada.
- **Reorganizar la interfaz**: panel izquierdo de navegación, panel derecho contextual y barra superior con notificaciones y perfil. Hoy siguen las pestañas a la derecha.
- **Accesibilidad**: P-12.

### Paneles reorganizados (31 de octubre de 2026, sin publicar)

- **Escritorio**:
  - **Panel izquierdo plegable** con las secciones nacionales: Prioridad, Emergencias, Ríos, Lluvia y El Niño. Se oculta con «‹» y se reabre con la pestaña «Secciones». La preferencia se recuerda en el navegador.
  - **Panel derecho contextual**: aparece solo al elegir un lugar, con su ficha completa. Se cierra con «×» o Escape, y al cerrarlo se quita la selección del mapa y de la dirección.
  - **Barra superior** sobre el mapa:
    - marca y buscador;
    - hora de Lima (la UTC se oculta si falta espacio);
    - estado de los datos («En vivo», la antigüedad, o «Sin conexión» cuando el equipo pierde la red);
    - **campana** con el número de alertas rojas, que abre y cierra la lista.
  - Las alertas empiezan plegadas: solo se ve su resumen.
  - Todos los controles flotantes (capas, alertas, escenarios, «Perú» y Asesor) se acomodan entre los dos paneles, y el mapa encuadra en el espacio libre.
- **Celular**: sigue la hoja inferior con pestañas, «Lugar» incluida. La campana está en la barra.
- **Pruebas en Chrome** (1536 × 730):
  - Los 7 lugares de prueba y Huancayo quedan enteros **dentro del espacio libre entre los dos paneles**. Esta comprobación es más estricta que la anterior.
  - Abrir y cerrar el panel derecho funciona.
  - Plegar y reabrir el panel izquierdo funciona.
  - La campana abre y cierra la lista.
  - La consola no mostró errores.
- **Celular (375 × 812)**: comprobé la disposición sin dibujar el mapa: nada se encima, «Lugar» queda en la hoja y el panel derecho no aparece.
- **Pendiente**:
  - el perfil (llega con las cuentas de la fase 6);
  - secciones de carreteras, reportes ciudadanos y operaciones (no se ponen vacías: no hay datos todavía);
  - probarlo en un teléfono real.

### Publicación de los paneles y una falla encontrada después (31 de octubre de 2026)

- Los paneles se publicaron en Netlify a la 1:04 p. m.; quedan 42 créditos.
- Al verificarlos en el sitio publicado encontré una falla que ya estaba desde la fase 3:
  - al pasar de un lugar cercano a otro (Piura y luego La Unión), La Unión quedaba a 35 km y no entraba entera en pantalla;
  - la causa es que `fitBounds` de MapLibre, con la vista de globo, da otro zoom según la altura de partida.
- **Corrección**: `encuadrar()` calcula el zoom en Mercator con el espacio libre entre los paneles.
- **Pruebas**: 19 combinaciones (desde 2 km, desde otro lugar y desde el planeta) dejan el lugar entero en pantalla y a la misma altura. Por ejemplo, La Unión queda a 85 km en los tres casos.
- La corrección se publicó en Netlify a la 1:08 p. m. En el sitio publicado, la secuencia Piura → La Unión → Catacaos → La Unión deja cada lugar entero en pantalla: La Unión queda a 85 km las dos veces.

## Resultado de la fase 4 (31 de octubre de 2026, publicada en Netlify hacia la 1:21 p. m.; quedan 12 créditos)

- **Ficha de 5 días** en la ficha de cualquier lugar del Perú. Consulta en vivo 7 modelos vía Open-Meteo: ECMWF, GFS, ICON, UKMO, GEM, JMA y ARPEGE. Para cada día muestra:
  - lluvia (la mediana y el rango entre modelos);
  - la hora más lluviosa (mm/h) y la probabilidad de lluvia;
  - tormenta, como número de modelos con código de tormenta o CAPE de 1000 J/kg o más;
  - viento y ráfagas;
  - el río de la cuenca según GloFAS, frente a la crecida de 2 años y con el % de los 51 escenarios que la superan;
  - el aviso del SENAMHI que cubre el punto;
  - la incertidumbre: cuánto difieren los modelos entre sí, con un criterio de VIGÍA que se explica en la ficha.
- **Resumen operacional** en lenguaje natural: «qué puede pasar», con los **hechos oficiales** separados de las **proyecciones de modelos** y una lista de **lo que falta para concluir**.
  - Si hay un aviso oficial y los modelos prevén poca lluvia, lo dice y aclara que manda el aviso.
  - Si no se puede consultar el pronóstico, lo dice y no saca conclusiones.
- **Amenaza, exposición, vulnerabilidad y riesgo** separados:
  - la exposición sale del SENAMHI y solo existe para la zona norte;
  - la vulnerabilidad todavía no está integrada;
  - el riesgo no se calcula, porque no hay un modelo validado.

  No hay porcentajes de inundación.
- **Informe para descargar** (HTML imprimible o PDF desde el navegador) y **CSV** de los 5 días. Incluyen:
  - la fecha de corte;
  - las fuentes con la fecha de cada una;
  - los hechos y las proyecciones;
  - la tabla de los 5 días;
  - las limitaciones.
- **El Niño**: nuevo bloque «Atmósfera y océano bajo la superficie», con datos mensuales del NOAA CPC (nueva fuente `oceano` del recolector):
  - alisios del Pacífico central: −7,6 m/s, −3,0 desviaciones en septiembre de 2026;
  - calor en los primeros 300 m del Pacífico ecuatorial: +3,4 °C;
  - Índice de Oscilación del Sur: −2,0.

  Tiene un gráfico de 24 meses y explica cómo se conectan el océano y la atmósfera. Aclara que una tormenta aislada no intensifica El Niño.
- Los datos del SENAMHI, el INDECI, el ENFEN y el pronóstico por distrito se renovaron hoy. Se actualizó el resumen al Comunicado ENFEN N° 19-2026.

Pruebas que ejecuté en Chrome:

- **La Unión**: 5 días; se reconoce el aviso amarillo N° 445 del SENAMHI para el 31 de octubre y el 1 de noviembre; el río Piura está a 180–266 m³/s, por debajo de la crecida de 2 años (493 m³/s), y 0 % de los escenarios la superan. El informe HTML trae la tabla y la fecha de corte, y el CSV tiene 16 columnas.
- **Huancayo** (fuera de la zona): señala tormentas posibles y el aviso amarillo N° 448, y dice que no hay datos de exposición.
- **El Niño**: se muestran los indicadores y el gráfico.
- Al probar los botones de descarga se bajaron dos archivos de La Unión a la carpeta Descargas.

Pendiente de la fase 4:

- **Recolección automática.** Necesita un lugar donde corra el recolector cada hora y publique los datos sin gastar créditos de Netlify; por ejemplo, GitHub Actions con un repositorio. Es una decisión del usuario (D-3).
- **Pronóstico hidrológico por centro poblado** del SENAMHI (SONICS): falta revisar sus datos y su licencia.
