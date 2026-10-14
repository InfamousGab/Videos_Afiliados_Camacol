# Videos de afiliados — Camacol Santander

Este paquete produce capítulos de la serie «Afiliados que construyen historias de éxito»:
entrevistas de dos minutos con la línea gráfica de Camacol, listas para publicar.

**Antes de decidir nada, lee las instrucciones completas** en
`.agents/skills/afiliados-historias-exito/SKILL.md`. Ahí está el criterio editorial, que es la
parte que importa. Lo de abajo es el resumen operativo, no un sustituto.

## Qué te van a pedir

Alguien pega la ruta de una carpeta de capítulo. Tiene esta forma:

```
Constructora Ejemplo/
├── Entrevista/      ← las tomas, numeradas: «1 - Cómo inicia la empresa.mp4»
├── Apoyo/           ← opcional: obra, renders, fotos
└── logo.png
```

Una carpeta con `Entrevista/` dentro es un capítulo nuevo. Ese es el disparador.

## El flujo

Trabaja desde la carpeta del paquete (donde está este archivo) y corre los scripts **siempre
con el Python del paquete**:

```bash
PY=.entorno/bin/python
S=.agents/skills/afiliados-historias-exito/scripts
$PY $S/comprobar_entorno.py                        # lo primero en cada sesión
$PY $S/revisar_insumos.py "/ruta/a/la carpeta"     # lo primero en cada capítulo
$PY $S/montar.py "/ruta/a/la carpeta/proyecto.json"
```

## Permisos y entorno: léelo antes del primer comando

- **Esta skill necesita «Acceso total».** whisper transcribe con la GPU del Mac y, en el modo
  protegido de Codex, macOS no deja usarla. Si `comprobar_entorno.py` dice que whisper no ve
  la GPU, **para** y pídele a la persona que cambie los permisos de la conversación a «Acceso
  total» («Full access»). No hay otro arreglo.
- **No instales nada** —ni `pip install`, ni otro whisper, ni otro ffmpeg, ni Homebrew— y no
  transcribas por otro camino. Todo lo necesario está en `.entorno/` con las versiones que se
  validaron; con otras, los cortes salen mal.
- Si falta `.entorno/` o `comprobar_entorno.py` marca FALTA, la solución es que la persona
  haga doble clic en `instalar.command`. Díselo con esas palabras.

`montar.py` hace el resto y se detiene **dos veces**, en los dos puntos donde hace falta
criterio humano —o tuyo—. Se relanza tantas veces como haga falta; retoma donde se quedó.

Si retocas cortes, vuelve a lanzar `montar.py` (o `render.py`): los clips que cambiaron se
rehacen solos, **no borres nada**. Y **después de cada render corre `verificar.py`**: no
entregues hasta que termine en «Texto correcto». Si dice «NO LO DES POR BUENO», corrige lo que
marca —incluye la revisión de sentido de los empalmes— y repite.

Los scripts son Python y ffmpeg, sin dependencias de ningún asistente. Todo lo mecánico
—transcribir, cortar, componer, mezclar, verificar— lo hacen ellos.

## Lo que decides tú, y es lo que hace bueno o malo el capítulo

**1. Qué frases entran.** Lee `transcripcion.txt` en la carpeta de trabajo del capítulo (`_archivos temporales/<capítulo>/`, junto a
la carpeta del capítulo; `transcribir.py` imprime la ruta exacta) (el guion de las tomas, con los
tiempos de cada palabra) y escribe la lista de segmentos en `proyecto.json`. Apunta a 2:05;
el límite es 2:10.

**2. Cómo suenan los empalmes.** `revisar_sentido.py` reconstruye cada costura —las últimas
palabras de un segmento seguidas de las primeras del siguiente— y las imprime. **Léelas.**

Tres reglas que costaron tres capítulos aprender y que no se pueden deducir de los números:

- **No hagas islas.** Un fragmento corto entre dos cortes a tope suena picado aunque cada
  corte por separado sea impecable. Se entregó un capítulo con «la casa de sus sueños»
  aislada: 0.95 s entre dos empalmes de 0.13 s. **Es preferible dejar una frase redundante
  que meter un corte que se oiga.**
- **Que cada segmento cierre una idea.** Acabar en «y», «de» o «que» solo vale si el segmento
  siguiente continúa esa misma frase. Un capítulo decía «...la casa de sus sueños **y** el
  tema del precio»: una conjunción huérfana cosiendo dos ideas sin relación.
- **No confíes en las marcas de tiempo de la transcripción para cortar.** Se adelantan al
  final real de la palabra. Los cortes se colocan midiendo energía del audio
  (`ajustar_cortes.py`), y se comprueban midiendo energía (`verificar.py`), no transcribiendo:
  whisper reconoce «nacional» aunque le falte la última sílaba.

## Datos que hay que pedir

Al empezar, en una sola pregunta: nombre del afiliado, nombre y cargo de quien habla —tal como
quiere que salga en pantalla—, usuarios de Facebook e Instagram (en Instagram, el usuario con @, no el nombre de la empresa), y si las preguntas son las de
siempre. No los inventes: el rótulo va sobreimpreso sobre la cara de una persona real.

## Qué se entrega

Dentro de la carpeta del capítulo, en «video terminado y editables»: el MP4, un FCPXML que
apunta a los archivos originales, la carpeta `Graficos/` que el XML necesita, y
`Guion de edicion.md`. De ese guion, **las dos últimas secciones se escriben a mano**: qué se
cortó y por qué, y qué quedó sin confirmar.
