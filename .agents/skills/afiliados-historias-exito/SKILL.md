---
name: afiliados-historias-exito
description: Produce un capítulo de la serie de video "Afiliados que construyen historias de éxito" de Camacol Santander a partir de las tomas crudas de la entrevista a un afiliado — transcribe, decide qué entra y qué se cae, elimina silencios y muletillas, monta con cenefas de pregunta, lower third, tarjetas de redes, intro y cortinilla, y entrega el MP4 final más un XML editable (Premiere / DaVinci Resolve). Úsala SIEMPRE que pidan editar, montar, armar o producir un video de un afiliado de Camacol, un capítulo de "historias de éxito", o cuando entreguen tomas de una entrevista a un constructor/afiliado para convertirlas en un video con la línea gráfica de Camacol Santander — aunque no mencionen la serie por su nombre y solo digan "edítame estas tomas" o "sácame un video de dos minutos con esto".
---

# Afiliados que construyen historias de éxito

Serie institucional de Camacol Santander: entrevistas cortas a empresas afiliadas, con
formato fijo. Un capítulo dura entre 2:00 y 2:10, va en 1920x1080 a 30 fps, y siempre tiene
la misma estructura:

```
placa de intro (3 s)  →  bloque por pregunta, con su cenefa  →  cierre de redes  →  cortinilla
```

Sobre ese esqueleto pueden correr **tomas auxiliares**: planos de obra, renders o fotos que
sustituyen la imagen mientras la voz de la entrevista sigue sonando debajo. Son opcionales
—hay capítulos sin ninguna— y se explican en la sección 3.

El material que llega suele ser una tanda de tomas sueltas de WhatsApp, una por pregunta, sin
cortar. El trabajo es decidir qué se queda, limpiar el habla y montarlo en la línea gráfica.

## Antes de empezar: cómo se corre esto

Abre el asistente **en la carpeta del paquete** (la que tiene `AGENTS.md` y `instalar.command`)
y usa siempre estas dos rutas:

```bash
PY=.entorno/bin/python                           # el Python del paquete, versiones fijas
S=.agents/skills/afiliados-historias-exito/scripts
$PY $S/comprobar_entorno.py                      # lo primero en cada sesión
```

`.entorno/` lo deja `instalar.command`: Python, librerías con las versiones de
`requisitos.txt`, ffmpeg y el modelo de whisper, todo dentro de la carpeta y sin internet.
**Esas versiones son las que se validaron.** Si algo falla:

- **No instales nada por tu cuenta** —ni `pip install`, ni otro whisper, ni otro ffmpeg— ni
  transcribas por otro camino. Los cortes están calibrados con este motor y esta versión.
- Si `comprobar_entorno.py` dice que **whisper no ve la GPU**, el asistente está en modo
  protegido (en Codex, el modo por defecto). Pide a la persona que cambie los permisos de la
  conversación a **«Acceso total»** y vuelve a empezar. No hay otra salida: dentro de ese modo
  macOS no deja usar la GPU.
- Si falta `.entorno/` o algo dentro, la solución es volver a hacer doble clic en
  `instalar.command`. Díselo así a la persona.

Si no existe `.entorno/` (el Mac donde se desarrolló la skill), `PY=python3` también funciona:
los scripts se relanzan solos bajo `uv` con las mismas versiones.

## Reunir lo que falta

El montaje necesita cinco datos que casi nunca vienen con las tomas. Pregúntalos de una sola
vez, al principio, en lugar de irlos descubriendo a mitad del render:

1. **Nombre y cargo del vocero** — va en el lower third. No lo inventes ni lo deduzcas de una
   firma de correo: se sobreimprime sobre la cara de una persona real y un error ahí es caro.
2. **Logo del afiliado** — PNG con transparencia o con fondo blanco. Si no existe, mira si hay
   un capítulo anterior de la serie del mismo afiliado y extráelo de ahí (`scripts/extraer_logo.py`).
3. **Las preguntas** — la serie usa cinco. Las de capítulos anteriores están en
   `references/estilo-serie.md`; confirma si este afiliado responde las mismas.
4. **Handles de Facebook e Instagram** — van en las tarjetas del cierre. En Facebook va el nombre
   de la página; en Instagram, el **usuario** (el que empieza por @), no el nombre de la empresa.
   `build_assets.py` se para si el de Instagram trae espacios o mayúsculas.
5. **Dónde entregar** — no hace falta preguntarlo: todo sale dentro de la carpeta del capítulo,
   en `video terminado y editables/`.

Pregunta además si hay **material de apoyo** (video de obra, renders, fotos de proyectos). No
es obligatorio, pero cambia mucho el resultado: sin él el capítulo son dos minutos de plano
fijo, y con él la empresa muestra lo que hace mientras lo cuenta.

Si hay un capítulo anterior de la serie a mano (`VIDEO ORIGINAL VERSION TERMINADA.mp4` o
similar), ábrelo primero: confirma la línea gráfica vigente y te da las preguntas ya redactadas.

## Cómo llega el material

Quien entrega duplica `_PLANTILLA CAPITULO`, la renombra con el nombre del afiliado y deja:

```
Constructora Ejemplo/
├── Entrevista/            ← las tomas, numeradas: «1 - Cómo inicia la empresa.mp4»
├── Apoyo/                 ← opcional: obra, renders, fotos
└── logo.png               ← suelto
```

Luego **copia esa carpeta y la pega en el chat**. Una carpeta pegada que contenga
`Entrevista/` es un capítulo nuevo: ese es el disparador.

Lo primero, siempre:

```bash
$PY $S/revisar_insumos.py "/ruta/a/la carpeta"
```

Dice qué tomas hay, en qué orden, si alguna viene muda o muy corta, si el logo tiene
transparencia y qué falta. Reportarlo antes de empezar ahorra media hora de render tirado.

**Los nombres de archivo dan el orden y el tema, no la redacción de la cenefa.**
`4 Estrategia tecnologica` no es una pregunta. La redacción sale del audio del entrevistador
cuando la formula —como en A1S, donde la dice al principio de cada toma— o se confirma con
quien entrega. `scripts/nombres.py` hace la lectura; un archivo sin número no es un bloque de
pregunta (en A1S era la vocera presentándose).

**Pide los cinco datos en una sola pregunta al empezar**, no a mitad del render: nombre del
afiliado, nombre y cargo de quien habla, usuarios de redes, si las preguntas son las de
siempre, y si hay material de apoyo. `revisar_insumos.py` ya te dice lo que se puede ver solo.

Las rutas se resuelven solas y **no hace falta escribir ninguna clave de carpetas** en
`proyecto.json`: `Entrevista`, `Apoyo`, el logo suelto y `video terminado y editables` se
encuentran por convención. Lo que el JSON diga explícitamente siempre gana, que es como
siguen funcionando los capítulos montados con la estructura vieja.

## Flujo

**La puerta de entrada es `scripts/montar.py`.** Sabe en qué punto está el capítulo, corre
las etapas que falten y se detiene en las dos que necesitan una persona: elegir qué frases
entran, y leer cómo suenan los empalmes. Se puede relanzar tantas veces como haga falta.

```bash
$PY $S/comprobar_entorno.py     # una vez por máquina
$PY $S/montar.py proyecto.json  # y esto las veces que haga falta
```

Los scripts sueltos que se describen abajo siguen ahí y se pueden correr uno a uno cuando
haga falta rehacer solo una parte. Todos se corren igual: `$PY $S/<script>.py proyecto.json`.

Todos los scripts leen un mismo `proyecto.json`. Créalo en la carpeta del capítulo — nunca
dentro de la skill — copiando `references/proyecto-ejemplo.json`, que es el capítulo de
Segen FP completo y sirve de plantilla. Las rutas del JSON se resuelven relativas a él.

```
Constructora Ejemplo/          ← la carpeta del capítulo (la «carpeta madre»)
├── proyecto.json
├── Entrevista/                ← las tomas crudas, numeradas en orden
├── Apoyo/                     ← opcional: tomas de apoyo, renders, fotos
├── logo.png                   ← el logo del afiliado, suelto en la carpeta
└── video terminado y editables/   ← el MP4, el XML, Graficos/ y el guion

_archivos temporales/Constructora Ejemplo/   ← al lado, no dentro: transcripción, gráficos,
                                                intermedios (~1 GB); se puede borrar al final
```

Los capítulos antiguos con `Insumo principal/`, `insumos/` y `Entrega/` siguen funcionando: el
`proyecto.json` dice dónde está cada cosa y lo que dice siempre gana.

### 1. Inventario y transcripción

```bash
$PY $S/transcribir.py proyecto.json
```

Recorre las tomas, saca duración/resolución/fps de cada una y las transcribe con marcas de
palabra. Deja en la carpeta de trabajo (`_archivos temporales/<capítulo>/`) un `transcripcion.txt` con el texto de cada toma con los tiempos de cada
palabra y las pausas marcadas. Ese archivo es la materia prima para decidir el corte: se lee
como un guion, no hay que ver el video para saber qué dice cada toma y dónde respira.

Tarda unos minutos. Mientras corre, examina fotogramas de las tomas para ver el encuadre
(sentada / de pie / sobre qué fondo) — influye en el orden y en dónde caen los jump cuts.

### 2. Decidir el corte

Aquí es donde está el criterio, y no lo puede tomar un script. Lee la transcripción completa y
arma la lista de segmentos en `proyecto.json`. Qué se cae, casi siempre:

- **Muletillas de arranque** — el «Bueno,» con el que empieza cada respuesta, las falsas
  entradas, las preguntas del entrevistador que se colaron.
- **Silencios y vacilaciones** — pausas de más de medio segundo entre frases, y los
  alargamientos de vocal («deee», «laaa», «cooon»). Estos últimos son un regalo: cortar *por
  dentro* de una vocal sostenida es inaudible, porque el empalme cae sobre un sonido continuo.
  Busca en la transcripción las palabras cortas que duran más de 0.6 s: casi siempre son eso.
- **Contenido redundante** — dos formas de decir lo mismo («la casa de sus sueños *y la que
  siempre ha soñado*»), o una idea que ya quedó dicha en otro bloque.

Y lo que se protege: la historia de origen, los datos concretos (nombre del proyecto, ubicación,
precios, diferenciales), la mención a Camacol, y el cierre. Si el afiliado dice algo que explica
su marca —por ejemplo que los pétalos de su logo son sus hijos— eso vale más que treinta
segundos de generalidades.

**No confíes en las marcas de tiempo de whisper para cortar.** Se adelantan al final real de
la palabra: whisper da «1972.» por terminada en 17.14 s cuando la voz sigue sonando hasta
17.61. Un corte colocado «con margen» según esa marca cae **dentro** de la palabra, y así se
entregaron dos capítulos con todas las frases tajadas. Las marcas sirven para decidir *qué*
entra; los milisegundos exactos, no.

Después de escribir la lista de segmentos vienen **dos pasos, y hacen cosas distintas**:

```bash
# 1. afina los milisegundos: lleva cada punto a la frontera de palabra más cercana
$PY $S/ajustar_cortes.py proyecto.json --aplicar

# 2. lee cómo suena cada costura y qué sentido tiene
$PY $S/revisar_sentido.py proyecto.json
```

`ajustar_cortes.py` **no decide contenido**: mueve cada punto como mucho 0.35 s hasta la
frontera de palabra más cercana. Eso corrige el adelanto de las marcas de whisper y nada más.
Deja más aire al abrir y cerrar un bloque de pregunta (0.30 s) que dentro de una misma
respuesta (0.13 s), que es como respira un montaje de verdad.

`revisar_sentido.py` reconstruye **cómo va a sonar cada empalme** —las últimas palabras del
segmento que sale seguidas de las primeras del que entra— y lo imprime para que lo leas. Esa
lectura es obligatoria y no la puede hacer el script: él solo detecta lo mecánico (un corte
que parte una palabra, un segmento que acaba en «y» o en «de» sin continuación, respuestas que
abren con muletilla). Que una costura sea gramatical no garantiza que signifique algo.

**Lo que ningún script va a decidir por ti.** Se entregó un capítulo donde el montaje decía
«...para que la persona pueda construir la casa de sus sueños **y** el tema del precio»: el
corte se colocó en el siguiente silencio largo, que estaba pasado el «y la que» siguiente, y
esa conjunción huérfana cosió dos ideas que no tienen nada que ver. El corrector no podía
verlo —acústicamente era un corte impecable— y la verificación por energía tampoco, porque el
audio estaba íntegro. Solo se ve leyendo.

**No hagas islas.** Un fragmento corto encajado entre dos cortes a tope suena picado aunque
cada corte por separado sea impecable. Se entregó un capítulo con «la casa de sus sueños»
aislada: 0.95 s entre dos empalmes de 0.13 s, tres cortes en tres segundos. Sonaba mal editado
y las tres comprobaciones automáticas lo daban por bueno, porque ninguna palabra estaba
partida y ninguna idea quedaba colgando.

La regla, y vale más que cualquier optimización de duración: **es preferible dejar una frase
redundante que meter un corte que se oiga.** Antes de partir un tramo, mira si la persona
respira ahí. Si no respira —hay tomas donde habla de corrido veinte segundos— no hay dónde
cortar: se toma entero o no se toma.

Tres cosas más que separan un montaje editado de uno crudo, y que hay que mirar a mano:

- **Que cada segmento cierre una idea.** Acabar en «y», «de», «que» solo vale si el segmento
  siguiente continúa esa misma frase.
- **Las muletillas de arranque.** Una suelta no molesta; tres respuestas seguidas abriendo con
  «Bueno,» suenan a archivo sin tocar. `revisar_sentido.py` las lista con el instante exacto
  donde empieza el contenido.
- **Que no se repita el conector.** «...y pues» seguido de «incluso pues...» es correcto y
  suena fatal.
- **Que los empalmes tengan dónde respirar.** `revisar_sentido.py` distingue silencio de
  respiración: un empalme con una inspiración en medio suena natural; uno dentro de habla
  continua, no. La transcripción marca esa inspiración como «pausa», así que no basta con
  fiarse de ella.

Ajusta la duración total apuntando a **2:05–2:09**, nunca más de 2:10. El script imprime el
total; si te pasas, quita un segmento entero antes que recortar diez cosas pequeñas: veinte
micro-cortes se notan más que una idea menos.

### 3. Colocar las tomas auxiliares (si las hay)

```bash
$PY $S/revisar_broll.py proyecto.json
```

Lee `Apoyo/` (acepta `.mp4/.mov` y `.jpg/.png`), imprime una ficha de cada archivo y
arma una hoja de contactos con tres fotogramas de cada video. **Míralas antes de colocar
nada**: hay que saber qué muestra cada toma para decidir sobre qué frase cae.

Colocar bien es lo único que importa aquí, y es criterio, no automatismo:

- **Que ilustre lo que se está diciendo.** Si ella habla de una obra en Lebrija, la aérea de
  Lebrija va *ahí*, no donde sobre hueco. Un plano de apoyo que no tiene que ver con la frase
  distrae más que el plano fijo que estaba tapando.
- **Nunca sobre el rótulo del nombre ni sobre las tarjetas de redes.** Esos gráficos presentan
  a quien debería estar en pantalla; encima de una grúa quedan absurdos. `render.py` avisa,
  pero es mejor no llegar a que avise.
- **Nunca en los primeros segundos de un bloque.** La cenefa acaba de entrar con la pregunta y
  hay que ver a quién se la están haciendo. Deja pasar al menos 2 s después de que salga.
- **Entre 2.5 y 9 segundos**, y con al menos 1.5 s de entrevista entre dos insertos. Más corto
  se lee como un parpadeo; más largo y el espectador olvida a quién está escuchando.
- **Sin pasar del 40 % del cuerpo.** Por encima de eso deja de ser una entrevista y se
  convierte en un institucional con voz en off, que es otro formato.
- **Los mejores momentos** son las frases enumerativas y las descripciones largas, donde la
  imagen de la vocera no aporta nada: «casas y lotes de interés social», «cimentación, ventas,
  acabados, estructura».

En `proyecto.json` cada inserto se ancla a un segmento, no a un segundo absoluto, para que
siga cayendo sobre la misma frase si más adelante se retoca un corte anterior:

```json
"broll": [
  {"archivo": "aerea-granadillo.mp4", "segmento": 7, "desde": 3.0,
   "duracion": 5.5, "entrada": 1.2, "texto": "aérea del proyecto"}
]
```

`entrada` es el punto de entrada dentro del archivo de apoyo — los videos de obra casi siempre
empiezan con un tirón de cámara, así que conviene entrar pasado un segundo. `ajuste` es
opcional: se decide solo por la proporción, `llenar` para 16:9 y `encajar` (centrada con fondo
desenfocado) para todo lo demás, que es lo que salva a las verticales de celular.

Las fotos llevan un acercamiento lento automático: una imagen fija cinco segundos en mitad de
una entrevista parece un cuadro congelado.

El audio de las tomas auxiliares **no se usa nunca**: debajo sigue corriendo la entrevista, y
ese es justamente el efecto de voz en off. Entran y salen con **corte seco**, sin disolvencia,
como en el resto de la serie.

### 4. Gráficos

```bash
$PY $S/build_assets.py proyecto.json
# si el python del sistema no tuviera Pillow:
# (si algo falta, el script se relanza solo bajo uv; no hay que invocarlo distinto)
```

Genera en `gfx/`, dentro de la carpeta de trabajo, la placa de intro, la caja de logos, las cinco cenefas, el lower third
y las dos tarjetas de redes, a partir del logo del afiliado y los textos de `proyecto.json`.
Las medidas, fuentes y colores están calcados del capítulo de referencia y documentados en
`references/estilo-serie.md`; tócalos solo si la línea gráfica cambió.

Revisa siempre la intro y la caja de logos como imagen antes de renderizar. El fallo típico es
el logo del afiliado: si vino recortado de un video, suele arrastrar el borde de la tarjeta
blanca y aparece una línea vertical fantasma al costado.

### 5. Render

```bash
$PY $S/render.py proyecto.json            # todas las etapas
$PY $S/render.py proyecto.json cortar cuerpo   # solo algunas
```

Etapas: `cortar` (cada segmento a 1080p con audio limpio) → `cuerpo` (montaje) → `broll`
(tomas auxiliares, si las hay) → `grafica` (sobreimpresos + loudness) → `intro` → `final`.

**Cómo se empalma, y por qué importa.** La imagen disuelve 0.20 s en cada corte, pero el audio
no se mezcla nunca. Un `xfade` solapa los dos clips, así que obliga a sacrificar 0.20 s de
material; aplicado al audio se come el final de una palabra y el arranque de la siguiente. Por
eso cada intermedio se saca con 0.1 s de más por cada lado: la disolvencia se alimenta de ese
material sobrante —las colas— y el audio del contenido se concatena **entero**, con un fundido
de 8 ms en los bordes que solo evita el chasquido. Es como se monta en cualquier mesa. El
detalle está en `references/trampas-ffmpeg.md`.

La etapa `broll` copia el audio sin recodificar, así que la voz de la entrevista es
bit a bit la misma antes y después. Si quitas las tomas auxiliares del JSON, la etapa borra
su render y `grafica` vuelve sola al cuerpo limpio.

Son reanudables: `cortar` reutiliza los clips cuyo segmento no cambió y rehace solos los que
sí. Si cambias segmentos, vuelve a lanzar el render o `montar.py`: **no borres nada**. (Codex
tiene prohibido `rm -f` y no le hace falta.)

`ffmpeg` tiene varias trampas en este flujo que ya están resueltas dentro del script —
desfase A/V acumulado, imágenes que entran a 25 fps, crossfades contra audio mudo. Si tocas el
render, lee `references/trampas-ffmpeg.md` antes.

### 6. Verificación

Este paso no es opcional, y se repite **después de cada render**, también de los retoques:

```bash
$PY $S/verificar.py proyecto.json
```

Si termina con «NO LO DES POR BUENO» o con palabras cortadas, sale con código 1: corrige y
vuelve a renderizar y verificar hasta que diga «Texto correcto».

Hace cuatro cosas. La más importante es la **comprobación de empalmes por energía**: compara la
envolvente de cada segmento del montaje con la de su toma original y exige parecido ~1.00 y
desfase 0.00 s. Cualquier otra cosa significa que el montaje perdió material.

No te fíes de la comparación de texto para esto: whisper sigue reconociendo «nacional» aunque
le falte la última sílaba, así que da por bueno un montaje con todas las frases tajadas. Sirve
para otra cosa —detectar que se cayó una palabra entera— pero no para juzgar los empalmes.

La tercera es **volver a pasar `revisar_sentido.py`** sobre los cortes definitivos. En la
prueba con Codex el asistente retocó cortes tres veces después de la primera revisión, verificó
cada render solo por energía y texto, y entregó un capítulo que abría con medio «Bueno» y
entraba a mitad de «nuestra». Ahora la verificación no pasa con eso.

La cuarta es la hoja de contactos con fotogramas en los momentos clave.

Mira también la hoja de contactos: confirma que cada cenefa cae sobre su bloque, que el lower
third no choca con nada y que la cortinilla cierra. Si hay tomas auxiliares, la hoja incluye un
fotograma de mitad de cada inserto: ahí se ve si el encaje dejó bandas o recortó de más.

### 7. Entrega

```bash
$PY $S/exportar_xml.py proyecto.json
```

Deja en la carpeta de salida:

| Archivo | Qué es |
|---|---|
| `<Afiliado> - Afiliados que construyen historias de exito 1080p.mp4` | el video final |
| `<Afiliado> - proyecto editable.xml` | XML de Final Cut Pro 7 (xmeml): timeline apuntando a **los originales**, no a los renders. Lo importan Premiere Pro y DaVinci Resolve |
| `Graficos/` | los PNG que el XML referencia, ya colocados a 1920x1080 — tiene que viajar junto al XML |
| `Guion de edicion.md` | tabla de cortes, tiempos de cada gráfico y de cada toma de apoyo, criterios y pendientes |

El `Guion de edicion.md` lo genera `exportar_xml.py`, pero **escribe tú a mano su sección final de
pendientes**: qué datos quedaron sin confirmar (nombre del vocero, origen del logo), qué
limitaciones tuvo el material (resolución de las tomas) y qué se podría mejorar con mejores
insumos. Es lo primero que lee quien recibe el video.

## Música de fondo

Opcional: si hay pistas en `assets/musica/`, el capítulo sale con música. Si no las hay, sale
sin ella y nada falla.

La skill elige una por capítulo **a partir del nombre del afiliado**, no al azar: parece
variado entre capítulos pero es estable para el mismo, así que volver a renderizar no cambia
la música. Con lo fácil que es tener que repetir un render, el azar puro sería una fuente de
incoherencias difícil de rastrear.

La mezcla no se inventó: se midió sobre el capítulo de referencia de la serie. Música sola en
la intro a −20 dBFS, agachada bajo el diálogo a −35, con la voz 16 dB por encima del colchón.
Se consigue con tres mecanismos que hacen cosas distintas:

- **Automatización por tramo**, que hace la bajada grande: protagonista en la placa, colchón
  en el cuerpo, arriba otra vez en la cortinilla.
- **Sidechain suave**, que aporta el movimiento: en las pausas entre frases la música respira
  y cuando la persona habla se retira un poco. Va suave a propósito — si se le pide que agache
  mucho, acaba haciendo él toda la bajada y subir la ganancia estática deja de tener efecto,
  porque se le da más señal y comprime más.
- **Un filtro** que le quita a la música parte del rango de la voz (300 Hz – 3 kHz). Deja
  sitio sin tener que bajarla tanto.

Después de renderizar con música, mide:

```bash
$PY $S/comprobar_mezcla.py proyecto.json
```

Lo que importa es **la relación entre la voz y el colchón**: por debajo de 14 dB la música
estorba, por encima de 22 dB no se oye y no aporta. El nivel absoluto depende de a cuánto se
normalice el capítulo, así que no sirve como criterio.

## Qué reportar al final

Di la duración exacta, de dónde salió cada decisión de contenido no obvia (qué quitaste y por
qué) y los puntos que quedaron pendientes de confirmar. Si las tomas venían comprimidas de
WhatsApp, dilo explícitamente: el resultado se ve más blando que un capítulo hecho con
archivos de cámara y conviene que quien lo reciba sepa por qué.

## Entorno

Todo lo externo vive en `<paquete>/.entorno/`, lo instala `instalar.command` y se encuentra
relativo a la carpeta (se puede mover o renombrar):

- **Python 3.11.15** y las librerías de `requisitos.txt` —whisper 0.4.3, mlx 0.32.2, numpy
  2.4.6, Pillow 11.3.0—, exactamente las del ensayo completo que salió bien. Durante el
  desarrollo la librería de GPU de whisper cambió cuatro veces de versión sin que nadie lo
  decidiera; por eso no se baja «la última».
- **ffmpeg 9.0.2** nativo para chip Apple. **No hay `ffprobe`**: los scripts sacan duraciones
  parseando la salida de `ffmpeg -i` y contando fotogramas con `-f null`.
- **El modelo de whisper** (`whisper-large-v3-turbo`, revisión fija), en una carpeta local:
  transcribir no necesita internet.
- whisper **usa la GPU**. Dentro del modo protegido de Codex no la ve; `comun.exige_gpu()`
  para antes de transcribir con un mensaje que dice qué hacer.

`scripts/comprobar_entorno.py` verifica todo esto —versiones incluidas— y dice qué falta.
Si no hay `.entorno/`, los scripts caen a lo que haya en el sistema (`ffmpeg` en el PATH y
`uv` con las mismas versiones fijas).

Las carpetas bajo `~/Documents` pueden estar bloqueadas por TCC de macOS. Si `ls` responde
`Operation not permitted`, no es la ruta: hay que dar Acceso a Disco Completo a la app en
Ajustes del Sistema.

## El error que no hay que repetir

Los dos primeros capítulos se entregaron con todos los empalmes de audio tajados, por dos
fallos que se reforzaban:

1. Los puntos de corte se colocaron con las marcas de whisper, que se adelantan al final real
   de la palabra.
2. El audio se mezclaba con `acrossfade` de 0.2 s, que además de solapar dos voces obligaba a
   sacrificar 0.2 s de contenido en cada empalme.

Y no se detectó porque la verificación era una transcripción, y whisper reconoce las palabras
aunque estén cortadas. Ahora los cortes se colocan midiendo energía y se comprueban midiendo
energía. Si tocas el montaje, **conserva esa comprobación**.

Arreglado eso quedaba el otro fallo, más difícil: los cortes estaban limpios pero no eran
inteligentes. Cerraban donde el audio bajaba, no donde acababa la idea. La regla que faltaba:
**el silencio dice dónde se puede cortar; el sentido dice dónde se debe.** Por eso
`ajustar_cortes.py` está limitado a mover 0.35 s y existe `revisar_sentido.py`, que no decide
nada — te obliga a leer.

## Referencias

- `references/estilo-serie.md` — especificación visual exacta: geometrías, fuentes, colores,
  tiempos de entrada y salida de cada gráfico, y las preguntas de la serie.
- `references/trampas-ffmpeg.md` — los errores de ffmpeg que cuestan un render entero.
- `references/proyecto-ejemplo.json` — el `proyecto.json` completo del capítulo de Segen FP,
  como plantilla.
