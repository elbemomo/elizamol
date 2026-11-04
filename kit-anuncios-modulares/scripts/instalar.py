"""Revisa el computador y, con --arreglar, instala lo que falte dentro del kit.

    python3 scripts/instalar.py                    # solo revisa
    python3 scripts/instalar.py --arreglar         # instala lo que falte
    python3 scripts/instalar.py --arreglar --modelo base

Todo queda dentro de la carpeta del kit (.venv, .modelos, fuentes): para
desinstalar basta con borrar la carpeta.
"""
import argparse
import os
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import ANUNCIOS, FUENTES, GRABACIONES, MODELOS, NEGOCIO, PIEZAS, RAIZ  # noqa: E402

VENV = RAIZ / ".venv"
PY_VENV = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MODELOS_VALIDOS = ["tiny", "base", "small", "medium"]
URL_FUENTES = "https://github.com/google/fonts/raw/main/ofl"
FUENTES_KIT = {
    "Anton-Regular.ttf": f"{URL_FUENTES}/anton/Anton-Regular.ttf",
    "Anton-OFL.txt": f"{URL_FUENTES}/anton/OFL.txt",
    "ArchivoBlack-Regular.ttf": f"{URL_FUENTES}/archivoblack/ArchivoBlack-Regular.ttf",
    "ArchivoBlack-OFL.txt": f"{URL_FUENTES}/archivoblack/OFL.txt",
}

resultados = []


def anotar(nombre, ok, detalle=""):
    resultados.append(ok)
    marca = "OK   " if ok else "FALTA"
    print(f"[{marca}] {nombre}" + (f" · {detalle}" if detalle else ""), flush=True)


def correr(cmd):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def revisar_python():
    v = sys.version_info
    ok = (3, 9) <= (v.major, v.minor) <= (3, 13)
    detalle = f"Python {v.major}.{v.minor}"
    if not ok:
        detalle += (" no sirve para la transcripción. Instala Python 3.12 "
                    "(Windows: winget install Python.Python.3.12; Mac: python.org) "
                    "y vuelve a correr este script con esa versión.")
    anotar("Python", ok, detalle)
    return ok


def revisar_venv(arreglar):
    if not PY_VENV.exists() and arreglar:
        print("Creando el entorno del kit (.venv)...", flush=True)
        venv.create(VENV, with_pip=True)
    anotar("Entorno del kit (.venv)", PY_VENV.exists())
    return PY_VENV.exists()


def revisar_paquetes(arreglar):
    prueba = [PY_VENV, "-c", "import faster_whisper, PIL, imageio_ffmpeg"]
    if correr(prueba).returncode != 0 and arreglar:
        print("Instalando faster-whisper, Pillow y ffmpeg (unos minutos)...", flush=True)
        correr([PY_VENV, "-m", "pip", "install", "--upgrade", "pip"])
        res = correr([PY_VENV, "-m", "pip", "install", "-r", RAIZ / "requirements.txt"])
        if res.returncode != 0:
            print(res.stderr[-1500:], flush=True)
    ok = correr(prueba).returncode == 0
    anotar("Paquetes (faster-whisper, Pillow, ffmpeg)", ok)
    return ok


def revisar_ffmpeg():
    res = correr([PY_VENV, "-c",
                  "import sys; sys.path.insert(0, r'%s'); from comun import ffmpeg; print(ffmpeg())"
                  % (RAIZ / "scripts")])
    ruta = res.stdout.strip()
    ok = res.returncode == 0 and bool(ruta) and Path(ruta).exists()
    anotar("ffmpeg", ok, ruta if ok else "corre con --arreglar")
    return ok


def revisar_modelo(nombre, arreglar):
    carpeta = MODELOS / f"models--Systran--faster-whisper-{nombre}"
    if not carpeta.exists() and arreglar:
        print(f"Descargando el modelo de transcripción '{nombre}' (una sola vez)...", flush=True)
        res = correr([PY_VENV, "-c",
                      "from faster_whisper import download_model; "
                      f"download_model('{nombre}', cache_dir=r'{MODELOS}')"])
        if res.returncode != 0:
            print(res.stderr[-1500:], flush=True)
    ok = any(carpeta.glob("snapshots/*/model.bin"))
    if ok:
        MODELOS.mkdir(exist_ok=True)
        (MODELOS / "elegido.txt").write_text(nombre, encoding="utf-8")
    anotar(f"Modelo de transcripción ({nombre})", ok)
    return ok


def revisar_fuentes(arreglar):
    FUENTES.mkdir(exist_ok=True)
    for archivo, url in FUENTES_KIT.items():
        destino = FUENTES / archivo
        if not destino.exists() and arreglar:
            try:
                urllib.request.urlretrieve(url, destino)
            except Exception as e:
                print(f"  no pude bajar {archivo}: {e}", flush=True)
    faltan = [a for a in FUENTES_KIT if not (FUENTES / a).exists()]
    # Sin las fuentes igual funciona: se usa una del sistema.
    anotar("Fuentes de los subtítulos", True,
           "listas" if not faltan else "se usará una fuente del sistema")


def revisar_carpetas():
    for carpeta in (NEGOCIO, NEGOCIO / "musica", GRABACIONES, PIEZAS, ANUNCIOS):
        carpeta.mkdir(parents=True, exist_ok=True)
    anotar("Carpetas del kit", True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arreglar", action="store_true", help="instala lo que falte")
    ap.add_argument("--modelo", default="small", choices=MODELOS_VALIDOS,
                    help="modelo de transcripción (small por defecto; base es más rápido)")
    args = ap.parse_args()

    print(f"Kit de Anuncios Modulares · revisando {RAIZ}\n", flush=True)
    if revisar_python() and revisar_venv(args.arreglar) and revisar_paquetes(args.arreglar):
        revisar_ffmpeg()
        revisar_modelo(args.modelo, args.arreglar)
    revisar_fuentes(args.arreglar)
    revisar_carpetas()

    if all(resultados):
        print("\nLISTO. El kit está preparado.")
    else:
        print("\nFALTA algo. " + ("Lee el detalle de arriba." if args.arreglar
                                  else "Corre de nuevo con --arreglar."))
        sys.exit(1)


if __name__ == "__main__":
    main()
