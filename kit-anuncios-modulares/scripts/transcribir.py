"""Transcribe las grabaciones de 1_grabaciones/ en el computador, sin internet.

    python3 scripts/transcribir.py
    python3 scripts/transcribir.py --modelo base     # más rápido
    python3 scripts/transcribir.py --rehacer         # vuelve a transcribir todo

Guarda las palabras con sus tiempos en 2_piezas/transcripcion.json.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (GRABACIONES, MODELOS, NEGOCIO, PIEZAS, avisar, fallar, ffmpeg,  # noqa: E402
                   guardar_json, info_medio, leer_json, videos_en)

DESTINO = PIEZAS / "transcripcion.json"


def modelo_por_defecto():
    elegido = MODELOS / "elegido.txt"
    return elegido.read_text(encoding="utf-8").strip() if elegido.exists() else "small"


def pista_del_guion():
    """Unas frases del guion ayudan a que escriba bien nombres y marcas."""
    ruta = NEGOCIO / "guion.json"
    if not ruta.exists():
        return None
    guion = leer_json(ruta)
    textos = [p["texto"] for clave in ("ganchos", "cuerpos", "ctas") for p in guion.get(clave, [])]
    return " ".join(textos)[:600] or None


def audio_16k(video):
    """Saca el audio con ffmpeg (mono, 16 kHz), sin depender de la versión de PyAV."""
    import numpy as np
    res = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(video), "-vn",
                          "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True)
    if res.returncode != 0:
        fallar(f"no pude leer el audio de {video.name}.")
    return np.frombuffer(res.stdout, dtype=np.float32)


def huella(ruta):
    estado = ruta.stat()
    return f"{estado.st_size}-{int(estado.st_mtime)}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelo", default=modelo_por_defecto())
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--rehacer", action="store_true")
    args = ap.parse_args()

    videos = videos_en(GRABACIONES)
    if not videos:
        fallar("no hay videos en 1_grabaciones/.")

    previo = leer_json(DESTINO) if DESTINO.exists() and not args.rehacer else {"clips": []}
    hechos = {(c["archivo"], c["huella"], c.get("modelo")): c for c in previo["clips"]}

    from faster_whisper import WhisperModel
    modelo = None
    clips = []
    for video in videos:
        clave = (video.name, huella(video), args.modelo)
        if clave in hechos:
            avisar(f"· {video.name}: ya estaba transcrito")
            clips.append(hechos[clave])
            continue
        if modelo is None:
            avisar(f"Cargando el modelo '{args.modelo}'...")
            modelo = WhisperModel(args.modelo, device="cpu", compute_type="int8",
                                  download_root=str(MODELOS))
        info = info_medio(video)
        avisar(f"· {video.name}: transcribiendo {info['duracion']:.0f} s de video...")
        inicio = time.time()
        segmentos, _ = modelo.transcribe(
            audio_16k(video), language=args.idioma, word_timestamps=True,
            condition_on_previous_text=False, initial_prompt=pista_del_guion(),
            vad_filter=True, vad_parameters={"min_silence_duration_ms": 500})
        palabras = []
        for seg in segmentos:
            for w in seg.words or []:
                palabras.append({"p": w.word.strip(), "i": round(w.start, 3), "f": round(w.end, 3)})
            avisar(f"    {seg.end:6.1f} s  {seg.text.strip()[:70]}")
        clips.append({"archivo": video.name, "huella": clave[1], "modelo": args.modelo,
                      "duracion": info["duracion"], "palabras": palabras})
        avisar(f"  listo en {time.time() - inicio:.0f} s ({len(palabras)} palabras)")

    guardar_json(DESTINO, {"clips": clips})
    avisar(f"\nTranscripción guardada en {DESTINO}")


if __name__ == "__main__":
    main()
