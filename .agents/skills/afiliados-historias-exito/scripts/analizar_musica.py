#!/usr/bin/env python3
"""Mide las pistas del banco para elegir cuáles sirven de colchón bajo la voz.

    python3 analizar_musica.py            # el banco de la skill
    python3 analizar_musica.py carpeta    # otra carpeta

Una pista puede sonar preciosa y ser pésima de fondo. Lo que la hace servir no es el gusto,
son tres cosas medibles:

- **Energía en la banda de la voz (300 Hz – 3 kHz).** Es donde vive el habla. Cuanta más
  tenga la música ahí, más se pelea con la voz y más hay que bajarla, hasta que deja de
  aportar. Por debajo del 45 % del total va sobrada de sitio; por encima del 60 % estorba.
- **Rango dinámico.** Una pista con subidas y bajadas grandes bombea bajo el compresor de
  ducking y se nota. Un colchón quiere ser parejo.
- **Duración.** Basta con que cubra el capítulo: los de esta serie duran 2:06–2:08, con un
  límite de 2:10. Una pista más larga que eso no entra nunca en bucle, y el punto de
  repetición —que sí se oye— deja de ser un problema.

El veredicto es orientativo: sirve para descartar, no para elegir. Entre las que pasan, la
decisión es de oído.
"""
import array
import math
import os
import subprocess
import sys

import comun as C

SR = 16000
BANDA_BIEN, BANDA_MAL = 0.45, 0.60
DUR_MIN = 135.0     # el límite de la serie es 2:10; con esto no hay que repetir en bucle
BORDE = 10.0        # se ignoran los primeros y últimos segundos al medir el rango: casi
                    # todas las pistas entran y salen con fundido y eso falsea la medida


def rms_db(path, filtro=None):
    cmd = [C.FF, "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR)]
    if filtro:
        cmd += ["-af", filtro]
    cmd += ["-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    a = array.array("h")
    a.frombytes(raw)
    if not a:
        return None, []
    x = [v / 32768.0 for v in a]
    total = 20 * math.log10(math.sqrt(sum(v * v for v in x) / len(x)) + 1e-9)
    n = SR  # ventanas de 1 s para el rango dinámico
    borde = int(BORDE * SR)
    medio = x[borde:-borde] if len(x) > 3 * borde else x
    ventanas = sorted(20 * math.log10(math.sqrt(sum(v * v for v in medio[i:i + n]) / n) + 1e-9)
                      for i in range(0, len(medio) - n, n))
    return total, ventanas


def main():
    carpeta = sys.argv[1] if len(sys.argv) > 1 else os.path.join(C.ASSETS, "musica")
    pistas = sorted(f for f in os.listdir(carpeta)
                    if f.lower().endswith(C.EXT_AUDIO) and not f.startswith("."))
    if not pistas:
        sys.exit(f"No hay pistas en {carpeta}")

    print(f"\n{len(pistas)} pista(s) en {carpeta}\n")
    print(f"  {'pista':<22}{'dur':>7}{'banda voz':>11}{'rango':>8}{'':>4}veredicto")
    filas = []
    for f in pistas:
        ruta = os.path.join(carpeta, f)
        dur = C.info_media(ruta)[0] or 0
        total, ventanas = rms_db(ruta)
        banda, _ = rms_db(ruta, "highpass=f=300,lowpass=f=3000")
        if total is None or banda is None:
            print(f"  {f:<22}  no pude leerla")
            continue
        # proporción de energía en la banda del habla
        prop = 10 ** ((banda - total) / 10)
        rango = (ventanas[len(ventanas) * 9 // 10] - ventanas[len(ventanas) // 10]
                 if len(ventanas) > 10 else 0)

        problemas = []
        if dur < DUR_MIN:
            problemas.append(f"más corta que el capítulo ({C.tc(dur)}): entraría en bucle")
        if prop > BANDA_MAL:
            problemas.append("mucha energía en la banda de la voz")
        if rango > 12:
            problemas.append(f"rango amplio ({rango:.0f} dB, tenderá a bombear)")
        estado = "descartar" if problemas else ("sirve" if prop <= BANDA_BIEN else "aceptable")
        filas.append((prop, rango, dur, f, estado, problemas))
        marca = {"sirve": "OK ", "aceptable": "~  ", "descartar": "NO "}[estado]
        print(f"  {f:<22}{C.tc(dur):>7}{prop:>10.0%}{rango:>7.0f} dB  {marca}{estado}")
        for x in problemas:
            print(f"  {'':<22}{'':>7}{'':>10}{'':>10}    - {x}")

    buenas = sorted((x for x in filas if x[4] != "descartar"), key=lambda x: x[0])
    print()
    if len(buenas) >= 4:
        print("  Las cuatro con más sitio para la voz, de mejor a peor:")
        for prop, rango, dur, f, _, _ in buenas[:4]:
            print(f"    {f:<22} {prop:.0%} en la banda de la voz")
        sobran = [x[3] for x in buenas[4:]]
        if sobran:
            print(f"  Sobran: {', '.join(sobran)}")
    else:
        print(f"  Solo {len(buenas)} pista(s) pasan el filtro; hacen falta cuatro.")
    print("\n  Esto descarta, no elige. Entre las que pasan, decide de oído.")


if __name__ == "__main__":
    main()
