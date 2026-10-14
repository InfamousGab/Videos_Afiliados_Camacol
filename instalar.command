#!/bin/bash
# Instalador de primera vez. Doble clic; no hace falta abrir Terminal ni contraseña.
#
# Deja TODO lo que la skill necesita dentro de esta carpeta, en .entorno/, con las versiones
# exactas con que se validó: un Python, las librerías, ffmpeg y el modelo de whisper. Así el
# resultado no depende de lo que tenga instalado este Mac ni de qué versión haya salido esa
# semana, y la carpeta se puede mover o renombrar después sin romper nada.
#
# Se puede volver a correr cuantas veces haga falta: lo que ya está, lo salta.
cd "$(dirname "$0")" || exit 1
RAIZ="$(pwd)"
SKILL="$RAIZ/.agents/skills/afiliados-historias-exito"
E="$RAIZ/.entorno"
set -o pipefail

# Versiones fijas. Cambiarlas exige volver a validar un capítulo completo.
UV_VERSION="0.11.15"
UV_SHA="7e5b336108f8576eda1939920ca0a805b4a9a3c3d3eb2f6140e38b7092fbe4f3"
PY_VERSION="3.11.15"
FFMPEG_URL="https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2/ffmpeg.zip"
FFMPEG_SHA="c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924"
MODELO="mlx-community/whisper-large-v3-turbo"
REVISION="a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"

# Al llegar por AirDrop, USB o zip, macOS marca el paquete como «en cuarentena» y bloquea lo
# que se abra con doble clic. Este archivo ya consiguió ejecutarse, así que lo primero es
# quitarle la marca al resto.
xattr -dr com.apple.quarantine . 2>/dev/null
chmod +x "$0" 2>/dev/null

# Nada de esto debe escribir fuera de la carpeta.
export UV_CACHE_DIR="$E/cache-uv"
export UV_PYTHON_INSTALL_DIR="$E/python-base"
export UV_NO_CONFIG=1
export HF_HOME="$E/cache-hf"

paso() { echo; echo "  • $1"; }
bien() { echo "    ok  $1"; }
mal()  { echo "    NO: $1"; falta=1; }
cierra() {
  echo
  read -n 1 -s -r -p "  Pulsa cualquier tecla para cerrar." 2>/dev/null </dev/tty
  echo
  exit "$1"
}
falta=0

echo
echo "  ══════════════════════════════════════════════════════════════"
echo "   Preparando este Mac para montar videos de Camacol"
echo "  ══════════════════════════════════════════════════════════════"
echo
echo "  Se hace una sola vez. Necesita internet y baja unos 3 GB:"
echo "  puede tardar de 10 a 30 minutos según la conexión."

# ---------------------------------------------------------------- chip
if [ "$(uname -m)" != "arm64" ]; then
  echo
  echo "  Este Mac es Intel. La transcripción de la skill necesita chip Apple"
  echo "  (M1 o posterior), así que aquí no puede funcionar."
  cierra 1
fi

mkdir -p "$E/bin" "$E/descargas"

# ---------------------------------------------------------------- uv
paso "Gestor de librerías (uv $UV_VERSION)"
if [ -x "$E/bin/uv" ] && "$E/bin/uv" --version 2>/dev/null | grep -q "$UV_VERSION"; then
  bien "ya está"
else
  f="$E/descargas/uv.tar.gz"
  if curl -sSfL -o "$f" \
       "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-aarch64-apple-darwin.tar.gz" \
     && echo "$UV_SHA  $f" | shasum -a 256 -c - >/dev/null 2>&1; then
    tar xzf "$f" -C "$E/descargas" && cp "$E/descargas/uv-aarch64-apple-darwin/uv" "$E/bin/uv" \
      && chmod +x "$E/bin/uv" && bien "instalado" || mal "no pude descomprimirlo"
  else
    mal "no pude descargarlo, o llegó dañado. Revisa la conexión y vuelve a intentarlo."
  fi
fi
[ "$falta" = 0 ] || cierra 1
UV="$E/bin/uv"

# ---------------------------------------------------------------- python
paso "Python $PY_VERSION"
PY="$(ls -d "$E"/python-base/cpython-"$PY_VERSION"-*/bin/python3.11 2>/dev/null | head -1)"
if [ -x "$PY" ]; then
  bien "ya está"
else
  "$UV" python install --no-bin "$PY_VERSION" >/dev/null 2>&1
  PY="$(ls -d "$E"/python-base/cpython-"$PY_VERSION"-*/bin/python3.11 2>/dev/null | head -1)"
  [ -x "$PY" ] && bien "instalado" || mal "no pude instalarlo. Revisa la conexión."
fi
[ "$falta" = 0 ] || cierra 1

# El Python del paquete se arranca siempre por aquí: busca todo relativo a su propia carpeta,
# así que sigue funcionando aunque se mueva o se renombre el paquete.
cat > "$E/bin/python" <<EOF
#!/bin/sh
E="\$(cd "\$(dirname "\$0")/.." && pwd)"
PY="\$(ls -d "\$E"/python-base/cpython-$PY_VERSION-*/bin/python3.11 2>/dev/null | head -1)"
if [ ! -x "\$PY" ]; then
  echo "Falta el Python del paquete: haz doble clic en instalar.command." >&2
  exit 1
fi
PYTHONPATH="\$E/paquetes" PYTHONNOUSERSITE=1 exec "\$PY" "\$@"
EOF
chmod +x "$E/bin/python"

# ---------------------------------------------------------------- librerías
paso "Librerías (whisper, numpy, Pillow), versiones fijas"
if "$E/bin/python" -c "import mlx_whisper, numpy, PIL" >/dev/null 2>&1 \
   && [ "$(cat "$E/paquetes/.requisitos" 2>/dev/null)" = "$(shasum "$SKILL/requisitos.txt" | cut -c1-40)" ]; then
  bien "ya están"
else
  echo "    descargando, es lo más pesado…"
  rm -rf "$E/paquetes"
  if "$UV" pip install --quiet --python "$PY" --target "$E/paquetes" \
       -r "$SKILL/requisitos.txt" 2>"$E/descargas/pip.log"; then
    shasum "$SKILL/requisitos.txt" | cut -c1-40 > "$E/paquetes/.requisitos"
    bien "instaladas"
  else
    tail -5 "$E/descargas/pip.log" | sed 's/^/    /'
    mal "no pude instalarlas. Revisa la conexión y vuelve a intentarlo."
  fi
fi
[ "$falta" = 0 ] || cierra 1

# ---------------------------------------------------------------- ffmpeg
paso "ffmpeg 9.0.2 (el motor de video)"
if [ -x "$E/bin/ffmpeg" ] && "$E/bin/ffmpeg" -version 2>/dev/null | grep -q "9.0.2"; then
  bien "ya está"
else
  f="$E/descargas/ffmpeg.zip"
  if curl -sSfL -o "$f" "$FFMPEG_URL" \
     && echo "$FFMPEG_SHA  $f" | shasum -a 256 -c - >/dev/null 2>&1; then
    unzip -o -q "$f" -d "$E/bin" && chmod +x "$E/bin/ffmpeg" \
      && "$E/bin/ffmpeg" -version >/dev/null 2>&1 && bien "instalado" || mal "no arranca"
  else
    mal "no pude descargarlo, o llegó dañado. Revisa la conexión."
  fi
fi
[ "$falta" = 0 ] || cierra 1

# ---------------------------------------------------------------- modelo
paso "Modelo de transcripción (1.5 GB, la parte más lenta)"
M="$E/modelos/whisper-large-v3-turbo"
if [ -f "$M/weights.safetensors" ] && [ "$(cat "$M/.revision" 2>/dev/null)" = "$REVISION" ]; then
  bien "ya está"
else
  if "$E/bin/python" -c "
from huggingface_hub import snapshot_download
snapshot_download('$MODELO', revision='$REVISION', local_dir='$M')
" >"$E/descargas/modelo.log" 2>&1 && [ -f "$M/weights.safetensors" ]; then
    echo "$REVISION" > "$M/.revision"
    bien "descargado"
  else
    tail -3 "$E/descargas/modelo.log" | sed 's/^/    /'
    mal "no pude descargarlo. Revisa la conexión y vuelve a intentarlo."
  fi
fi
[ "$falta" = 0 ] || cierra 1

# Lo descargado ya está instalado; las cachés solo ocupan espacio.
rm -rf "$E/descargas" "$E/cache-uv" "$E/cache-hf" "$M/.cache"

# ---------------------------------------------------------------- comprobación
echo
echo "  Comprobando que todo esté en su sitio…"
echo
if "$E/bin/python" "$SKILL/scripts/comprobar_entorno.py"; then
  echo
  echo "  ══════════════════════════════════════════════════════════════"
  echo "   Listo. Ya puedes preparar un capítulo:"
  echo "   duplica «_PLANTILLA CAPITULO» y sigue el LÉEME de dentro."
  echo "  ══════════════════════════════════════════════════════════════"
  cierra 0
else
  echo
  echo "  Algo no quedó bien. Mira arriba lo que dice FALTA."
  cierra 1
fi
