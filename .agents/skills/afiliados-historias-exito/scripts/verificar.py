#!/usr/bin/env python3
"""Control de calidad del montaje. No es opcional.

    python3 verificar.py proyecto.json

Necesita numpy:

    uv run --with numpy --with pillow --python 3.11 python verificar.py proyecto.json

Hace tres cosas:

1. **Compara la energía de cada segmento del montaje con la de su toma original.** Es la
   prueba importante: exige parecido ~1.00 y desfase 0.00 s. Cualquier otra cosa significa
   que el montaje perdió material, que es como se colaron dos capítulos con todas las frases
   tajadas.
2. **Vuelve a transcribir el cuerpo montado** y lo compara con el texto esperado. Sirve para
   detectar que se cayó una palabra entera, pero **no vale para juzgar los empalmes**:
   whisper sigue reconociendo «nacional» aunque le falte la última sílaba.
3. **Saca una hoja de contactos** con fotogramas en la entrada de cada cenefa, en el lower
   third, en las tarjetas de redes, en cada toma de apoyo y en la cortinilla.

Cuando reporte un empalme con problema: corre `ajustar_cortes.py` y relanza `render.py`; los
clips de los segmentos que cambiaron se rehacen solos.
"""
import json
import os
import subprocess
import re
import sys

import comun as C

C.asegura_dependencias('numpy', 'PIL')
import render as R



def normaliza(t):
    t = t.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u")):
        t = t.replace(a, b)
    return re.findall(r"[a-zñ]+", t)


def transcribe(p, wav, nombre):
    # `--condition-on-previous-text False` es imprescindible aquí: sobre un montaje ya
    # cortado, whisper se engancha con facilidad en un bucle y repite la misma frase durante
    # minutos, con lo que el resto del texto se pierde y la comparación pasa a ser ruido.
    # La temperatura se deja por defecto para que conserve el reintento automático cuando
    # detecta repetición.
    C.run(C.whisper(wav, "--language", "es", "--condition-on-previous-text", "False",
                    "--output-format", "txt", "--output-dir",
                    os.path.join(p["_trabajo"], "audio"), "--output-name", nombre),
          "transcribiendo el montaje para compararlo con el guion", env=C.entorno_whisper())
    with open(os.path.join(p["_trabajo"], "audio", nombre + ".txt"), encoding="utf-8") as f:
        return f.read()


def revisa_texto(p):
    cuerpo = os.path.join(p["_out"], "cuerpo.mov")
    if not os.path.exists(cuerpo):
        sys.exit("Falta el cuerpo renderizado (out/cuerpo.mov) — corre render.py primero.")
    wav = os.path.join(p["_trabajo"], "audio", "montaje.wav")
    os.makedirs(os.path.dirname(wav), exist_ok=True)
    C.run([C.FF, "-y", "-v", "error", "-i", cuerpo, "-vn", "-ac", "1", "-ar", "16000", wav])
    dicho = normaliza(transcribe(p, wav, "montaje"))

    print("\n=== Texto del montaje frente al guion ===\n")
    faltantes = []
    for k, s in enumerate(p["segmentos"]):
        esperadas = normaliza(s.get("texto", ""))
        # Se revisan las palabras del borde, que son las que se lleva la disolvencia.
        bordes = [(w, "entrada") for w in esperadas[:3]] + [(w, "salida") for w in esperadas[-3:]]
        perdidas = [(w, lado) for w, lado in bordes if len(w) > 3 and w not in dicho]
        if perdidas:
            faltantes.append((k, s, perdidas))
            for w, lado in perdidas:
                print(f"  segmento {k:02d} ({s['archivo'][-14:]}): no aparece «{w}» "
                      f"— revisa el punto de {lado} ({s['entrada']} -> {s['salida']})")
    if not faltantes:
        print("  Todas las palabras de los bordes están presentes.")
    print("\nTexto completo del montaje:\n")
    with open(os.path.join(p["_trabajo"], "audio", "montaje.txt"), encoding="utf-8") as f:
        print(f.read())
    return faltantes


def revisa_empalmes(p):
    """Comprueba, midiendo energía, que ningún empalme se comió el final de una frase.

    Es la prueba que faltaba, y la que descubrió el peor fallo que ha tenido este flujo. La
    comparación de texto no sirve para esto: whisper sigue reconociendo «nacional» aunque le
    falte la última sílaba, así que daba por bueno un montaje en el que todas las frases
    estaban tajadas.

    Aquí se compara la envolvente de energía de cada segmento del montaje con la de la toma
    original, buscando además el desfase que mejor las hace coincidir:

    - **parecido** por debajo de 0.93 significa que el montaje no contiene lo mismo que la
      toma: se perdió material por el camino.
    - **desfase** distinto de cero significa que el segmento entró corrido, y entonces el
      empalme se comió su principio o su final.

    Se mide contra `cuerpo.mov`, que es PCM. Contra el MP4 final saldría un desfase constante
    de unos 30 ms que no es del montaje sino del arranque del codificador AAC.

    La tolerancia de desfase es de 80 ms y no menos por el mismo motivo del lado de la
    entrada: las tomas recomprimidas traen audio AAC, y decodificarlas desde puntos de
    búsqueda distintos alinea el resultado hasta un par de tramas AAC (21 ms cada una) más
    acá o más allá. Con el parecido en 1.000 y el contenido íntegro, esa deriva no es un
    error de montaje sino del códec de origen.
    """
    import numpy as np
    import audio_util as A

    cuerpo = os.path.join(p["_out"], "cuerpo.mov")
    if not os.path.exists(cuerpo):
        sys.exit("Falta el cuerpo renderizado (out/cuerpo.mov) — corre render.py primero.")
    dur = C.duraciones_reales(p)
    ini = C.inicios(p, dur)
    f = int(A.SR * A.MARCO)

    def env(x, n):
        """Envolvente en dB, recortada a los 30 dB de arriba para que la reducción de ruido
        y la normalización no distorsionen la comparación en los silencios."""
        e = 20 * np.log10(np.sqrt((x[:n].reshape(-1, f) ** 2).mean(axis=1)) + 1e-9)
        e = np.clip(e, e.max() - 30, None)
        return e - e.mean()

    print("\n=== Empalmes de audio (energía) ===\n")
    print(f"{'seg':>3}  {'parecido':>8}  {'desfase':>8}  {'aire antes':>10}  {'aire después':>12}")
    malos = []
    for k, s in enumerate(p["segmentos"]):
        src = os.path.join(p["_tomas"], s["archivo"])
        d = dur[k]
        # El primer segmento arranca en 0 y no tiene margen por delante: hay que medir
        # cuánto se pudo tomar, o la búsqueda de desfase se calibra sobre un margen que no
        # existe y da un falso positivo.
        margen = min(0.2, ini[k])
        m = A.pcm(cuerpo, ini[k] - margen, d + margen + 0.2)
        o = A.pcm(src, s["entrada"], d)
        n = len(o) // f * f
        if n < A.SR:
            continue
        eo = env(o, n)
        mejor = (-9.0, 0.0)
        for paso in range(-15, 16):
            off = int((margen + paso * A.MARCO) * A.SR)
            trozo = m[off:off + n]
            if len(trozo) < n:
                continue
            r = float(np.corrcoef(env(trozo, n), eo)[0, 1])
            if r > mejor[0]:
                mejor = (r, round(paso * A.MARCO, 3))
        par, desf = mejor

        db_src, piso = A.envolvente(src)
        aire_in = A.aire(db_src, piso, s["entrada"], "despues")
        aire_out = A.aire(db_src, piso, s["salida"], "antes")

        estado = "ok"
        if par < 0.93:
            estado = "REVISAR: falta material"
            malos.append((k, f"el montaje no coincide con la toma (parecido {par:.2f})"))
        elif abs(desf) > 0.08:
            estado = "REVISAR: entró corrido"
            malos.append((k, f"el segmento entró {desf:+.2f} s corrido"))
        print(f"{k:>3}  {par:>8.3f}  {desf:>+7.2f}s  {aire_in:>9.2f}s  {aire_out:>11.2f}s   {estado}")

    print("\n=== Aire en cada empalme (medido sobre las tomas) ===\n")
    for k in range(1, len(dur)):
        ant, sig = p["segmentos"][k - 1], p["segmentos"][k]
        d1, pi1 = A.envolvente(os.path.join(p["_tomas"], ant["archivo"]))
        d2, pi2 = A.envolvente(os.path.join(p["_tomas"], sig["archivo"]))
        a = A.aire(d1, pi1, ant["salida"], "antes") + A.aire(d2, pi2, sig["entrada"], "despues")
        # Sin aire no hay nada roto: el empalme queda a tope entre final de palabra y
        # principio de palabra, que es como se monta diálogo. Solo se avisa para que quien
        # revise sepa dónde va a oír un corte más marcado.
        nota = "" if a >= 0.20 else "  (a tope: final de palabra con principio de palabra)"
        print(f"  empalme {k:>2} en {C.tc(ini[k])}: pausa de {a:.2f} s{nota}")

    if malos:
        print(f"\n{len(malos)} empalme(s) con problema:")
        for k, m in malos:
            print(f"  segmento {k}: {m}")
        print("\nCorre `ajustar_cortes.py proyecto.json` y vuelve a renderizar esos clips.")
    else:
        print("\nTodos los segmentos entran completos y en su sitio: "
              "ninguna frase queda tajada.")
    return malos


def hoja_contactos(p):
    """Fotogramas del video final en los momentos donde entra cada gráfico."""
    final = next((os.path.join(p["_salida"], f) for f in os.listdir(p["_salida"])
                  if f.endswith(".mp4")), None)
    if not final:
        print("Aún no hay MP4 final; me salto la hoja de contactos.")
        return None
    dur = C.duraciones_reales(p)
    t = R.tiempos_grafica(p, dur)
    desfase = C.DUR_INTRO - C.XF_BLOQUE          # el cuerpo empieza después de la intro
    momentos = [("intro", 1.5)]
    for n, t0, t1 in t["cenefas"]:
        momentos.append((f"cenefa {n}", desfase + t0 + 1.6))
    momentos.append(("lower third", desfase + t["lower"][0] + 1.6))
    if t["redes"]:
        momentos.append(("redes", desfase + t["redes"][0] + 2.0))
    total = C.dur_real(final)
    momentos.append(("cortinilla", total - 2.0))
    # Un fotograma en mitad de cada inserto: es la única forma de comprobar que la toma
    # auxiliar cayó donde debía y que el encaje no dejó bandas ni recortó de más.
    for i, b in enumerate(C.broll(p, dur, avisar=False), start=1):
        momentos.append((f"apoyo {i}", round(desfase + (b["t_in"] + b["t_out"]) / 2, 2)))
    momentos.sort(key=lambda m: m[1])       # que la hoja se lea en orden cronológico

    qc = os.path.join(p["_trabajo"], "qc")
    os.makedirs(qc, exist_ok=True)
    for viejo in os.listdir(qc):            # si quedan PNG de una pasada anterior, el glob
        os.remove(os.path.join(qc, viejo))  # de `tile` los mezclaría con los nuevos
    archivos = []
    for i, (etiqueta, seg) in enumerate(momentos):
        dst = os.path.join(qc, f"f{i:02d}.png")
        C.run([C.FF, "-y", "-v", "error", "-ss", f"{seg:.2f}", "-i", final,
               "-frames:v", "1", "-vf", "scale=480:-1", dst])
        if os.path.exists(dst):
            archivos.append((etiqueta, seg, dst))

    # La hoja se arma con Pillow y no con `tile` de ffmpeg: el glob de ffmpeg se rompe con
    # rutas que contienen llaves (`{data}.strat/...`) y falla en silencio, dejando los
    # fotogramas sueltos pero sin hoja.
    hoja = os.path.join(qc, "hoja-contactos.png")
    if archivos:
        from PIL import Image, ImageDraw
        ims = [Image.open(f).convert("RGB") for _, _, f in archivos]
        an, al, m = ims[0].width, ims[0].height, 6
        filas = (len(ims) + 1) // 2
        sheet = Image.new("RGB", (2 * an + 3 * m, filas * al + (filas + 1) * m), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for i, (im, (etiqueta, seg, _)) in enumerate(zip(ims, archivos)):
            x, y = m + (i % 2) * (an + m), m + (i // 2) * (al + m)
            sheet.paste(im, (x, y))
            d.text((x + 8, y + 6), f"{etiqueta}  {C.tc(seg)}", fill=(255, 90, 90))
        sheet.save(hoja)
    print("\n=== Fotogramas de control ===")
    for etiqueta, seg, f in archivos:
        print(f"  {etiqueta:14s} {C.tc(seg):>8s}  {f}")
    if os.path.exists(hoja):
        print(f"\n  hoja de contactos: {hoja}")
    return hoja


def revisa_sentido(p):
    """La revisión de costuras, otra vez, sobre los cortes definitivos.

    Existe porque en la prueba con Codex el asistente retocó cortes tres veces después de la
    primera revisión, verificó cada render con este script —que solo miraba energía y texto—
    y entregó con un problema de sentido que `revisar_sentido.py` habría marcado. La
    verificación final no puede depender de que alguien se acuerde de repetir otra."""
    print("\n=== Sentido de los empalmes (revisar_sentido.py) ===\n")
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "revisar_sentido.py"), sys.argv[1]], capture_output=True, text=True)
    salida = r.stdout
    if "problema(s) de sentido" in salida:
        bloque = salida[salida.index("problema(s) de sentido") - 4:]
        print(bloque.rstrip())
        return [l.strip() for l in bloque.splitlines() if l.strip().startswith("segmento ")]
    print("  Ninguna costura rompe el sentido.")
    return []


if __name__ == "__main__":
    proyecto = C.uso("verificar.py")
    problemas = revisa_texto(proyecto)
    problemas += revisa_empalmes(proyecto)
    sentido = revisa_sentido(proyecto)
    hoja_contactos(proyecto)
    if sentido:
        print(f"\nNO LO DES POR BUENO: {len(sentido)} empalme(s) con problema de sentido "
              "(arriba). Corrígelos y vuelve a renderizar y verificar.")
    if problemas:
        print(f"\n{len(problemas)} segmento(s) con palabras posiblemente cortadas. "
              "Dale más aire al punto señalado y vuelve a cortar ese clip.\n\n"
              "Ojo: si la palabra ya venía muy floja en la toma original (un «gracias» dicho\n"
              "de lado, fuera del micrófono), whisper la deja fuera aunque el corte esté bien.\n"
              "Para distinguirlo, extrae ese trozo del original y del montaje y transcribe\n"
              "los dos por separado, subiendo el volumen:\n\n"
              f"  {C.FF} -ss <t> -t 1.5 -i <toma> -vn -ac 1 -ar 16000 -af volume=8dB frag.wav\n"
              f"  {' '.join(C.whisper('frag.wav', '--language', 'es'))}")
    elif not sentido:
        print("\nTexto correcto. Revisa la hoja de contactos y el capítulo queda listo.")
    if problemas or sentido:
        sys.exit(1)
