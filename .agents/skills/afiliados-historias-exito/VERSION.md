# Versiones

## 1.2 — octubre de 2026: el editable pasa a XML

El proyecto editable deja de ser FCPXML y pasa a ser **XML de Final Cut Pro 7** (xmeml), que
es lo que la mayoría de editores llama «el XML»: lo importan **Premiere Pro** y **DaVinci
Resolve**. Premiere no abría el FCPXML sin un conversor, aunque la documentación decía que sí.
Final Cut Pro (el actual) no lee este formato; si algún día hace falta, se puede generar
también el FCPXML.

Al rehacerlo salieron dos defectos que ya traía el FCPXML:

- **Los gráficos no llevaban posición.** Los PNG son pequeños (la tarjeta de Instagram mide
  417x140) y se colocan en el render, así que en el editable aparecían todos centrados. Ahora
  se entregan ya colocados sobre un PNG transparente de 1920x1080: caen en su sitio en
  cualquier editor sin depender de cómo interprete las coordenadas.
- **Las tomas que no son 1080p no se escalaban** (las de WhatsApp, 848x478, se habrían visto
  pequeñas), y la cortinilla vertical tampoco. Ahora llevan su escala, igual que en el render.

`exportar_xml.py` sustituye a `fcpxml.py`. Validado leyendo de vuelta los XML de A1S y Segen
con OpenTimelineIO: entradas a menos de medio fotograma del proyecto, transiciones y gráficos
en su sitio. No viajan la animación de entrada de los gráficos, el color, el tratamiento de
audio ni la música: eso está en el MP4.

## 1.1 — octubre de 2026: que salga igual en otro Mac, con Codex

La 1.0 funcionaba en el Mac donde se escribió. Probada dentro del sandbox real de Codex, con
su configuración por defecto, **no habría pasado del primer paso**: sin red, sin poder
escribir la caché de `uv` y, sobre todo, **sin acceso a la GPU**, que es donde corre whisper.
Y aun con permisos, bajaba «la última versión» de cada librería en cada uso: durante el
desarrollo, la librería de GPU de whisper pasó por cuatro versiones sin que nadie lo decidiera.

- **Todo lo externo vive en `.entorno/`**, dentro del paquete, y lo deja `instalar.command`
  sin contraseña: Python 3.11.15, las librerías exactas de `requisitos.txt` (whisper 0.4.3,
  mlx 0.32.2), ffmpeg 9.0.2 nativo para chip Apple y el modelo de whisper en una revisión
  fija. Las descargas se verifican por checksum. Al trabajar no hace falta internet.
- **Se puede mover o renombrar la carpeta**: todo se busca relativo a ella.
- **La skill está en `.agents/skills/`**, donde Codex la encuentra sola. Para Claude Code hay
  un `CLAUDE.md` que importa `AGENTS.md`; no se usa un enlace simbólico porque una memoria
  USB en exFAT no puede guardarlo y la copia del paquete fallaría.
- **Codex en «Acceso total»**: `.codex/config.toml` lo pide para esta carpeta (Codex lo
  aplica si se marca como de confianza) y `comprobar_entorno.py` / `exige_gpu()` paran con un
  mensaje claro si whisper no ve la GPU, en vez de dejar que el asistente improvise otro
  camino.
- **Tipografías por nombre de estilo**, no por posición dentro del archivo, y aviso si sale
  una de repuesto.

**Validado en un Mac simulado desde cero** (carpeta personal vacía, sin nada instalado, el
paquete renombrado después de instalar): la transcripción de A1S coincide con la original en
1.298 de 1.302 palabras —las cuatro restantes son signos de puntuación— con marcas de tiempo a
menos de 0.04 s, y el ajuste de cortes da exactamente los mismos números que en el Mac de
desarrollo. El capítulo renderizado allí, con los mismos cortes, es prácticamente idéntico al
entregado: misma duración (2:06.49), audio con correlación 0.99996 y diferencia media de
imagen de 1/255, que es ruido del codificador. Pasa la verificación completa.

Esa prueba encontró además el único fallo que el Mac de desarrollo no podía mostrar: ffmpeg 9
eliminó `-filter_complex_script`, y el montaje del cuerpo no arrancaba. Ahora se usa
`-/filter_complex`, que funciona desde ffmpeg 7.

**Probado con Codex de verdad** (Codex CLI 0.155, en el sandbox real de macOS):

- Con sus permisos por defecto, Codex leyó la skill, corrió `comprobar_entorno.py`, vio que
  whisper no tenía GPU y **pidió «Acceso total» sin intentar instalar nada**.
- Con la carpeta marcada como de confianza, aplicó solo el `.codex/config.toml` del paquete y
  trabajó en acceso total sin que nadie tocara nada.
- Montó A1S **desde las tomas crudas**, sin nada de lo decidido antes: mismas cinco preguntas
  sacadas del audio, mismos datos de rótulo y redes, cuerpo de 120 s (el nuestro, 120.5) y
  verificación en verde. Su selección editorial es distinta pero defendible.

La prueba destapó tres fallos de la skill, ya corregidos:

1. **Rehacer un segmento obligaba a borrar su clip**, y Codex tiene prohibido `rm -f`. Ahora
   cada clip guarda su firma (`sNN.firma`) y `cortar` rehace solo los que cambiaron.
2. **La verificación final no revisaba el sentido.** Codex retocó cortes tres veces, verificó
   solo energía y texto, y entregó un capítulo que abría con medio «Bueno» y entraba a mitad
   de «nuestra». Ahora `verificar.py` vuelve a pasar `revisar_sentido.py` y sale con código 1
   si algo falla.
3. **Las muletillas se detectaban con las marcas de whisper**, que situaban ese «Bueno» 0.7 s
   antes de donde suena. Ahora, si el corte de entrada cae con voz sonando, se escucha el
   arranque real.

Con esos arreglos, Codex corrigió su capítulo solo, rehízo dos clips sin borrar nada y la
verificación pasó limpia.

## 1.0 — septiembre de 2026

Primera versión lista para que la opere alguien distinto de quien la escribió.

**Capítulos producidos con ella:** Segen FP Inversiones (2:04.23) y A1S Security Group
(2:04.73). Los dos verificados: cada segmento del montaje coincide con su toma original con
correlación 1.000 y desfase 0.00 s.

### Cómo se monta un empalme, y por qué importa

Las dos primeras entregas salieron con todos los cortes de audio tajados, por dos fallos que
se reforzaban y que conviene no repetir:

1. **Los puntos de corte se colocaron con las marcas de tiempo de whisper**, que se adelantan
   al final real de la palabra: da «1972.» por terminada en 17.14 s cuando la voz suena hasta
   17.61. Ahora se colocan midiendo la energía del audio.
2. **El audio se mezclaba con la imagen.** Una disolvencia de 0.2 s obliga a sacrificar 0.2 s
   de material en cada empalme; aplicada al audio, se come el final de una palabra y el
   arranque de la siguiente. Ahora la disolvencia de imagen se alimenta de material sobrante
   fuera del corte —las colas— y el audio se empalma entero.

No se detectó a tiempo porque la comprobación era una transcripción, y whisper reconoce
«nacional» aunque le falte la última sílaba. La comprobación buena compara energía.

### Lo que ningún script decide

Un capítulo se entregó diciendo «...la casa de sus sueños **y** el tema del precio»: el corte
cayó en el siguiente silencio largo, que estaba pasado el «y la que» siguiente, y esa
conjunción huérfana cosió dos ideas sin relación. Acústicamente era un corte impecable.

De ahí el reparto actual: `ajustar_cortes.py` afina milisegundos y no puede mover un punto
más de 0.35 s; `revisar_sentido.py` reconstruye cómo suena cada empalme y **obliga a leerlo**.

### Estado conocido

- **Requiere macOS**, y es una decisión, no un descuido: las tipografías de la serie (Avenir
  Next y Helvetica Neue) vienen con el sistema y no se pueden redistribuir. Como el equipo que
  la opera trabaja en Mac, no se incorporaron alternativas libres. `build_assets.py` mantiene
  una lista de respaldos (Montserrat, Open Sans, Oswald) por si algún día hace falta salir de
  macOS: instalándolas, funciona, y probablemente se parezcan más al capítulo original.
- **Requiere chip Apple** (M1 o posterior): whisper corre sobre la GPU con mlx.
- **La línea gráfica es ingeniería inversa** de un capítulo terminado, no hay manual de marca
  de Camacol. Valores y método en `references/estilo-serie.md`.
- **Sin manual de marca, las tipografías son aproximaciones**: se eligieron por parecido entre
  las del sistema.
