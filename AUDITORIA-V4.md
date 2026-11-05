# VIGÍA · Auditoría integral 4 — diagnóstico verificable y plan (5 de noviembre de 2026)

Continúa la auditoría 3 (`AUDITORIA-V3.md`). Aquí figura solo lo comprobado hoy. Cada hallazgo tiene una de estas marcas:
- **confirmado**: se reprodujo, o hay evidencia directa;
- **riesgo potencial**: no se demostró un fallo, pero la exposición existe;
- **no verificable**: con el acceso disponible no se puede comprobar.

No se ejecutaron pruebas intrusivas contra servicios de terceros. Solo se hicieron lecturas normales de páginas públicas y una solicitud no permitida al puente propio.

## 1. Arquitectura real (inventario)

| Pieza | Qué es | Evidencia |
|---|---|---|
| Página | Un solo HTML con JavaScript sin framework (`vigia.html`, unas 5 300 líneas), armado por `construir.py` en `index.html` (481 KB, 147 KB comprimido) | Repositorio `Victor73917/vigia`, ramas `main` y `desarrollo` |
| Mapa | MapLibre GL 6.14.0 y three.js 0.185.1 como respaldo, desde jsDelivr | `vigia.html` |
| Alojamiento principal | GitHub Pages: producción en `/vigia/` y pruebas en `/vigia/pruebas/` (noindex) | `publicar.yml` |
| Recolector | GitHub Actions: `recolectar.py` cada hora (:17) y completo 4 veces al día | `publicar.yml` |
| Puente | Cloudflare Worker `vigia-puente` para SENAMHI y ENFEN, con lista cerrada de direcciones | `nube/puente-peru.js`; una ruta no permitida responde 400 |
| Base de datos | Supabase `vigia-pruebas` (plan Free, Ohio): centro de comando y portal ciudadano **solo en pruebas**, con datos ficticios | `nube/supabase/*.sql` |
| Autenticación | Supabase Auth con TOTP (aal2), registro abierto desactivado, RLS en todas las tablas | Auditoría 3, sección 13 |
| IA | Función `analista` de Supabase (Claude Haiku 5.5), desplegada y **apagada** (sin clave) | Auditoría 3, sección 15 |
| Datos en el navegador | Solo `localStorage` (tema, capas, lugares recientes, guía vista). No hay cookies propias | Revisión del código |
| Versión vieja | **Netlify `vigia-pe.netlify.app`**: copia congelada (sin despliegues desde el 31 de octubre) | Ver H-02 |

## 2. Hallazgos

| ID | Hallazgo | Marca | Criticidad | Evidencia | Causa raíz |
|---|---|---|---|---|---|
| H-01 | La consulta en vivo de caudales falla (400) **cada vez** que se abre la página, y los escenarios de ríos (`ensamble`) no se actualizan desde el 2 de noviembre | confirmado | **Alta** | Consola de producción: `flood-api…latitude=…,s,…` → 400. Estado de `ensamble`: 2026-11-02 00:09 | `datos/salidas.json` lo comparten dos funciones. `salida_por_cauce` anota «sin» y `caudal_salida` lo convertía en el punto `('s','i','n')`, por ejemplo en Bocapán |
| H-02 | Dos versiones públicas que se contradicen: Netlify muestra datos del **31 de octubre** | confirmado | **Alta** | `vigia-pe.netlify.app/datos/instantanea.js`: `"generado":"2026-10-31T18:12:55"` | Netlify quedó congelado (cada despliegue cuesta créditos) |
| H-03 | Las corridas programadas de GitHub no son puntuales: no hubo ninguna entre 07:25 y 16:27 UTC del 5 de noviembre, y la de 16:27 falló | confirmado | **Alta** | API de Actions: corridas 41987101880 → 42064593288. Producción quedó con datos de 07:25 durante unas 12 h | GitHub no garantiza el horario de `schedule` y lo retrasa con carga. La falla dice: «The hosted runner lost communication with the server» |
| H-04 | Una fuente que falla no queda registrada: la página solo ve la fecha del último dato bueno | confirmado | Media | `instantanea.js` no tiene campo de errores; `ensamble` y `mundo` llevan 2 a 3 días sin renovarse y no hubo aviso técnico | El recolector solo guarda la hora de éxito |
| H-05 | Bibliotecas de terceros sin verificación de integridad: jsDelivr, sin SRI | riesgo potencial | Media | 0 atributos `integrity`. La CSP permite cualquier ruta de `cdn.jsdelivr.net` | Se cargan con versión fija pero desde la CDN |
| H-06 | Dependencias de Python sin versión fija en el recolector | riesgo potencial | Media | `pip install eccodes numpy pillow pypdf h5py` | Una versión nueva puede romper la corrida sin aviso |
| H-07 | Acciones de GitHub fijadas por etiqueta (`@v7`), no por hash | riesgo potencial | Baja | `publicar.yml` | Práctica común; el hash es más seguro |
| H-08 | Sin política de privacidad, términos de uso ni aviso legal en la página | confirmado | Media | No existen. Sí hay avisos de «no reemplaza los avisos oficiales» | No se habían pedido |
| H-09 | Roles del centro de comando: 3 (lector, operador, supervisor) contra los 5 pedidos | confirmado | Media (solo pruebas) | `001_esquema.sql` | Diseño de la fase 6 |
| H-10 | Límite de intentos de acceso, duración de sesión y revocación en Supabase Auth | no verificable | — | Se configuran en el panel de Supabase. No se revisaron hoy | — |
| H-11 | Peso de los datos al abrir: unos 1,6 MB comprimidos (instantánea, territorio, ríos) | confirmado | Media | `instantanea.js` 430 KB, `territorio.json` 538 KB y `rios.js` 642 KB, comprimidos | Todo se carga al inicio |
| H-12 | Página sin `<h1>` | confirmado | Baja | Revisión del DOM | El título visible es un `<b>` |
| H-13 | METAR/TAF en vivo solo funciona en Netlify (proxy `/awc/`). En GitHub Pages llega con la instantánea horaria | confirmado | Baja | `actualizarAerodromos()` | AWC no permite leerlo desde el navegador |

**Lo que se revisó y está bien:**
- **Secretos:** no hay ninguno en el historial de git. Se buscaron cadenas de PostgreSQL con contraseña, claves de Supabase, de Anthropic y privadas.
- **HTTPS y HSTS:** activos en GitHub Pages.
- **CSP:** sin `unsafe-inline` en scripts y sin `eval` (auditoría 3, sección 16).
- **Puente:** rechaza las rutas no permitidas.
- **Accesibilidad:** 0 botones o campos sin nombre accesible; contraste mínimo del texto 4,94:1 (AA); idioma `es` declarado.
- **Frescura:** los datos de producción eran del mismo día, salvo H-03 y H-04.

**Cabeceras HTTP:** GitHub Pages no permite configurar `X-Content-Type-Options`, `Permissions-Policy` ni `frame-ancestors`. La CSP va en `<meta>`, que no admite `frame-ancestors`. Para tenerlas habría que servir la página con un proxy o con Cloudflare Pages. Ver decisión D-03.

## 3. Correcciones aplicadas hoy (rama `desarrollo`)

| ID | Corrección | Archivos | Prueba |
|---|---|---|---|
| H-01 | `caudal_salida` devuelve «sin punto» cuando el caché dice «sin». `ensamble_rios` y la página usan solo puntos formados por dos números (`conPunto`), y las cuencas sin punto quedan como «sin datos suficientes» | `recolectar.py`, `vigia.html` | Con la instantánea real de producción en local, las dos consultas a `flood-api` responden 200 (antes, 400), sin errores en la consola. `caudal_salida('0148')` → `None` y `ensamble_rios` pide solo los puntos válidos |

## 4. Plan priorizado

**Sin costo y sin decisión tuya** (los hago a continuación, en `desarrollo` → /pruebas/):
1. H-04: registrar el estado de cada fuente: último intento, último éxito y error resumido. La página mostrará «fuente sin actualizar desde…» y el tipo de dato: observado, pronóstico, estimación, simulación o alerta oficial.
2. H-05: servir MapLibre, three.js y supabase-js desde el propio sitio y quitar jsDelivr de la CSP de scripts.
3. H-06 y H-07: fijar las versiones de Python (`requirements.txt`) y las acciones por hash, y poner un tiempo límite a la corrida.
4. H-08: borradores de aviso legal, política de privacidad y términos de uso, ajustados a lo que la página hace de verdad. Los datos del responsable quedan marcados como **pendientes**.
5. H-11 y H-12: cargar el territorio y los ríos solo al usarlos, y agregar un `<h1>`.

**Requieren tu decisión o una credencial que solo tú puedes crear:**
- **D-01 · Netlify (H-02):**
  - **a)** publicar en Netlify una redirección a GitHub Pages: un solo despliegue, que gasta créditos de Netlify (recomendado);
  - **b)** borrar el sitio de Netlify: irreversible;
  - **c)** dejarlo como está.
- **D-02 · Horario confiable (H-03):** un disparador horario en el Worker de Cloudflare que ya existe (gratis), que pide a GitHub la corrida y avisa si los datos tienen más de 3 h. Necesita un token de GitHub de permisos mínimos (solo «Actions: write» sobre `vigia`). Tú lo creas y lo guardas como secreto en Cloudflare, sin pegarlo en el chat.
- **D-03 · Cabeceras de seguridad completas:** mover el sitio a Cloudflare Pages (gratis) o mantener GitHub Pages con las limitaciones descritas.
- **D-04 · Roles y Supabase (H-09, H-10):** pasar a 5 roles (superadministrador, administrador institucional, analista, operador y ciudadano) en el proyecto de pruebas, y revisar contigo en el panel los límites de intentos y de sesión.
- **Datos reales:** siguen pendientes las condiciones de la auditoría 3:
  - el titular del banco de datos (Ley 29733) y la autorización de la institución;
  - un proyecto en São Paulo con plan Pro (unos 25 USD al mes);
  - el almacenamiento de fotos (con costo y con una base legal).

**Libro de Reclamaciones (Ley 29571):** con el funcionamiento actual (servicio gratuito, sin venta ni contrato con el usuario), no parece haber una relación de consumo que lo exija. Debe confirmarlo un abogado antes de lanzar cualquier modalidad de pago o convenio.

## 5. Matriz de trazabilidad

| Problema | Evidencia | Criticidad | Solución | Archivo | Prueba | Estado |
|---|---|---|---|---|---|---|
| H-01 caudales y escenarios rotos | 400 en `flood-api` | Alta | Validar el punto de control | `recolectar.py`, `vigia.html` | Local con datos de producción: 200 | Corregido en desarrollo |
| H-02 Netlify desactualizado | Datos del 31/10 | Alta | Redirección (D-01) | — | — | Espera decisión |
| H-03 horario irregular | 9 h sin corridas, runner caído | Alta | Disparador en el Worker (D-02) y tiempo límite | `publicar.yml`, `nube/puente-peru.js` | — | Espera token |
| H-04 fuente caída invisible | Sin registro de errores | Media | Estado por fuente | `recolectar.py`, `vigia.html` | — | Pendiente |
| H-05 sin SRI | 0 `integrity` | Media | Bibliotecas propias | `construir.py`, `vigia.html` | — | Pendiente |
| H-06 Python sin versión fija | `pip install` libre | Media | `requirements.txt` | `publicar.yml` | — | Pendiente |
| H-07 acciones por etiqueta | `@v7` | Baja | Fijar hash | `.github/workflows/*` | — | Pendiente |
| H-08 sin documentos legales | No existen | Media | Borradores | nuevos `.html` | — | Pendiente |
| H-09 3 roles | Esquema | Media | 5 roles (D-04) | `nube/supabase/` | — | Espera decisión |
| H-10 sesión y límites de acceso | No verificable | — | Revisión en el panel | — | — | Espera decisión |
| H-11 carga inicial pesada | 1,6 MB comprimidos | Media | Carga diferida | `vigia.html` | — | Pendiente |
| H-12 sin `<h1>` | DOM | Baja | Agregarlo | `vigia.html` | — | Pendiente |
| H-13 METAR solo con proxy | Código | Baja | Proxy en el Worker (opcional) | `nube/puente-peru.js` | — | Pendiente |
