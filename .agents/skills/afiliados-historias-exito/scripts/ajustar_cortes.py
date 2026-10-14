#!/usr/bin/env python3
"""Coloca cada punto de corte donde lo pondría un editor: en una frontera de palabra.

    python3 ajustar_cortes.py proyecto.json            # muestra qué cambiaría
    python3 ajustar_cortes.py proyecto.json --aplicar  # lo escribe

Necesita numpy y la transcripción hecha (`transcribir.py`).

**Este script no decide contenido, solo afina.** Mueve cada punto como mucho `MAX_MOVER`
segundos hasta la frontera de palabra más cercana, que es justo lo que hace falta para
corregir el adelanto de las marcas de whisper. Qué frase entra y cuál se cae es una decisión
de sentido, y esa se toma leyendo `revisar_sentido.py`.

Ese reparto no es un capricho: al intentar que el script dedujera las fronteras a partir del
campo `texto` de cada segmento, recortó once segundos de contenido bueno, porque `texto` es
una paráfrasis escrita a mano y no una especificación. Y al dejarlo buscar el siguiente
silencio *largo*, se saltó fronteras de palabra: el corte de «...la casa de sus sueños» acabó
pasado el «y la que» siguiente, y el montaje decía «la casa de sus sueños **y** el tema del
precio», dos ideas cosidas por una conjunción huérfana.

Cómo afina, combinando las dos fuentes:

- **Whisper** tiene la palabra pero no el instante: sus marcas se adelantan al final real.
- **La energía** tiene el instante: entre dos palabras encadenadas hay un valle de 30–60 ms.
  Buscarlo a ciegas daría falsos positivos dentro de las palabras; buscarlo cerca del punto
  que ya estaba escrito es fiable.

El aire que deja depende del sitio, como en cualquier montaje: al abrir o cerrar un bloque de
pregunta se respira, y dentro de una misma respuesta se va seguido.
"""
import difflib
import json
import os
import shutil
import sys

import comun as C

C.asegura_dependencias('numpy')

import audio_util as A
import palabras as P

# Cuánto se respira en cada empalme. No es una constante: un montaje suena mecánico cuando
# todas las pausas miden lo mismo. Lo que manda es si la frase cerró o sigue abierta.
AIRE_BLOQUE = 0.30    # cambio de pregunta: beat para que entre la cenefa nueva
AIRE_FRASE = 0.26     # el segmento cierra una frase (whisper le puso punto)
AIRE_INCISO = 0.17    # cierra en coma
AIRE_SEGUIDO = 0.10   # la frase continúa en el segmento siguiente: va pegado
MARGEN = 0.02
MAX_MOVER = 0.35      # cuánto puede desplazarse un punto; más que esto ya es cambiar contenido


def afina(db, piso, t, aire, lado):
    """Lleva `t` a la frontera de palabra más cercana, sin moverlo más de MAX_MOVER."""
    v = A.valle(db, piso, t, atras=MAX_MOVER, adelante=MAX_MOVER)
    if not v:
        return round(t, 3), "sin hueco cerca; queda a tope"
    ini, fin = v
    if lado == "salida":
        nuevo = min(fin - MARGEN, ini + aire)
        nuevo = max(nuevo, ini + MARGEN)
    else:
        nuevo = max(ini + MARGEN, fin - aire)
        nuevo = min(nuevo, fin - MARGEN)
    if abs(nuevo - t) > MAX_MOVER:
        return round(t, 3), f"el hueco más cercano está a {abs(nuevo - t):.2f} s; no lo muevo"
    return round(nuevo, 3), None


def _aire(cierre, cambia_bloque):
    if cambia_bloque:
        return AIRE_BLOQUE
    return {"punto": AIRE_FRASE, "coma": AIRE_INCISO}.get(cierre, AIRE_SEGUIDO)


def ajusta(p):
    segs = p["segmentos"]
    voc = P.carga_palabras(p)
    env, filas, avisos = {}, [], []
    # Cómo cierra cada segmento: es lo que decide la pausa que le sigue.
    cierres = []
    for s in segs:
        pal = P.para(voc, s["archivo"])
        cierres.append(P.cierra_idea(P.dentro(pal, s["entrada"], s["salida"])))

    for k, s in enumerate(segs):
        arch = s["archivo"]
        if arch not in env:
            env[arch] = A.envolvente(os.path.join(p["_tomas"], arch))
        db, piso = env[arch]
        e0, s0 = float(s["entrada"]), float(s["salida"])

        abre = k == 0 or segs[k - 1].get("bloque") != s.get("bloque")
        cierra = k == len(segs) - 1 or segs[k + 1].get("bloque") != s.get("bloque")

        # La entrada respira según cómo cerró el segmento anterior; la salida, según cómo
        # cierra este. Una frase terminada pide un beat; una que sigue abierta, ninguno.
        aire_in = AIRE_BLOQUE if abre else _aire(cierres[k - 1], False)
        aire_out = _aire(cierres[k], cierra)

        # `"fijo": true` protege un punto colocado a mano. Hace falta porque el buscador de
        # valles se equivoca dentro de una muletilla larga («Bueeeno,» tiene un valle interno
        # de 40 ms) y arrastra la entrada de vuelta al principio de la palabra.
        if s.get("fijo"):
            e1 = e0
            s1 = s0
            av1 = av2 = None
        else:
            e1, av1 = afina(db, piso, e0, aire_in, "entrada")
            s1, av2 = afina(db, piso, s0, aire_out, "salida")
        if av1:
            avisos.append(f"segmento {k} entrada: {av1}")
        if av2:
            avisos.append(f"segmento {k} salida: {av2}")
        if s1 <= e1 + 0.3:
            avisos.append(f"segmento {k}: el ajuste lo dejaría vacío; se deja como estaba")
            e1, s1 = e0, s0
        filas.append((k, s, e0, s0, e1, s1, abre, cierra, cierres[k], ""))
    return filas, avisos


def main():
    if len(sys.argv) < 2:
        sys.exit("uso: python3 ajustar_cortes.py proyecto.json [--aplicar]")
    ruta = sys.argv[1]
    p = C.carga(ruta)
    filas, avisos = ajusta(p)

    print(f"\n{'seg':>3}  {'entrada':>16}  {'salida':>16}  {'dur':>14}  abre/cierra  "
          f"palabras ancla")
    d0t = d1t = 0.0
    for k, s, e0, s0, e1, s1, ab, ci, p0, p1 in filas:
        d0t += s0 - e0
        d1t += s1 - e1
        marca = ("B" if ab else "·") + ("B" if ci else "·")
        print(f"{k:>3}  {e0:>7.2f} -> {e1:>6.2f}  {s0:>7.2f} -> {s1:>6.2f}  "
              f"{s0-e0:>6.2f} -> {s1-e1:>5.2f}     {marca}   {p0}")

    fijo = (C.DUR_INTRO - C.XF_BLOQUE) + (3.733 - C.XF_BLOQUE)
    print(f"\ncuerpo {d0t:.2f} s -> {d1t:.2f} s   total {C.tc(d0t + fijo)} -> "
          f"{C.tc(d1t + fijo)} (límite {C.tc(p['duracion_maxima'])})")
    if d1t + fijo > p["duracion_maxima"]:
        print("  *** se pasa del límite: hay que quitar contenido ***")
    if avisos:
        print("\navisos:")
        for a in avisos:
            print(f"  - {a}")

    if "--aplicar" not in sys.argv:
        print("\n(nada escrito; añade --aplicar para guardarlo)")
        return
    with open(ruta, encoding="utf-8") as f:
        crudo = json.load(f)
    shutil.copy2(ruta, ruta + ".bak")
    cambiados = [k for (k, s, e0, s0, e1, s1, *_) in filas if (e0, s0) != (e1, s1)]
    for (k, s, e0, s0, e1, s1, *_) in filas:
        crudo["segmentos"][k]["entrada"] = e1
        crudo["segmentos"][k]["salida"] = s1
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(crudo, f, ensure_ascii=False, indent=2)
    print(f"\n{len(cambiados)} segmento(s) ajustados; copia previa en "
          f"{os.path.basename(ruta)}.bak")
    if cambiados:
        print("  El próximo render rehace solo esos segmentos; no hay que borrar nada.")


if __name__ == "__main__":
    main()
