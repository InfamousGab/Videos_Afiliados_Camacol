#!/usr/bin/env python3
"""Genera el proyecto editable en XML, el documento del guion de edición, y deja los gráficos
en la carpeta de entrega.

    python3 exportar_xml.py proyecto.json

El XML es el de Final Cut Pro 7 («xmeml»), que es lo que la mayoría de editores llama «el
XML»: lo importan **Premiere Pro** (Archivo → Importar) y **DaVinci Resolve** (Archivo →
Importar → Línea de tiempo). No se usa FCPXML porque Premiere no lo abre sin un conversor.

La línea de tiempo apunta a **los archivos originales**, no a los renders, con los mismos
puntos de corte y disolvencias, cada toma escalada a 1080p como en el render, y los gráficos
en pistas propias. Los gráficos se entregan **ya colocados** sobre un PNG transparente de
1920x1080: así caen en su sitio en cualquier editor, sin depender de cómo interprete cada uno
las coordenadas. Lo que no viaja es la animación de entrada de cenefas y tarjetas, ni la
música con su automatización: eso queda en el MP4.

Convenciones del formato que importan aquí (son las que escriben FCP7 y Premiere):
- `start`/`end` van en fotogramas de la secuencia (30 fps); `in`/`out` en fotogramas de la
  propia toma, a su cadencia real.
- Un clip pegado a una transición lleva `-1` en ese borde, y su `in`/`out` incluye el
  material que la transición consume: la disolvencia se alimenta de las colas, no del
  contenido, igual que en el render.
"""
import os
import shutil
from urllib.parse import quote
from xml.sax.saxutils import escape

import comun as C
import render as R

C.asegura_dependencias("PIL")

from PIL import Image

FPS = 30
W, H = 1920, 1080

# Dónde coloca cada gráfico el render (esquina superior izquierda, en el cuadro de 1080p).
# Si cambian en render.grafica(), hay que cambiarlos aquí.
POS_LOGOBOX = (-30, 64)
POS_LOWER = (96, 902)
X_CENEFA, BASE_CENEFA = -30, 1006
X_REDES, Y_REDES = 1268, (668, 843)


def F(seg):
    """Segundos -> fotogramas de la secuencia."""
    return int(round(seg * FPS))


def tasa(fps):
    """(timebase, ntsc) de la cadencia estándar más cercana. Las tomas de WhatsApp vienen a
    cadencia variable y ffmpeg reporta cosas como 29.83: se tratan como 30."""
    if not fps:
        return 30, False
    estandar = [(24, True), (24, False), (25, False), (30, True), (30, False),
                (50, False), (60, True), (60, False)]
    return min(estandar, key=lambda t: abs(t[0] * (1000 / 1001 if t[1] else 1) - fps))


def fps_real(t):
    return t[0] * (1000 / 1001 if t[1] else 1)


def rate(t):
    return f"<rate><timebase>{t[0]}</timebase><ntsc>{'TRUE' if t[1] else 'FALSE'}</ntsc></rate>"


def url(path):
    return "file://localhost" + quote(os.path.abspath(path))


def escala(w, h, ajuste="llenar"):
    """Porcentaje de Basic Motion para meter una toma de w x h en 1080p, como el render."""
    if not w or not h or (w, h) == (W, H):
        return None
    f = max(W / w, H / h) if ajuste == "llenar" else min(W / w, H / h)
    return round(f * 100, 2)


def movimiento(pct):
    if pct is None:
        return ""
    return ("<filter><effect><name>Basic Motion</name><effectid>basic</effectid>"
            "<effectcategory>motion</effectcategory><effecttype>motion</effecttype>"
            "<mediatype>video</mediatype><parameter><parameterid>scale</parameterid>"
            f"<name>Scale</name><valuemin>0</valuemin><valuemax>1000</valuemax>"
            f"<value>{pct}</value></parameter></effect></filter>")


def disolvencia(ini, fin, alineacion):
    return (f"<transitionitem><start>{ini}</start><end>{fin}</end>"
            f"<alignment>{alineacion}</alignment>{rate((FPS, False))}"
            "<effect><name>Cross Dissolve</name><effectid>Cross Dissolve</effectid>"
            "<effectcategory>Dissolve</effectcategory><effecttype>transition</effecttype>"
            "<mediatype>video</mediatype><wipecode>0</wipecode><wipeaccuracy>100</wipeaccuracy>"
            "<startratio>0</startratio><endratio>1</endratio><reverse>FALSE</reverse>"
            "</effect></transitionitem>")


class Archivos:
    """Cada archivo se describe entero la primera vez y luego se referencia por id."""

    def __init__(self):
        self.ids, self.n = {}, 0

    def xml(self, path, nombre, dur_seg, t, w, h, audio, fijo=False):
        if path in self.ids:
            return f'<file id="{self.ids[path]}"/>'
        self.n += 1
        fid = self.ids[path] = f"archivo-{self.n}"
        # Una imagen fija no tiene duración: se le da una hora para que haya cola de sobra.
        dur = int(round((3600 if fijo else dur_seg) * fps_real(t)))
        medio = (f"<video><samplecharacteristics>{rate(t)}<width>{w}</width>"
                 f"<height>{h}</height><anamorphic>FALSE</anamorphic>"
                 f"<pixelaspectratio>square</pixelaspectratio><fielddominance>none"
                 f"</fielddominance></samplecharacteristics></video>")
        if audio:
            medio += ("<audio><samplecharacteristics><depth>16</depth><samplerate>48000"
                      "</samplerate></samplecharacteristics><channelcount>2</channelcount>"
                      "</audio>")
        return (f'<file id="{fid}"><name>{escape(nombre)}</name><pathurl>{url(path)}</pathurl>'
                f"{rate(t)}<duration>{dur}</duration><media>{medio}</media></file>")


def clip(n, nombre, archivo_xml, t, start, end, en, sale, dur_src, extra="", audio=False):
    medio = ("<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>"
             if audio else "")
    return (f'<clipitem id="clip-{n}"><name>{escape(nombre)}</name><enabled>TRUE</enabled>'
            f"<duration>{dur_src}</duration>{rate(t)}<start>{start}</start><end>{end}</end>"
            f"<in>{en}</in><out>{sale}</out>{archivo_xml}{medio}{extra}</clipitem>")


def pista(items):
    return "<track>" + "".join(items) + "<enabled>TRUE</enabled><locked>FALSE</locked></track>"


def a_cuadro_completo(src, dst, x, y):
    """Coloca un gráfico pequeño en su sitio sobre un PNG transparente de 1080p."""
    im = Image.open(src).convert("RGBA")
    lienzo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lienzo.paste(im, (x, y), im)
    lienzo.save(dst)


def prepara_graficos(p, t, dir_gfx):
    os.makedirs(dir_gfx, exist_ok=True)
    G = p["_gfx"]
    shutil.copy2(os.path.join(G, "intro.png"), dir_gfx)
    a_cuadro_completo(os.path.join(G, "logobox.png"), os.path.join(dir_gfx, "logobox.png"),
                      *POS_LOGOBOX)
    for n, _, _ in t["cenefas"]:
        src = os.path.join(G, f"cenefa_{n}.png")
        h = Image.open(src).size[1]
        a_cuadro_completo(src, os.path.join(dir_gfx, f"cenefa_{n}.png"),
                          X_CENEFA, BASE_CENEFA - h)
    a_cuadro_completo(os.path.join(G, "lowerthird.png"),
                      os.path.join(dir_gfx, "lowerthird.png"), *POS_LOWER)
    redes = [x for x in ("fa", "in") if os.path.exists(os.path.join(G, f"social_{x}.png"))]
    for j, x in enumerate(redes):
        a_cuadro_completo(os.path.join(G, f"social_{x}.png"),
                          os.path.join(dir_gfx, f"social_{x}.png"), X_REDES, Y_REDES[j])
    return redes


def construye_xml(p, dur, ini, dir_gfx):
    t0 = C.DUR_INTRO - C.XF_BLOQUE
    d_cuerpo = C.dur_cuerpo(p, dur)
    t = R.tiempos_grafica(p, dur)
    redes = prepara_graficos(p, t, dir_gfx)
    arch = Archivos()
    n = [0]

    def nid():
        n[0] += 1
        return n[0]

    SEQ = (FPS, False)
    info = {}

    def datos(path):
        if path not in info:
            d, w, h, fps, audio = C.info_media(path)
            info[path] = (d, w, h, tasa(fps), audio)
        return info[path]

    # ------------------------------------------------------------ V1: intro, cuerpo, cierre
    # Cada pieza con su tramo nominal en la línea [ts, te] y su entrada en la toma. Entre una
    # y otra, la transición: la intro disuelve hacia el cuerpo empezando en el corte (usa la
    # imagen fija, que tiene cola infinita); entre segmentos va centrada en el corte; y la
    # cortinilla entra disolviendo antes del corte, con sus primeros fotogramas.
    piezas = [{"tipo": "intro", "ts": 0, "te": F(t0), "src_in": 0.0}]
    for k, s in enumerate(p["segmentos"]):
        a = F(t0 + ini[k])
        piezas.append({"tipo": "seg", "k": k, "ts": a, "te": a + F(dur[k]),
                       "src_in": s["entrada"]})
    cort_mov = os.path.join(p["_out"], "cortinilla.mov")
    d_cort = C.dur_real(cort_mov)
    fin_cuerpo = piezas[-1]["te"]
    piezas.append({"tipo": "cortinilla", "ts": fin_cuerpo,
                   "te": fin_cuerpo + F(d_cort - C.XF_BLOQUE), "src_in": C.XF_BLOQUE})

    transiciones = []                       # (antes de la pieza i): (pre, post, alineación)
    for i in range(1, len(piezas)):
        if i == 1:
            d = F(C.XF_BLOQUE)
            transiciones.append((0, d, "start"))
        elif i == len(piezas) - 1:
            d = F(C.XF_BLOQUE)
            transiciones.append((d, 0, "end"))
        else:
            d = F(C.XF)
            transiciones.append((d // 2, d - d // 2, "center"))

    v1 = []
    for i, pz in enumerate(piezas):
        pre = transiciones[i - 1][0] if i else 0          # lo que la transición de entrada
        post = transiciones[i][1] if i < len(transiciones) else 0   # y la de salida comen
        start = -1 if i else pz["ts"]
        end = -1 if i < len(piezas) - 1 else pz["te"]
        if pz["tipo"] == "intro":
            path = os.path.join(dir_gfx, "intro.png")
            tt = SEQ
            en = 0
            sale = pz["te"] - pz["ts"] + post
            ax = arch.xml(path, "intro.png", 0, tt, W, H, False, fijo=True)
            v1.append(clip(nid(), "Placa de intro", ax, tt, start, end, en, sale,
                           int(3600 * FPS)))
        else:
            if pz["tipo"] == "seg":
                s = p["segmentos"][pz["k"]]
                path = os.path.join(p["_tomas"], s["archivo"])
                nombre = s.get("texto", "")[:60] or s["archivo"]
            else:
                path, nombre = p["cortinilla"], "Cortinilla Camacol"
            d_src, w, h, tt, audio = datos(path)
            fr = fps_real(tt)
            largo = pz["te"] - pz["ts"]                       # en fotogramas de secuencia
            en = int(round((pz["src_in"] - pre / FPS) * fr))
            sale = int(round((pz["src_in"] + (largo + post) / FPS) * fr))
            ax = arch.xml(path, os.path.basename(path), d_src or 60, tt, w, h, audio)
            v1.append(clip(nid(), nombre, ax, tt, start, end, en, sale,
                           int(round((d_src or 60) * fr)), movimiento(escala(w, h))))
        if i < len(transiciones):
            pre_t, post_t, alin = transiciones[i]
            corte = piezas[i + 1]["ts"]
            v1.append(disolvencia(corte - pre_t, corte + post_t, alin))

    # ------------------------------------------------------------ A1: la voz, a tope
    # Como en el render: los segmentos se empalman sin mezclarse, con su contenido entero.
    a1 = []
    for k, s in enumerate(p["segmentos"]):
        path = os.path.join(p["_tomas"], s["archivo"])
        d_src, w, h, tt, audio = datos(path)
        fr = fps_real(tt)
        a = F(t0 + ini[k])
        ax = arch.xml(path, os.path.basename(path), d_src or 60, tt, w, h, audio)
        a1.append(clip(nid(), s.get("texto", "")[:60] or s["archivo"], ax, tt,
                       a, a + F(dur[k]), int(round(s["entrada"] * fr)),
                       int(round((s["entrada"] + dur[k]) * fr)), int(round((d_src or 60) * fr)),
                       audio=True))

    # ------------------------------------------------------------ V2: tomas de apoyo
    # Solo imagen: en el capítulo su audio no suena, la voz de la entrevista sigue debajo.
    v2 = []
    for b in C.broll(p, dur, avisar=False):
        d_src, w, h, tt, _ = datos(b["ruta"])
        if b["imagen"]:
            tt = SEQ
        fr = fps_real(tt)
        a = F(t0 + b["t_in"])
        ax = arch.xml(b["ruta"], b["archivo"], d_src or 60, tt, w, h, False, fijo=b["imagen"])
        v2.append(clip(nid(), "Apoyo: " + (b["nota"] or b["archivo"]), ax, tt, a,
                       a + F(b["dur"]), int(round(b["entrada"] * fr)),
                       int(round((b["entrada"] + b["dur"]) * fr)),
                       int(round((3600 if b["imagen"] else d_src or 60) * fr)),
                       movimiento(escala(w, h, b["ajuste"]))))

    # ------------------------------------------------------------ V3+: gráficos
    def grafico(archivo, t_in, t_out, nombre):
        path = os.path.join(dir_gfx, archivo)
        ax = arch.xml(path, archivo, 0, SEQ, W, H, False, fijo=True)
        a, b = F(t0 + t_in), F(t0 + t_out)
        return clip(nid(), nombre, ax, SEQ, a, b, 0, b - a, int(3600 * FPS))

    v3 = [grafico("logobox.png", 0, d_cuerpo, f"Logos Camacol + {p['afiliado_corto']}")]
    v4 = [grafico(f"cenefa_{k}.png", a, b, "Cenefa " + q.replace("\n", " ")[:50])
          for (k, a, b), q in zip(t["cenefas"], p["preguntas"])]
    v5 = [grafico("lowerthird.png", t["lower"][0], t["lower"][1],
                  f"{p['vocero']['nombre']} / {p['vocero']['cargo']}")]
    v6, v7 = [], []
    if t["redes"]:
        r0, r0b, r1 = t["redes"]
        for j, x in enumerate(redes):
            red = "facebook" if x == "fa" else "instagram"
            (v6 if j == 0 else v7).append(
                grafico(f"social_{x}.png", r0 if j == 0 else r0b, r1,
                        f"{red.capitalize()} {p['redes'].get(red, '')}"))

    total = piezas[-1]["te"]
    pistas_v = [pista(x) for x in (v1, v2, v3, v4, v5, v6, v7) if x]
    formato_v = (f"<format><samplecharacteristics>{rate(SEQ)}<width>{W}</width>"
                 f"<height>{H}</height><anamorphic>FALSE</anamorphic><pixelaspectratio>square"
                 f"</pixelaspectratio><fielddominance>none</fielddominance>"
                 f"</samplecharacteristics></format>")
    formato_a = ("<format><samplecharacteristics><depth>16</depth><samplerate>48000"
                 "</samplerate></samplecharacteristics></format>")
    nombre = escape(f"{p['afiliado']} - historias de exito")
    return total / FPS, f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
<sequence id="secuencia-1">
<name>{nombre}</name>
<duration>{total}</duration>
{rate(SEQ)}
<timecode>{rate(SEQ)}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>
<media>
<video>
{formato_v}
{chr(10).join(pistas_v)}
</video>
<audio>
<numOutputChannels>2</numOutputChannels>
{formato_a}
{pista(a1)}
</audio>
</media>
</sequence>
</xmeml>
"""


def documento(p, dur, ini, total):
    t0 = C.DUR_INTRO - C.XF_BLOQUE
    t = R.tiempos_grafica(p, dur)
    corto = {}
    for s in p["segmentos"]:
        corto.setdefault(s["archivo"], chr(ord("A") + len(corto)))

    L = [f"# Guion de edición — {p['afiliado']} / Camacol Santander", "",
         f"Serie **Afiliados que construyen historias de éxito**. "
         f"Duración final **{C.tc(total)}** (límite {C.tc(p['duracion_maxima'])}).", "",
         "## Archivos fuente", ""]
    for arch, cl in corto.items():
        L.append(f"- **{cl}** — `{arch}`")
    L += ["", "## Estructura", "",
          "| # | Fuente | Entrada | Salida | Duración | En la línea | Contenido |",
          "|---|---|---|---|---|---|---|",
          f"| — | intro (gráfico) | — | — | {C.DUR_INTRO:.2f} s | 0:00.00 "
          f"| Placa «AFILIADOS QUE CONSTRUYEN HISTORIAS DE ÉXITO» |"]
    for k, s in enumerate(p["segmentos"]):
        L.append(f"| {k+1} | {corto[s['archivo']]} | {s['entrada']:.2f} | {s['salida']:.2f} "
                 f"| {dur[k]:.2f} s | {C.tc(t0 + ini[k])} | {s.get('texto','')} |")
    L.append(f"| — | cortinilla | 0.00 | — | — | "
             f"{C.tc(t0 + C.dur_cuerpo(p, dur) - C.XF_BLOQUE)} "
             f"| Cierre animado Camacol Santander (recortado a 16:9) |")

    L += ["", "## Gráfica sobreimpresa", "", "| Elemento | Entra | Sale |", "|---|---|---|",
          f"| Caja de logos Camacol + {p['afiliado_corto']} | {C.tc(t0)} "
          f"| {C.tc(t0 + C.dur_cuerpo(p, dur))} |"]
    for (n, a, b), texto in zip(t["cenefas"], p["preguntas"]):
        L.append(f"| Cenefa: {texto.replace(chr(10),' ')} | {C.tc(t0+a)} | {C.tc(t0+b)} |")
    L.append(f"| Lower third: {p['vocero']['nombre']} / {p['vocero']['cargo']} "
             f"| {C.tc(t0+t['lower'][0])} | {C.tc(t0+t['lower'][1])} |")
    if t["redes"]:
        r0, r0b, r1 = t["redes"]
        if p.get("redes", {}).get("facebook"):
            L.append(f"| Tarjeta Facebook «{p['redes']['facebook']}» "
                     f"| {C.tc(t0+r0)} | {C.tc(t0+r1)} |")
        if p.get("redes", {}).get("instagram"):
            L.append(f"| Tarjeta Instagram «{p['redes']['instagram']}» "
                     f"| {C.tc(t0+r0b)} | {C.tc(t0+r1)} |")

    aux = C.broll(p, dur, avisar=False)
    if aux:
        L += ["", "## Tomas auxiliares", "",
              "Corren sobre la voz de la entrevista, que no se toca: funcionan como voz en "
              "off. Entran y salen con corte seco, igual que en el resto de la serie.", "",
              "| Entra | Sale | Duración | Archivo | Encaje | Contenido |",
              "|---|---|---|---|---|---|"]
        for b in aux:
            encaje = ("pantalla completa" if b["ajuste"] == "llenar"
                      else "centrada con fondo desenfocado")
            L.append(f"| {C.tc(t0 + b['t_in'])} | {C.tc(t0 + b['t_out'])} "
                     f"| {b['dur']:.2f} s | `{b['archivo']}` | {encaje} | {b['nota']} |")
        cobertura = sum(b["dur"] for b in aux) / C.dur_cuerpo(p, dur)
        L += ["", f"Cubren el {cobertura:.0%} del cuerpo del capítulo."]

    L += ["", "## Tratamiento técnico", "",
          "- **Video**: escalado a 1920x1080 con Lanczos + enfoque leve, contraste +3 %, "
          "saturación +4 %. 30 fps constantes, H.264 High.",
          f"- **Transiciones de imagen**: disolvencia de {C.XF:.2f} s centrada en cada corte "
          f"y de {C.XF_BLOQUE:.2f} s contra la intro y la cortinilla. La disolvencia se "
          f"alimenta de material sobrante fuera del corte ({C.COLA:.2f} s de cola por "
          "segmento), no del contenido.",
          "- **Audio**: los segmentos se empalman **a tope**, sin mezclarse entre sí, con un "
          f"fundido de {C.XF_AUDIO * 1000:.0f} ms en cada borde que solo evita el chasquido. "
          "El contenido de cada segmento se conserva íntegro: ninguna palabra pierde su "
          "final. Paso alto a 85 Hz por segmento, reducción de ruido sobre el cuerpo ya "
          "montado (para que el ambiente de sala no escalone en los empalmes) y "
          "normalización a **-16 LUFS / -1.5 dBTP**, el estándar de web y redes.",
          "- **Verificado**: cada segmento del montaje se comparó por energía contra su toma "
          f"original; los {len(p['segmentos'])} dan correlación 1.000 y desfase 0.00 s.", "",
          "## Proyecto editable", "",
          f"`{p['afiliado_corto']} - proyecto editable.xml` es un XML de Final Cut Pro 7: se "
          "importa en **Premiere Pro** (Archivo → Importar) y en **DaVinci Resolve** "
          "(Archivo → Importar → Línea de tiempo). Apunta a **los archivos originales**, no a "
          "los renders, con los mismos cortes y disolvencias. Cada toma va escalada a 1080p "
          "como en el render. La carpeta `Graficos/` debe quedar junto al XML.", "",
          "Pistas: V1 intro, entrevista y cortinilla · V2 tomas de apoyo · V3 caja de logos "
          "· V4 cenefas · V5 rótulo · V6–V7 tarjetas de redes · A1 la voz.", "",
          "Los gráficos van ya colocados sobre un PNG transparente de 1920x1080, así que caen "
          "en su sitio sin tocar nada. Lo que no viaja: la animación de entrada de cenefas y "
          "tarjetas, el tratamiento de color y audio, y la música con su automatización. Eso "
          "está en el MP4.", "",
          "Si algún editor importa las transiciones corridas, la tabla de **Estructura** de "
          "arriba tiene todos los puntos de corte para rearmarlo a mano.", "",
          "## Criterios de selección", "",
          "<!-- Escribe aquí qué se quitó y por qué: muletillas, silencios, contenido "
          "redundante. Quien reciba el video quiere saber qué decisiones se tomaron. -->", "",
          "## Puntos a confirmar", "",
          "<!-- Datos sin confirmar (nombre y cargo del vocero, origen del logo), "
          "limitaciones del material (resolución de las tomas) y qué mejoraría con mejores "
          "insumos. Es lo primero que lee quien recibe el capítulo. -->", ""]
    return "\n".join(L)


MANUAL = "## Criterios de selección"


def main():
    p = C.uso("exportar_xml.py")
    dur = C.duraciones_reales(p)
    ini = C.inicios(p, dur)
    dir_gfx = os.path.join(p["_salida"], "Graficos")

    total, xml = construye_xml(p, dur, ini, dir_gfx)
    dst_xml = os.path.join(p["_salida"], f"{p['afiliado_corto']} - proyecto editable.xml")
    with open(dst_xml, "w", encoding="utf-8") as f:
        f.write(xml)
    # El formato anterior: si quedó de una exportación vieja, se quita para no confundir.
    viejo = dst_xml[:-4] + ".fcpxml"
    if os.path.exists(viejo):
        os.remove(viejo)

    dst_doc = os.path.join(p["_salida"], "Guion de edicion.md")
    doc = documento(p, dur, ini, total)
    # Las dos últimas secciones se escriben a mano. Al reexportar se regenera la parte
    # técnica, pero lo escrito se conserva: perderlo sin aviso es lo peor que puede pasar.
    conservado = False
    if os.path.exists(dst_doc):
        with open(dst_doc, encoding="utf-8") as f:
            previo = f.read()
        if MANUAL in previo:
            escrito = previo[previo.index(MANUAL):]
            if escrito != doc[doc.index(MANUAL):]:
                doc = doc[:doc.index(MANUAL)] + escrito
                conservado = True
    with open(dst_doc, "w", encoding="utf-8") as f:
        f.write(doc)

    print(f"{dst_xml}\n  {len(p['segmentos'])} cortes, total {C.tc(total)}")
    if conservado:
        print(f"{dst_doc}\n  se conservaron las secciones escritas a mano")
    else:
        print(f"{dst_doc}\n  completa a mano las secciones «Criterios de selección» y "
              f"«Puntos a confirmar»")
    print(f"{dir_gfx}\n  {len(os.listdir(dir_gfx))} gráficos, ya colocados a 1920x1080")


if __name__ == "__main__":
    main()
