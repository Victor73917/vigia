# VIGÍA · mapa de diseño y criterio

Salida de la skill **taste**, medida sobre https://victor73917.github.io/vigia (1440×900 y 390×844, 3 nov 2026) y aplicada con **impeccable** (modo *Operate*: una herramienta de trabajo, no una página de venta) y **emil-design-eng** (movimiento y detalles).

## Mapa de diseño

| Token | Valor |
|---|---|
| Fondo | `--abismo #03060D`, mapa a pantalla completa |
| Paneles | vidrio `rgba(7,13,26,.84)` / `rgba(13,22,41,.92)` con desenfoque 10–16 px |
| Bordes | `--filo rgba(150,180,225,.15)`, `--filo-2 .30` |
| Texto | `#E8EDF5` · `#A9B6C9` · `#74839A` (≥ 4,5:1 sobre el fondo) |
| Control del usuario | ámbar sodio `#FFB547` (botón principal, foco, selección) |
| Niveles | rojo `#FF3B3B` · naranja `#FF9F1C` · amarillo `#FFD23F` · verde `#3DDC84` · rayado = sin datos |
| Títulos | Barlow Condensed 700 (20–34 px) |
| Texto y rótulos | Barlow 400/600; rótulos en mayúsculas a 11 px, espaciado .08em |
| Cifras | JetBrains Mono, siempre con `tabular-nums` |
| Escala | 10,5 (solo fechas de la línea de tiempo) · 11 · 12 · 13 · 14 · 15 · 16 · 18 · 20 · 22 · 24 · 28 · 32 · 34 · 52 |
| Radios | 2 (celdas) · 6–8 (botones) · 10–12 (tarjetas) · 14–18 (paneles) · 999 (chips) |
| Movimiento | `--ease-out cubic-bezier(.23,1,.32,1)` 140–250 ms; hoja del celular `--ease-cajon cubic-bezier(.32,.72,0,1)` 400 ms |

## Criterio (por qué)

**El color es del riesgo, no de la marca.** Rojo, naranja, amarillo y verde solo dicen nivel de peligro; el único color "propio" es el ámbar, y solo marca lo que el usuario controla. *Compromiso:* no hay color libre para decorar; la jerarquía sale del tamaño y el peso.

**Faltar datos nunca se ve como calma.** Lo que no tiene registro va rayado en gris, nunca en verde. *Compromiso:* el mapa se ve más "sucio" donde falta información, a propósito.

**Monoespaciada solo para cifras.** Horas, conteos, códigos y coordenadas van en JetBrains Mono para que se alineen; frases, fechas escritas y rótulos van en Barlow, que se lee mejor a 11 px. *Compromiso:* se pierde algo del aire de "consola"; se gana lectura en el celular.

**Nada por debajo de 11 px salvo la línea de tiempo.** Es una plataforma de emergencias que se mira en el celular, de noche y con prisa. *Compromiso:* entra menos texto por panel; se resolvió con desplazamiento, no achicando letra.

**El nivel se marca con borde y fondo teñidos, no con una franja lateral gruesa.** Una tarjeta roja es roja entera (`color-mix` al 45 % en el borde y 8 % en el fondo); en listas, un punto de 8 px. *Compromiso:* la franja se leía de reojo más rápido en listas largas; el punto y el teñido conservan esa lectura sin el recurso gastado.

**Cada toque responde y nada demora.** Los botones se hunden 3 % al tocarlos; los paneles entran desde donde se abrieron en ≤ 250 ms y los avisos se apilan en vez de taparse. Sin animaciones de carga ni coreografías: con "reducir movimiento" solo queda el fundido.
