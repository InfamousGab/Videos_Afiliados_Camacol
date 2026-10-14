#!/usr/bin/env python3
"""Análisis de energía del audio, para colocar los cortes sobre silencio de verdad.

Existe por un error que costó dos capítulos: las marcas de palabra de whisper **se adelantan
al final real de la palabra**. Whisper da por terminada «1972.» cuando todavía queda un
tercio de segundo de cola de vocal sonando. Cortar 0.22 s después de esa marca, que parecía
un margen prudente, caía en mitad del sonido y el empalme se oía tajado.

La energía no miente: aquí se mide el nivel real marco a marco y se busca dónde calla la voz.
"""
import subprocess
import numpy as np

import comun as C

SR = 16000
MARCO = 0.010          # resolución del análisis: 10 ms
SOBRE_PISO = 8.0       # dB sobre el piso a partir de los cuales hay algo (voz o aliento)
SOBRE_PISO_VOZ = 18.0  # a partir de aquí ya es voz articulada, no una inspiración


def pcm(path, ss=0.0, dur=None, salto=2.0):
    """Audio mono a 16 kHz de una ventana, con búsqueda exacta.

    En dos etapas: `-ss` **antes** de `-i` salta rápido hasta `salto` segundos antes del
    punto, y un segundo `-ss` **después** de `-i` afina decodificando. Con búsqueda rápida
    a secas, sobre MP4 recomprimidos (los de WhatsApp) el audio aterriza hasta 60 ms antes
    de lo pedido, y eso hacía que la comprobación de empalmes acusara de «entrar corrido» a
    segmentos que estaban perfectos.
    """
    cmd = [C.FF, "-v", "error"]
    if ss > salto:
        cmd += ["-ss", f"{ss - salto}"]
        fino = salto
    else:
        fino = ss
    cmd += ["-i", path]
    if fino:
        cmd += ["-ss", f"{fino}"]
    if dur:
        cmd += ["-t", f"{dur}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def envolvente(path):
    """(niveles_dB_por_marco, piso_de_ruido_dB) de un archivo completo."""
    x = pcm(path)
    n = int(SR * MARCO)
    m = len(x) // n
    if m == 0:
        return np.array([]), -90.0
    db = 20 * np.log10(np.sqrt((x[:m * n].reshape(m, n) ** 2).mean(axis=1)) + 1e-9)
    return db, float(np.percentile(db, 5))


def _voz(db, piso):
    return db > piso + SOBRE_PISO


def inicio_de_habla(db, piso, t, limite=1.2):
    """Instante en que arranca la primera voz a partir de `t`."""
    voz = _voz(db, piso)
    i = max(0, int(round(t / MARCO)))
    tope = min(len(voz), i + int(limite / MARCO))
    idx = np.where(voz[i:tope])[0]
    return (i + idx[0]) * MARCO if len(idx) else None


def voz_anterior(db, piso, t, limite=1.2):
    """Instante en que calló la última voz antes de `t` (para no invadir la frase previa)."""
    voz = _voz(db, piso)
    i = int(round(t / MARCO))
    desde = max(0, i - int(limite / MARCO))
    idx = np.where(voz[desde:i])[0]
    return (desde + idx[-1] + 1) * MARCO if len(idx) else None


def aire(db, piso, t, lado):
    """Silencio real, en segundos, entre `t` y la voz más cercana por el lado indicado."""
    if lado == "antes":
        v = voz_anterior(db, piso, t)
        return round(t - v, 3) if v is not None else 1.2
    v = inicio_de_habla(db, piso, t)
    return round(v - t, 3) if v is not None else 1.2


def valle(db, piso, t, atras=0.30, adelante=0.40, min_hueco=0.03):
    """Frontera de palabra más cercana a `t`: (inicio, fin) del hueco de energía.

    Buscar «el final de una frase» pide exigir 120 ms de silencio, porque huecos más cortos
    suelen ser la oclusión de una /p/ o una /t/. Pero entre dos palabras encadenadas el hueco
    real es de 30–60 ms, y ahí es donde hay que cortar cuando la persona no respira.

    Por eso este buscador es fino y **guiado**: se le pasa el instante en que whisper cree
    que acaba la palabra y devuelve el valle real más cercano. Sin esa pista sería
    inservible —encontraría valles dentro de las propias palabras—; con ella es lo que
    permite cortar justo después de «sueños» y no arrastrar el «y» siguiente.
    """
    voz = _voz(db, piso)
    i0 = max(0, int(round((t - atras) / MARCO)))
    i1 = min(len(voz), int(round((t + adelante) / MARCO)))
    if i1 <= i0:
        return None
    n = max(1, int(round(min_hueco / MARCO)))
    huecos, j = [], i0
    while j < i1:
        if not voz[j]:
            k = j
            while k < len(voz) and not voz[k]:
                k += 1
            if k - j >= n:
                huecos.append((j * MARCO, k * MARCO))
            j = k
        else:
            j += 1
    if not huecos:
        return None
    # el más cercano a la marca de whisper, midiendo contra el borde que toca
    return min(huecos, key=lambda h: min(abs(h[0] - t), abs(h[1] - t)))


def clasifica(db, piso, t, ventana=0.05):
    """Qué hay realmente en un instante: «silencio», «respiración» o «voz».

    La distinción importa al juzgar un empalme. Midiendo solo con un umbral, una inspiración
    cuenta como voz y el hueco parece no existir: una pausa que la transcripción da como de
    0.78 s se mide como 0.10 s de aire y el empalme parece a tope cuando en realidad tiene
    una respiración, que es lo más natural que puede haber entre dos frases.

    Al revés también engaña: un empalme dentro de habla continua, sin ni siquiera aliento,
    es el que de verdad suena tajado.

    La ventana es corta a propósito. Las fronteras que sirven para cortar cuando la persona
    no respira son huecos de 60–80 ms; con una ventana de 0.12 s se promedian con las sílabas
    vecinas y el hueco desaparece del análisis, que era lo que hacía dar por malo un corte
    perfectamente colocado.
    """
    i = int(round(t / MARCO))
    n = max(1, int(ventana / MARCO))
    tramo = db[max(0, i - n // 2):i + n // 2]
    if len(tramo) == 0:
        return "silencio"
    pico = max(tramo)
    if pico > piso + SOBRE_PISO_VOZ:
        return "voz"
    if pico > piso + SOBRE_PISO:
        return "respiración"
    return "silencio"
