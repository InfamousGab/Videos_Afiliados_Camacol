> **De dónde salen estos valores.** Camacol no tiene manual de marca para esta serie, así
> que todo lo de este documento se obtuvo **midiendo píxeles** de un capítulo ya terminado
> (`VIDEO ORIGINAL VERSION TERMINADA.mp4`, el de Segen FP): geometrías con detección de
> bordes, colores muestreando el fotograma, y tiempos con detección de escena.
>
> Las tipografías son la parte más frágil: se eligieron buscando el parecido más cercano
> entre las que trae macOS, **no porque sean las de la marca**. Si algún día aparece un
> manual oficial, este archivo y `FUENTES` en `scripts/build_assets.py` son los dos sitios
> que hay que cambiar.

# Línea gráfica de la serie

Todas las medidas son en píxeles sobre un cuadro de **1920x1080**. Están sacadas midiendo
sobre el capítulo de Segen FP Inversiones, que es el que fija el estándar. `build_assets.py`
las tiene codificadas; esta ficha existe para poder ajustarlas con criterio o reconstruir los
gráficos desde cero si hiciera falta.

## Paleta

| Uso | Valor |
|---|---|
| Azul institucional Camacol | `#1F4394` — rgb(31, 67, 148) |
| Tinta de las cenefas | `#1A1A1A` — casi negro, no azul |
| Fondo de las píldoras y cajas | blanco puro, opaco |
| Barra inferior del lower third | `#1C1C1C` al 96 % |

## Tipografías

Todas del sistema macOS, no hay que instalar nada.

| Elemento | Fuente | Tamaño |
|---|---|---|
| Título de la intro | Avenir Next **Heavy** (índice 8 del .ttc) | 66 |
| «AFILIADO A:» | Avenir Next Heavy | 44 |
| Texto de cenefa | Helvetica Neue **Medium** (índice 10) | 44 |
| Nombre del vocero | Avenir Next Condensed **Heavy** (índice 8) | 76 |
| Cargo del vocero | Avenir Next Condensed **Demi Bold** (índice 2) | 44 |
| Handles de redes | Helvetica Neue **Bold** (índice 1) | 36 |

## Geometría

**Caja de logos** (presente durante todo el cuerpo, nunca sobre la intro ni la cortinilla)
- 600x158, colocada en `x=-30, y=64`. Sangra por el borde izquierdo: solo se redondean las
  esquinas derechas, radio 26.
- Logo Camacol Santander a la izquierda, caja de 230x108 desde `x=46`.
- Logo del afiliado a la derecha, caja de 262x116 desde `x=330`. Ambos centrados en vertical.

**Cenefa de pregunta** (píldora blanca, una por bloque)
- Borde inferior siempre en `y=1006`; la altura la define el texto, así que el `y` de la
  superposición se calcula como `1006-h`.
- Sangra por la izquierda igual que la caja de logos: `x=-30`, radio 26.
- Texto a 39 px del borde izquierdo del cuadro, interlínea 52, 20 px de aire arriba y abajo.
- Pestaña azul asomando por detrás del borde derecho: 62 px de ancho, radio 16.
- Con estas medidas, una pregunta de dos líneas da una píldora de ~132 px de alto, que es lo
  que mide en el capítulo de referencia.

**Lower third** (una sola vez, sobre el primer bloque)
- 1320x132 en `x=96, y=902`.
- Banda superior de 76 px, blanca, con degradado a transparente en los 150 px de la izquierda
  y los 260 de la derecha. Encima el nombre en condensada oscura.
- Banda inferior oscura desde `x=100` hasta `x=1120`, con el cargo en blanco.
- Dos paralelogramos azules inclinados cierran el extremo derecho.

**Tarjetas de redes** (sobre el bloque de cierre)
- Icono de 132 px + píldora blanca con el handle, radio 47.
- Facebook en `x=1268, y=668`; Instagram en `x=1268, y=843`. Entran deslizándose desde la
  derecha, Instagram 0.45 s después que Facebook.

**Placa de intro**
- Fondo: `assets/fondo-edificios.png` (vertical 1080x1920) escalado a 1920 de ancho y
  recortado desde `y=900`, con `colorlevels=rimax=0.75:gimax=0.78:bimax=0.85`.
- «AFILIADOS QUE CONSTRUYEN» en `y=62`, «HISTORIAS DE ÉXITO» en `y=146`, ambas centradas.
- Tarjeta blanca de 520x292 en `y=300`, radio 30, con el logo del afiliado centrado dentro
  (caja de 430x232).
- «AFILIADO A:» en `y=688` y el logo Camacol blanco en `y=782` (caja de 310x210).
- Dura 3 s, con fundido de entrada de 0.5 s y un zoom lentísimo del 2.5 %.

**Cortinilla**
- El archivo original es vertical 1080x1920 y muda. Se recorta `crop=1080:608:0:624` (la banda
  central, donde está el logo) y se escala a 1920x1080.
- Si algún día aparece la versión horizontal nativa, cámbiala en `proyecto.json` con la clave
  `cortinilla` y quita el recorte de `render.py`.

## Tiempos

| Gráfico | Entra | Dura |
|---|---|---|
| Caja de logos | con el cuerpo | todo el cuerpo |
| Cenefa | 0.9 s después de arrancar su bloque | 5.4 s (una línea) / 6.9 s (dos líneas) |
| Lower third | 9.0 s desde el inicio del cuerpo | 6.2 s |
| Tarjetas de redes | 1.6 s después de arrancar el bloque de cierre | hasta 0.8 s antes del final |

Las entradas y salidas son deslizamientos: 0.42 s para entrar, 0.32 s para salir, desde fuera
de cuadro por el lado que corresponda.

La cenefa entra 0.9 s tarde a propósito: si aparece a la vez que el corte, compite con el
arranque de la frase y las dos cosas se leen peor.

## Las preguntas de la serie

Las que se han usado hasta ahora, en orden. Confirma con quien encargue el capítulo si este
afiliado responde las mismas — el salto de línea es parte de la redacción, porque define cómo
se parte la cenefa en dos renglones.

1. `¿Cómo inicia <AFILIADO>?`
2. `¿En dónde se encuentran sus sedes?`
3. `¿Cuál consideran es su mayor diferencial\nrespecto a la competencia dentro del sector?`
4. `¿Cómo han evolucionado sus proyectos para\nresponder a las necesidades del mercado?`
5. `¿Qué impacto ha tenido su afiliación a Camacol\nSantander en su estrategia de negocio?`

Y el bloque de cierre, sin cenefa: el vocero dice dónde encontrarlos en redes, y ahí entran
las tarjetas de Facebook e Instagram.

## Estructura del capítulo

```
0:00  placa de intro (3 s)
0:02.6  bloque 1 — cenefa 1, y a los 9 s el lower third con nombre y cargo
        bloque 2 — cenefa 2
        bloque 3 — cenefa 3
        bloque 4 — cenefa 4
        bloque 5 — cenefa 5
        cierre    — tarjetas de redes
        cortinilla Camacol (3.7 s)
2:05-2:09
```

Un capítulo dura entre 2:00 y 2:10. Los capítulos anteriores rondan 2:01-2:09.


## Tomas auxiliares (planos de apoyo)

Medido sobre `VIDEO ORIGINAL VERSION TERMINADA.mp4` con detección de escena
(`select='gt(scene,0.25)'`):

| Entra | Sale | Dura | Qué muestra |
|---|---|---|---|
| 27.07 | 32.07 | 5.0 s | aérea de la obra, casas en construcción |
| 53.43 | 59.03 | 5.6 s | suelo y movimiento de tierras |
| 62.40 | 68.47 | 6.1 s | aérea del terreno |
| 87.13 | 95.00 | 7.9 s | aérea de la zona verde |

Tres cosas que fija ese patrón:

- **Corte seco**, sin disolvencia. Los saltos marcan 0.47–0.72 de score de escena en un solo
  fotograma; una disolvencia repartiría valores bajos entre varios.
- **Entre 5 y 8 segundos** por inserto.
- **La caja de logos se mantiene encima** del plano de apoyo. Las cenefas y el rótulo también,
  aunque en el capítulo de referencia nunca coinciden con un inserto.

Nunca hay tomas de apoyo sobre el rótulo del nombre ni sobre el cierre de redes: en esos
momentos la vocera está en pantalla.
