#!/usr/bin/env python3
"""Mide la mezcla de música y voz del capítulo terminado.

    python3 comprobar_mezcla.py proyecto.json

La música de fondo se juzga de oído, pero se calibra con números. Estos son los del capítulo
de referencia de la serie, medidos sobre él:

    música sola en la intro      -20 dBFS
    música agachada bajo la voz  -35 dBFS   (15 dB por debajo de cuando suena sola)
    voz por encima del colchón    16 dB

Lo que importa de verdad es **la relación entre la voz y el colchón**: por debajo de 14 dB la
música empieza a estorbar, y por encima de 22 dB no se oye y no aporta nada. El nivel absoluto
depende de a cuánto se normalice el capítulo.
"""
import array
import math
import os
import subprocess
import sys

import comun as C

SR = 16000
RELACION_MIN = 14.0
RELACION_MAX = 22.0


def marcos(ruta, desde, dur, ms=50):
    r = subprocess.run([C.FF, "-v", "error", "-ss", str(desde), "-t", str(dur), "-i", ruta,
                        "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                       capture_output=True)
    a = array.array("h")
    a.frombytes(r.stdout)
    x = [v / 32768.0 for v in a]
    n = int(SR * ms / 1000)
    return sorted(20 * math.log10(math.sqrt(sum(v * v for v in x[i:i + n]) / n) + 1e-9)
                  for i in range(0, len(x) - n, n))


def main():
    p = C.uso("comprobar_mezcla.py")
    final = next((os.path.join(p["_salida"], f) for f in os.listdir(p["_salida"])
                  if f.endswith(".mp4")), None)
    if not final:
        sys.exit("No hay MP4 final todavía.")
    total = C.dur_real(final)
    t0 = C.DUR_INTRO - C.XF_BLOQUE

    intro = marcos(final, 0.4, max(0.5, t0 - 0.8))
    cuerpo = marcos(final, t0 + 3, total - t0 - 8)
    cort = marcos(final, total - 2.6, 2.0)
    if not intro or not cuerpo:
        sys.exit("No pude medir; ¿el capítulo tiene audio?")

    m_intro = intro[len(intro) // 2]
    colchon = cuerpo[len(cuerpo) // 10]
    voz = cuerpo[len(cuerpo) * 9 // 10]
    m_cort = cort[len(cort) // 2] if cort else None
    relacion = voz - colchon
    bajada = m_intro - colchon

    print(f"\n{'':2}{'tramo':<30}{'medido':>10}{'referencia':>13}")
    print(f"  {'música sola en la intro':<30}{m_intro:>9.1f} {'-20.4':>12}")
    print(f"  {'colchón bajo el diálogo':<30}{colchon:>9.1f} {'-35.3':>12}")
    print(f"  {'picos de voz':<30}{voz:>9.1f} {'-19.1':>12}")
    if m_cort is not None:
        print(f"  {'música sola en la cortinilla':<30}{m_cort:>9.1f} {'-21.9':>12}")
    print(f"\n  {'bajada al entrar la voz':<30}{bajada:>9.1f} dB{'14.9':>10}")
    print(f"  {'voz por encima del colchón':<30}{relacion:>9.1f} dB{'16.2':>10}")

    if m_intro < -45:
        sys.exit("\nNo hay música: la intro está en silencio. ¿Falta la pista en assets/musica?")
    if relacion < RELACION_MIN:
        print(f"\n  La música compite con la voz (menos de {RELACION_MIN:.0f} dB de margen).")
        print(f"  Baja MUSICA_FONDO_DB en comun.py.")
        return 1
    if relacion > RELACION_MAX:
        print(f"\n  La música casi no se oye bajo el diálogo (más de {RELACION_MAX:.0f} dB).")
        print(f"  Sube MUSICA_FONDO_DB en comun.py.")
        return 1
    print("\n  La mezcla está en rango: la música se oye sin taparle la voz.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
