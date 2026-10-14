#!/usr/bin/env python3
"""Inventario visual de las tomas auxiliares, para decidir dónde va cada una.

    python3 revisar_broll.py proyecto.json

Recorre `insumos/broll/`, imprime una ficha de cada archivo (duración, tamaño, proporción,
si trae audio, y cómo se va a encajar) y arma una hoja de contactos con tres fotogramas de
cada video —principio, medio y final— para poder mirarlas todas de un vistazo.

De los videos con audio avisa: su sonido **no se usa**, la entrevista sigue sonando debajo.
Si una toma trae algo que valga la pena oír, eso es otra conversación y no un inserto.
"""
import os
import sys

import comun as C

C.asegura_dependencias('PIL')


def main():
    p = C.uso("revisar_broll.py")
    carpeta = p["_broll"]
    if not os.path.isdir(carpeta):
        os.makedirs(carpeta, exist_ok=True)
        sys.exit(f"Creé la carpeta {carpeta}.\nDeja ahí las tomas auxiliares "
                 f"(video o fotos) y vuelve a correr esto.")

    archivos = sorted(f for f in os.listdir(carpeta)
                      if f.lower().endswith(C.EXT_VIDEO + C.EXT_IMAGEN)
                      and not f.startswith("."))
    if not archivos:
        sys.exit(f"No hay tomas auxiliares en {carpeta}")

    qc = os.path.join(p["_trabajo"], "qc")
    os.makedirs(qc, exist_ok=True)
    fichas, miniaturas = [], []

    print(f"\n{len(archivos)} toma(s) auxiliar(es) en {carpeta}\n")
    for n, arch in enumerate(archivos):
        ruta = os.path.join(carpeta, arch)
        dur, w, h, fps, audio = C.info_media(ruta)
        es_img = arch.lower().endswith(C.EXT_IMAGEN)
        ajuste = C.ajuste_auto(w, h)
        prop = f"{w/h:.2f}" if w and h else "?"
        etiqueta = "foto" if es_img else f"{dur:.1f} s"
        fichas.append((arch, etiqueta, f"{w}x{h}", prop, ajuste, audio and not es_img))
        print(f"  {arch}")
        print(f"      {etiqueta:>8s}  {w}x{h} (proporción {prop})"
              f"{'' if es_img else f'  {fps:.0f} fps'}  ->  encaje «{ajuste}»")
        if audio and not es_img:
            print(f"      trae audio, que NO se va a usar: debajo sigue sonando la entrevista")

        # Tres fotogramas por video (principio, medio, final) y uno por foto.
        instantes = [0.2] if es_img or not dur else [dur * f for f in (0.1, 0.5, 0.88)]
        for j, t in enumerate(instantes):
            dst = os.path.join(qc, f"br{n:02d}{j}.png")
            cmd = [C.FF, "-y", "-v", "error"]
            if not es_img:
                cmd += ["-ss", f"{t}"]
            cmd += ["-i", ruta, "-frames:v", "1", "-vf", "scale=480:-2", dst]
            C.run(cmd, fatal=False)
            if os.path.exists(dst):
                miniaturas.append((f"{n+1}. {arch[:26]}", dst))

    if miniaturas:
        from PIL import Image, ImageDraw
        ims = [Image.open(f).convert("RGB") for _, f in miniaturas]
        an = max(i.width for i in ims)
        al = max(i.height for i in ims)
        cols, m = 3, 6
        filas = (len(ims) + cols - 1) // cols
        hoja = Image.new("RGB", (cols * an + (cols + 1) * m, filas * al + (filas + 1) * m),
                         (20, 20, 20))
        d = ImageDraw.Draw(hoja)
        for i, (im, (etiqueta, _)) in enumerate(zip(ims, miniaturas)):
            x, y = m + (i % cols) * (an + m), m + (i // cols) * (al + m)
            hoja.paste(im, (x, y))
            d.text((x + 6, y + 5), etiqueta, fill=(255, 90, 90))
        ruta_hoja = os.path.join(qc, "hoja-broll.png")
        hoja.save(ruta_hoja)
        print(f"\nhoja de contactos: {ruta_hoja}")

    print("\nPara colocarlas, añade a proyecto.json algo así:\n")
    print('  "broll": [')
    print(f'    {{"archivo": "{fichas[0][0]}", "segmento": 5, "desde": 3.0,')
    print(f'     "duracion": 5.5, "entrada": 2.0, "texto": "obra en Lebrija"}}')
    print("  ]\n")
    print("  segmento  índice en la lista de segmentos sobre el que cae el inserto")
    print("  desde     segundos desde que arranca ese segmento")
    print("  duracion  cuánto dura el inserto (entre "
          f"{C.BROLL_MIN} y {C.BROLL_MAX} s)")
    print("  entrada   punto de entrada dentro del archivo auxiliar (los videos suelen")
    print("            empezar con un tirón de cámara: entra pasado un segundo)")
    print('  ajuste    "llenar" o "encajar"; si se omite se decide por la proporción')


if __name__ == "__main__":
    main()
