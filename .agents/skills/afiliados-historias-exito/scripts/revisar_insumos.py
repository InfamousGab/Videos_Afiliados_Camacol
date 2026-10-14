#!/usr/bin/env python3
"""Revisa la carpeta de un capítulo y dice en español qué hay y qué falta.

    python3 revisar_insumos.py "/ruta/a/la carpeta del capítulo"

Se corre **antes de montar nada**, y recibe la carpeta —no un proyecto.json— porque en ese
momento el proyecto todavía no existe: quien entrega solo ha arrastrado archivos.

Es la primera cosa que ve quien entrega el material, así que habla de tomas y de logos, no de
rutas ni de claves. Los problemas que detecta aquí cuestan un minuto; detectados a mitad del
render cuestan media hora.
"""
import os
import sys

import comun as C

C.asegura_dependencias('PIL')

import nombres as N

OK, FALTA, AVISO = "  ok  ", " FALTA", " aviso"
DUR_TOMA_CORTA = 8.0
LOGO_ANCHO_MIN = 400


def linea(estado, que, detalle=""):
    print(f"[{estado}] {que}" + (f"  — {detalle}" if detalle else ""))


def main():
    if len(sys.argv) < 2:
        sys.exit('uso: python3 revisar_insumos.py "/ruta/a/la carpeta del capítulo"')
    base = os.path.abspath(os.path.expanduser(sys.argv[1].rstrip("/")))
    if not os.path.isdir(base):
        sys.exit(f"No encuentro la carpeta:\n  {base}")

    print(f"\nCapítulo: {os.path.basename(base)}\n")
    problemas, avisos = [], []

    # ---------------------------------------------------------------- entrevista
    carpeta_tomas = next((os.path.join(base, c) for c in ("Entrevista", "Insumo principal")
                          if os.path.isdir(os.path.join(base, c))), None)
    print("=== Tomas de la entrevista ===")
    if not carpeta_tomas:
        # Caso frecuente y con arreglo obvio: los videos están, pero sueltos en la raíz.
        sueltos = [f for f in os.listdir(base)
                   if f.lower().endswith(C.EXT_VIDEO) and not f.startswith(".")]
        if sueltos:
            problemas.append(f"hay {len(sueltos)} video(s) sueltos en la carpeta; "
                             f"muévelos a una subcarpeta llamada «Entrevista»")
            linea(FALTA, "carpeta «Entrevista»",
                  f"hay {len(sueltos)} video(s) sueltos aquí; créala y muévelos dentro")
        else:
            problemas.append("no hay carpeta «Entrevista» con las tomas")
            linea(FALTA, "carpeta «Entrevista»",
                  "crea una carpeta con ese nombre y arrastra dentro los videos")
        tomas = []
    else:
        tomas = sorted(f for f in os.listdir(carpeta_tomas)
                       if f.lower().endswith(C.EXT_VIDEO) and not f.startswith("."))
        if not tomas:
            problemas.append("la carpeta «Entrevista» está vacía")
            linea(FALTA, "tomas", f"la carpeta {os.path.basename(carpeta_tomas)} está vacía")

    resoluciones, total = set(), 0.0
    for orden, tema, arch in N.ordena(tomas):
        dur, w, h, fps, audio = C.info_media(os.path.join(carpeta_tomas, arch))
        total += dur or 0
        if w:
            resoluciones.add(f"{w}x{h}")
        etiqueta = f"{orden}. {tema}" if orden else tema
        detalle = f"{C.tc(dur or 0)} · {w}x{h}" + (f" · {fps:.0f} fps" if fps else "")
        if not audio:
            problemas.append(f"«{arch}» no tiene pista de audio")
            linea(FALTA, etiqueta, detalle + " · SIN AUDIO")
        elif dur and dur < DUR_TOMA_CORTA:
            avisos.append(f"«{arch}» dura {C.tc(dur)}; ¿es una toma de la entrevista?")
            linea(AVISO, etiqueta, detalle + " · muy corta")
        elif orden is None:
            avisos.append(f"«{arch}» no lleva número al principio, así que no sé en qué "
                          f"orden va; se tratará aparte de las respuestas")
            linea(AVISO, etiqueta, detalle + " · sin número de orden")
        else:
            linea(OK, etiqueta, detalle)

    if tomas:
        print(f"\n  {len(tomas)} toma(s), {C.tc(total)} de material en bruto")
        if len(resoluciones) > 1:
            avisos.append(f"las tomas vienen en resoluciones distintas ({', '.join(sorted(resoluciones))})")
            linea(AVISO, "resoluciones mezcladas", ", ".join(sorted(resoluciones)))

    # ---------------------------------------------------------------- logo
    print("\n=== Logo del afiliado ===")
    carpeta_apoyo = next((os.path.join(base, c) for c in ("Apoyo", "insumos/broll")
                          if os.path.isdir(os.path.join(base, c))), os.path.join(base, "Apoyo"))
    logo = C.busca_logo(base, carpeta_tomas or base, carpeta_apoyo)
    if not logo:
        problemas.append("falta el logo del afiliado")
        linea(FALTA, "logo", "deja el archivo suelto en la carpeta del capítulo")
    else:
        from PIL import Image
        try:
            im = Image.open(logo)
            transp = im.mode in ("RGBA", "LA") or "transparency" in im.info
            detalle = f"{im.width}x{im.height}" + (" · con transparencia" if transp
                                                   else " · SIN transparencia")
            if not transp:
                avisos.append("el logo no tiene fondo transparente; sobre la placa de intro "
                              "puede aparecer con un recuadro blanco. Pide el PNG original.")
                linea(AVISO, os.path.basename(logo), detalle)
            elif im.width < LOGO_ANCHO_MIN:
                avisos.append(f"el logo mide {im.width} px de ancho; puede verse borroso")
                linea(AVISO, os.path.basename(logo), detalle + " · resolución justa")
            else:
                linea(OK, os.path.basename(logo), detalle)
        except Exception as e:
            problemas.append(f"no pude leer el logo: {e}")
            linea(FALTA, os.path.basename(logo), "no pude abrirlo como imagen")

    # ---------------------------------------------------------------- apoyo
    print("\n=== Material de apoyo ===")
    apoyo = ([f for f in sorted(os.listdir(carpeta_apoyo))
              if f.lower().endswith(C.EXT_VIDEO + C.EXT_IMAGEN) and not f.startswith(".")]
             if os.path.isdir(carpeta_apoyo) else [])
    if not apoyo:
        linea(OK, "sin material de apoyo",
              "el capítulo saldrá con plano fijo; es válido, pero con obra o renders gana")
    for f in apoyo:
        dur, w, h, _, _ = C.info_media(os.path.join(carpeta_apoyo, f))
        es_img = f.lower().endswith(C.EXT_IMAGEN)
        encaje = C.ajuste_auto(w, h)
        detalle = ("foto" if es_img else C.tc(dur or 0)) + f" · {w}x{h}"
        detalle += " · vertical, irá con fondo desenfocado" if encaje == "encajar" else ""
        linea(OK, f, detalle)

    # ---------------------------------------------------------------- resumen
    print()
    if problemas:
        print(f"{len(problemas)} cosa(s) que faltan antes de poder montar:")
        for x in problemas:
            print(f"  - {x}")
    if avisos:
        print(f"{len(avisos)} cosa(s) que conviene mirar:")
        for x in avisos:
            print(f"  - {x}")
    if not problemas:
        print("Todo lo necesario está. Falta decir el nombre del afiliado, quién habla y")
        print("con qué cargo, y los usuarios de redes.")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
