#!/usr/bin/env python3
"""Configuración compartida por los scripts de la serie «Afiliados que construyen
historias de éxito» (Camacol Santander).

Todos los scripts reciben la ruta de un `proyecto.json` y trabajan sobre él. Las rutas
del JSON se interpretan relativas a la carpeta donde vive ese archivo.
"""
import glob
import hashlib
import math
import json
import os
import shutil
import subprocess
import sys

FPS = 30
XF = 0.20            # disolvencia de imagen entre segmentos

# --- Por qué el audio no se mezcla en esos 0.20 s -----------------------------------------
# Un `xfade` de 0.20 s solapa el final de un clip con el principio del siguiente, así que
# obliga a sacrificar 0.20 s de material en cada empalme. Aplicado también al audio, eso se
# come el final de una palabra y el arranque de la siguiente, y las mezcla: es exactamente lo
# que hacía que los cortes se oyeran tajados y poco profesionales.
#
# Ningún editor monta así. En una mesa de montaje la disolvencia de imagen se alimenta de
# **material sobrante fuera del corte** (los «handles» o colas), no del contenido: los dos
# planos se acercan hasta tocarse y la mezcla ocurre sobre lo que había antes y después del
# punto de corte. El audio, debajo, es un empalme a tope con una disolvencia de milisegundos
# que solo evita el chasquido.
#
# Aquí se hace igual: cada segmento se recorta con COLA/2 de más por cada lado, la imagen
# disuelve sobre esas colas y el audio del contenido se conserva **entero**, sin perder ni un
# milisegundo. Ver `references/trampas-ffmpeg.md`.
COLA = 0.20          # material extra por segmento (COLA/2 antes y COLA/2 después)
XF_AUDIO = 0.008     # micro-fundido en cada empalme de audio, solo contra el chasquido
XF_BLOQUE = 0.40     # disolvencia contra la intro y la cortinilla
DUR_INTRO = 3.0

# Dos tratamientos de imagen según de dónde venga la toma. Las copias de WhatsApp llegan a
# ~848x478 y hay que escalarlas más del doble, así que piden enfoque y contraste con mano
# firme. El material de cámara ya viene a 1080p: aplicarle el mismo enfoque le deja halos en
# los bordes y le da un aspecto crujiente, así que solo se retoca lo justo.
V_IN_ESCALADO = ("fps=30,scale=1920:-2:flags=lanczos,crop=1920:1080,"
                 "unsharp=5:5:0.55:5:5:0.0,eq=contrast=1.03:saturation=1.04")
V_IN_NATIVO = ("fps=30,scale=1920:-2:flags=lanczos,crop=1920:1080,"
               "unsharp=5:5:0.18:5:5:0.0,eq=contrast=1.015:saturation=1.02")
# Por segmento solo se quita el retumbe. La reducción de ruido va sobre el cuerpo ya montado
# (A_CUERPO): si se aplica clip a clip, cada uno converge a un residuo distinto y el ambiente
# de la sala «escalona» en cada empalme, que con un splice corto se oye como un golpecito.
A_IN = "highpass=f=85"
A_CUERPO = "afftdn=nr=8:nf=-30"


def filtro_video(ancho, recorte=None):
    """Filtro de imagen para una toma de `ancho` píxeles.

    `recorte` opcional, en formato ffmpeg (`crop=1400:788:200:292`), para cerrar el encuadre
    cuando el plano viene muy abierto; se aplica antes de reescalar a 1080p.
    """
    base = V_IN_ESCALADO if (ancho or 0) < 1900 else V_IN_NATIVO
    if recorte:
        return f"fps=30,{recorte}," + base.split("fps=30,", 1)[1]
    return base

# ------------------------------------------------------------------ tomas auxiliares
EXT_VIDEO = (".mp4", ".mov", ".m4v", ".mkv", ".avi")
EXT_IMAGEN = (".jpg", ".jpeg", ".png", ".webp", ".heic")

# Márgenes de la ventana donde puede entrar una toma auxiliar. Nacen de mirar la serie:
# los insertos del capítulo de referencia duran entre 5 y 8 s y entran con corte seco.
BROLL_MIN = 2.5      # menos que esto se lee como un parpadeo
BROLL_MAX = 9.0      # más que esto y el espectador olvida a quién está escuchando
BROLL_SEPARACION = 1.5   # entrevista mínima entre dos insertos
BROLL_COBERTURA = 0.40   # proporción del cuerpo que no conviene pasar


def encaje(src, dst, ajuste, i, w=1920, h=1080):
    """Filtro que mete una toma auxiliar de cualquier proporción en un cuadro `w`x`h`.

    - «llenar»: amplía hasta cubrir y recorta lo que sobra. Para material que ya es 16:9.
    - «encajar»: la toma va entera y centrada, y los lados se rellenan con ella misma
      ampliada, desenfocada y oscurecida. Es lo que salva a las tomas verticales de obra,
      donde recortar se comería la grúa o el edificio.
    """
    if ajuste == "llenar":
        return (f"{src}scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}{dst}")
    return (f"{src}split[bf{i}][bg{i}];"
            f"[bg{i}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"gblur=sigma={max(12, w // 64)},eq=brightness=-0.12:saturation=0.80[bb{i}];"
            f"[bf{i}]scale={w}:{h}:force_original_aspect_ratio=decrease[bs{i}];"
            f"[bb{i}][bs{i}]overlay=(W-w)/2:(H-h)/2{dst}")


def ajuste_auto(w, h):
    """16:9 (o casi) se lleva a pantalla completa; cualquier otra cosa va con fondo."""
    if not w or not h:
        return "encajar"
    return "llenar" if abs((w / h) - 16 / 9) / (16 / 9) <= 0.12 else "encajar"


def broll(p, dur, avisar=True):
    """Resuelve `broll` de proyecto.json a tiempos absolutos del cuerpo, ya validados.

    Cada entrada del JSON se ancla a un segmento (`segmento` + `desde`) y no a un segundo
    absoluto: así, si más adelante se retoca un corte anterior, el inserto sigue cayendo
    sobre la misma frase en vez de quedar desplazado.
    """
    if not p.get("broll"):
        return []
    ini = inicios(p, dur)
    largo = dur_cuerpo(p, dur)
    fuera, avisos = [], []
    for b in p["broll"]:
        ruta = os.path.join(p["_broll"], b["archivo"])
        if not os.path.exists(ruta):
            sys.exit(f"No encuentro la toma auxiliar: {ruta}")
        k = b["segmento"]
        if not 0 <= k < len(dur):
            sys.exit(f"{b['archivo']}: el segmento {k} no existe")
        d = float(b["duracion"])
        t_in = round(ini[k] + float(b.get("desde", 0)), 3)
        t_out = round(t_in + d, 3)
        es_img = ruta.lower().endswith(EXT_IMAGEN)
        d_src, w, h, _, _ = info_media(ruta)
        entrada = float(b.get("entrada", 0))

        if t_in < 0 or t_out > largo:
            sys.exit(f"{b['archivo']}: cae fuera del cuerpo "
                     f"({tc(t_in)}–{tc(t_out)}, cuerpo {tc(largo)})")
        if not es_img and d_src and entrada + d > d_src + 0.05:
            sys.exit(f"{b['archivo']}: dura {d_src:.1f} s y le pides {entrada}+{d} s")
        if d < BROLL_MIN:
            avisos.append(f"{b['archivo']}: {d:.1f} s se lee como un parpadeo "
                          f"(mínimo recomendado {BROLL_MIN} s)")
        if d > BROLL_MAX:
            avisos.append(f"{b['archivo']}: {d:.1f} s es mucho sin volver a la vocera "
                          f"(máximo recomendado {BROLL_MAX} s)")
        fuera.append({"ruta": ruta, "archivo": b["archivo"], "t_in": t_in, "t_out": t_out,
                      "dur": d, "entrada": entrada, "imagen": es_img,
                      "ajuste": b.get("ajuste") or ajuste_auto(w, h),
                      "nota": b.get("texto", "")})

    fuera.sort(key=lambda x: x["t_in"])
    for a, b2 in zip(fuera, fuera[1:]):
        hueco = round(b2["t_in"] - a["t_out"], 2)
        if hueco < BROLL_SEPARACION:
            avisos.append(f"entre «{a['archivo']}» y «{b2['archivo']}» solo quedan "
                          f"{hueco:.1f} s de entrevista (mínimo {BROLL_SEPARACION} s)")
    cobertura = sum(x["dur"] for x in fuera) / largo
    if cobertura > BROLL_COBERTURA:
        avisos.append(f"las tomas auxiliares cubren el {cobertura:.0%} del cuerpo; "
                      f"pasado el {BROLL_COBERTURA:.0%} el capítulo deja de ser una entrevista")
    if avisar and avisos:
        print("    avisos sobre las tomas auxiliares:")
        for a in avisos:
            print(f"      - {a}")
    return fuera


# El nombre con que se importa un módulo no siempre es el del paquete que hay que instalar.
PAQUETE = {"PIL": "pillow==11.3.0", "numpy": "numpy==2.4.6"}


def asegura_dependencias(*modulos):
    """Relanza el script bajo `uv` si falta alguna dependencia, en vez de reventar.

    Tres de los scripts necesitan numpy y otros Pillow, pero el Python del sistema no trae
    numpy. Obligar a recordar un invocador distinto según el script es una trampa: se olvida,
    y lo que sale es un `ModuleNotFoundError` que no dice qué hacer. Así todos se corren
    igual, con `python3 lo-que-sea.py proyecto.json`.

    Dos detalles que costaron una pasada de pruebas: al relanzar hay que pedir **todos** los
    módulos, no solo los que faltaban, porque el entorno que crea uv no hereda los del
    sistema; y hay que pedirlos por su nombre de paquete (`pillow`, no `PIL`).
    """
    faltan = []
    for m in modulos:
        try:
            __import__(m)
        except ImportError:
            faltan.append(m)
    if not faltan:
        return
    paquetes = [PAQUETE.get(m, m) for m in modulos]
    if os.path.exists(PY_ENTORNO) and not os.environ.get("SKILL_RELANZADO"):
        # El paquete trae su propio Python con las versiones fijas: es el camino normal en el
        # Mac de trabajo, y no necesita ni internet ni escribir fuera de la carpeta.
        raise SystemExit(subprocess.run(
            [PY_ENTORNO] + sys.argv, env=dict(os.environ, SKILL_RELANZADO="1")).returncode)
    if os.environ.get("SKILL_RELANZADO"):
        sys.exit(f"Faltan dependencias ({', '.join(faltan)}) y el relanzado con uv tampoco "
                 f"las encontró.\nInstálalas a mano:  pip install {' '.join(paquetes)}")
    cmd = ["uv", "run"]
    for q in paquetes:
        cmd += ["--with", q]
    cmd += ["--python", "3.11", "python"] + sys.argv
    try:
        raise SystemExit(subprocess.run(
            cmd, env=dict(os.environ, SKILL_RELANZADO="1")).returncode)
    except FileNotFoundError:
        sys.exit(f"Falta {', '.join(faltan)} y no encuentro `uv` para resolverlo al vuelo.\n"
                 f"Instala uv (https://docs.astral.sh/uv/) o:  "
                 f"pip install {' '.join(paquetes)}")


# ------------------------------------------------------------------ música de fondo
# Niveles medidos sobre el capítulo de referencia de la serie: la música sola en la intro
# está a -20 dBFS y agachada bajo el diálogo a -35, o sea 15 dB de diferencia, con la voz
# 16 dB por encima del colchón. No son valores inventados, son los de la serie.
#
# Los valores de abajo están calibrados para que la mezcla caiga en esas cifras; se
# comprobaron midiendo el resultado, no a ojo. Si se cambia la pista y la mezcla se va de
# sitio, `comprobar_mezcla.py` lo dice y estos cuatro números son los que hay que mover.
MUSICA_LUFS = -17.5       # a esto se normaliza la pista antes de mezclarla
MUSICA_INTRO_DB = 0.0     # en la placa de intro suena sola y protagonista
MUSICA_FONDO_DB = -7.0    # bajo el diálogo
MUSICA_CIERRE_DB = -2.0   # vuelve a subir en la cortinilla
MUSICA_BAJADA = 0.8       # cuánto tarda en agacharse cuando entra la voz
MUSICA_SUBIDA = 0.6       # y en volver a subir al final
EXT_AUDIO = (".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg")


def banco_musica():
    return sorted(glob.glob(os.path.join(ASSETS, "musica", "*")))


def elige_musica(p):
    """Pista para este capítulo: la indicada, o una del banco elegida por el afiliado.

    La elección parece azarosa entre capítulos pero es **estable para un mismo afiliado**:
    sale de una huella del nombre. Si fuera azar de verdad, volver a renderizar un capítulo
    le cambiaría la música, y con lo fácil que es tener que repetir un render eso sería una
    fuente de incoherencias difícil de rastrear.
    """
    explicita = (p.get("musica") or {}).get("pista")
    if explicita:
        ruta = explicita if os.path.isabs(explicita) else os.path.join(p["_base"], explicita)
        if not os.path.exists(ruta):
            sys.exit(f"No encuentro la pista de música: {ruta}")
        return ruta
    banco = [f for f in banco_musica() if f.lower().endswith(EXT_AUDIO)]
    if not banco:
        return None
    huella = int(hashlib.sha1(p["afiliado"].encode("utf-8")).hexdigest(), 16)
    return banco[huella % len(banco)]


# Filtros que se le aplican a la música para dejarle sitio a la voz. Viven aquí, y no en el
# render, porque la ganancia hay que medirla **con ellos puestos**: el paso alto le quita a
# una pista con mucho grave más de 3 dB, y medir antes de aplicarlo deja la música siete dB
# por debajo de donde debería, que fue exactamente lo que pasó.
MUSICA_FILTROS = "highpass=f=90,equalizer=f=1200:width_type=o:width=2.2:g=-4"


MUSICA_VENTANA = 0.05   # tiene que ser la misma que usa comprobar_mezcla.py


def _niveles_musica(ruta, limite=40.0, desde=0.0, filtros=None, ventana=1.0):
    """Niveles de una pista en ventanas de `ventana` segundos, opcionalmente ya filtrada.

    El tamaño de ventana no es un detalle: sobre música con pulso, la mediana de ventanas de
    50 ms cae unos 7 dB por debajo de la de ventanas de 1 s, porque las cortas caen en los
    huecos entre golpes. Calibrar con una y verificar con otra hace que la música acabe
    siete dB por debajo de donde debería, y el error es invisible porque los dos números
    parecen decibelios comparables.
    """
    import array
    cmd = [FF, "-v", "error", "-ss", str(desde), "-t", str(limite), "-i", ruta,
           "-vn", "-ac", "1", "-ar", "16000"]
    if filtros:
        cmd += ["-af", filtros]
    cmd += ["-f", "s16le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    a = array.array("h")
    a.frombytes(r.stdout)
    if not a:
        return []
    x = [v / 32768.0 for v in a]
    n = max(1, int(16000 * ventana))
    return [20 * math.log10(math.sqrt(sum(v * v for v in x[i:i + n]) / n) + 1e-9)
            for i in range(0, len(x) - n, n)]


def ganancia_musica(ruta, desde=0.0, objetivo=-20.4):
    """Ganancia en dB para que la pista suene al nivel que usa la serie.

    Se hacía con `loudnorm` y no servía: en una sola pasada no acierta el objetivo, así que
    dos pistas normalizadas al mismo valor acababan sonando con 3.6 dB de diferencia y la
    música de la placa salía siete dB por debajo de lo que debía. Medir el nivel típico y
    aplicar una ganancia fija es exacto y además reproducible.

    Se mide **desde el punto donde la música entra y con los filtros ya aplicados**, que es
    la única forma de que el número signifique algo: medir la pista cruda desde el segundo
    cero mezcla la construcción inicial con el resto y no descuenta lo que se llevan el paso
    alto y el ecualizador.

    El objetivo por defecto es el medido en el capítulo de referencia de la serie para la
    música sola en la intro.
    """
    niv = _niveles_musica(ruta, 30.0, desde, MUSICA_FILTROS, MUSICA_VENTANA)
    if not niv:
        return 0.0
    tipico = sorted(niv)[len(niv) // 2]
    return round(objetivo - tipico, 2)


def entrada_musica(ruta, limite=40.0):
    """Segundo de la pista donde empieza a sonar a su nivel normal.

    Casi toda la música de banco entra con fundido o con una construcción lenta: Pista2 tarda
    12 segundos en llegar a su nivel y Pista5 dieciséis. Como la placa de intro dura tres
    segundos, arrancar la pista desde el principio significa que justo donde la música tiene
    que ser protagonista suena 15 dB por debajo de lo que debería.

    Se busca el primer segundo que llega a 3 dB del nivel típico de la pista y se entra por
    ahí. El fundido de entrada de la mezcla disimula que se empieza a mitad.
    """
    niv = _niveles_musica(ruta, limite)
    if not niv:
        return 0.0
    tipico = sorted(niv)[len(niv) // 2]
    return float(next((i for i, v in enumerate(niv) if v >= tipico - 3), 0))


# Nombres de la convención nueva. Se usan como valor por defecto; lo que diga proyecto.json
# siempre gana, para no romper los capítulos ya montados.
SALIDA = "video terminado y editables"
TEMPORALES = "_archivos temporales"


def _tiene_video(carpeta):
    return any(f.lower().endswith(EXT_VIDEO) for f in os.listdir(carpeta))


def busca_logo(base, tomas, broll):
    """Primera imagen suelta en la carpeta del capítulo, que es donde la deja quien entrega.

    Se excluyen las carpetas de tomas y de apoyo: ahí puede haber fotos que son material del
    video, no el logo del afiliado.
    """
    for carpeta in (base, os.path.join(base, "insumos")):
        if not os.path.isdir(carpeta):
            continue
        if os.path.abspath(carpeta) in (os.path.abspath(tomas), os.path.abspath(broll)):
            continue
        for f in sorted(os.listdir(carpeta)):
            if f.startswith(".") or not f.lower().endswith(EXT_IMAGEN):
                continue
            return os.path.join(carpeta, f)
    return None


SKILL = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ASSETS = os.path.join(SKILL, "assets")

# --- El entorno del paquete -----------------------------------------------------------------
# Lo que salió bien en el Mac donde se desarrolló la skill tiene que salir igual en otro Mac, y
# eso no se consigue bajando «la última versión» de cada cosa cada vez que se corre: durante el
# desarrollo la librería de GPU de whisper cambió cuatro veces sin que nadie lo decidiera.
# `instalar.command` deja en `<paquete>/.entorno/` un Python, las librerías con las versiones
# exactas de `requisitos.txt`, ffmpeg y el modelo de whisper. Todo se busca relativo a la
# carpeta, así que se puede mover o renombrar sin romper nada. Si no existe (el Mac de
# desarrollo), se cae a lo que haya en el sistema.
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(SKILL)))
ENTORNO = os.path.join(RAIZ, ".entorno")
PY_ENTORNO = os.path.join(ENTORNO, "bin", "python")
MODELO_WHISPER = "mlx-community/whisper-large-v3-turbo"
REVISION_WHISPER = "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"
VERSION_WHISPER = "0.4.3"
MODELO_LOCAL = os.path.join(ENTORNO, "modelos", "whisper-large-v3-turbo")
REQUISITOS = os.path.join(SKILL, "requisitos.txt")


def _busca_ffmpeg():
    propio = os.path.join(ENTORNO, "bin", "ffmpeg")
    if os.path.exists(propio):
        return propio
    for c in (shutil.which("ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg",
              os.path.expanduser("~/.local/bin/ffmpeg")):
        if c and os.path.exists(c):
            return c
    return "ffmpeg"


FF = _busca_ffmpeg()


SIN_GPU = """
whisper no puede usar la GPU de este Mac, y sin ella no se puede transcribir.

Casi siempre es porque el asistente está trabajando en modo protegido (en Codex, el modo
por defecto). Solución: en Codex, cambia los permisos de esta conversación a «Acceso total»
(«Full access») y vuelve a pedir el capítulo.

Para el asistente: NO instales otro whisper ni transcribas por otro camino. Los cortes de
esta skill están calibrados con este motor y esta versión; con otro, salen mal.
"""

_gpu = None


def exige_gpu():
    """Para con un mensaje claro si whisper no va a poder usar la GPU. Se comprueba una vez:
    lanzar whisper sin GPU tarda en fallar y el error que da no dice qué hacer."""
    global _gpu
    if _gpu:
        return
    prueba = "import mlx.core as mx; mx.eval(mx.ones(8).sum())"
    if os.path.exists(PY_ENTORNO):
        cmd = [PY_ENTORNO, "-c", prueba]
    else:
        cmd = ["uv", "run", "--with-requirements", REQUISITOS, "--python", "3.11.15",
               "python", "-c", prueba]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        sys.exit("Falta el entorno de la skill: haz doble clic en instalar.command.")
    if r.returncode:
        if "Metal" in r.stderr or "metal" in r.stderr:
            sys.exit(SIN_GPU)
        sys.exit(f"whisper no arranca:\n{r.stderr[-1500:]}\n"
                 "Si el error habla de módulos que faltan, vuelve a correr instalar.command.")
    _gpu = True


def whisper(wav, *opciones):
    """Comando para transcribir con whisper: el del paquete si está, o uvx con la versión fija."""
    exige_gpu()
    if os.path.exists(PY_ENTORNO):
        base = [PY_ENTORNO, "-m", "mlx_whisper.cli"]
    else:
        base = ["uvx", "--python", "3.11.15", "--with-requirements", REQUISITOS,
                "--from", f"mlx-whisper=={VERSION_WHISPER}", "mlx_whisper"]
    modelo = MODELO_LOCAL if os.path.isdir(MODELO_LOCAL) else MODELO_WHISPER
    return base + [wav, "--model", modelo] + list(opciones)


def entorno_whisper():
    """Variables para whisper: sin red, y con el ffmpeg del paquete en el PATH, porque whisper
    lo llama por su nombre para leer el audio."""
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([os.path.dirname(FF) if os.sep in FF else "",
                                   env.get("PATH", "")]).strip(os.pathsep)
    if os.path.isdir(MODELO_LOCAL):
        env["HF_HUB_OFFLINE"] = "1"
    return env


def run(cmd, etapa="", fatal=True, env=None):
    """Ejecuta ffmpeg o whisper y devuelve stderr (ffmpeg escribe ahí toda su información)."""
    if etapa:
        print(f">>> {etapa}", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if p.returncode and fatal:
        print(p.stderr[-4000:])
        sys.exit(f"FALLO en {etapa or cmd[0]}")
    return p.stderr


def carga(ruta_json):
    """Lee proyecto.json y resuelve rutas, carpetas de trabajo e índices de bloque."""
    ruta_json = os.path.abspath(ruta_json)
    base = os.path.dirname(ruta_json)
    if not os.path.exists(ruta_json):
        sys.exit(f"No encuentro {ruta_json}\n"
                 f"Crea el proyecto copiando references/proyecto-ejemplo.json a la carpeta "
                 f"del capítulo como proyecto.json.")
    try:
        with open(ruta_json, encoding="utf-8") as f:
            p = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"{os.path.basename(ruta_json)} tiene un error de formato en la línea "
                 f"{e.lineno}: {e.msg}\nSuele ser una coma de más o unas comillas sin cerrar.")
    for clave in ("afiliado", "segmentos"):
        if clave not in p:
            sys.exit(f"A {os.path.basename(ruta_json)} le falta la clave «{clave}».")
    def ruta(clave, defecto=None):
        v = p.get(clave, defecto)
        return None if v is None else os.path.normpath(os.path.join(base, v))

    def resuelve(clave, candidatas, con_video=False):
        """Primera carpeta que exista, empezando por la indicada en proyecto.json.

        El valor explícito manda siempre, así que los capítulos antiguos —que traen
        `carpeta_tomas` escrito a mano— siguen resolviendo igual. Las candidatas que siguen
        son la convención nueva y luego la vieja, para que una carpeta recién armada funcione
        sin escribir ni una clave.
        """
        if p.get(clave):
            return ruta(clave)
        for c in candidatas:
            d = os.path.normpath(os.path.join(base, c))
            if os.path.isdir(d) and (not con_video or _tiene_video(d)):
                return d
        return os.path.normpath(os.path.join(base, candidatas[0]))

    p["_base"] = base
    p["_tomas"] = resuelve("carpeta_tomas", ["Entrevista", "Insumo principal", "."], True)
    p["_broll"] = resuelve("carpeta_broll", ["Apoyo", "insumos/broll"])
    p["_salida"] = resuelve("carpeta_salida", [SALIDA, "Entrega"])
    p["_logo"] = ruta("logo_afiliado") or busca_logo(base, p["_tomas"], p["_broll"])
    if not os.path.isdir(p["_tomas"]):
        sys.exit(f"No encuentro las tomas de la entrevista.\n"
                 f"Deberían estar en una carpeta «Entrevista» dentro de "
                 f"{os.path.basename(base) or base}.")
    # Los intermedios pesan ~1 GB por capítulo y no le interesan a nadie: van fuera de la
    # carpeta del capítulo para que esa quede con lo que importa y se pueda copiar o enviar
    # sin arrastrarlos.
    p["_trabajo"] = (ruta("carpeta_trabajo") if p.get("carpeta_trabajo")
                     else os.path.join(os.path.dirname(base), TEMPORALES,
                                       os.path.basename(base)))
    p["_gfx"] = os.path.join(p["_trabajo"], "gfx")
    p["_clips"] = os.path.join(p["_trabajo"], "clips")
    p["_out"] = os.path.join(p["_trabajo"], "out")
    for d in (p["_trabajo"], p["_gfx"], p["_clips"], p["_out"], p["_salida"]):
        os.makedirs(d, exist_ok=True)
    aviso = os.path.join(os.path.dirname(p["_trabajo"]), "LÉEME.txt")
    if os.path.basename(os.path.dirname(p["_trabajo"])) == TEMPORALES \
            and not os.path.exists(aviso):
        with open(aviso, "w", encoding="utf-8") as f:
            f.write("Archivos intermedios del montaje.\n\n"
                    "Se pueden borrar sin miedo: los videos terminados están en la carpeta de\n"
                    "cada capítulo, en «" + SALIDA + "».\n\n"
                    "Si los borras y luego hay que retocar un capítulo, se vuelven a generar\n"
                    "solos; solo tarda unos minutos más.\n")

    p.setdefault("duracion_maxima", 130)
    # Nombre corto para los archivos de salida (sin S.A.S. ni caracteres raros).
    p.setdefault("afiliado_corto", p["afiliado"].split(" S.A.S")[0].split(" SAS")[0].title())
    p.setdefault("cortinilla", os.path.join(ASSETS, "cortinilla.mp4"))
    if not os.path.isabs(p["cortinilla"]):
        p["cortinilla"] = ruta("cortinilla")

    # Primer segmento de cada bloque de pregunta: ahí entra su cenefa.
    inicio_bloque, visto = [], set()
    for k, s in enumerate(p["segmentos"]):
        b = s.get("bloque")
        if isinstance(b, int) and b not in visto:
            visto.add(b)
            inicio_bloque.append((b, k))
    p["_inicio_bloque"] = [k for _, k in sorted(inicio_bloque)]
    p["_inicio_redes"] = next(
        (k for k, s in enumerate(p["segmentos"]) if s.get("bloque") == "redes"), None)
    return p


def duraciones_reales(p):
    """Duración de **contenido** de cada intermedio, en segundos (sin las colas).

    Se usan estas y no las nominales del JSON porque cada corte se redondea a fotograma
    entero, y esa diferencia desplaza los tiempos de las cenefas.
    """
    ruta = os.path.join(p["_trabajo"], "duraciones.txt")
    if not os.path.exists(ruta):
        sys.exit("Falta trabajo/duraciones.txt: corre antes `render.py proyecto.json cuerpo`.")
    return [float(l.split()[1]) for l in open(ruta) if l.strip()]


def inicios(p, dur):
    """Inicio de cada segmento en la línea de tiempo del cuerpo.

    Los segmentos van pegados uno detrás de otro: la disolvencia de imagen no consume
    contenido, se alimenta de las colas (ver COLA arriba), así que no hay nada que descontar.
    """
    out, acc = [], 0.0
    for d in dur:
        out.append(round(acc, 4))
        acc += d
    return out


def dur_cuerpo(p, dur):
    return round(sum(dur), 4)


def dur_real(path):
    """Duración exacta de un archivo CFR 30 fps: número de fotogramas / 30.

    No usamos `ffprobe` porque no está instalado; contar fotogramas además es más fiable
    que leer la duración del contenedor, que redondea.
    """
    err = run([FF, "-hide_banner", "-i", path, "-map", "0:v", "-f", "null", "-"])
    fr = [l for l in err.splitlines() if l.startswith("frame=")][-1]
    return round(int(fr.split("frame=")[1].split()[0]) / float(FPS), 4)


def info_media(path):
    """(duración_segundos, ancho, alto, fps, tiene_audio) leídos de `ffmpeg -i`."""
    err = run([FF, "-hide_banner", "-i", path], fatal=False)
    dur = w = h = fps = None
    audio = False
    for l in err.splitlines():
        if "Duration:" in l and dur is None:
            # Una imagen fija reporta «Duration: N/A»: se deja en None en vez de reventar.
            try:
                hh, mm, ss = l.split("Duration:")[1].split(",")[0].strip().split(":")
                dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
            except ValueError:
                dur = None
        if "Stream #" in l and "Video:" in l and w is None:
            for tok in l.split(","):
                tok = tok.strip()
                if "x" in tok and tok.split("x")[0].strip().isdigit():
                    try:
                        w, h = (int(v) for v in tok.split()[0].split("x"))
                    except ValueError:
                        pass
                if tok.endswith("fps"):
                    fps = float(tok.split()[0])
        if "Stream #" in l and "Audio:" in l:
            audio = True
    return dur, w, h, fps, audio


def tc(s):
    return f"{int(s // 60)}:{s % 60:05.2f}"


def uso(nombre):
    if len(sys.argv) < 2:
        sys.exit(f"uso: python3 {nombre} proyecto.json [...]")
    return carga(sys.argv[1])
