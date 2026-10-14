#!/usr/bin/env python3
"""Genera los gráficos del capítulo: placa de intro, caja de logos, cenefas de pregunta,
lower third y tarjetas de redes.

    uv run --with pillow --python 3.11 python3 build_assets.py proyecto.json

Las medidas están calcadas del capítulo de referencia de la serie y explicadas en
`references/estilo-serie.md`. Salen en `trabajo/gfx/`.
"""
import os
import re
import sys

import comun as C

C.asegura_dependencias('PIL')

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080

# Tipografías por papel, en orden de preferencia. No se fija una ruta porque las que usa la
# serie —Avenir Next y Helvetica Neue— vienen con macOS y **no se pueden redistribuir**: en
# otra máquina hay que caer en algo equivalente sin que reviente el render.
#
# Ninguna es la tipografía oficial de Camacol: no hay manual de marca, así que se eligieron
# midiendo un capítulo terminado y buscando el parecido más cercano entre las del sistema.
# Si algún día aparece el manual, se cambia aquí y en `references/estilo-serie.md`.
#
# Cada entrada es (ruta, estilo). En un .ttc —un archivo con varias fuentes dentro— el estilo
# se busca **por nombre**, no por posición: el orden interno puede cambiar entre versiones de
# macOS y entonces saldría otro grosor sin que nada avise. Se toma la primera que exista; si
# no es la primera de la lista, se avisa, porque los gráficos ya no saldrán como los de la serie.
FUENTES = {
    "titulo": [("/System/Library/Fonts/Avenir Next.ttc", "Heavy"),
               ("/Library/Fonts/Montserrat-ExtraBold.ttf", None),
               ("/System/Library/Fonts/Supplemental/Arial Black.ttf", None)],
    "cenefa": [("/System/Library/Fonts/HelveticaNeue.ttc", "Medium"),
               ("/Library/Fonts/OpenSans-Regular.ttf", None),
               ("/System/Library/Fonts/Supplemental/Arial.ttf", None)],
    "cenefa_negrita": [("/System/Library/Fonts/HelveticaNeue.ttc", "Bold"),
                       ("/Library/Fonts/OpenSans-Bold.ttf", None),
                       ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", None)],
    "rotulo": [("/System/Library/Fonts/Avenir Next Condensed.ttc", "Heavy"),
               ("/Library/Fonts/Oswald-Bold.ttf", None),
               ("/System/Library/Fonts/Supplemental/Arial Narrow Bold.ttf", None)],
    "rotulo_cargo": [("/System/Library/Fonts/Avenir Next Condensed.ttc", "Demi Bold"),
                     ("/Library/Fonts/Oswald-Regular.ttf", None),
                     ("/System/Library/Fonts/Supplemental/Arial Narrow.ttf", None)],
}


CENEFA_MAX = 46     # caracteres por renglón antes de que la píldora se pase de ancha
# Palabras que no deben quedar al final de un renglón: arrastran al siguiente y se lee peor.
COLGANTES = {"el", "la", "los", "las", "un", "una", "de", "del", "a", "al", "en", "con",
             "por", "para", "y", "e", "o", "u", "su", "sus", "que", "es", "ha", "se"}


def parte_en_renglones(texto):
    """Parte una pregunta en uno o dos renglones para la cenefa.

    Un `\n` explícito manda: sirve para forzar un corte concreto cuando la partición
    automática cae en mal sitio. Si no lo hay, se parte sola por el espacio más cercano a la
    mitad, que es lo que equilibra los dos renglones.

    Existe porque escribir un `\n` literal dentro de una cadena de un JSON era el requisito
    más técnico que se le pedía a quien prepara el capítulo, y no hacía falta.
    """
    if "\n" in texto:
        return texto.split("\n")
    if len(texto) <= CENEFA_MAX:
        return [texto]
    mitad = len(texto) / 2
    espacios = [i for i, c in enumerate(texto) if c == " "]
    if not espacios:
        return [texto]

    def penaliza(i):
        """Distancia a la mitad, castigando los cortes que dejan colgando un enlace.

        Partir «...la / alianza...» separa el artículo de su sustantivo y se lee peor. Se
        prefiere un corte algo más descentrado antes que terminar renglón en «la», «de» o
        «y»; es lo que hace cualquiera al maquetar a mano.
        """
        ultima = texto[:i].split()[-1].lower().strip("¿¡")
        castigo = 6 if ultima in COLGANTES else 0
        return abs(i - mitad) + castigo

    corte = min(espacios, key=penaliza)
    return [texto[:corte], texto[corte + 1:]]


def abre_fuente(ruta, estilo, tam=20):
    """La fuente de ese archivo y estilo, o None si no está."""
    if not os.path.exists(ruta):
        return None
    if estilo is None:
        return ImageFont.truetype(ruta, tam)
    i = 0
    while True:
        try:
            f = ImageFont.truetype(ruta, tam, index=i)
        except OSError:
            return None
        if f.getname()[1] == estilo:
            return f
        i += 1


def resuelve(papel, tam):
    """Primera tipografía disponible para ese papel, o un error que dice qué instalar."""
    for k, (ruta, estilo) in enumerate(FUENTES[papel]):
        f = abre_fuente(ruta, estilo, tam)
        if f:
            if k:
                print(f"AVISO: «{papel}» sale con {os.path.basename(ruta)} porque falta "
                      f"{os.path.basename(FUENTES[papel][0][0])}; los gráficos no quedarán "
                      f"idénticos a los de la serie.")
            return f
    opciones = "\n  ".join(r for r, _ in FUENTES[papel])
    sys.exit(f"No encuentro ninguna tipografía para «{papel}». Instala una de estas:\n"
             f"  {opciones}\n"
             f"Corre `comprobar_entorno.py` para ver el estado completo.")

AZUL = (31, 67, 148, 255)      # azul institucional Camacol
TINTA = (26, 26, 26, 255)      # texto de las cenefas

# Cenefa: el borde inferior siempre en y=1006 y el texto a 39 px del margen izquierdo.
CENEFA_PAD_X, CENEFA_LINEA, CENEFA_PAD_V = 39, 52, 20


def ancho_texto(texto, f):
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    b = d.textbbox((0, 0), texto, font=f)
    return b[2] - b[0]


def encaja(im, box_w, box_h):
    r = min(box_w / im.width, box_h / im.height)
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)


def recorta_blanco(im, thr=238):
    px = im.convert("RGB").load()
    w, h = im.size
    fila = lambda y: all(min(px[x, y]) > thr for x in range(0, w, 3))
    col = lambda x: all(min(px[x, y]) > thr for y in range(0, h, 3))
    t = 0
    while t < h - 1 and fila(t):
        t += 1
    b = h - 1
    while b > t and fila(b):
        b -= 1
    l = 0
    while l < w - 1 and col(l):
        l += 1
    r = w - 1
    while r > l and col(r):
        r -= 1
    return im.crop((l, t, r + 1, b + 1))


def blanco_a_alpha(im, thr=240):
    im = im.convert("RGBA")
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, _ = px[x, y]
            m = min(r, g, b)
            if m > thr:
                px[x, y] = (r, g, b, 0)
            elif m > 200:
                px[x, y] = (r, g, b, int((thr - m) / (thr - 200) * 255))
    return im


def carga_logo(path):
    """Acepta el logo del afiliado con transparencia o con fondo blanco."""
    if not path or not os.path.exists(path):
        sys.exit(f"No encuentro el logo del afiliado: {path}")
    im = Image.open(path).convert("RGBA")
    if im.getchannel("A").getextrema()[0] < 250:
        return im.crop(im.getbbox())            # ya viene recortable por alpha
    return blanco_a_alpha(recorta_blanco(im))   # venía sobre blanco (típico si se sacó de un video)


def fondo_intro(p):
    """El fondo de edificios es vertical 1080x1920: se escala a 1920 de ancho y se recorta
    la banda que usa la serie. Se hace con ffmpeg para que el resultado sea idéntico al del
    capítulo de referencia."""
    dst = os.path.join(p["_trabajo"], "intro_bg.png")
    C.run([C.FF, "-y", "-v", "error", "-i", os.path.join(C.ASSETS, "fondo-edificios.png"),
           "-vf", "scale=1920:-1:flags=lanczos,crop=1920:1080:0:900,"
                  "colorlevels=rimax=0.75:gimax=0.78:bimax=0.85", dst])
    return Image.open(dst).convert("RGBA")


USUARIO_IG = re.compile(r"[a-z0-9._]{1,30}")


def revisa_instagram(p):
    """Un usuario de Instagram solo admite minúsculas, números, punto y guion bajo. Si el
    dato trae espacios o mayúsculas casi seguro es el nombre de la empresa y no el usuario
    —pasó con A1S: «A1S Group» llegó a pantalla en vez de «a1s_group»—, así que se para
    aquí en vez de imprimirlo en la tarjeta. No adivina el bueno: solo pide confirmarlo."""
    ig = (p.get("redes") or {}).get("instagram")
    if not ig:
        return
    limpio = ig.strip().lstrip("@")
    if (USUARIO_IG.fullmatch(limpio) and not limpio.endswith(".")
            and ".." not in limpio):
        p["redes"]["instagram"] = limpio
        return
    motivos = []
    if " " in limpio:
        motivos.append("tiene espacios")
    if limpio != limpio.lower():
        motivos.append("tiene mayúsculas")
    if not motivos:
        motivos.append("no cumple las reglas de Instagram")
    sys.exit(f"\nEl Instagram «{ig}» no puede ser un usuario de Instagram: "
             f"{' y '.join(motivos)}.\n"
             "Parece el nombre de la empresa, no el usuario. Pide el usuario exacto: está en "
             "el perfil, debajo de la foto, y empieza por @ (por ejemplo @a1s_group).\n"
             "Corrígelo en proyecto.json, en \"redes\" → \"instagram\", y vuelve a correr.")


def main():
    p = C.uso("build_assets.py")
    revisa_instagram(p)
    OUT = p["_gfx"]

    f_titulo = resuelve("titulo", 66)
    f_afiliado = resuelve("titulo", 44)
    f_cenefa = resuelve("cenefa", 44)
    f_nombre = resuelve("rotulo", 76)
    f_cargo = resuelve("rotulo_cargo", 44)
    f_social = resuelve("cenefa_negrita", 36)

    logo = carga_logo(p["_logo"])
    camacol = Image.open(os.path.join(C.ASSETS, "camacol-santander.png")).convert("RGBA")
    camacol_blanco = Image.open(os.path.join(C.ASSETS, "camacol-blanco.png")).convert("RGBA")

    # ---------------------------------------------------------------- caja de logos
    # Sangrada por el borde izquierdo del cuadro: solo se redondean las esquinas derechas.
    BW, BH = 600, 158
    caja = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
    d = ImageDraw.Draw(caja)
    d.rounded_rectangle([-40, 0, BW - 1, BH - 1], radius=26, fill=(255, 255, 255, 255))
    cam = encaja(camacol, 230, 108)
    caja.paste(cam, (46, (BH - cam.height) // 2), cam)
    af = encaja(logo, 262, 116)
    caja.paste(af, (330, (BH - af.height) // 2), af)
    caja.save(f"{OUT}/logobox.png")

    # ---------------------------------------------------------------- cenefas
    for i, texto in enumerate(p["preguntas"], 1):
        lineas = parte_en_renglones(texto)
        tmp = Image.new("RGBA", (1700, 320), (0, 0, 0, 0))
        dt = ImageDraw.Draw(tmp)
        for j, l in enumerate(lineas):
            dt.text((20, 40 + j * CENEFA_LINEA), l, font=f_cenefa, fill=TINTA)
        texto_im = tmp.crop(tmp.getbbox())
        bw = texto_im.width + CENEFA_PAD_X * 2
        bh = texto_im.height + CENEFA_PAD_V * 2
        lienzo = Image.new("RGBA", (bw + 60, bh), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lienzo)
        dd.rounded_rectangle([bw - 40, 12, bw + 22, bh - 12], radius=16, fill=AZUL)
        dd.rounded_rectangle([-40, 0, bw - 1, bh - 1], radius=26, fill=(255, 255, 255, 255))
        lienzo.paste(texto_im, (CENEFA_PAD_X, CENEFA_PAD_V), texto_im)
        lienzo.save(f"{OUT}/cenefa_{i}.png")

    # ---------------------------------------------------------------- lower third
    LW, LH, banda = 1320, 132, 76
    lt = Image.new("RGBA", (LW, LH), (0, 0, 0, 0))
    dd = ImageDraw.Draw(lt)
    franja = Image.new("RGBA", (LW, banda), (255, 255, 255, 255))
    mask = Image.new("L", (LW, banda), 255)
    mk = mask.load()
    for x in range(LW):                      # se desvanece por los extremos
        if x < 150:
            v = int(255 * (x / 150) ** 1.4)
        elif x > LW - 260:
            v = int(255 * max(0.0, (LW - x) / 260) ** 1.2)
        else:
            v = 255
        for y in range(banda):
            mk[x, y] = v
    franja.putalpha(mask)
    lt.paste(franja, (0, 0), franja)
    dd.text((118, 2), p["vocero"]["nombre"].upper(), font=f_nombre, fill=(38, 38, 38, 255))
    dd.rectangle([100, banda, LW - 200, LH - 1], fill=(28, 28, 28, 245))
    dd.text((118, banda + 6), p["vocero"]["cargo"], font=f_cargo, fill=(255, 255, 255, 255))
    dd.polygon([(LW - 200, banda), (LW - 140, banda), (LW - 200, LH - 1), (LW - 260, LH - 1)],
               fill=AZUL)
    dd.polygon([(LW - 148, 6), (LW - 96, 6), (LW - 152, banda), (LW - 204, banda)],
               fill=(31, 67, 148, 210))
    lt.save(f"{OUT}/lowerthird.png")

    # ---------------------------------------------------------------- tarjetas de redes
    for clave, icono in (("facebook", "icono-facebook.png"), ("instagram", "icono-instagram.png")):
        etiqueta = p.get("redes", {}).get(clave)
        if not etiqueta:
            continue
        ic = Image.open(os.path.join(C.ASSETS, icono)).convert("RGBA").resize((132, 132),
                                                                             Image.LANCZOS)
        pill = ancho_texto(etiqueta, f_social) + 96
        card = Image.new("RGBA", (ic.width + pill + 10, 140), (0, 0, 0, 0))
        dc = ImageDraw.Draw(card)
        dc.rounded_rectangle([ic.width - 26, 22, ic.width - 26 + pill, 116], radius=47,
                             fill=(255, 255, 255, 255))
        dc.text((ic.width + 22, 52), etiqueta, font=f_social, fill=(20, 20, 20, 255))
        card.paste(ic, (0, 4), ic)
        card.save(f"{OUT}/social_{clave[:2]}.png")

    # ---------------------------------------------------------------- placa de intro
    intro = fondo_intro(p).resize((W, H), Image.LANCZOS)
    dd = ImageDraw.Draw(intro)

    def centrado(texto, f, y):
        dd.text(((W - ancho_texto(texto, f)) // 2, y), texto, font=f, fill=(255, 255, 255, 255))

    centrado("AFILIADOS QUE CONSTRUYEN", f_titulo, 62)
    centrado("HISTORIAS DE ÉXITO", f_titulo, 146)
    cw, ch = 520, 292
    tarjeta = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(tarjeta).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=30,
                                              fill=(255, 255, 255, 255))
    grande = encaja(logo, 430, 232)
    tarjeta.paste(grande, ((cw - grande.width) // 2, (ch - grande.height) // 2), grande)
    intro.paste(tarjeta, ((W - cw) // 2, 300), tarjeta)
    centrado("AFILIADO A:", f_afiliado, 688)
    cb = encaja(camacol_blanco, 310, 210)
    intro.paste(cb, ((W - cb.width) // 2, 782), cb)
    intro.save(f"{OUT}/intro.png")

    print(f"Gráficos en {OUT}")
    for f in sorted(os.listdir(OUT)):
        print(f"  {f:20s} {Image.open(os.path.join(OUT, f)).size}")
    print("\nRevisa intro.png y logobox.png como imagen antes de renderizar: si el logo del\n"
          "afiliado se extrajo de un video, puede arrastrar el borde de la tarjeta blanca.")


if __name__ == "__main__":
    main()
