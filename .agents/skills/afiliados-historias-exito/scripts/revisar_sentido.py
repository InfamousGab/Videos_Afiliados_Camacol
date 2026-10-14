#!/usr/bin/env python3
"""Lee en voz alta cada costura del montaje, para comprobar que el sentido no se rompe.

    python3 revisar_sentido.py proyecto.json

Los cortes se colocan midiendo energía, y la energía no entiende de frases. Este script
reconstruye, palabra por palabra, **cómo va a sonar cada empalme**: las últimas palabras del
segmento que sale seguidas de las primeras del que entra. Con eso a la vista se juzga lo
único que ningún script puede juzgar solo — si la frase resultante significa algo.

Marca automáticamente tres averías que sí son mecánicas:

- **media palabra**: el corte parte una palabra y esa sílaba suelta se pega al segmento
  siguiente. Es lo que produjo «...la casa de sus sueños **y** el tema del precio».
- **enlace colgando**: el segmento acaba en «y», «de», «que»... y el siguiente no continúa
  esa frase, así que la idea queda en el aire.
- **arranque huérfano**: el segmento empieza por una palabra de enlace que se refiere a algo
  que se cortó.
"""
import os
import sys

import subprocess
import tempfile

import comun as C

C.asegura_dependencias('numpy')

import audio_util as A
import palabras as P

ISLA_DURACION = 2.5   # por debajo de esto, un segmento entre dos cortes a tope canta


def escucha(p, ruta_toma, desde, segundos=1.8):
    """Transcribe un fragmento corto de la toma para saber qué se oye de verdad ahí.

    Cuando un corte cae dentro de habla continua, ni whisper ni la energía pueden decidir
    solos si parte una palabra: las fronteras de whisper tienen un tercio de segundo de
    error, y la energía no distingue una frontera de palabra de una consonante oclusiva.
    La única respuesta fiable es oírlo, y eso se puede automatizar para los pocos casos
    sospechosos: se extrae el fragmento y se transcribe aparte.
    """
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "frag.wav")
        C.run([C.FF, "-y", "-v", "error", "-ss", f"{max(0, desde)}", "-t", f"{segundos}",
               "-i", ruta_toma, "-vn", "-ac", "1", "-ar", "16000",
               "-af", "volume=6dB", wav], fatal=False)
        if not os.path.exists(wav):
            return None
        r = subprocess.run(
            C.whisper(wav, "--language", "es", "--condition-on-previous-text", "False",
                      "--output-format", "txt", "--output-dir", tmp),
            capture_output=True, text=True, env=C.entorno_whisper())
        txt = os.path.join(tmp, "frag.txt")
        if r.returncode or not os.path.exists(txt):
            return None
        return open(txt, encoding="utf-8").read().strip()


def main():
    p = C.uso("revisar_sentido.py")
    voc = P.carga_palabras(p)
    env = {}
    if not voc:
        sys.exit("Faltan las marcas de palabra: corre antes `transcribir.py proyecto.json`.")

    segs = p["segmentos"]
    info = []
    for k, s in enumerate(segs):
        pal = P.para(voc, s["archivo"])
        if s["archivo"] not in env:
            env[s["archivo"]] = A.envolvente(os.path.join(p["_tomas"], s["archivo"]))
        db, piso = env[s["archivo"]]
        dentro = P.dentro(pal, s["entrada"], s["salida"])
        info.append({
            "k": k, "s": s, "pal": pal, "dentro": dentro,
            "cierre": P.cierra_idea(dentro),
            "corta_final": P.parcial_final(pal, s["salida"], db, piso),
            "corta_inicio": P.parcial_inicio(pal, s["entrada"], db, piso),
        })

    print("\n=== Cómo suena cada costura ===\n")
    problemas = []
    for a, b in zip(info, info[1:]):
        ka, kb = a["k"], b["k"]
        mismo_bloque = a["s"].get("bloque") == b["s"].get("bloque")
        misma_toma = a["s"]["archivo"] == b["s"]["archivo"]
        continua = misma_toma and abs(b["s"]["entrada"] - a["s"]["salida"]) < 2.5

        print(f"  {ka:>2} → {kb:<2}  bloque {a['s'].get('bloque')} → {b['s'].get('bloque')}"
              f"{'' if mismo_bloque else '   (cambia de pregunta)'}")
        print(f"      «...{P.cola(a['dentro'])}» ⟶ «{P.cabeza(b['dentro'])}...»")

        if a["corta_final"]:
            w = a["corta_final"]
            oido = escucha(p, os.path.join(p["_tomas"], a["s"]["archivo"]),
                           a["s"]["salida"] - 1.5, 1.5)
            print(f"      ? podría partir «{w['word'].strip()}» — al oírlo: «{oido}»")
            if oido and P.limpia(w["word"]) not in [P.limpia(x) for x in oido.split()]:
                problemas.append((ka, f"el corte parte «{w['word'].strip()}»; el fragmento "
                                      f"suena a «{oido}»"))
        if b["corta_inicio"]:
            w = b["corta_inicio"]
            oido = escucha(p, os.path.join(p["_tomas"], b["s"]["archivo"]),
                           b["s"]["entrada"])
            print(f"      ? podría entrar a mitad de «{w['word'].strip()}» — "
                  f"al oírlo: «{oido}»")
            # Si lo primero que se oye es la palabra entera, el corte estaba bien puesto.
            primera = P.limpia(oido.split()[0]) if oido and oido.split() else ""
            if primera and primera != P.limpia(w["word"]):
                problemas.append((kb, f"entra a mitad de «{w['word'].strip()}»; "
                                      f"el fragmento empieza sonando «{oido}»"))
        if a["cierre"] == "enlace" and not continua:
            ult = a["dentro"][-1]["word"].strip() if a["dentro"] else "?"
            problemas.append((ka, f"acaba en «{ult}» y el segmento {kb} no continúa esa "
                                 f"frase: la idea queda colgando"))
            print(f"      *** acaba en el enlace «{ult}» y no hay continuación ***")
        elif a["cierre"] == "media" and not continua:
            print(f"      (acaba a mitad de frase; revisa si se entiende)")
        print()

    print("=== Fragmentos aislados ===\n")
    # Un trozo corto encajado entre dos empalmes apretados es la firma de un montaje que
    # suena picado, aunque cada corte por separado sea impecable. Pasó con «la casa de sus
    # sueños»: 0.95 s entre dos empalmes de 0.13 s, tres cortes en tres segundos. La regla
    # que salió de ahí: es preferible dejar una frase redundante que meter una isla.
    islas = False
    for k, i in enumerate(info):
        d = i["s"]["salida"] - i["s"]["entrada"]
        if d >= ISLA_DURACION:
            continue
        db, piso = env[i["s"]["archivo"]]
        # Se mira EN el punto de corte, no un poco antes o después: los huecos que sirven
        # para cortar cuando la persona no respira duran 60–80 ms, así que asomarse 50 ms
        # afuera cae de lleno en la sílaba vecina y todo parece habla continua.
        antes = A.clasifica(db, piso, i["s"]["entrada"])
        despues = A.clasifica(db, piso, i["s"]["salida"])
        if antes == "voz" and despues == "voz":
            islas = True
            print(f"  {k:>2}  dura {d:.2f} s y entra y sale en mitad de habla continua.")
            print(f"      «{P.cabeza(i['dentro'], 9)}»")
            print(f"      Fúndelo con el segmento vecino aunque cueste segundos: un trozo")
            print(f"      corto entre dos cortes a tope se oye picado.")
    if not islas:
        print("  Ninguno.")

    print("\n=== Arranques con muletilla ===\n")
    hay = False
    for i in info:
        mul, sig = P.muletilla_inicial(i["pal"], i["s"]["entrada"])
        if mul and sig:
            hay = True
            print(f"  {i['k']:>2}  abre con «{mul['word'].strip()}»; el contenido empieza "
                  f"en {sig['start']:.2f} («{sig['word'].strip()}»)")
            continue
        # Las marcas de whisper pueden situar la muletilla bastante antes de donde suena: en
        # A1S, un «Bueno» dicho pegado a «A1S» aparecía terminando en 7.22 s y en realidad
        # sonaba hasta casi 7.38. Un corte en 7.24 lo daba por fuera y el capítulo abría con
        # medio «Bueno». Así que, si el corte cae con la voz sonando, se escucha el arranque.
        db, piso = env[i["s"]["archivo"]]
        if A.clasifica(db, piso, i["s"]["entrada"]) != "voz":
            continue
        oido = escucha(p, os.path.join(p["_tomas"], i["s"]["archivo"]), i["s"]["entrada"], 2.5)
        primera = oido.split()[0] if oido and oido.split() else ""
        if P.limpia(primera) in P.MULETILLAS:
            hay = True
            print(f"  {i['k']:>2}  AL OÍRLO abre con «{primera.strip(',.')}» —«{oido}»— aunque la\n"
                  f"      transcripción la daba por fuera. Sube la entrada hasta donde empieza la\n"
                  f"      palabra de contenido (mídelo con ajustar_cortes.py, no con las marcas).")
            problemas.append((i["k"], f"al oírlo, abre con «{primera.strip(',.')}»: «{oido}»"))
    if not hay:
        print("  Ninguno.")
    else:
        print("\n  Una suelta no molesta. Dos o tres respuestas seguidas abriendo igual sí:\n"
              "  suena a material sin editar. Sube la entrada al instante que se indica.")

    print("\n=== Cómo cierra cada segmento ===\n")
    etiqueta = {"punto": "frase cerrada", "coma": "inciso", "media": "mitad de frase",
                "enlace": "ENLACE COLGANDO", "vacío": "sin palabras"}
    for i in info:
        print(f"  {i['k']:>2}  {etiqueta[i['cierre']]:<16}  «...{P.cola(i['dentro'], 5)}»")

    if problemas:
        print(f"\n{len(problemas)} problema(s) de sentido:\n")
        for k, m in problemas:
            print(f"  segmento {k}: {m}")
        print("\nCorrige entrada/salida en proyecto.json y vuelve a renderizar: los clips de\n"
              "esos segmentos se rehacen solos, no hay que borrar nada.")
    else:
        print("\nNinguna costura rompe el sentido por sí sola. Aun así, lee las de arriba: "
              "que sea gramatical no garantiza que se entienda.")
    return problemas


if __name__ == "__main__":
    main()
