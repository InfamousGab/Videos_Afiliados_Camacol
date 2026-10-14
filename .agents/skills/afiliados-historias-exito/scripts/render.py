#!/usr/bin/env python3
"""Motor de render del capítulo.

    python3 render.py proyecto.json                 # todas las etapas
    python3 render.py proyecto.json grafica final   # solo algunas

Etapas: cortar → cuerpo → broll → grafica → intro → final.

Es reanudable: `cortar` reutiliza los clips cuyo segmento no cambió y rehace solos los que sí
(cada clip guarda su `sNN.firma`). Si cambias un punto de corte, relanza: no hay que borrar
nada.

Las decisiones de ffmpeg que parecen raras están explicadas en
`references/trampas-ffmpeg.md`; casi todas nacieron de un render echado a perder.
"""
import json
import os
import sys

import comun as C


# ------------------------------------------------------------------ 1. cortes
def cortar(p):
    anchos, duraciones_src = {}, {}
    for k, s in enumerate(p["segmentos"]):
        dst = os.path.join(p["_clips"], f"s{k:02d}.mov")
        src = os.path.join(p["_tomas"], s["archivo"])
        # Cada clip guarda al lado con qué datos se cortó. Si el segmento cambia (otra toma,
        # otra entrada o salida, otro orden), se vuelve a cortar solo; si no, se reutiliza.
        # Antes había que borrar el clip a mano, y un asistente como Codex tiene prohibido
        # `rm -f`: se quedaba atascado o pedía permisos que el operador no entiende.
        firma = json.dumps([s["archivo"], s["entrada"], s["salida"], C.COLA, C.FPS,
                            p.get("recorte"), C.A_IN], ensure_ascii=False)
        f_firma = dst[:-4] + ".firma"
        if os.path.exists(dst) and os.path.exists(f_firma):
            with open(f_firma, encoding="utf-8") as fh:
                if fh.read() == firma:
                    continue
        if src not in anchos:
            info = C.info_media(src)
            anchos[src] = info[1]
            duraciones_src[src] = info[0]
        vf = C.filtro_video(anchos[src], p.get("recorte"))
        # Cada intermedio se saca con COLA/2 de más por cada lado. Ese material sobrante no
        # se ve nunca: es lo que alimenta la disolvencia de imagen del empalme, y es lo que
        # permite que el audio del contenido salga entero. Sin colas, la disolvencia tendría
        # que comerse el principio y el final de cada frase.
        media = C.COLA / 2
        d_src = duraciones_src.get(src)
        if d_src and s["salida"] + media > d_src:
            sys.exit(f"segmento {k}: la salida ({s['salida']}) está a menos de {media} s "
                     f"del final de la toma ({d_src:.2f} s) y no deja cola")
        if s["entrada"] < media:
            sys.exit(f"segmento {k}: la entrada ({s['entrada']}) está a menos de {media} s "
                     f"del principio de la toma y no deja cola para la disolvencia")
        nf = int(round((s["salida"] - s["entrada"] + C.COLA) * C.FPS))
        d = nf / float(C.FPS)
        # `-ss` antes de `-i`, en una sola etapa. Se probó la búsqueda en dos etapas (salto
        # rápido + afinado de salida) para quitar unos milisegundos de deriva, y **rompe el
        # audio**: con búsqueda de salida las marcas de tiempo no arrancan en cero, `atrim`
        # no selecciona nada y el clip sale mudo. En los clips de un segundo se ve enseguida
        # porque el montaje falla; en los largos pasaría inadvertido.
        C.run([C.FF, "-y", "-v", "error",
               "-ss", f"{round(s['entrada'] - media, 4)}", "-i", src, "-t", f"{d + 0.5}",
               "-vf", vf, "-frames:v", str(nf),
               "-af", f"{C.A_IN},atrim=0:{d},apad=whole_dur={d},asetpts=N/SR/TB",
               "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p",
               "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", dst],
              f"corte {k:02d}  {s['archivo'][-14:]}  {s['entrada']}->{s['salida']}  "
              f"({nf} fot. con colas)")
        with open(f_firma, "w", encoding="utf-8") as fh:
            fh.write(firma)


# ------------------------------------------------------------------ 2. cuerpo
def cuerpo(p):
    """Monta los segmentos: imagen con disolvencias sobre las colas, audio a tope.

    La imagen y el audio se construyen por separado y se vuelven a encontrar exactos:

    - **Imagen**: cadena de `xfade` de 0.20 s. Como cada intermedio trae COLA/2 de más por
      cada lado, la mezcla ocurre sobre ese material sobrante y el contenido queda intacto.
      Al final se recorta la media cola que sobra al principio y al final.
    - **Audio**: de cada intermedio se toma solo el contenido (sin colas) y se concatenan a
      tope, con un fundido de 8 ms en cada borde para que no chasquee. No se mezcla nada:
      la última palabra de cada segmento se oye entera.

    Ambos suman lo mismo, así que el labial no se corre.
    """
    n = len(p["segmentos"])
    H = C.COLA
    faltan = [k for k in range(n)
              if not os.path.exists(os.path.join(p["_clips"], f"s{k:02d}.mov"))]
    if faltan:
        sys.exit(f"Faltan {len(faltan)} intermedio(s) por cortar "
                 f"({', '.join(f's{k:02d}' for k in faltan[:6])}"
                 f"{'…' if len(faltan) > 6 else ''}).\n"
                 f"Corre antes:  python3 render.py {os.path.basename(sys.argv[1])} cortar")
    largo = [C.dur_real(os.path.join(p["_clips"], f"s{k:02d}.mov")) for k in range(n)]
    dur = [round(l - H, 4) for l in largo]          # duración de contenido, sin colas
    with open(os.path.join(p["_trabajo"], "duraciones.txt"), "w") as f:
        f.write("\n".join(f"{k} {d}" for k, d in enumerate(dur)))
    total = round(sum(dur), 4)

    entradas = []
    for k in range(n):
        entradas += ["-i", os.path.join(p["_clips"], f"s{k:02d}.mov")]

    fv, vprev, acc = [], "[0:v]", largo[0]
    for k in range(1, n):
        off = round(acc - C.XF, 4)
        vout = f"[v{k}]"
        fv.append(f"{vprev}[{k}:v]xfade=transition=fade:duration={C.XF}:offset={off}{vout}")
        vprev, acc = vout, round(off + largo[k], 4)
    fv.append(f"{vprev}trim=start={H / 2}:duration={total},setpts=PTS-STARTPTS[vout]")

    fa = []
    for k in range(n):
        fa.append(f"[{k}:a]atrim=start={H / 2}:duration={dur[k]},asetpts=N/SR/TB,"
                  f"afade=t=in:st=0:d={C.XF_AUDIO},"
                  f"afade=t=out:st={round(dur[k] - C.XF_AUDIO, 4)}:d={C.XF_AUDIO}[u{k}]")
    fa.append("".join(f"[u{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[aout]")

    filtro = os.path.join(p["_trabajo"], "_cuerpo.filter")
    with open(filtro, "w") as f:
        f.write(";".join(fv + fa))
    C.run([C.FF, "-y", "-v", "error"] + entradas +
          ["-/filter_complex", filtro, "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "pcm_s16le", os.path.join(p["_out"], "cuerpo.mov")],
          f"montaje del cuerpo ({n} segmentos, {n - 1} empalmes; audio sin mezclar)")
    print(f"    cuerpo: {total:.2f} s")


# ------------------------------------------------------------------ 3. tomas auxiliares
def avisa_choques(p, lista, dur):
    """Avisa si un inserto tapa a la vocera justo cuando un gráfico habla de ella.

    Son errores que el render no puede detectar y que en pantalla se ven fatal: el rótulo
    con el nombre encima de una grúa, o las tarjetas de redes sobre una fachada mientras
    ella dice «ahí pueden encontrarnos».
    """
    if not lista:
        return
    t = tiempos_grafica(p, dur)
    ventanas = [("el rótulo con el nombre de la vocera", t["lower"])]
    if t["redes"]:
        ventanas.append(("las tarjetas de redes", (t["redes"][0], t["redes"][2])))
    for nombre, (a, b) in ventanas:
        for x in lista:
            if x["t_in"] < b and x["t_out"] > a:
                print(f"    OJO: «{x['archivo']}» ({C.tc(x['t_in'])}–{C.tc(x['t_out'])}) "
                      f"se cruza con {nombre} ({C.tc(a)}–{C.tc(b)}).\n"
                      f"         Muévelo o acórtalo: ese gráfico presenta a quien debería "
                      f"estar en pantalla.")


def broll(p):
    """Sustituye la imagen por tomas de apoyo en las ventanas indicadas, sin tocar el audio.

    La voz de la entrevista sigue corriendo debajo, así que el inserto funciona como voz en
    off. Entran y salen con corte seco, que es lo que hace la serie: en el capítulo de
    referencia los saltos a las tomas aéreas marcan 0.47–0.72 de score de escena en un solo
    fotograma, sin rastro de disolvencia.
    """
    src = os.path.join(p["_out"], "cuerpo.mov")
    dst = os.path.join(p["_out"], "cuerpo_broll.mov")
    dur = C.duraciones_reales(p)
    lista = C.broll(p, dur)
    avisa_choques(p, lista, dur)
    if not lista:
        if os.path.exists(dst):
            os.remove(dst)     # si se quitaron del JSON, que no quede el render viejo
        print(">>> sin tomas auxiliares")
        return

    entradas, pasos = ["-i", src], []
    prev = "[0:v]"
    for i, b in enumerate(lista, start=1):
        nf = int(round(b["dur"] * C.FPS))
        if b["imagen"]:
            # `-loop 1` + zoompan: una foto quieta cinco segundos en mitad de una entrevista
            # parece un cuadro congelado, así que se le da un acercamiento lento. El encaje
            # se hace al doble de tamaño para que el zoom no ablande la imagen.
            entradas += ["-loop", "1", "-framerate", "30", "-t", f"{b['dur']}",
                         "-i", b["ruta"]]
            pasos.append(C.encaje(f"[{i}:v]", f"[e{i}]", b["ajuste"], i, 3840, 2160))
            pasos.append(f"[e{i}]zoompan=z='min(1.0+0.08*on/{nf},1.08)':d=1:"
                         f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30[f{i}]")
        else:
            entradas += ["-ss", f"{b['entrada']}", "-t", f"{b['dur']}", "-i", b["ruta"]]
            pasos.append(f"[{i}:v]fps=30[p{i}]")
            pasos.append(C.encaje(f"[p{i}]", f"[f{i}]", b["ajuste"], i))
        # `tpad` corre el inserto hasta su sitio en la línea de tiempo. Sin esto habría que
        # desplazar los PTS, y overlay no sabe qué pintar mientras la segunda entrada aún no
        # ha empezado.
        pasos.append(f"[f{i}]eq=contrast=1.015:saturation=1.02,"
                     f"tpad=start_duration={b['t_in']}:start_mode=add:color=black[x{i}]")
        salida = "[vout]" if i == len(lista) else f"[c{i}]"
        pasos.append(f"{prev}[x{i}]overlay=0:0:eof_action=pass:"
                     f"enable='between(t,{b['t_in']},{b['t_out']})'{salida}")
        prev = salida

    filtro = os.path.join(p["_trabajo"], "_broll.filter")
    with open(filtro, "w") as f:
        f.write(";".join(pasos))
    C.run([C.FF, "-y", "-v", "error"] + entradas +
          ["-/filter_complex", filtro, "-map", "[vout]", "-map", "0:a",
           "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "copy", dst],
          f"tomas auxiliares ({len(lista)} insertos, audio intacto)")
    for b in lista:
        print(f"    {C.tc(b['t_in'])}–{C.tc(b['t_out'])}  {b['ajuste']:8s} {b['archivo']}")


# ------------------------------------------------------------------ 4. gráfica
def _desliza(x_final, t_in, t_out, d_in=0.42, d_out=0.32, desde="izq"):
    """Expresión de X para que el gráfico entre y salga deslizándose fuera de cuadro."""
    m = (f"min(min(1\\,max(0\\,(t-{t_in})/{d_in}))\\,"
         f"min(1\\,max(0\\,({t_out}-t)/{d_out})))")
    return f"-w+({x_final}+w)*{m}" if desde == "izq" else f"1920-(1920-{x_final})*{m}"


def tiempos_grafica(p, dur=None):
    """Cuándo entra y sale cada gráfico, en la línea de tiempo del cuerpo."""
    dur = dur or C.duraciones_reales(p)
    ini = C.inicios(p, dur)
    cuerpo_d = C.dur_cuerpo(p, dur)
    t = {"logobox": (0.0, cuerpo_d), "cenefas": [], "lower": None, "redes": None}
    for n, k in enumerate(p["_inicio_bloque"]):
        t0 = ini[k] + 0.9                                  # deja arrancar la respuesta
        d = 5.4 if "\n" not in p["preguntas"][n] else 6.9  # dos líneas piden más lectura
        t["cenefas"].append((n + 1, round(t0, 2), round(t0 + d, 2)))
    t["lower"] = (round(ini[0] + 9.0, 2), round(ini[0] + 15.2, 2))
    if p["_inicio_redes"] is not None:
        r0 = round(ini[p["_inicio_redes"]] + 1.6, 2)
        t["redes"] = (r0, round(r0 + 0.45, 2), round(cuerpo_d - 0.8, 2))
    return t


def grafica(p):
    t = tiempos_grafica(p)
    # Si hay tomas auxiliares se parte de la versión con ellas: los sobreimpresos van
    # siempre encima, también sobre el inserto (la caja de logos no se despega en la serie).
    con_broll = os.path.join(p["_out"], "cuerpo_broll.mov")
    cuerpo_mov = con_broll if os.path.exists(con_broll) else os.path.join(p["_out"], "cuerpo.mov")
    G = p["_gfx"]

    entradas = ["-i", cuerpo_mov, "-i", f"{G}/logobox.png"]
    for n, _, _ in t["cenefas"]:
        entradas += ["-i", f"{G}/cenefa_{n}.png"]
    entradas += ["-i", f"{G}/lowerthird.png"]
    redes = [x for x in ("fa", "in") if os.path.exists(f"{G}/social_{x}.png")]
    for x in redes:
        entradas += ["-i", f"{G}/social_{x}.png"]

    pasos = ["[0:v][1:v]overlay=-30:64[b0]"]
    i = 0
    for i, (_, t0, t1) in enumerate(t["cenefas"]):
        pasos.append(f"[b{i}][{i+2}:v]overlay=x='{_desliza(-30, t0, t1)}':y=1006-h:"
                     f"enable='between(t,{t0 - 0.1},{t1 + 0.1})'[b{i+1}]")
    n = len(t["cenefas"])
    lt0, lt1 = t["lower"]
    pasos.append(f"[b{n}][{n+2}:v]overlay=x='{_desliza(96, lt0, lt1)}':y=902:"
                 f"enable='between(t,{lt0 - 0.1},{lt1 + 0.1})'[b{n+1}]")
    idx, ys = n + 1, [668, 843]
    if t["redes"] and redes:
        r0, r0b, r1 = t["redes"]
        for j, x in enumerate(redes):
            entra = r0 if j == 0 else r0b
            destino = "[vout]" if j == len(redes) - 1 else f"[b{idx+1}]"
            pasos.append(f"[b{idx}][{n+3+j}:v]"
                         f"overlay=x='{_desliza(1268, entra, r1, desde='der')}':y={ys[j]}:"
                         f"enable='between(t,{entra - 0.1},{r1 + 0.1})'{destino}")
            idx += 1
    else:
        pasos[-1] = pasos[-1].replace(f"[b{n+1}]", "[vout]")

    filtro = os.path.join(p["_trabajo"], "_gfx.filter")
    with open(filtro, "w") as f:
        f.write(";".join(pasos))

    # Loudness en dos pasadas: medir el cuerpo entero y luego aplicar linealmente. En una
    # sola pasada loudnorm va corrigiendo sobre la marcha y la voz bombea.
    med = C.run([C.FF, "-hide_banner", "-i", cuerpo_mov,
                 "-af", f"{C.A_CUERPO},loudnorm=I=-16:TP=-1.5:LRA=11:print_format=summary",
                 "-f", "null", "-"], "midiendo loudness")
    # Se buscan exactamente estas cuatro claves: el resumen viene mezclado con la cabecera
    # `Input #0, mov,mp4,...` del archivo, que también empieza por "Input" pero no trae valor.
    CLAVES = ("Input Integrated", "Input True Peak", "Input LRA", "Input Threshold")
    v = {}
    for linea in med.splitlines():
        limpia = linea.strip()
        for c in CLAVES:
            if limpia.startswith(c + ":"):
                v[c] = limpia.split(":", 1)[1].strip().split()[0]
    if len(v) != len(CLAVES):
        print(med[-2000:])
        sys.exit("No pude leer el resumen de loudnorm; revisa la salida de arriba.")
    af = (f"{C.A_CUERPO},loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={v['Input Integrated']}"
          f":measured_TP={v['Input True Peak']}:measured_LRA={v['Input LRA']}"
          f":measured_thresh={v['Input Threshold']}:linear=true,aresample=48000")
    print(f"    entrada {v['Input Integrated']} LUFS -> salida -16 LUFS")

    C.run([C.FF, "-y", "-v", "error"] + entradas +
          ["-/filter_complex", filtro, "-map", "[vout]", "-map", "0:a", "-af", af,
           "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "pcm_s16le", os.path.join(p["_out"], "cuerpo_gfx.mov")],
          "sobreimpresos + normalización de audio")


# ------------------------------------------------------------------ 5. intro y cortinilla
def intro(p):
    d = C.DUR_INTRO
    # `-framerate 30` en la imagen: sin eso entra a 25 fps y la placa dura 2.5 s en vez de 3.
    C.run([C.FF, "-y", "-v", "error",
           "-loop", "1", "-framerate", "30", "-t", f"{d}",
           "-i", os.path.join(p["_gfx"], "intro.png"),
           "-f", "lavfi", "-t", f"{d}", "-i", "anullsrc=r=48000:cl=stereo",
           "-vf", (f"scale=3840:-2,zoompan=z='min(1.0+0.025*on/{int(d * 30)},1.025)':d=1:"
                   f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,"
                   f"fade=t=in:st=0:d=0.5"),
           "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2",
           os.path.join(p["_out"], "intro.mov")], "placa de intro")

    # La cortinilla original es vertical 1080x1920: se recorta la banda central, donde está
    # el logo, y se escala a 16:9.
    C.run([C.FF, "-y", "-v", "error", "-i", p["cortinilla"],
           "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
           "-vf", "crop=1080:608:0:624,scale=1920:1080:flags=lanczos,fps=30",
           "-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "pcm_s16le", os.path.join(p["_out"], "cortinilla.mov")],
          "cortinilla recortada a 16:9")


# ------------------------------------------------------------------ 6. montaje final
def _mezcla_musica(p, off1, off2, total, ganancia=0.0):
    """Cadena de mezcla de la música bajo la voz.

    Tres mecanismos que hacen cosas distintas y se complementan:

    1. **Automatización por tramo.** La música entra sola y protagonista en la placa, se
       agacha cuando llega la voz y vuelve a subir en la cortinilla. Son los niveles medidos
       sobre el capítulo de referencia de la serie (ver MUSICA_* en comun.py).
    2. **Sidechain.** Además de la bajada fija, la propia voz controla la música marco a
       marco: en las pausas entre frases el colchón respira y cuando ella habla se retira.
       Sin esto la música es una manta uniforme; con esto acompaña.
    3. **Filtro de banda.** Se le quita a la música parte del rango donde vive el habla
       (300 Hz – 3 kHz). Deja sitio sin tener que bajarla tanto, que es como se consigue que
       se oiga sin molestar.
    """
    g_intro = 10 ** (C.MUSICA_INTRO_DB / 20)
    g_fondo = 10 ** (C.MUSICA_FONDO_DB / 20)
    g_cierre = 10 ** (C.MUSICA_CIERRE_DB / 20)
    # rampas: baja al entrar la voz, sube al empezar la cortinilla
    t1 = round(off1 - 0.2, 3)
    t2 = round(t1 + C.MUSICA_BAJADA, 3)
    t3 = round(off2 - 0.3, 3)
    t4 = round(t3 + C.MUSICA_SUBIDA, 3)
    env = (f"if(lt(t,{t1}),{g_intro:.5f},"
           f"if(lt(t,{t2}),{g_intro:.5f}+({g_fondo:.5f}-{g_intro:.5f})*(t-{t1})/{C.MUSICA_BAJADA},"
           f"if(lt(t,{t3}),{g_fondo:.5f},"
           f"if(lt(t,{t4}),{g_fondo:.5f}+({g_cierre:.5f}-{g_fondo:.5f})*(t-{t3})/{C.MUSICA_SUBIDA},"
           f"{g_cierre:.5f}))))")
    return (
        f"[3:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
        f"atrim=0:{total},asetpts=PTS-STARTPTS,"
        f"volume={ganancia:+.2f}dB,{C.MUSICA_FILTROS},"
        f"volume=volume='{env}':eval=frame,"
        f"afade=t=in:st=0:d=0.35,afade=t=out:st={round(total - 1.8, 3)}:d=1.8[mus];"
        f"[voz]asplit=2[voz1][llave];"
        # Sidechain suave a propósito. La bajada grande (15 dB) ya la hace la automatización
        # por tramo; si además se le pide al compresor que agache mucho, acaba haciendo él
        # todo el trabajo y subir la ganancia estática deja de tener efecto: se le da más
        # señal y comprime más, así que el colchón no sube. Aquí solo aporta el movimiento,
        # unos pocos dB, para que la música respire en las pausas entre frases.
        f"[mus][llave]sidechaincompress=threshold=0.05:ratio=2.5:attack=30:release=400:"
        f"makeup=1:level_sc=1[musduck];"
        f"[voz1][musduck]amix=inputs=2:duration=first:normalize=0,"
        f"alimiter=limit=0.89:level=disabled[aout]")


def final(p):
    O = p["_out"]
    # Offsets sobre las duraciones reales de los tres bloques: si se calculan con las
    # nominales y alguna no coincide, la cortinilla se queda fuera del montaje sin avisar.
    d_intro = C.dur_real(f"{O}/intro.mov")
    d_cuerpo = C.dur_real(f"{O}/cuerpo_gfx.mov")
    d_cort = C.dur_real(f"{O}/cortinilla.mov")
    X = C.XF_BLOQUE
    off1 = round(d_intro - X, 3)
    off2 = round(off1 + d_cuerpo - X, 3)
    total = round(off2 + d_cort, 3)

    # El video disuelve contra intro y cortinilla, pero el audio se concatena sin crossfade:
    # ambas son mudas y un crossfade se comería la primera y la última palabra.
    graph = (f"[0:v][1:v]xfade=transition=fade:duration={X}:offset={off1}[v1];"
             f"[v1][2:v]xfade=transition=fade:duration={X}:offset={off2}[vout];"
             f"[0:a]atrim=0:{off1},asetpts=PTS-STARTPTS[a0];"
             f"[1:a]afade=t=out:st={round(d_cuerpo - 0.2, 3)}:d=0.2[a1];"
             f"[2:a]atrim=0:{round(d_cort - X, 3)},asetpts=PTS-STARTPTS[a2];"
             f"[a0][a1][a2]concat=n=3:v=0:a=1")

    pista = C.elige_musica(p)
    entradas = ["-i", f"{O}/intro.mov", "-i", f"{O}/cuerpo_gfx.mov", "-i", f"{O}/cortinilla.mov"]
    if pista:
        arranque = C.entrada_musica(pista)
        ganancia = (C.ganancia_musica(pista, arranque)
                    + (p.get("musica") or {}).get("ganancia", 0))
        graph += "[voz];" + _mezcla_musica(p, off1, off2, total, ganancia)
        d_pista = C.info_media(pista)[0] or 0
        util = d_pista - arranque
        if util < total:
            print(f"    OJO: de {os.path.basename(pista)} solo quedan {C.tc(util)} útiles "
                  f"para {C.tc(total)} de capítulo; se repetirá en bucle y el empalme se oye.")
        # `-stream_loop -1` la repite si hiciera falta; `-ss` entra por donde ya suena a
        # nivel, saltándose el fundido o la construcción inicial de la pista.
        entradas += ["-stream_loop", "-1", "-ss", f"{arranque}", "-i", pista]
        print(f"    música: {os.path.basename(pista)}  {ganancia:+.1f} dB"
              + (f", entra en {C.tc(arranque)}" if arranque else ""))
    else:
        graph += "[aout]"

    filtro = os.path.join(p["_trabajo"], "_final.filter")
    with open(filtro, "w") as f:
        f.write(graph)

    nombre = f"{p['afiliado_corto']} - Afiliados que construyen historias de exito 1080p.mp4"
    dst = os.path.join(p["_salida"], nombre)
    C.run([C.FF, "-y", "-v", "error"] + entradas +
          ["-/filter_complex", filtro, "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-level", "4.1",
           "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
           "-movflags", "+faststart", dst],
          f"montaje final -> {C.tc(total)}")

    limite = p["duracion_maxima"]
    aviso = "  *** SE PASA DEL LÍMITE ***" if total > limite else ""
    print(f"\n{dst}\n    {C.tc(total)} ({total:.2f} s, límite {C.tc(limite)}){aviso}")
    if total > limite:
        print("    Quita un segmento entero de proyecto.json; recortar muchas cosas pequeñas\n"
              "    llena el montaje de micro-cortes y se nota más.")


ETAPAS = {"cortar": cortar, "cuerpo": cuerpo, "broll": broll, "grafica": grafica,
          "intro": intro, "final": final}

if __name__ == "__main__":
    proyecto = C.uso("render.py")
    pedidas = sys.argv[2:] or list(ETAPAS)
    for nombre in pedidas:
        if nombre not in ETAPAS:
            sys.exit(f"Etapa desconocida: {nombre}. Opciones: {', '.join(ETAPAS)}")
    for nombre in pedidas:
        ETAPAS[nombre](proyecto)
    print("\nlisto — ahora corre verificar.py antes de dar el capítulo por bueno")
