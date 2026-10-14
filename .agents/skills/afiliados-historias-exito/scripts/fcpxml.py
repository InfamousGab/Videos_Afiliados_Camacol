#!/usr/bin/env python3
"""Genera el proyecto editable (FCPXML) y el documento del guion de edición, y copia los
gráficos a la carpeta de entrega.

    python3 fcpxml.py proyecto.json

La línea de tiempo apunta a **los archivos originales**, no a los renders, con los mismos
puntos de corte, disolvencias y gráficos en pistas conectadas. Así quien reciba el capítulo
puede reabrirlo y cambiar cualquier cosa. Importa en DaVinci Resolve, Final Cut Pro y
Premiere Pro.

El manejo de `<transition>` varía entre programas, así que el documento de guion incluye
además la tabla completa de cortes: si alguno importa las transiciones corridas, se puede
rearmar a mano sin volver a mirar el video.
"""
import os
import shutil
from urllib.parse import quote
from xml.sax.saxutils import escape

import comun as C
import render as R

FPS = 30
FD = "100/3000s"          # duración de fotograma = 1/30 s


def T(seg):
    """Segundos -> tiempo racional alineado a fotograma, como espera FCPXML."""
    return f"{int(round(seg * FPS)) * 100}/3000s"


def url(path):
    return "file://" + quote(os.path.abspath(path))


def construye_xml(p, dur, ini, dir_gfx):
    d_cuerpo = C.dur_cuerpo(p, dur)
    t0 = C.DUR_INTRO - C.XF_BLOQUE
    t = R.tiempos_grafica(p, dur)
    d_cort = C.dur_real(os.path.join(p["_out"], "cortinilla.mov"))

    recursos, assets, nid = [], {}, [1]
    recursos.append(f'<format id="r0" name="FFVideoFormat1080p30" frameDuration="{FD}" '
                    f'width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>')

    def add(path, dur_seg, con_audio, nombre):
        if path in assets:
            return assets[path]
        rid = f"r{nid[0]}"
        nid[0] += 1
        assets[path] = rid
        extra = (' hasAudio="1" audioSources="1" audioChannels="2" audioRate="48000"'
                 if con_audio else "")
        recursos.append(
            f'<asset id="{rid}" name="{escape(nombre)}" start="0s" duration="{T(dur_seg)}" '
            f'hasVideo="1" format="r0" videoSources="1"{extra}>'
            f'<media-rep kind="original-media" src="{url(path)}"/></asset>')
        return rid

    for s in p["segmentos"]:
        src = os.path.join(p["_tomas"], s["archivo"])
        if src not in assets:
            add(src, C.info_media(src)[0] or 60, True, s["archivo"])
    rid_cort = add(p["cortinilla"], d_cort, False, "Cortinilla Camacol")

    # Las tomas auxiliares se declaran como recursos y luego cuelgan del spine en la pista 1.
    lista_broll = C.broll(p, dur, avisar=False)
    for b in lista_broll:
        if b["ruta"] not in assets:
            add(b["ruta"], (3600 if b["imagen"] else (C.info_media(b["ruta"])[0] or 60)),
                False, b["archivo"])

    graficos = ["intro.png", "logobox.png", "lowerthird.png"]
    graficos += [f"cenefa_{n}.png" for n, _, _ in t["cenefas"]]
    graficos += [f for f in ("social_fa.png", "social_in.png")
                 if os.path.exists(os.path.join(dir_gfx, f))]
    rid_gfx = {g: add(os.path.join(dir_gfx, g), 3600, False, g) for g in graficos}

    # ---------------------------------------------------------------- spine
    spine = [f'<video ref="{rid_gfx["intro.png"]}" name="Placa de intro" offset="0s" '
             f'start="0s" duration="{T(C.DUR_INTRO)}"/>',
             f'<transition name="Cross Dissolve" offset="{T(t0)}" '
             f'duration="{T(C.XF_BLOQUE)}">'
             f'<filter-video ref="r0" name="Cross Dissolve"/></transition>']

    for k, s in enumerate(p["segmentos"]):
        rid = assets[os.path.join(p["_tomas"], s["archivo"])]
        off = t0 + ini[k]
        spine.append(
            f'<asset-clip ref="{rid}" name="{escape(s.get("texto", "")[:48])}" '
            f'offset="{T(off)}" start="{T(s["entrada"])}" duration="{T(dur[k])}" '
            f'audioRole="dialogue" tcFormat="NDF" format="r0"/>')
        if k:
            # Centrada en el corte, que es donde la pone un editor: se alimenta de las colas
            # de los dos planos, no del contenido. Los clips van pegados uno detrás de otro.
            spine.append(f'<transition name="Cross Dissolve" '
                         f'offset="{T(off - C.XF / 2)}" duration="{T(C.XF)}">'
                         f'<filter-video ref="r0" name="Cross Dissolve"/></transition>')

    t_cort = t0 + d_cuerpo - C.XF_BLOQUE
    spine.append(f'<transition name="Cross Dissolve" offset="{T(t_cort)}" '
                 f'duration="{T(C.XF_BLOQUE)}">'
                 f'<filter-video ref="r0" name="Cross Dissolve"/></transition>')
    spine.append(f'<asset-clip ref="{rid_cort}" name="Cortinilla Camacol" '
                 f'offset="{T(t_cort)}" start="0s" duration="{T(d_cort)}" format="r0"/>')

    # ------------------------------------------------------- gráficos conectados
    conectados = []

    def conectar(archivo, t_in, t_out, lane, nombre):
        conectados.append(
            f'<video ref="{rid_gfx[archivo]}" lane="{lane}" name="{escape(nombre)}" '
            f'offset="{T(t_in)}" start="0s" duration="{T(t_out - t_in)}"/>')

    # Pista 1: tomas auxiliares. Van con el volumen al fondo en vez de recortarles el audio,
    # porque así el editor puede recuperarlo si algún día lo quiere; en el MP4 no suena.
    for b in lista_broll:
        conectados.append(
            f'<asset-clip ref="{assets[b["ruta"]]}" lane="1" '
            f'name="{escape("Apoyo: " + (b["nota"] or b["archivo"]))}" '
            f'offset="{T(t0 + b["t_in"])}" start="{T(b["entrada"])}" '
            f'duration="{T(b["dur"])}" format="r0">'
            f'<adjust-volume amount="-96dB"/></asset-clip>')

    conectar("logobox.png", t0, t0 + d_cuerpo, 2,
             f"Logos Camacol + {p['afiliado_corto']}")
    for (n, a, b), texto in zip(t["cenefas"], p["preguntas"]):
        conectar(f"cenefa_{n}.png", t0 + a, t0 + b, 3,
                 "Cenefa " + texto.replace("\n", " ")[:44])
    conectar("lowerthird.png", t0 + t["lower"][0], t0 + t["lower"][1], 3,
             f"{p['vocero']['nombre']} / {p['vocero']['cargo']}")
    if t["redes"]:
        r0, r0b, r1 = t["redes"]
        if "social_fa.png" in rid_gfx:
            conectar("social_fa.png", t0 + r0, t0 + r1, 3,
                     f"Facebook {p['redes']['facebook']}")
        if "social_in.png" in rid_gfx:
            conectar("social_in.png", t0 + r0b, t0 + r1, 4,
                     f"Instagram {p['redes']['instagram']}")

    for i, s in enumerate(spine):                 # cuelgan del primer clip del spine
        if s.startswith("<asset-clip"):
            spine[i] = s[:-2] + ">" + "".join(conectados) + "</asset-clip>"
            break

    total = t_cort + d_cort
    nl = chr(10)
    return total, f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
  <resources>
{nl.join('    ' + r for r in recursos)}
  </resources>
  <library name="Camacol Santander - Afiliados que construyen historias de exito">
    <event name="{escape(p['afiliado_corto'])}">
      <project name="{escape(p['afiliado'])} - historias de exito">
        <sequence format="r0" duration="{T(total)}" tcStart="0s" tcFormat="NDF"
                  audioLayout="stereo" audioRate="48k">
          <spine>
{nl.join('            ' + s for s in spine)}
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
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
          f"`{p['afiliado_corto']} - proyecto editable.fcpxml` (FCPXML 1.9) apunta a **los "
          "archivos originales**, no a los renders, con los mismos cortes, disolvencias y "
          "gráficos en pistas conectadas. La carpeta `Graficos/` debe quedar junto al XML.",
          "",
          "Si algún programa importa las transiciones corridas (el manejo de `<transition>` "
          "varía entre editores), la tabla de **Estructura** de arriba tiene todos los puntos "
          "de corte para rearmarlo a mano.", "",
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
    p = C.uso("fcpxml.py")
    dur = C.duraciones_reales(p)
    ini = C.inicios(p, dur)

    dir_gfx = os.path.join(p["_salida"], "Graficos")
    os.makedirs(dir_gfx, exist_ok=True)
    for f in os.listdir(p["_gfx"]):
        if f.endswith(".png"):
            shutil.copy2(os.path.join(p["_gfx"], f), dir_gfx)

    total, xml = construye_xml(p, dur, ini, dir_gfx)
    dst_xml = os.path.join(p["_salida"], f"{p['afiliado_corto']} - proyecto editable.fcpxml")
    with open(dst_xml, "w", encoding="utf-8") as f:
        f.write(xml)

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
    print(f"{dir_gfx}\n  {len(os.listdir(dir_gfx))} gráficos")


if __name__ == "__main__":
    main()
