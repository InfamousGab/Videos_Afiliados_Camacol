# Trampas de ffmpeg en este flujo

Todas están ya resueltas dentro de los scripts. Están documentadas porque cada una costó un
render entero, y porque son silenciosas: ffmpeg termina con código 0 y el resultado sale mal.

## 1. El desfase A/V que se acumula corte a corte

**Síntoma**: al final del montaje el labial va corrido ~0.3 s. Los primeros segmentos se ven
bien, así que es fácil no notarlo hasta el final.

**Causa**: al cortar con `-ss X -t D`, el video sale con un número entero de fotogramas
(D redondeado a 1/30) pero el audio sale con la duración exacta pedida. Cada intermedio queda
con unos milisegundos de audio de más. Las cadenas de `xfade` (video) y `acrossfade` (audio)
son independientes, así que esas sobras se suman: con 20 segmentos, ~0.28 s.

**Solución**: forzar ambas pistas a la misma medida exacta en fotogramas.

```
nf = round((salida - entrada) * 30);  d = nf / 30
-frames:v {nf}
-af "...,atrim=0:{d},apad=whole_dur={d},asetpts=N/SR/TB"
```

Con esto la diferencia final baja a un fotograma. Para comprobarlo, cuenta fotogramas y
compara con la duración del audio:

```bash
ffmpeg -i cuerpo.mov -map 0:v -f null - 2>&1 | tail -1   # frame= N  → N/30 s
ffmpeg -i cuerpo.mov -map 0:a -f null - 2>&1 | tail -1   # time=...
```

## 2. Las imágenes entran a 25 fps

**Síntoma**: la placa de intro dura 2.5 s en vez de 3, y como los offsets del montaje final
se calculan con 3, la cortinilla se queda fuera del video sin ningún error.

**Causa**: `-loop 1 -t 3 -i imagen.png` usa el framerate por defecto de la demuxer de
imágenes, que es 25. Son 75 fotogramas, que a 30 fps duran 2.5 s.

**Solución**: `-loop 1 -framerate 30 -t 3 -i imagen.png`.

**Y además**: nunca calcules los offsets del montaje con las duraciones nominales. Mide los
tres bloques con `dur_real()` justo antes de montar. Si un bloque no mide lo esperado, el
`xfade` con un offset mayor que la duración disponible no falla: simplemente no ocurre.

## 3. `zoompan` usa `zoom`, no `z`, en las expresiones de x/y

`x='iw/2-(iw/z/2)'` da `Undefined constant or missing '(' in 'z/2)'`. La variable se llama
`z` solo dentro del parámetro `z`; en `x` e `y` es `zoom`:

```
zoompan=z='min(1.0+0.025*on/90,1.025)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30
```

Escala la imagen bastante por encima del destino antes del `zoompan` (a 3840 de ancho): el
filtro trabaja sobre el original y sin margen el zoom se ve pixelado.

## 4. Crossfade de audio contra pistas mudas

La intro y la cortinilla no tienen audio. Un `acrossfade` contra silencio no es una
transición: es un fundido sobre la voz, y se lleva la primera palabra del cuerpo y la última
antes del cierre.

**Solución**: el video disuelve, el audio se concatena.

```
[0:a]atrim=0:{off1},asetpts=PTS-STARTPTS[a0];
[1:a]afade=t=out:st={d_cuerpo-0.2}:d=0.2[a1];
[2:a]atrim=0:{d_cort-X},asetpts=PTS-STARTPTS[a2];
[a0][a1][a2]concat=n=3:v=0:a=1[aout]
```

Los recortes están calculados para que el audio total mida exactamente lo mismo que el video
con sus dos disolvencias.

## 5. `loudnorm` en una sola pasada bombea

En una pasada, `loudnorm` va corrigiendo sobre la marcha y la voz respira de forma audible.
Hay que medir primero sobre el material completo y luego aplicar con los valores medidos y
`linear=true`:

```bash
ffmpeg -i cuerpo.mov -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=summary -f null -
# → measured_I, measured_TP, measured_LRA, measured_thresh
```

Objetivo **-16 LUFS / -1.5 dBTP**, que es lo que esperan YouTube, Instagram y LinkedIn.

Al parsear ese resumen, busca las cuatro claves por nombre exacto. La cabecera del archivo
(`Input #0, mov,mp4,m4a,...`) también empieza por `Input` y no trae valor, así que un filtro
por prefijo se traga esa línea y revienta al partirla. Es un fallo que aparece **después** de
montar el cuerpo, o sea diez minutos de render tirados.

## 6. No hay `ffprobe` en esta máquina

Solo está el binario `ffmpeg` de evermeet en `~/.local/bin`. Para las duraciones:

- exactas, de material CFR: contar fotogramas con `-map 0:v -f null -` y dividir entre 30;
- aproximadas: parsear la línea `Duration:` de `ffmpeg -i`.

`comun.py` tiene las dos (`dur_real` e `info_media`).

## 7. Las imágenes como superposición no necesitan `-loop`

Un PNG de un solo fotograma sirve como superposición permanente sin `-loop 1`, porque
`overlay` tiene `eof_action=repeat` por defecto y repite el último fotograma. Usar `-loop 1`
en varias entradas a la vez obliga a andar poniendo `shortest` y es fácil truncar el montaje
sin querer.

## 8. Comas dentro de las expresiones de `overlay`

Una expresión como `min(a,b)` dentro de `x='...'` rompe el parseo del filtergraph, porque la
coma separa filtros. Hay que escaparla como `min(a\,b)`. Cuando la cadena crece, es más
seguro escribir el grafo a un archivo y pasarlo con `-/filter_complex archivo`, que es lo que
hacen los scripts. **No uses `-filter_complex_script`**: ffmpeg 9 la eliminó, y fue lo primero
que se rompió al probar la skill con el ffmpeg del paquete. `-/opción archivo` funciona desde
ffmpeg 7.

## 9. Whisper miente en los tiempos de palabra

Los timestamps por palabra de `whisper-large-v3-turbo` se desvían, a veces mucho: en el
capítulo de Segen FP situó «apartamentos» entre 12.84 y 13.11 s cuando en realidad la palabra
terminaba cerca de 13.7. Cortar confiando en ese dato parte la palabra.

Los timestamps sirven para **encontrar** los puntos de corte, no para confirmarlos. La
confirmación es `verificar.py`: volver a transcribir el montaje y comparar. Y cuando algo
suene raro, la prueba directa es extraer ese trozo del original y del montaje y transcribir
los dos por separado — la diferencia salta enseguida.

## 10. Si una toma sale casi vacía en la transcripción

A veces whisper devuelve dos segundos de texto para una toma de treinta. No es que no haya
audio: comprueba con `silencedetect` que hay voz, y reintenta sobre el audio normalizado.

```bash
ffmpeg -i toma.wav -af "silencedetect=noise=-35dB:d=0.6" -f null -
ffmpeg -i toma.wav -af "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11" -ar 16000 -ac 1 norm.wav
```

`transcribir.py` ya hace este reintento solo cuando la cobertura es menor que la mitad de la
toma.


## Colocar un inserto en su sitio de la línea de tiempo

Para tapar la imagen entre los segundos T y T+D con otra toma, lo intuitivo es desplazar los
PTS del inserto (`setpts=PTS-STARTPTS+T/TB`) y taparlo con `overlay ... enable`. No funciona
bien: mientras la segunda entrada todavía no ha empezado, `overlay` no tiene fotograma que
componer y el comportamiento depende de la versión.

Lo que sí funciona es rellenar el principio del inserto con negro hasta su posición:

    [1:v]fps=30,<encaje>,tpad=start_duration=23.2:start_mode=add:color=black[x1];
    [0:v][x1]overlay=0:0:eof_action=pass:enable='between(t,23.2,28.2)'[vout]

El relleno negro nunca se ve porque `enable` solo deja pintar dentro de la ventana, y
`eof_action=pass` evita que el flujo principal se corte cuando el inserto se acaba.

## `Duration: N/A` en imágenes fijas

`ffmpeg -i foto.png` responde `Duration: N/A, bitrate: N/A`. Cualquier parser que haga
`split(":")` sobre eso revienta con `ValueError`. `info_media()` lo captura y devuelve
`None`, que es además la forma de distinguir una imagen de un video sin mirar la extensión.

## Una foto fija dura menos de lo que pides

Igual que con la placa de intro: una imagen entra a 25 fps si no se le dice otra cosa. Para un
inserto de 4.5 s hay que pasar `-loop 1 -framerate 30 -t 4.5` **antes** del `-i`. Y para que
no parezca un cuadro congelado, `zoompan` con `d=1` sobre el material ya escalado al doble:
si se hace `zoompan` sobre 1920x1080 directamente, el acercamiento ablanda la imagen.


## La peor de todas: `xfade` obliga a sacrificar contenido

`xfade=duration=0.2` **no inserta** una disolvencia: solapa los últimos 0.2 s del primer clip
con los primeros 0.2 s del segundo, y el resultado dura 0.2 s menos. Aplicar el equivalente al
audio (`acrossfade=d=0.2`) parece lo natural para que no se descuadre el labial, y es un error
grave: se come el final de una palabra y el arranque de la siguiente, y además los mezcla. El
montaje suena tajado en cada empalme.

Ningún editor monta así. En una mesa de montaje la disolvencia se alimenta de **material
sobrante fuera del corte** —las colas o *handles*—, no del contenido.

La forma correcta:

1. Sacar cada intermedio con `COLA/2` de más por cada lado: `[entrada - 0.1, salida + 0.1]`.
2. Encadenar los `xfade` de 0.2 s sobre esos clips alargados. El total queda
   `suma(contenido) + COLA`, con media cola sobrante al principio y al final.
3. Recortar esa media cola: `trim=start=COLA/2:duration=suma(contenido)`.
4. Montar el audio aparte: de cada clip se toma solo `[COLA/2, COLA/2 + contenido]` y se
   concatenan con `concat`, con un `afade` de 8 ms en cada borde contra el chasquido.

Imagen y audio suman exactamente lo mismo, el labial no se corre, y el contenido sale entero.

## Las marcas de palabra de whisper se adelantan al final real

Whisper da «1972.» por terminada en 17.14 s cuando la voz sigue sonando hasta 17.61. Colocar
un corte «0.22 s después de que acabe la palabra» según whisper cae **dentro** de la palabra.

No se puede confiar en esas marcas para cortar: hay que medir energía (`scripts/audio_util.py`)
y buscar dónde calla la voz de verdad. `scripts/ajustar_cortes.py` hace ese reajuste sobre un
`proyecto.json` ya escrito.

Y ojo con verificar esto transcribiendo: whisper sigue reconociendo «nacional» aunque le falte
la última sílaba, así que la comparación de texto da el montaje por bueno. La comprobación
buena es comparar la envolvente de energía del montaje contra la de la toma original
(`verificar.py`, sección de empalmes): tiene que dar parecido ~1.00 y desfase 0.00.

## El MP4 final lleva ~30 ms de retardo de audio que no es tuyo

Medido contra las tomas, el MP4 con audio AAC sale 0.03 s desplazado, y `cuerpo.mov` en PCM
sale a 0.000. Es el retardo de arranque del codificador AAC, va señalado en el contenedor y
los reproductores lo compensan. Por eso las comprobaciones de energía se hacen contra
`cuerpo.mov`, no contra el MP4: si no, salen 30 ms de desfase en todos los segmentos y parece
un error de montaje.


## Los nombres de archivo con tilde no casan (NFC vs NFD)

macOS guarda «1-Cómo Inicia.mp4» con la tilde **descompuesta** (o + acento combinante, NFD),
mientras que el mismo nombre escrito en un JSON viene **compuesto** (ó, NFC). Son cadenas
distintas para Python, así que un `dict[nombre_de_archivo]` falla en silencio para toda toma
con acento en el nombre.

Costó una revisión entera: tres segmentos de un capítulo salieron «sin palabras» y el revisor
de sentido los dio por buenos sin haber mirado nada. Se normaliza con
`unicodedata.normalize("NFC", nombre)` en las dos puntas (`palabras.nfc`).

## Un valle de 50 ms no es un final de frase, pero sí una frontera de palabra

`fin_de_habla` exige 120 ms de silencio para dar una frase por terminada, porque huecos más
cortos suelen ser la oclusión de una /p/ o una /t/. Correcto para buscar el final de una
idea, y desastroso para cortar entre dos palabras encadenadas, donde el hueco real es de
30–60 ms: se salta la frontera y arrastra la palabra siguiente.

Por eso hay dos buscadores. `valle()` encuentra huecos de 30 ms, pero **solo funciona
guiado**: se le pasa el instante donde whisper cree que acaba la palabra y devuelve el valle
más cercano. A ciegas encontraría valles dentro de las propias palabras.


## `-ss` de salida deja el clip mudo

Tentación razonable: buscar en dos etapas (`-ss <t-2>` antes de `-i`, `-ss 2` después) para
que el corte caiga exacto. **No lo hagas al cortar los intermedios.** Con búsqueda de salida
las marcas de tiempo del audio no arrancan en cero, así que `atrim=0:d` no selecciona nada y
el clip sale **sin pista de audio**. Ni `asetpts=PTS-STARTPTS` ni `aresample=first_pts=0` ni
`atrim=duration=` lo arreglan.

En un clip de un segundo salta a la vista, porque el montaje del cuerpo falla con
«Stream specifier ':a' matches no streams». En uno largo pasaría inadvertido.

## Los milisegundos de deriva al buscar son del AAC de origen, no tuyos

Comparando la envolvente de cada segmento contra su toma, en el capítulo hecho con copias de
WhatsApp cuatro segmentos daban parecido 1.000 pero con desfase de −0.04 a −0.06 s, y el pico
de correlación era **agudo**, no plano. Parecía slop del corte.

No lo es: las tomas traen audio **AAC**, y decodificarlo arrancando desde puntos de búsqueda
distintos alinea el resultado hasta un par de tramas AAC (21 ms cada una) más acá o más allá.
La medición y el render buscan desde sitios distintos, así que la diferencia aparece aunque
el corte esté donde se pidió. El capítulo hecho con archivos de cámara da 0.00 en todos los
segmentos, que es la confirmación.

Con el parecido en 1.000 y el contenido íntegro, esa deriva no es un error de montaje. La
tolerancia de `verificar.py` está en 80 ms por eso. Perseguirla con búsqueda de salida cuesta
el audio entero (ver arriba).


## Los huecos entre palabras de la transcripción no son huecos de audio

La transcripción marca «pausas» calculando la distancia entre el final de una palabra y el
principio de la siguiente **según whisper**. Como esas marcas tienen un tercio de segundo de
error, el hueco que anuncia puede no existir en el audio, y al revés: donde no marca nada
puede haber un silencio perfectamente cortable.

Pasó en un capítulo: la transcripción daba un hueco de 0.18 s en 19.78–19.96, se movió el
corte ahí, y el audio en ese punto estaba a −15 dB, en plena sílaba. El silencio real —de
60 ms, a −41 dB— estaba en 21.02–21.08, justo donde el corte ya estaba antes de moverlo.

**Para decidir un punto de corte, mira la envolvente de energía, no los huecos de la
transcripción.** La transcripción sirve para saber qué palabra es, no cuándo.

## Al clasificar un empalme, mira EN el corte, no a su lado

Los huecos que sirven para cortar cuando la persona habla de corrido duran 60–80 ms. Dos
consecuencias para cualquier análisis:

- La ventana de promediado tiene que ser corta (0.05 s). Con 0.12 s el hueco se promedia con
  las sílabas vecinas y desaparece del análisis.
- Hay que medir **en el instante del corte**. Asomarse 50 ms antes o después cae de lleno en
  la sílaba de al lado, y un corte impecable se reporta como si estuviera en mitad del habla.

Los dos errores juntos hacían que `revisar_sentido.py` diera por malos empalmes que estaban
bien puestos.


## Calibrar con una estadística y verificar con otra

Sobre música con pulso, la mediana de ventanas de 50 ms está unos **7 dB por debajo** de la
mediana de ventanas de 1 s: las cortas caen en los huecos entre golpes y las largas los
promedian. Los dos números se imprimen en decibelios y parecen comparables.

Calibrando la ganancia de la música con ventanas de 1 s y comprobando el resultado con
ventanas de 50 ms, la música acababa siete decibelios por debajo de donde debía y el error
era invisible: cada medición era correcta por separado. `MUSICA_VENTANA` en `comun.py` existe
para que las dos usen la misma.

## La ganancia de la música se mide con los filtros puestos

A la música se le aplica un paso alto y un corte en la banda de la voz para dejarle sitio al
habla. En una pista con mucho grave, el paso alto a 90 Hz se lleva **3.5 dB** y el
ecualizador otro 1. Medir el nivel de la pista cruda y aplicar la ganancia después de
filtrar deja la mezcla cuatro decibelios corta, y la cifra cambia según la pista, así que no
se puede compensar con una constante.

`MUSICA_FILTROS` vive en `comun.py`, no en el render, precisamente para que la medición y la
aplicación no puedan separarse.

## `loudnorm` en una sola pasada no acierta el objetivo

Ya documentado para la voz, y vuelve a morder con la música: dos pistas normalizadas ambas a
-17.5 LUFS acababan sonando con 3.6 dB de diferencia entre sí. Para la música se sustituyó
por una ganancia medida y aplicada con `volume`, que es exacta y además reproducible.
