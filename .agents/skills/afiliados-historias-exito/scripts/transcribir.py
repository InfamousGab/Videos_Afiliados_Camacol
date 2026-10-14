#!/usr/bin/env python3
"""Inventario + transcripción con marcas de palabra de las tomas crudas.

Deja en `trabajo/transcripcion.txt` un guion legible: cada toma con sus palabras
cronometradas y las pausas señaladas. Ese archivo es lo que se lee para decidir el corte.

    python3 transcribir.py proyecto.json

Si una toma sale casi vacía (whisper a veces se rinde con audio flojo), se reintenta con el
audio normalizado antes de darla por perdida.
"""
import glob
import json
import os
import sys

import comun as C

PAUSA_MIN = 0.45          # a partir de aquí se considera pausa y se marca en el guion


def tomas(p):
    fs = sorted(glob.glob(os.path.join(p["_tomas"], "*.mp4")) +
                glob.glob(os.path.join(p["_tomas"], "*.mov")) +
                glob.glob(os.path.join(p["_tomas"], "*.MP4")))
    if not fs:
        sys.exit(f"No hay tomas en {p['_tomas']}")
    return fs


def extrae_audio(src, dst, normalizar=False):
    af = "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11" if normalizar else None
    cmd = [C.FF, "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000"]
    if af:
        cmd += ["-af", af]
    C.run(cmd + [dst])


def whisper(wav, salida_dir, nombre):
    C.run(C.whisper(wav, "--language", "es", "--output-format", "json",
                    "--output-dir", salida_dir, "--output-name", nombre,
                    "--word-timestamps", "True", "--condition-on-previous-text", "False",
                    "--temperature", "0"),
          f"transcribiendo {os.path.basename(wav)}", env=C.entorno_whisper())
    with open(os.path.join(salida_dir, nombre + ".json"), encoding="utf-8") as f:
        return json.load(f)


def palabras(d):
    return [w for s in d.get("segments", []) for w in s.get("words", [])]


def main():
    p = C.uso("transcribir.py")
    audio_dir = os.path.join(p["_trabajo"], "audio")
    os.makedirs(audio_dir, exist_ok=True)
    lineas = ["# Transcripción de las tomas crudas",
              "",
              "Los tiempos son segundos dentro de cada toma. `<<< pausa >>>` marca los huecos",
              "de silencio: son los puntos naturales de corte. Las palabras cortas que duran",
              "más de 0.6 s son alargamientos de vocal — cortar por dentro de ellas es inaudible.",
              ""]

    for i, src in enumerate(tomas(p), 1):
        nombre = os.path.basename(src)
        dur, w, h, fps, audio = C.info_media(src)
        cab = f"## Toma {i}: {nombre}"
        meta = f"    {dur:.2f} s · {w}x{h} · {fps} fps" + ("" if audio else " · SIN AUDIO")
        print(cab)
        lineas += ["", cab, "", meta, ""]
        if not audio:
            lineas.append("    (sin pista de audio, no se transcribe)")
            continue

        wav = os.path.join(audio_dir, f"toma{i}.wav")
        extrae_audio(src, wav)
        d = whisper(wav, audio_dir, f"toma{i}")
        ws = palabras(d)

        # Si cubre menos de la mitad de la toma, whisper probablemente se rindió: reintenta
        # con el audio normalizado, que suele desatascarlo.
        cubierto = (ws[-1]["end"] - ws[0]["start"]) if ws else 0
        if dur and cubierto < dur * 0.5:
            print(f"    poca cobertura ({cubierto:.1f}/{dur:.1f} s), reintentando normalizado")
            wav2 = os.path.join(audio_dir, f"toma{i}_norm.wav")
            extrae_audio(src, wav2, normalizar=True)
            d2 = whisper(wav2, audio_dir, f"toma{i}n")
            if len(palabras(d2)) > len(ws):
                ws = palabras(d2)
                lineas.append("    (transcrita sobre el audio normalizado)")
                # El JSON bueno tiene que quedar en tomaN.json: es el que leen los scripts
                # que colocan los cortes. Si solo se arregla el texto legible, el reintento
                # no sirve de nada aguas abajo y los cortes se colocan a ciegas sobre una
                # transcripción de seis palabras.
                with open(os.path.join(audio_dir, f"toma{i}.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(d2, f, ensure_ascii=False)

        prev, linea = 0.0, ""
        for wd in ws:
            if wd["start"] - prev >= PAUSA_MIN:
                if linea:
                    lineas.append("    " + linea)
                lineas.append(f"    <<< pausa {wd['start'] - prev:.2f}s "
                              f"({prev:.2f} -> {wd['start']:.2f}) >>>")
                linea = ""
            largo = "*" if (wd["end"] - wd["start"]) > 0.6 and len(wd["word"].strip()) <= 5 else ""
            linea += f"{wd['word'].strip()}[{wd['start']:.2f}-{wd['end']:.2f}]{largo} "
            if len(linea) > 140:
                lineas.append("    " + linea)
                linea = ""
            prev = wd["end"]
        if linea:
            lineas.append("    " + linea)
        lineas.append("")
        lineas.append("    Texto corrido: " + " ".join(
            s["text"].strip() for s in d.get("segments", [])))

    lineas += ["", "---", "",
               "`*` marca palabras cortas sostenidas más de 0.6 s (alargamientos de vocal)."]
    dst = os.path.join(p["_trabajo"], "transcripcion.txt")
    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    print(f"\nGuion escrito en {dst}")


if __name__ == "__main__":
    main()
