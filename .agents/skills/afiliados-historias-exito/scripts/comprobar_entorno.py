#!/usr/bin/env python3
"""Comprueba que la máquina tiene todo lo que la skill necesita, antes de empezar.

    python3 comprobar_entorno.py

Existe porque los fallos por entorno incompleto aparecen tarde y mal: la fuente que no está
revienta a mitad de generar los gráficos, y whisper que no arranca deja una transcripción de
seis palabras que parece buena hasta que los cortes salen donde no son. Mejor saberlo antes.

Devuelve 0 si se puede trabajar y 1 si falta algo imprescindible.
"""
import os
import shutil
import subprocess
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
# La lista vive en build_assets.py para no duplicarla; aquí solo se comprueba.
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
ASSETS = ["cortinilla.mp4", "fondo-edificios.png", "camacol-santander.png",
          "camacol-blanco.png", "icono-facebook.png", "icono-instagram.png"]

OK, FALTA, AVISO = "  ok  ", " FALTA", " aviso"
problemas, avisos = [], []


def linea(estado, que, detalle=""):
    print(f"[{estado}] {que}" + (f"  — {detalle}" if detalle else ""))


print("\n=== Sistema ===")
if sys.platform == "darwin":
    v = os.popen("sw_vers -productVersion 2>/dev/null").read().strip()
    linea(OK, "macOS", v or "versión desconocida")
    import platform
    chip = platform.machine()
    if chip == "arm64":
        linea(OK, "chip Apple", chip)
    else:
        # mlx-whisper solo corre en Apple Silicon. Sin él no hay transcripción, y sin
        # transcripción no se puede decidir el corte.
        problemas.append("este Mac es Intel y el motor de transcripción (mlx-whisper) "
                         "necesita chip Apple; habría que sustituirlo")
        linea(FALTA, "chip", f"{chip} — mlx-whisper necesita chip Apple (M1 o posterior)")
else:
    # Las dos tipografías de la serie vienen con macOS. En otra plataforma hay que
    # instalarlas aparte: la lista de respaldos está en build_assets.py.
    avisos.append("esto está pensado para macOS; fuera de ahí hay que instalar las "
                  "tipografías a mano (mira la sección de abajo)")
    linea(AVISO, sys.platform, "la serie se produce en macOS")

print("\n=== Entorno del paquete ===")
# Lo normal es que instalar.command haya dejado en .entorno/ un Python, las librerías con las
# versiones de requisitos.txt, ffmpeg y el modelo de whisper. Así el resultado no depende de lo
# que tenga instalado cada Mac ni de qué versión haya salido esa semana.
import comun as C

if os.path.exists(C.PY_ENTORNO):
    r = subprocess.run([C.PY_ENTORNO, "-c", "import sys; print(sys.version.split()[0])"],
                       capture_output=True, text=True)
    if r.returncode:
        problemas.append("el Python del paquete no arranca: vuelve a correr instalar.command")
        linea(FALTA, "Python del paquete", (r.stderr or r.stdout).strip()[-120:])
    else:
        linea(OK, "Python del paquete", r.stdout.strip())
        pedidas = {}
        with open(os.path.join(SKILL, "requisitos.txt"), encoding="utf-8") as fq:
            for l in fq:
                if "==" in l and not l.startswith("#"):
                    n, v = l.strip().split("==")
                    pedidas[n.lower().replace("_", "-")] = v
        # Se queda con la primera aparición de cada librería, que es la que de verdad se
        # importa: el Python base trae su propio setuptools detrás de los paquetes instalados.
        r = subprocess.run([C.PY_ENTORNO, "-c",
                            "import importlib.metadata as m, json\nv = {}\n"
                            "for d in m.distributions():\n"
                            "    v.setdefault(d.metadata['Name'].lower().replace('_', '-'), d.version)\n"
                            "print(json.dumps(v))"],
                           capture_output=True, text=True)
        import json
        hay = json.loads(r.stdout or "{}")
        distintas = [f"{n} {hay.get(n, 'falta')} (debe ser {v})"
                     for n, v in pedidas.items() if hay.get(n) != v]
        if distintas:
            problemas.append("librerías con otra versión: " + ", ".join(distintas[:4]))
            linea(FALTA, "librerías", ", ".join(distintas[:4]))
        else:
            linea(OK, "librerías", f"las {len(pedidas)} con la versión validada "
                                   f"(whisper {pedidas.get('mlx-whisper')})")
    pesos = os.path.join(C.MODELO_LOCAL, "weights.safetensors")
    if os.path.exists(pesos):
        linea(OK, "modelo de whisper", f"{os.path.getsize(pesos) // 2**20} MB, sin internet")
    else:
        problemas.append("falta el modelo de whisper: vuelve a correr instalar.command")
        linea(FALTA, "modelo de whisper", "vuelve a correr instalar.command")
else:
    avisos.append("no hay entorno propio (.entorno): se usará lo del sistema, sin versiones fijas")
    linea(AVISO, "entorno propio", "no está — haz doble clic en instalar.command")

try:
    v = subprocess.run([C.FF, "-version"], capture_output=True, text=True, timeout=30)
    linea(OK, "ffmpeg", v.stdout.splitlines()[0][:60])
    if not C.FF.startswith(C.ENTORNO):
        avisos.append("ffmpeg no es el del paquete")
except (FileNotFoundError, IndexError):
    problemas.append("falta ffmpeg: haz doble clic en instalar.command")
    linea(FALTA, "ffmpeg", "haz doble clic en instalar.command")

print("\n=== GPU para transcribir ===")
# Dentro del modo protegido de Codex, whisper no ve la GPU. Se prueba aquí y no a mitad del
# capítulo, porque ahí el error tarda en salir y no dice qué hacer.
prueba = "import mlx.core as mx; mx.eval(mx.ones(8).sum()); print(mx.default_device())"
cmd = ([C.PY_ENTORNO, "-c", prueba] if os.path.exists(C.PY_ENTORNO) else
       ["uv", "run", "--with-requirements", C.REQUISITOS, "--python", "3.11.15",
        "python", "-c", prueba])
try:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode == 0:
        linea(OK, "GPU", r.stdout.strip())
    elif "etal" in r.stderr:
        problemas.append("whisper no ve la GPU: en Codex, pon los permisos en «Acceso total»")
        linea(FALTA, "GPU", "no disponible — en Codex, cambia los permisos a «Acceso total»")
    else:
        problemas.append("whisper no arranca: " + r.stderr.strip()[-160:])
        linea(FALTA, "GPU", r.stderr.strip()[-160:])
except FileNotFoundError:
    problemas.append("no hay con qué probar whisper: haz doble clic en instalar.command")
    linea(FALTA, "GPU", "haz doble clic en instalar.command")

print("\n=== Tipografías ===")
try:
    from build_assets import FUENTES
except Exception as e:
    FUENTES = {}
    linea(FALTA, "build_assets", f"no pude leer la lista de tipografías: {e}")
for papel, candidatas in FUENTES.items():
    from build_assets import abre_fuente
    k = next((k for k, (r, e) in enumerate(candidatas) if abre_fuente(r, e)), None)
    if k == 0:
        linea(OK, papel, f"{os.path.basename(candidatas[0][0])} {candidatas[0][1] or ''}".strip())
    elif k is not None:
        avisos.append(f"«{papel}» saldrá con una tipografía de repuesto")
        linea(AVISO, papel, f"falta {os.path.basename(candidatas[0][0])} "
                            f"{candidatas[0][1] or ''}; usará {os.path.basename(candidatas[k][0])}")
    else:
        problemas.append(f"ninguna tipografía disponible para «{papel}»")
        linea(FALTA, papel, "instala " + os.path.basename(candidatas[0][0]))

print("\n=== Assets de la serie ===")
for a in ASSETS:
    ruta = os.path.join(SKILL, "assets", a)
    if os.path.exists(ruta):
        linea(OK, a, f"{os.path.getsize(ruta) // 1024} KB")
    else:
        problemas.append(f"falta el asset {a}")
        linea(FALTA, a)

print("\n=== Plantilla y documentación ===")
for rel in ("references/proyecto-ejemplo.json", "references/estilo-serie.md",
            "references/trampas-ffmpeg.md", "SKILL.md", "MANUAL-CAMACOL.md"):
    ruta = os.path.join(SKILL, rel)
    linea(OK if os.path.exists(ruta) else FALTA, rel)
    if not os.path.exists(ruta):
        problemas.append(f"falta {rel}")

print("\n=== Espacio en disco ===")
libre = shutil.disk_usage(SKILL).free // (1024 ** 3)
if libre < 5:
    avisos.append(f"solo quedan {libre} GB libres; un capítulo usa ~1.5 GB de intermedios")
    linea(AVISO, "espacio libre", f"{libre} GB — un capítulo usa ~1.5 GB")
else:
    linea(OK, "espacio libre", f"{libre} GB")

print()
if problemas:
    print(f"{len(problemas)} problema(s) que impiden trabajar:")
    for x in problemas:
        print(f"  - {x}")
if avisos:
    print(f"{len(avisos)} aviso(s):")
    for x in avisos:
        print(f"  - {x}")
if not problemas:
    print("Entorno completo: se puede montar un capítulo.")
sys.exit(1 if problemas else 0)
