"""Piezas compartidas por todos los scripts del Kit de Anuncios Modulares.

Solo usa la biblioteca estándar de Python, así instalar.py puede importarlo
antes de que exista el entorno virtual.
"""
import functools
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NEGOCIO = RAIZ / "negocio"
GRABACIONES = RAIZ / "1_grabaciones"
PIEZAS = RAIZ / "2_piezas"
ANUNCIOS = RAIZ / "3_anuncios"
PLANTILLAS = RAIZ / "plantillas"
FUENTES = RAIZ / "fuentes"
MODELOS = RAIZ / ".modelos"

EXT_VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".3gp"}
EXT_AUDIO = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}

FPS = 30
FORMATOS = {"9x16": (1080, 1920), "4x5": (1080, 1350)}
ORDEN_ROLES = ["problema", "mecanismo", "prueba", "oferta"]


def avisar(mensaje=""):
    print(mensaje, flush=True)


def fallar(mensaje):
    print(f"\nNO SE PUDO: {mensaje}", file=sys.stderr, flush=True)
    sys.exit(1)


def leer_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar_json(ruta, datos):
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def leer_guion():
    ruta = NEGOCIO / "guion.json"
    if not ruta.exists():
        fallar("todavía no hay guion en negocio/guion.json.")
    guion = leer_json(ruta)
    for clave in ("ganchos", "cuerpos", "ctas"):
        guion.setdefault(clave, [])
    return guion


def piezas_del_guion(guion):
    """Devuelve todas las piezas en orden de grabación, con su tipo."""
    salida = []
    for tipo, clave in (("gancho", "ganchos"), ("cuerpo", "cuerpos"), ("cta", "ctas")):
        for pieza in guion[clave]:
            salida.append({**pieza, "tipo": tipo})
    return salida


# ---------- texto ----------

def sin_tildes(texto):
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def tokens(texto):
    """Palabras comparables: minúsculas, sin tildes ni signos, cifras pegadas."""
    texto = sin_tildes(texto.lower())
    texto = re.sub(r"(?<=\d)[.,](?=\d)", "", texto)
    return re.findall(r"[a-z0-9]+", texto)


def slug(texto, largo=28):
    limpio = re.sub(r"[^A-Za-z0-9]+", "-", sin_tildes(texto)).strip("-").upper()
    return limpio[:largo].strip("-") or "SIN-ANGULO"


# ---------- ffmpeg ----------

@functools.lru_cache(maxsize=None)
def ffmpeg():
    encontrado = shutil.which("ffmpeg")
    if encontrado:
        return encontrado
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        fallar("no encuentro ffmpeg. Corre scripts/instalar.py --arreglar.")


def correr_ffmpeg(argumentos):
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *map(str, argumentos)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        cola = "\n".join(res.stderr.strip().splitlines()[-12:])
        raise RuntimeError(f"ffmpeg falló:\n{cola}")
    return res


@functools.lru_cache(maxsize=None)
def tiene_filtro(nombre):
    res = subprocess.run([ffmpeg(), "-hide_banner", "-filters"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return re.search(rf"^\s*\S+\s+{re.escape(nombre)}\s", res.stdout, re.M) is not None


def info_medio(ruta):
    """Duración, tamaño visible, audio y HDR, leyendo lo que ffmpeg imprime."""
    res = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(ruta)], capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    texto = res.stderr
    info = {"duracion": 0.0, "ancho": 0, "alto": 0, "audio": False, "hdr": False}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", texto)
    if m:
        h, mi, s = m.groups()
        info["duracion"] = int(h) * 3600 + int(mi) * 60 + float(s)
    linea_video = next((l for l in texto.splitlines() if "Video:" in l), "")
    m = re.search(r"[ ,](\d{2,5})x(\d{2,5})[ ,\[]", linea_video + " ")
    if m:
        info["ancho"], info["alto"] = int(m.group(1)), int(m.group(2))
    giro = re.search(r"rotation of (-?\d+(?:\.\d+)?)", texto)
    if giro and abs(round(float(giro.group(1)))) % 180 == 90:
        info["ancho"], info["alto"] = info["alto"], info["ancho"]
    info["audio"] = "Audio:" in texto
    info["hdr"] = any(marca in linea_video for marca in ("arib-std-b67", "smpte2084"))
    return info


def videos_en(carpeta):
    return sorted(p for p in Path(carpeta).glob("*") if p.suffix.lower() in EXT_VIDEO)
