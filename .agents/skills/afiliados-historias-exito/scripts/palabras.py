#!/usr/bin/env python3
"""Acceso a las marcas de palabra de las tomas, para que los cortes sepan de lenguaje.

Los cortes colocados solo por energía no entienden dónde acaba una frase: buscan el siguiente
hueco acústico y se llevan por delante lo que haya. Así se coló en un capítulo un corte que
dejaba «...la casa de sus sueños **y**» pegado a «el tema del precio», con la conjunción
colgando y dos ideas distintas cosidas.

Este módulo aporta lo que faltaba: qué palabras hay dentro de cada segmento, cuáles son de
contenido y cuáles son de enlace, y cómo suena la costura entre dos segmentos.
"""
import glob
import json
import os
import re
import unicodedata


def nfc(nombre):
    """macOS guarda «Cómo» con la tilde descompuesta (NFD) y el JSON la trae compuesta (NFC).

    Sin normalizar, `voc[s["archivo"]]` falla en silencio para toda toma con acento en el
    nombre y el segmento se queda «sin palabras»: la revisión de sentido lo daba por bueno
    sin haber mirado nada.
    """
    return unicodedata.normalize("NFC", nombre)

# Palabras que no pueden quedar al final de un segmento salvo que el siguiente continúe la
# misma frase: dejan la idea en el aire y, peor, se enganchan a lo que venga detrás.
ENLACE = {
    "y", "e", "o", "u", "ni", "pero", "sino", "que", "porque", "pues", "como", "cuando",
    "donde", "si", "aunque", "mientras", "de", "del", "a", "al", "en", "con", "sin", "por",
    "para", "sobre", "entre", "hasta", "desde", "el", "la", "los", "las", "un", "una",
    "unos", "unas", "lo", "su", "sus", "mi", "mis", "nuestro", "nuestra", "nuestros",
    "nuestras", "este", "esta", "estos", "estas", "ese", "esa", "muy", "más", "también",
    "además", "adicionalmente", "es", "son", "ha", "han", "se",
}


def limpia(w):
    return re.sub(r"[^\wáéíóúüñ]", "", w.lower(), flags=re.UNICODE)


def tomas_ordenadas(p):
    """Las tomas en el mismo orden que usa transcribir.py para numerar los JSON."""
    return sorted(glob.glob(os.path.join(p["_tomas"], "*.mp4")) +
                  glob.glob(os.path.join(p["_tomas"], "*.mov")) +
                  glob.glob(os.path.join(p["_tomas"], "*.MP4")))


def carga_palabras(p):
    """{nombre_de_archivo: [palabras con start/end]} leído de trabajo/audio/tomaN.json."""
    fuera = {}
    for i, ruta in enumerate(tomas_ordenadas(p), 1):
        js = os.path.join(p["_trabajo"], "audio", f"toma{i}.json")
        if not os.path.exists(js):
            continue
        with open(js, encoding="utf-8") as f:
            d = json.load(f)
        fuera[nfc(os.path.basename(ruta))] = [
            w for s in d.get("segments", []) for w in s.get("words", [])]
    return fuera


def para(voc, archivo):
    """Palabras de una toma, tolerando la normalización de acentos de macOS."""
    return voc.get(nfc(archivo), [])


def dentro(palabras, entrada, salida, borde=0.03):
    """Palabras que suenan completas dentro de [entrada, salida]."""
    return [w for w in palabras
            if w["start"] >= entrada - borde and w["end"] <= salida + borde]


def _hay_voz(db, piso, t):
    import audio_util as A
    i = int(round(t / A.MARCO))
    return bool(0 <= i < len(db) and A._voz(db, piso)[i])


def parcial_final(palabras, salida, db=None, piso=None, borde=0.03):
    """Palabra que el corte parte por la mitad al final, si la hay.

    Es la firma del fallo: el segmento se lleva el arranque de la palabra siguiente y esa
    sílaba suelta se pega al segmento que venga detrás.

    Se exigen **las dos fuentes de acuerdo**: whisper para saber qué palabra es, y la energía
    para saber si de verdad hay sonido en el punto de corte. Las fronteras de palabra de
    whisper tienen fácilmente un tercio de segundo de error, así que por sí solas señalan
    cortes partidos que en realidad caen sobre silencio.
    """
    if db is not None and not _hay_voz(db, piso, salida):
        return None
    for w in palabras:
        if w["start"] < salida - borde < w["end"]:
            return w
    return None


def parcial_inicio(palabras, entrada, db=None, piso=None, borde=0.03):
    if db is not None and not _hay_voz(db, piso, entrada):
        return None
    for w in palabras:
        if w["start"] < entrada + borde < w["end"]:
            return w
    return None


def cola(palabras, n=7):
    return " ".join(w["word"].strip() for w in palabras[-n:])


def cabeza(palabras, n=7):
    return " ".join(w["word"].strip() for w in palabras[:n])


# Arranques que delatan material sin editar. Uno suelto pasa desapercibido; dos o tres
# respuestas seguidas abriendo igual suenan a que nadie tocó el archivo.
MULETILLAS = {"bueno", "pues", "entonces", "digamos", "listo", "ok", "eh", "este"}


def muletilla_inicial(palabras, entrada, borde=0.35):
    """Muletilla al principio del segmento, con la palabra de contenido que la sigue.

    El margen es generoso a propósito: el punto de entrada suele caer unas décimas antes de
    la muletilla, así que buscarla solo entre las palabras «dentro» no la encuentra, y el
    montaje acaba diciendo «Bueno,» aunque el análisis jurara que no.
    """
    cerca = [w for w in palabras if entrada - borde <= w["start"] <= entrada + borde + 0.6]
    if not cerca or limpia(cerca[0]["word"]) not in MULETILLAS:
        return None, None
    j = 0
    while j < len(cerca) and limpia(cerca[j]["word"]) in MULETILLAS:
        j += 1
    return cerca[0], (cerca[j] if j < len(cerca) else None)


def es_enlace(palabra):
    return limpia(palabra) in ENLACE


def cierra_idea(palabras):
    """¿El segmento termina en un punto donde la idea está cerrada?

    Se apoya en la puntuación que pone whisper, que para esto es sorprendentemente fiable:
    un punto marca frase cerrada, una coma marca inciso, y nada marca mitad de frase.
    """
    if not palabras:
        return "vacío"
    ultima = palabras[-1]["word"].strip()
    if es_enlace(ultima):
        return "enlace"          # termina en «y», «de», «que»...: queda colgando
    if ultima.endswith((".", "!", "?")):
        return "punto"
    if ultima.endswith((",", ";", ":")):
        return "coma"
    return "media"
