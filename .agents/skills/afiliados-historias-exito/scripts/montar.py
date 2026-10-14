#!/usr/bin/env python3
"""Monta un capítulo entero, parando donde hace falta una persona.

    python3 montar.py proyecto.json

Es la puerta de entrada: en vez de recordar siete scripts y su orden, se corre este y él
sabe en qué punto está el capítulo y qué toca. Se puede volver a lanzar tantas veces como
haga falta — retoma donde se quedó y no repite trabajo hecho.

Hay dos paradas que **no se pueden automatizar**, y son justo las que hacen que el capítulo
se entienda: elegir qué frases entran, y leer cómo suenan los empalmes. El script se detiene
ahí, explica qué mirar, y espera.
"""
import os
import subprocess
import sys

import comun as C

AQUI = os.path.dirname(os.path.abspath(__file__))


def corre(script, *args, silencioso=False):
    r = subprocess.run([sys.executable, os.path.join(AQUI, script), *args],
                       capture_output=silencioso, text=True)
    return r.returncode, (r.stdout or "") if silencioso else ""


def titulo(n, texto):
    print(f"\n{'─' * 72}\n  PASO {n}. {texto}\n{'─' * 72}")


def para(mensaje, siguiente):
    print(f"\n{'=' * 72}")
    print(f"  ALTO — te toca a ti")
    print(f"{'=' * 72}\n{mensaje}\n")
    print(f"Cuando termines, vuelve a correr montar.py con el mismo comando ({siguiente}).\n"
          f"Si cambias segmentos, no borres nada: los clips que cambiaron se rehacen solos.")
    sys.exit(0)


def main():
    if len(sys.argv) < 2:
        sys.exit("uso: python3 montar.py proyecto.json")
    ruta = sys.argv[1]
    p = C.carga(ruta)
    nombre = os.path.basename(ruta)
    print(f"\nCapítulo: {p['afiliado']}")

    titulo(1, "Revisar el material entregado")
    if corre("revisar_insumos.py", p["_base"])[0] != 0:
        sys.exit("\nFalta material. Mira arriba qué es.")

    titulo(2, "Transcribir las tomas")
    guion = os.path.join(p["_trabajo"], "transcripcion.txt")
    if os.path.exists(guion):
        print(f"  ya está hecha: {guion}")
    elif corre("transcribir.py", ruta)[0] != 0:
        sys.exit("\nLa transcripción falló.")

    if not p["segmentos"]:
        para(f"Ahora hay que decidir qué entra en el capítulo.\n\n"
             f"  1. Lee  {guion}\n"
             f"     Es el guion de las tomas: cada palabra con su tiempo y las pausas\n"
             f"     marcadas. Se lee sin ver el video.\n"
             f"  2. Escribe la lista de segmentos en {nombre}, siguiendo el ejemplo de\n"
             f"     references/proyecto-ejemplo.json\n"
             f"  3. Apunta a 2:05 de duración total; el límite de la serie es 2:10.", nombre)

    titulo(3, "Afinar los puntos de corte")
    if corre("ajustar_cortes.py", ruta, "--aplicar")[0] != 0:
        sys.exit("\nEl ajuste de cortes falló.")

    titulo(4, "Revisar que el sentido no se rompe")
    corre("revisar_sentido.py", ruta)
    marca = os.path.join(p["_trabajo"], ".sentido-revisado")
    if not os.path.exists(marca):
        open(marca, "w").close()
        para("Lee las costuras de arriba: son las frases tal como van a sonar al empalmar.\n"
             "Que sean gramaticales no basta — tienen que significar algo.\n\n"
             "  · Si alguna no encaja, corrige `entrada`/`salida` de ese segmento.\n"
             "  · Si una respuesta abre con muletilla, sube su `entrada` al instante\n"
             "    que se indica.\n\n"
             "Si todo está bien, no toques nada.", nombre)

    titulo(5, "Tomas de apoyo")
    hay = os.path.isdir(p["_broll"]) and [
        f for f in os.listdir(p["_broll"])
        if f.lower().endswith(C.EXT_VIDEO + C.EXT_IMAGEN) and not f.startswith(".")]
    if not hay:
        print("  no hay material en Apoyo/ — el capítulo va con plano fijo")
    elif p.get("broll"):
        print(f"  {len(p['broll'])} inserto(s) ya colocados")
    else:
        corre("revisar_broll.py", ruta)
        para("Hay material de apoyo sin colocar. Arriba tienes la ficha de cada toma y una\n"
             "hoja de contactos con sus fotogramas.\n\n"
             "Decide sobre qué frase cae cada una y añádelas a la lista «broll» del\n"
             "proyecto, con el formato que se indica arriba. Tres reglas:\n\n"
             "  · Que ilustre lo que se está diciendo en ese momento.\n"
             "  · Nunca sobre el rótulo del nombre ni sobre las tarjetas de redes.\n"
             "  · Entre 2.5 y 9 segundos, y sin pasar del tercio del capítulo.\n\n"
             "Si prefieres dejarlo con plano fijo, saca el material de Apoyo/.", nombre)

    titulo(6, "Generar los gráficos")
    if corre("build_assets.py", ruta)[0] != 0:
        sys.exit("\nNo pude componer los gráficos.")
    print(f"\n  Mira {os.path.join(p['_gfx'], 'intro.png')} antes de seguir:\n"
          f"  si el logo del afiliado salió de un video, suele arrastrar una línea fantasma.")

    titulo(7, "Renderizar")
    if corre("render.py", ruta)[0] != 0:
        sys.exit("\nEl render falló. Mira el error de arriba.")

    titulo(8, "Verificar")
    if corre("verificar.py", ruta)[0] != 0:
        print("\n  La verificación encontró algo. Léelo arriba antes de entregar.")

    titulo(9, "Preparar la entrega")
    corre("exportar_xml.py", ruta)

    print(f"\n{'=' * 72}")
    print(f"  Capítulo montado.  Revisa dos cosas antes de darlo por bueno:")
    print(f"{'=' * 72}")
    print(f"  1. La hoja de contactos: {os.path.join(p['_trabajo'], 'qc', 'hoja-contactos.png')}")
    print(f"  2. El video con audífonos, atento a los empalmes.")
    print(f"\n  Y completa a mano las dos últimas secciones de")
    print(f"  {os.path.join(p['_salida'], 'Guion de edicion.md')}\n")


if __name__ == "__main__":
    main()
