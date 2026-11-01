# VIGÍA PERÚ 3.0 — Fase 1: auditoría y propuesta de nube

Fecha: 31 de octubre de 2026 (noche, hora de Lima).
Versión auditada: https://victor73917.github.io/vigia (commit 55e6ece, rama `main`).
Esta auditoría continúa la de [AUDITORIA-FASE1.md](AUDITORIA-FASE1.md); aquí solo va lo que se comprobó de nuevo y lo que pide el documento 3.0.

---

## 1. Qué existe hoy (comprobado)

| Componente | Estado | Cobertura | Cómo se comprobó |
|---|---|---|---|
| Página pública (GitHub Pages) | Funciona | — | Abierta en el navegador; 16 corridas de GitHub Actions, las 14 últimas con éxito |
| Mapa 2D/globo MapLibre | Funciona | Todo el Perú | 17 departamentos, 4 provincias y 8 distritos encuadrados dentro del área libre (prueba automática, abajo) |
| Índice territorial INEI (UBIGEO) | Funciona | 25 dep., 196 prov., 1 873 distritos, 127 681 centros poblados | `datos/territorio.json` y `datos/ccpp.json` |
| URL `?lugar=UBIGEO` | Funciona | Todo el Perú | `?lugar=140203` abre Incahuasi (Ferreñafe, Lambayeque) encuadrado |
| Desambiguación de homónimos | Funciona | Todo el Perú | «San Jerónimo» → pide elegir entre 3 |
| Pronóstico de 5 días por punto | Funciona | Cualquier punto | 7 modelos de Open-Meteo, en vivo desde el navegador |
| Avisos meteorológicos SENAMHI | Funciona **solo con la PC encendida** | Nacional | La PC los sube a la rama `datos-peru` |
| Activación de quebradas SENAMHI | Funciona **solo con la PC encendida** | Nacional (1 059 distritos en el aviso vigente) | Igual |
| Comunicado ENFEN | Resumen escrito a mano + número automático | — | `ENFEN_RESUMEN` en `recolectar.py` |
| Emergencias INDECI (30 días) | Funciona desde GitHub | Nacional (45 emergencias hoy) | Corrida horaria |
| Índices El Niño (ONI, Niño 1+2/3.4, alisios, contenido de calor, SOI) | Funciona desde GitHub | Pacífico | Corrida de 6 h |
| Caudales GloFAS + ensamble | Funciona desde GitHub | **Solo 20 ríos del norte** | Corrida de 6 h |
| Prioridad por distrito, salud, colegios | Funciona | **Solo 326 distritos de 5 dep. del norte** | `zona` en la instantánea |
| Pronóstico de 32 ciudades | Funciona | Capitales del Perú + Guayaquil | `clima` |
| METAR/TAF | Funciona | **Solo 6 aeródromos del norte** | `aerodromos` |
| Analista con IA | **No funciona en la web pública** | — | Solo se activa dentro de Claude (`window.claude`); en GitHub Pages la pestaña se oculta |
| Reportes ciudadanos, usuarios, roles, incidencias, recursos, misiones | **No existen** | — | No hay backend |

### Estado de las fuentes en la última corrida de GitHub (1 nov 00:09 UTC)

| Fuente | Resultado desde GitHub |
|---|---|
| Open-Meteo (clima, multimodelo, conjunto, ensamble, ríos Ecuador) | Responde |
| NOAA CPC (ONI, Niño, océano) | Responde |
| INDECI, aviationweather.gov, NASA GIBS, GDACS | Responden |
| SENAMHI GeoServer (`zona`, `cuencas`) | **No responde** (datos del 27 y 31 de octubre, de la PC) |
| ECMWF GRIB (`ecmwf`) | **Falla**, causa por revisar en el registro de la corrida |
| SENAMHI avisos y quebradas, ENFEN | Llegan desde la PC |

---

## 2. Hallazgo clave: el SENAMHI no bloquea por país, sino por red

Prueba real del 31 de octubre con check-host.net: se pidió `idesep.senamhi.gob.pe/geoserver` desde 40 servidores de distintos países.

- **Responde desde 17:** São Paulo, Vancouver, Frankfurt, Barcelona, Hong Kong, Yakarta, Mumbai, Milán, Tokio, Varsovia, Atlanta y otros.
- **No responde desde 23:** Los Ángeles, Nueva York, Londres, París, Singapur y otros.
- **ENFEN** respondió desde todos los servidores probados. El fallo de DNS de la corrida #4 fue pasajero.

**Conclusión:** el bloqueo depende de la red del servidor, no del país. Por eso un servicio en la nube distinto de GitHub Actions *puede* llegar al SENAMHI. Hay que probarlo con el proveedor elegido antes de apagar la tarea de la PC. Este es el camino para cumplir el requisito 39 («la PC no debe ser servidor»).

---

## 3. Pruebas de navegación ejecutadas (sitio publicado, 31 oct)

Se ejecutaron en el navegador integrado con el gancho `?prueba`.

**Departamentos (17):** Piura, Tumbes, Lambayeque, La Libertad, Áncash, Lima, Ica, Arequipa, Cajamarca, Amazonas, San Martín, Loreto, Ucayali, Cusco, Puno, Callao y Madre de Dios.
- Resultado: los 17 quedan **dentro** del área libre del mapa. Ningún caso aleja la vista al planeta.

**Provincias:** Chiclayo, Maynas, Huancayo y Arequipa. Todas quedan dentro.

**Distritos:** La Unión (Piura), Iquitos, Juliaca, Tarapoto, Yarinacocha, Chachapoyas y San Jerónimo. Todos quedan dentro, y la URL cambia al UBIGEO correcto.

**Centro poblado:** «Pedregal, Piura» devuelve 7 resultados del INEI, y el primero es Pedregal de Catacaos.

| Caso | Resultado |
|---|---|
| «nazca» como distrito | **Falla**: el INEI lo escribe «NASCA» y no hay sinónimos |
| «lambayeke», «piurra», «chiclallo» | **Falla**: muestra la tarjeta genérica «Zona norte» en lugar de sugerir el lugar correcto |
| «cuzco» | **Falla**: ofrece centros poblados llamados Cuzco, no el departamento de Cusco |
| `?lugar=999999` (código inexistente) | Va a la vista nacional **sin avisar** que el código no existe |
| Vista inicial | Centrada en el norte (lat −6,2, 1 460 km), **no en todo el Perú** |

**Peso de la carga inicial:** unos 1,4 MB comprimidos. Luego llegan 2 MB del índice territorial y, al buscar, 5,3 MB de centros poblados. Es aceptable en wifi y pesado con datos móviles débiles.

---

## 4. Matriz de problemas

| ID | Problema | Gravedad | Fase |
|---|---|---|---|
| A-01 | Avisos y quebradas del SENAMHI dependen de la PC encendida | **Crítica** (requisito 39) | Nube |
| A-02 | No hay backend: imposible recibir reportes, autenticar ni guardar incidencias de forma segura | **Crítica** para fases 6–7 | Nube |
| A-03 | Prioridad, caudales, salud, colegios y METAR solo cubren el norte | Alta (requisito 3) | 4–5 |
| A-04 | La vista inicial muestra el norte, no el Perú | Media | 2 |
| A-05 | La búsqueda no tolera errores de escritura ni nombres alternativos (Nazca/Nasca, Cuzco/Cusco) | Alta | 2 |
| A-06 | Un UBIGEO inválido en la URL no avisa | Baja | 2 |
| A-07 | Falta el botón «Volver a mi localidad» y el historial de lugares | Media | 2 |
| A-08 | El analista IA no funciona fuera de Claude | Alta (fase 8) | 8 |
| A-09 | ECMWF falla desde GitHub | Media | 2 |
| A-10 | El resumen del ENFEN se actualiza a mano | Media | 5 |
| A-11 | No hay entorno de pruebas: todo cambio en `main` se publica directo | **Alta** (el documento pide no tocar producción sin verificar) | 2 |
| A-12 | No hay tarjetas nacionales filtrables (avisos por departamento, ríos sobre umbral, etc.) | Alta | 3 |
| A-13 | No hay modo claro, y la navegación con teclado y la accesibilidad están incompletas | Media | 3 |
| A-14 | No hay política de seguridad de contenido (CSP). GitHub Pages no permite cabeceras; se puede usar `<meta>` | Media | 9 |
| A-15 | Hay 91 usos de `innerHTML` y 131 de `esc()`. Una muestra no mostró inyección de datos externos sin escapar, pero falta revisarlos todos | Media | 9 |
| A-16 | Capas nacionales pendientes: vulnerabilidad CENEPRED, vías MTC/Provías, SONICS por centro poblado. Su licencia y su acceso no están verificados | Alta | 5 |
| A-17 | No hay rayos ni radar. No existe una fuente pública abierta para el Perú confirmada; la página debe decirlo, no simularlo | Informativa | 5 |

---

## 5. Arquitectura en la nube propuesta

### Principio

GitHub Pages solo sirve la parte **pública**: mapa, avisos, pronósticos y El Niño. Todo lo privado va a un backend gestionado: reportes, DNI, incidencias, recursos, misiones y usuarios. Ningún dato personal toca GitHub.

```
Ciudadano / Operador
      │ HTTPS
      ▼
GitHub Pages (página pública, sin datos personales)
      │                       │
      │ datos públicos        │ API con sesión (JWT)
      ▼                       ▼
instantanea.js        Supabase (São Paulo)
(GitHub Actions)        ├─ PostgreSQL + PostGIS: incidencias, recursos, misiones, auditoría
      ▲                 ├─ Auth: usuarios, roles, MFA para operadores
      │                 ├─ Storage privado: fotos (enlaces temporales firmados)
      │                 ├─ Edge Functions: validar reportes, analista IA (clave como secreto)
      │                 └─ Cron (pg_cron): limpieza, retención, alertas internas
      │
Recolector del SENAMHI en la nube (reemplaza la tarea de la PC)
  opción A: Cloudflare Worker con cron (gratis; hay que probar si llega al SENAMHI)
  opción B: VM gratuita en São Paulo o Santiago (Oracle Cloud Always Free)
```

### Comparación de proveedores (precios aproximados; verificarlos en la página oficial al contratar)

| Necesidad | Opción recomendada | Plan gratuito | Plan de pago | Por qué |
|---|---|---|---|---|
| Página pública | **GitHub Pages** (ya en uso) | Gratis | — | Funciona, despliegue automático, HTTPS |
| Recolección programada | **GitHub Actions** (ya en uso) | Gratis en repositorio público | — | Ya corre cada hora y cada 6 h |
| Recolector del SENAMHI | **Cloudflare Worker** (prueba) → si no llega, **VM en São Paulo** | Workers: unas 100 000 solicitudes al día | — | São Paulo respondió en la prueba de red |
| Base de datos + autenticación + archivos | **Supabase** (región São Paulo) | 500 MB de base, 1 GB de archivos, 50 000 usuarios al mes; **se pausa tras 7 días sin uso; sin copias de seguridad** | Pro: unos **25 USD al mes**, con copias diarias y sin pausa | PostGIS, RLS (permisos por fila y jurisdicción), MFA y almacenamiento privado en un solo servicio |
| Analista IA | API de Claude desde una Edge Function | — | Pago por consulta; lo calculo con el precio vigente antes de activarlo | La clave nunca va al navegador |
| Monitoreo | Alertas de GitHub Actions + tabla de estado de fuentes | Gratis | — | Ya existe el «estado» por fuente |

**Costo estimado**
- **Piloto sin datos personales reales:** 0 USD al mes, con Supabase gratuito. Sirve para pruebas, no para producción: se pausa y no tiene copias de seguridad.
- **Piloto con reportes ciudadanos reales:** unos 25 USD al mes (Supabase Pro), más la IA según su uso.
- **Plataforma institucional:** de 100 a 600 USD al mes o más. Incluye Supabase Team o un PostgreSQL gestionado, almacenamiento con retención legal, monitoreo 24/7 y un dominio `.gob.pe`. Requiere contrato y un responsable institucional.

### Separación de ambientes

- Rama `desarrollo` → publicada en un segundo sitio de pruebas (repositorio `vigia-pruebas` o Cloudflare Pages), con un proyecto Supabase de pruebas y **datos ficticios marcados**.
- Rama `main` → producción. Solo recibe cambios que pasaron las pruebas automáticas (una prueba de navegador en GitHub Actions con las 17 localidades de arriba).

---

## 6. Requisitos legales que no puede resolver el código

1. **Ley 29733 (protección de datos personales).** Un banco de datos con nombres, DNI o teléfonos necesita:
   - un **titular** identificado (una persona o una institución),
   - una política de privacidad y consentimiento,
   - su **inscripción ante la Autoridad Nacional de Protección de Datos Personales** (Ministerio de Justicia).

   Hay que definir quién es el titular antes de recibir reportes reales.
2. **Verificar el DNI con RENIEC** solo es posible mediante un convenio institucional. Recomendación para el piloto: **no pedir DNI**. Basta con un teléfono opcional y la verificación por llamada del operador. El requisito 22 permite reportar sin registro.
3. **Uso operativo militar.** Un centro de comando con misiones y recursos reales debe contar con la autorización de la institución. El sistema se puede construir y probar con datos ficticios, pero ponerlo en servicio es una decisión del mando.
4. **No sustituye canales oficiales.** El portal ciudadano mostrará siempre los números de emergencia oficiales (105 Policía, 116 Bomberos, 106 SAMU; por confirmar antes de publicar) y el aviso de que no reemplaza al COEN ni al INDECI.

---

## 7. Plan de ejecución propuesto

| Paso | Contenido | Necesita de ti |
|---|---|---|
| 1 | **Entorno de pruebas** (rama `desarrollo` + sitio de pruebas + prueba automática de navegación) | Nada (lo hago en tu repositorio) |
| 2 | **Estabilización:** vista inicial del Perú, búsqueda tolerante (Nasca/Nazca, errores de escritura), aviso de UBIGEO inválido, «Volver a mi localidad», historial, ECMWF | Nada |
| 3 | **Recolector del SENAMHI en la nube** y retiro de la tarea de la PC | Crear una cuenta gratuita de Cloudflare (tú inicias sesión; yo no manejo contraseñas) |
| 4 | **Rediseño del tablero** (tarjetas nacionales filtrables, modo claro/oscuro, franja temporal) | Nada |
| 5 | **Cobertura nacional del análisis** (ríos GloFAS y prioridad para los 1 873 distritos, comparación de localidades) | Nada |
| 6 | **Backend Supabase** + centro de comando con datos ficticios en el entorno de pruebas | Crear el proyecto Supabase y pegar las claves en *GitHub → Settings → Secrets*, nunca en el chat |
| 7 | **Portal ciudadano** (sin DNI en el piloto) | Definir el titular de los datos y aprobar el plan Pro antes de recibir reportes reales |
| 8 | **Analista IA** en la web pública | Clave de la API de Claude como secreto, más un límite de gasto |
| 9 | **Validación** (pruebas integrales, seguridad, móvil) y publicación controlada | Tu aprobación para pasar a producción |

---

## 8. Resultado de la fase 2 (estabilización), 31 de octubre de 2026

**Objetivo:** corregir la navegación y la búsqueda sin tocar la versión publicada, y crear el entorno de pruebas.

**Dónde verlo:** https://victor73917.github.io/vigia/pruebas/ (rama `desarrollo`, con la marca «Entorno de pruebas»). Producción, en https://victor73917.github.io/vigia/, sigue con el código anterior.

| Problema | Solución | Archivo |
|---|---|---|
| A-04 vista inicial en el norte | La página arranca y encuadra todo el Perú | `vigia.html` |
| A-05 búsqueda sin tolerancia | Nombres alternativos (Nazca→Nasca, Cuzco→Cusco) y tarjeta «¿Quisiste decir…?». Compara cómo suena (qu/k, c/s, z/s, v/b, ll/y/i, h muda) y admite 1 letra de diferencia hasta 7 letras y 2 desde 8 | `vigia.html` |
| A-06 UBIGEO inválido | Aviso «El código UBIGEO … no existe en el índice del INEI» y vista nacional | `vigia.html` |
| A-07 sin regreso ni historial | Botones «Mi lugar» y «Recientes» (10 últimos lugares, guardados solo en el navegador). Escape y clic fuera cierran la lista | `vigia.html` |
| Mapa angosto en pantallas de 1024 px | Con los dos paneles abiertos el mapa quedaba en 334 px. Ahora el izquierdo se pliega solo si quedan menos de 520 px (pasa a 694 px) y vuelve al cerrar el derecho; no cambia la preferencia guardada | `vigia.html` |
| «Emergencias en Tumbes» preguntaba cuál Tumbes | Va directo al departamento | `vigia.html` |
| A-11 sin entorno de pruebas | Rama `desarrollo` → `/pruebas/`, sin indexar. Un cambio en desarrollo corre la prueba automática y, si pasa, pide a main que publique | `.github/workflows/publicar.yml`, `construir.py` |
| — | Prueba automática: Chromium sin ventana, 27 lugares de todas las regiones, un centro poblado, 7 errores de escritura y un UBIGEO inválido | `pruebas/navegacion.py` |

**Pruebas ejecutadas**

1. **Navegador local, 1024×768 y diseño de celular**
   - 22 lugares: 17 departamentos, provincias y distritos de costa, sierra y selva. Los 22 quedan dentro del área libre.
   - Vista inicial: el Perú entero, con 86 % del ancho libre.
   - «lambayeke», «arekipa», «huancaio», «nazka», «kusko», «chiclallo», «moyobanba» y «tarapotto» ofrecen el lugar correcto.
   - Las consultas de ejemplo («¿Dónde atender primero?», «Río Piura», «Provincia de Sullana») siguen funcionando igual.
2. **GitHub Actions, corrida #19:** `pruebas/navegacion.py` terminó sin fallas.
3. **Sitio publicado `/pruebas/?lugar=999999`:** muestra el aviso y la vista nacional.

**Limitaciones**
- La tolerancia a errores cubre departamentos, provincias y distritos. En centros poblados solo funciona la coincidencia exacta o por el comienzo del nombre.
- «Puerto Maldonado» con error de escritura no se sugiere, porque no es un distrito (el distrito es Tambopata).
- La prueba automática no cubre todavía el celular ni el globo 3D.

**Para pasar a producción:** unir `desarrollo` en `main` (`git merge desarrollo` y `git push`). El flujo publica solo.
