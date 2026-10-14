#!/usr/bin/env python3
"""Lee el orden y el tema de cada toma a partir del nombre del archivo.

Cuando el material llega ordenado, quien graba ya numera y titula: las tomas de A1S llegaron
como `1-Cómo Inicia la empresa A1S.mp4`, `2-En dónde se encuentran Ubicados.mp4`. Esa
información estaba ahí y se estaba ignorando.

**El nombre da el orden y el tema, no la redacción de la cenefa.** `4 Estrategia tecnologica`
no es una pregunta. La redacción sale del audio del entrevistador cuando la formula, o se
confirma con quien entrega. Esto quita la parte mecánica, no el criterio.
"""
import os
import re
import unicodedata

# Sufijos que pone el navegador o el sistema al descargar dos veces el mismo archivo.
_COPIA = re.compile(r"\s*(\(\d+\)|copia|copy)\s*$", re.IGNORECASE)
# Número de orden al principio: «1-algo», «2 - algo», «3. algo», «4 algo».
_ORDEN = re.compile(r"^\s*(\d{1,2})\s*[-–.)]?\s+?(.*)$|^\s*(\d{1,2})\s*[-–.)]\s*(.*)$")


def limpia_tema(texto):
    texto = _COPIA.sub("", texto).strip(" -–_.")
    texto = re.sub(r"\s+", " ", texto)
    if not texto:
        return ""
    # Se respeta cómo lo escribió quien nombró el archivo y solo se asegura la inicial.
    # Normalizar a minúsculas parecía más pulcro y se comía los nombres propios: «Alianza
    # con Camacol» quedaba «Alianza con camacol».
    return texto[0].upper() + texto[1:]


def lee(nombre):
    """(orden, tema) de un nombre de archivo. `orden` es None si no lleva número."""
    base = os.path.splitext(os.path.basename(nombre))[0]
    m = _ORDEN.match(base)
    if not m:
        return None, limpia_tema(base)
    orden = m.group(1) or m.group(3)
    resto = m.group(2) if m.group(1) else m.group(4)
    return int(orden), limpia_tema(resto or "")


def ordena(rutas):
    """Tomas ordenadas por su número, con las que no lo llevan al final.

    Las que no llevan número no son bloques de pregunta: en A1S, el archivo
    `PRESENTACIÓN NADYA IBARRA.mp4` era la vocera presentándose, material aparte de las
    respuestas. Se devuelven igual, pero marcadas, para que quien decida el corte las vea.
    """
    leidas = [(lee(r), r) for r in rutas]
    con = sorted(((o, t, r) for (o, t), r in leidas if o is not None), key=lambda x: x[0])
    sin = [(None, t, r) for (o, t), r in leidas if o is None]
    return con + sin


def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


def parece_cierre(tema):
    """¿Este bloque es el de redes sociales? Es el único que la serie trata distinto."""
    t = sin_acentos(tema or "").lower()
    return any(x in t for x in ("redes", "social", "instagram", "facebook", "contacto",
                                "encontrar", "internet"))
