# Cómo montar un capítulo de «Afiliados que construyen historias de éxito»

Manual de operación. No hace falta saber programar, pero sí seguir el orden y leer lo que el
programa va diciendo.

Un capítulo terminado dura entre 2:00 y 2:10, va en 1920x1080 y siempre tiene la misma
estructura: placa de entrada, un bloque por pregunta con su cenefa, el cierre de redes y la
cortinilla de Camacol.

---

## Antes de la primera vez

**Hace falta un Mac con chip Apple** (M1 o posterior). Dos de las tipografías de la serie
vienen con macOS y no se pueden instalar aparte por licencia, y la transcripción usa la
tarjeta gráfica del chip. No pide máquina potente, solo paciencia: un capítulo son unos 25
minutos de proceso.

1. **Instalar.** Clic derecho sobre `instalar.command` → «Abrir» (la primera vez no sirve el
   doble clic: macOS lo bloquea por venir de otro Mac). No pide contraseña. Baja unos 3 GB
   —Python, librerías, ffmpeg y el modelo de transcripción— y lo deja todo **dentro de la
   carpeta del paquete**, con las versiones exactas con que se validó la serie. Al final
   corre una comprobación y tiene que decir «Listo». Si algo falla, se vuelve a abrir: retoma
   donde se quedó.
2. **Preparar Codex.** Ábrelo en la carpeta del paquete. Si pregunta si confías en la
   carpeta, di que sí; y pon los permisos en **«Acceso total»** («Full access»). La
   transcripción usa la tarjeta gráfica, y en el modo protegido de Codex macOS no la deja
   usar. Si se olvida, Codex lo avisa en el primer paso.

Esto se hace una vez por máquina, no en cada capítulo. La carpeta del paquete se puede
renombrar o mover después sin romper nada.

---

## Los cinco datos que hay que pedirle al afiliado

Consíguelos **antes** de empezar a montar. Si aparecen a mitad, hay que rehacer los gráficos:

1. **Nombre y cargo de quien habla**, escrito como quiere que salga en pantalla. Se
   sobreimprime sobre la cara de una persona real: un error aquí es caro y se nota.
2. **El logo, en PNG con fondo transparente.** Si te mandan una captura o un JPG con fondo
   blanco, pídelo otra vez. Un logo sacado de un video se nota en pantalla.
3. **Las preguntas de la entrevista**, tal como se las hicieron.
4. **Los usuarios de Facebook e Instagram**, exactamente como se escriben. El de Instagram es el
   que empieza por @ y está debajo de la foto del perfil, no el nombre de la empresa.
5. **Material de apoyo** (opcional pero recomendable): video de obra, renders, fotos de
   proyectos. Sin él, el capítulo son dos minutos de plano fijo.

---

## Preparar la carpeta

Duplica `_PLANTILLA CAPITULO` y ponle el nombre del afiliado. Dentro solo hay que llenar dos
carpetas y soltar el logo:

```
Constructora Ejemplo/
├── Entrevista/            ← los videos de la entrevista
│   ├── 1 - Cómo inicia la empresa.mp4
│   ├── 2 - Dónde están ubicados.mp4
│   └── ...
├── Apoyo/                 ← opcional: obra, renders, fotos
└── logo.png
```

**Numera los videos de la entrevista.** El número marca el orden en que aparecen; el texto
que va detrás dice de qué trata la toma. Si llegaron con otro nombre, renómbralos: cuesta un
minuto y ahorra confusiones. Si no puedes renombrarlos, déjalos como estén y dilo — el orden
se puede deducir escuchándolos.

**El logo, en PNG con fondo transparente.** Si te mandan una captura de pantalla o un JPG con
fondo blanco, pídelo otra vez: en la placa de entrada se nota el recuadro.

**El material de apoyo es opcional**, pero cambia mucho el resultado. Se ve mientras la
persona sigue hablando, así que convierte dos minutos de plano fijo en un video que enseña lo
que la empresa hace. Ponles de nombre lo que muestran.

## Montar

Abre Codex **en la carpeta del paquete**, no dentro del capítulo, con los permisos en
«Acceso total». Copia la carpeta del capítulo y **pégala en el chat**. Nada más.

Lo primero que hace es revisar el material y decirte qué encontró: cuántas tomas, en qué
orden, si alguna viene sin sonido, si el logo sirve. Luego te pregunta los datos que no se
pueden adivinar y se pone a trabajar.

Se va a detener **dos veces**, y son las dos veces en que hace falta una persona:

### Primera parada: decidir qué entra

El programa transcribe las tomas y deja un archivo `transcripcion.txt` en la carpeta de trabajo del
capítulo (`_archivos temporales/<capítulo>/`). Es el guion:
cada palabra con su tiempo, y las pausas marcadas. Se lee sin ver el video.

Con eso escribes la lista de segmentos en `proyecto.json`. Lo que se cae casi siempre:

- El **«Bueno,»** con que arranca cada respuesta, y las preguntas del entrevistador.
- Las **pausas largas** entre frases.
- Lo que **se dice dos veces**.

Lo que se protege: la historia de origen, los datos concretos (nombre del proyecto, ubicación,
precios, cuántos empleados) y la mención a Camacol. Si el afiliado dice algo que explica su
marca, eso vale más que treinta segundos de generalidades.

Apunta a **2:05**. El límite es 2:10 y el programa avisa si te pasas.

### Segunda parada: leer las costuras

El programa reconstruye cómo va a sonar cada empalme —las últimas palabras de un segmento
seguidas de las primeras del siguiente— y las imprime. **Léelas.**

Que una frase sea gramatical no significa que se entienda. Un capítulo se entregó diciendo
«...la casa de sus sueños **y** el tema del precio»: el corte arrastró una conjunción que
acabó cosiendo dos ideas sin relación. Ningún programa puede ver eso.

Tres cosas que buscar:

- Que cada segmento **cierre una idea**. Acabar en «y», «de» o «que» solo vale si el segmento
  siguiente continúa esa misma frase.
- Que **no queden fragmentos sueltos**. Un trozo de dos segundos entre dos cortes apretados
  se oye picado aunque las frases estén completas. Si la persona habla de corrido y no hay
  dónde cortar, **toma el tramo entero**: es preferible dejar algo redundante a que se note
  la edición.
- Que **no se repita el arranque**. Tres respuestas seguidas abriendo con «Bueno,» suenan a
  material sin editar; el programa las lista con el segundo exacto donde empieza el contenido.
- Que no queden **dos conectores pegados**: «...y pues» seguido de «incluso pues...» es
  correcto y suena fatal.

Si algo no encaja, corriges `entrada` o `salida` de ese segmento y vuelves a lanzar.

### Parada extra: colocar las tomas de apoyo

Solo aparece si dejaste material en `Apoyo/`. Son planos de obra, renders o fotos que
**sustituyen la imagen mientras la voz de la entrevista sigue sonando**: se ve lo que la
empresa hace mientras lo cuenta. Es la diferencia entre una entrevista y un video.

El programa te muestra una ficha de cada archivo y una hoja de contactos con sus fotogramas.
Con eso decides dónde va cada uno y lo añades a la lista `broll` del proyecto. Tres reglas:

- **Que ilustre lo que se está diciendo ahí.** Un plano que no tiene que ver con la frase
  distrae más que el plano fijo que estaba tapando.
- **Nunca sobre el rótulo del nombre ni sobre las tarjetas de redes.** Esos gráficos presentan
  a quien debería estar en pantalla.
- **Entre 2.5 y 9 segundos**, y sin pasar de un tercio del capítulo. Más allá deja de ser una
  entrevista.

Sirven video (`.mp4`, `.mov`) y fotos (`.jpg`, `.png`). Las fotos llevan un acercamiento lento
automático, y las tomas verticales de celular van centradas con el fondo desenfocado, sin
recortar nada. **El audio de esas tomas no se usa nunca.**

### La música de fondo

Va sola: si hay pistas en el banco de la skill, el capítulo sale con música sin que haya que
hacer nada. Suena protagonista en la placa de entrada, se agacha cuando la persona empieza a
hablar, acompaña de fondo durante la entrevista y vuelve a subir en la cortinilla.

Cada afiliado recibe una pista del banco, siempre la misma para ese afiliado. Si quieres otra,
se indica en `proyecto.json`.

Al terminar, comprueba la mezcla:

```bash
.entorno/bin/python .agents/skills/afiliados-historias-exito/scripts/comprobar_mezcla.py "<capítulo>/proyecto.json"
```

(o pídeselo a Codex: «comprueba la mezcla»).

Te dice si la música quedó tapando la voz o si quedó tan baja que no aporta. Si hay que
moverla, el propio mensaje indica qué cambiar.

---

## Antes de dar el capítulo por bueno

El programa deja una **hoja de contactos** en `_archivos temporales/<capítulo>/qc/hoja-contactos.png`: el capítulo
entero resumido en nueve fotogramas. Confirma de un vistazo que cada cenefa cae sobre su
pregunta, que el rótulo con el nombre está bien escrito y que la cortinilla cierra.

Y **ve el video con audífonos**, atento a los empalmes. Es lo único que no se puede
automatizar.

---

## Qué se entrega

Dentro de la carpeta del capítulo, en **«video terminado y editables»**:

| Archivo | Qué es |
|---|---|
| `<Afiliado> - ... 1080p.mp4` | el capítulo final, listo para publicar |
| `<Afiliado> - proyecto editable.fcpxml` | la línea de tiempo, para reabrirla y cambiar cosas |
| `Graficos/` | las imágenes que usa el proyecto editable |
| `Guion de edicion.md` | qué se cortó y por qué, y qué quedó pendiente de confirmar |

El **FCPXML** apunta a los archivos originales, no al video renderizado: se abre en DaVinci
Resolve, Final Cut Pro o Premiere y se puede cambiar cualquier corte. La carpeta `Graficos/`
tiene que viajar con él; si mandas el proyecto a alguien, manda la carpeta completa.

Del `Guion de edicion.md`, las dos últimas secciones —los criterios y los pendientes— se
escriben a mano. Es donde queda constancia de qué datos no se confirmaron y qué limitaciones
tuvo el material.

---

## Cuando algo sale mal

El programa siempre dice qué pasó y qué hacer. Los casos frecuentes:

| Dice | Qué hacer |
|---|---|
| «Faltan N intermedios por cortar» | correr `montar.py` otra vez; retoma solo |
| «No encuentro el logo del afiliado» | revisar la ruta en `proyecto.json` |
| «se pasa del límite» | quitar un segmento entero, no recortar diez cosas pequeñas |
| «no aparece la palabra X» | ese corte se comió una sílaba: dale más aire y relanza |

**Cambiar una sola cosa es barato.** Corregir un corte y volver a exportar son unos ocho
minutos; no hace falta rehacer el capítulo.

---

## Dos límites que conviene conocer

- **La calidad depende del material que entre.** Las tomas que llegan por WhatsApp vienen a
  848x478 y hay que ampliarlas a 1080p: se ven más blandas que un capítulo hecho con archivos
  de cámara. Vale la pena pedir siempre los originales del rodaje.
- **La línea gráfica se reconstruyó midiendo un capítulo terminado**, no hay manual de marca.
  Los colores, tipografías y proporciones están documentados en `references/estilo-serie.md`.
  Si Camacol formaliza un manual, ahí es donde se cambian — y en `FUENTES`, dentro de
  `scripts/build_assets.py`.
