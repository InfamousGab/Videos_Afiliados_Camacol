#!/usr/bin/env python3
"""Extrae el logo de un afiliado desde un capítulo anterior de la serie, cuando no existe el
archivo original del logo.

    # 1. mirar dónde aparece el logo (saca fotogramas cada 2 s de los primeros 12 s)
    python3 extraer_logo.py buscar "VIDEO ORIGINAL VERSION TERMINADA.mp4" salida/

    # 2. recortar la tarjeta blanca que contiene el logo, en coordenadas de 1920x1080
    python3 extraer_logo.py recortar video.mp4 2.6 722 348 470 250 salida/logo.png
                                              ^t   ^x  ^y  ^an ^al

La placa de intro de la serie muestra el logo grande sobre una tarjeta blanca: es el mejor
sitio de donde sacarlo. Recorta **por dentro** de la tarjeta, sin incluir sus esquinas
redondeadas — si entra el borde, aparece luego una línea vertical fantasma al costado del
logo en todos los gráficos.

El resultado sale con el fondo blanco convertido en transparencia, listo para `proyecto.json`.
Un logo sacado de un video está comprimido; si el afiliado puede mandar el original, siempre
es mejor.
"""
import os
import sys

import comun as C


def buscar(video, destino):
    os.makedirs(destino, exist_ok=True)
    for t in (0.5, 1.5, 2.5, 3.5, 6.0, 12.0):
        C.run([C.FF, "-y", "-v", "error", "-ss", str(t), "-i", video,
               "-frames:v", "1", "-vf", "scale=640:-1",
               os.path.join(destino, f"t{t}.png")], fatal=False)
    print(f"Fotogramas en {destino}. Ábrelos, localiza la tarjeta blanca con el logo y\n"
          "calcula el recorte en coordenadas de 1920x1080 (los PNG están a 640 de ancho:\n"
          "multiplica por 3).")


def recortar(video, t, x, y, an, al, dst):
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    C.run([C.FF, "-y", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1",
           "-vf", f"crop={an}:{al}:{x}:{y}", dst], "recortando el logo")
    print(f"{dst}\n  Ábrelo y comprueba que no arrastra el borde de la tarjeta ni recorta\n"
          "  parte del logo. build_assets.py se encarga de volver transparente el blanco.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    modo = sys.argv[1]
    if modo == "buscar":
        buscar(sys.argv[2], sys.argv[3])
    elif modo == "recortar":
        v, t, x, y, an, al, dst = sys.argv[2:9]
        recortar(v, t, int(x), int(y), int(an), int(al), dst)
    else:
        sys.exit(__doc__)
