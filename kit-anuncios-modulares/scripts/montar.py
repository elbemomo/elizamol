"""Arma los anuncios terminados en 3_anuncios/, con título, subtítulos y música.

    python3 scripts/montar.py --solo 3 --formatos 9x16   # 3 de prueba
    python3 scripts/montar.py                            # todos, en 9:16 y 4:5

Estilo (usa el mismo en la prueba y en el armado final):
    --mayusculas            subtítulos en mayúsculas
    --subtitulos frase      la frase entera sin pintar palabra por palabra (o: no)
    --color "#FFD400"       color de la palabra que se está diciendo
    --recorte-y 0.3         recorte más arriba (0) o más abajo (1) en 4:5
    --fuente archivo.ttf    otra fuente para título y subtítulos
    --sin-titulo            sin el título fijo de arriba
Música (la primera canción de negocio/musica/ si hay):
    --musica cancion.mp3    --volumen-musica 0.12    --sin-musica
Otros:
    --union 0.17            pausa entre pieza y pieza, en segundos
    --rehacer               vuelve a armar aunque ya existan
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (ANUNCIOS, EXT_AUDIO, FORMATOS, FPS, FUENTES, NEGOCIO, PIEZAS, avisar,  # noqa: E402
                   correr_ffmpeg, fallar, guardar_json, leer_json, slug)

REGISTRO = ANUNCIOS / "registro.json"
FUENTES_SISTEMA = [
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
# Dónde va cada cosa, como fracción del alto del video.
POSICION = {"9x16": {"titulo": 0.12, "subtitulos": 0.66}, "4x5": {"titulo": 0.06, "subtitulos": 0.74}}


# ---------- dibujo con Pillow ----------

def cargar_fuente(preferida, propia, tam):
    from PIL import ImageFont
    for ruta in [propia, FUENTES / preferida, *FUENTES_SISTEMA]:
        if ruta and Path(ruta).exists():
            return ImageFont.truetype(str(ruta), tam)
    return ImageFont.load_default(tam)


def partir_en_lineas(palabras, fuente, ancho_max, dibujo, espacio):
    lineas, actual, largo = [], [], 0.0
    for p in palabras:
        w = dibujo.textlength(p, font=fuente)
        if actual and largo + espacio + w > ancho_max:
            lineas.append(actual)
            actual, largo = [], 0.0
        largo += (espacio if actual else 0) + w
        actual.append(p)
    if actual:
        lineas.append(actual)
    return lineas


def dibujar_titulo(texto, ancho, alto, formato, fuente_propia, destino):
    from PIL import Image, ImageDraw
    lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(lienzo)
    tam = int(ancho * 0.08)
    while True:
        fuente = cargar_fuente("Anton-Regular.ttf", fuente_propia, tam)
        espacio = dibujo.textlength(" ", font=fuente)
        lineas = partir_en_lineas(texto.upper().split(), fuente, ancho * 0.82, dibujo, espacio)
        if len(lineas) <= 2 or tam < 30:
            break
        tam = int(tam * 0.9)
    if len(lineas) == 2:  # reparte parejo para no dejar una palabra sola abajo
        palabras = lineas[0] + lineas[1]
        lineas = min(([palabras[:k], palabras[k:]] for k in range(1, len(palabras))),
                     key=lambda par: max(dibujo.textlength(" ".join(l), font=fuente) for l in par))
    textos = [" ".join(l) for l in lineas]
    alto_linea = int(tam * 1.18)
    ancho_caja = max(dibujo.textlength(t, font=fuente) for t in textos) + ancho * 0.08
    alto_caja = alto_linea * len(textos) + tam * 0.45
    x0 = (ancho - ancho_caja) / 2
    y0 = alto * POSICION[formato]["titulo"]
    dibujo.rounded_rectangle([x0, y0, x0 + ancho_caja, y0 + alto_caja], radius=int(ancho * 0.03),
                             fill=(255, 255, 255, 240))
    y = y0 + tam * 0.2
    for t in textos:
        dibujo.text((ancho / 2, y), t, font=fuente, fill=(17, 17, 17, 255), anchor="ma")
        y += alto_linea
    lienzo.save(destino)


def dibujar_subtitulo(palabras, activa, color, ancho, alto, formato, fuente_propia, destino):
    from PIL import Image, ImageDraw
    lienzo = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(lienzo)
    tam = int(ancho * 0.072)
    fuente = cargar_fuente("ArchivoBlack-Regular.ttf", fuente_propia, tam)
    borde = max(4, int(tam * 0.1))
    espacio = dibujo.textlength(" ", font=fuente)
    lineas = partir_en_lineas(palabras, fuente, ancho * 0.86, dibujo, espacio)
    alto_linea = int(tam * 1.25)
    y = alto * POSICION[formato]["subtitulos"] - alto_linea * len(lineas) / 2
    n = 0
    for linea in lineas:
        largo = sum(dibujo.textlength(p, font=fuente) for p in linea) + espacio * (len(linea) - 1)
        x = (ancho - largo) / 2
        for p in linea:
            relleno = color if n == activa else (255, 255, 255, 255)
            dibujo.text((x, y), p, font=fuente, fill=relleno, stroke_width=borde,
                        stroke_fill=(0, 0, 0, 255))
            x += dibujo.textlength(p, font=fuente) + espacio
            n += 1
        y += alto_linea
    lienzo.save(destino)


def color_rgba(hexa):
    hexa = hexa.lstrip("#")
    if len(hexa) != 6:
        fallar(f"el color '{hexa}' no es válido. Usa algo como \"#FFD400\".")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


# ---------- subtítulos en el tiempo ----------

def frases_de_pieza(palabras):
    """Agrupa las palabras de una pieza en frases cortas de hasta 3 palabras."""
    frases, actual = [], []
    for p in palabras:
        actual.append(p)
        corta_aqui = p["t"][-1] in ".,;:?!" or len(actual) == 3 or sum(len(x["t"]) for x in actual) > 16
        if corta_aqui:
            frases.append(actual)
            actual = []
    if actual:
        frases.append(actual)
    return frases


def linea_de_tiempo_subtitulos(combo_ids, piezas, union, modo, mayusculas):
    """Lista de (inicio, fin, palabras, palabra_activa) para todo el anuncio."""
    eventos, desfase = [], 0.0
    for pid in combo_ids:
        frases = frases_de_pieza(piezas[pid]["palabras"])
        for n, frase in enumerate(frases):
            textos = [(p["t"].upper() if mayusculas else p["t"]) for p in frase]
            ini = desfase + frase[0]["i"]
            fin = desfase + frase[-1]["f"]
            if n + 1 < len(frases):
                siguiente = desfase + frases[n + 1][0]["i"]
                fin = siguiente if siguiente - fin < 0.4 else fin + 0.15
            else:
                fin = min(fin + 0.15, desfase + piezas[pid]["duracion"])
            if modo == "frase":
                eventos.append((ini, fin, textos, None))
                continue
            for k, p in enumerate(frase):
                desde = ini if k == 0 else desfase + p["i"]
                hasta = desfase + frase[k + 1]["i"] if k + 1 < len(frase) else fin
                eventos.append((desde, max(hasta, desde + 1 / FPS), textos, k))
        desfase += piezas[pid]["duracion"] + union
    return eventos


def preparar_subtitulos(eventos, color, ancho, alto, formato, fuente_propia, carpeta):
    """Dibuja cada estado del subtítulo y escribe la lista que ffmpeg lee en orden."""
    from PIL import Image
    vacio = carpeta / "vacio.png"
    Image.new("RGBA", (ancho, alto), (0, 0, 0, 0)).save(vacio)
    entradas, cuadro = [], 0
    for n, (ini, fin, palabras, activa) in enumerate(eventos):
        c_ini, c_fin = round(ini * FPS), round(fin * FPS)
        c_ini = max(c_ini, cuadro)
        if c_fin <= c_ini:
            continue
        if c_ini > cuadro:
            entradas.append((vacio, c_ini - cuadro))
        imagen = carpeta / f"s{n:04d}.png"
        dibujar_subtitulo(palabras, activa, color, ancho, alto, formato, fuente_propia, imagen)
        entradas.append((imagen, c_fin - c_ini))
        cuadro = c_fin
    entradas.append((vacio, FPS))
    lista = carpeta / "subtitulos.txt"
    with open(lista, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for imagen, cuadros in entradas:
            f.write(f"file '{imagen.as_posix()}'\nduration {cuadros / FPS:.6f}\n")
        f.write(f"file '{vacio.as_posix()}'\n")
    return lista


# ---------- armado con ffmpeg ----------

def recorte(pw, ph, ancho, alto, recorte_y):
    proporcion = ancho / alto
    if pw / ph > proporcion:
        cw, ch = int(ph * proporcion) // 2 * 2, ph
        return cw, ch, (pw - cw) // 2, 0
    cw, ch = pw, int(pw / proporcion) // 2 * 2
    return cw, ch, 0, int((ph - ch) * recorte_y)


def armar(combo_ids, piezas, formato, opciones, musica, titulo, destino, carpeta):
    ancho, alto = FORMATOS[formato]
    n = len(combo_ids)
    total = sum(piezas[p]["duracion"] for p in combo_ids) + opciones.union * (n - 1)
    entradas, partes = [], []
    for i, pid in enumerate(combo_ids):
        d = piezas[pid]
        largo = d["duracion"] + (opciones.union if i < n - 1 else 0)
        cw, ch, x, y = recorte(d["ancho"], d["alto"], ancho, alto, opciones.recorte_y)
        entradas += ["-i", PIEZAS / d["archivo"]]
        partes.append(f"[{i}:v]crop={cw}:{ch}:{x}:{y},scale={ancho}:{alto},setsar=1,fps={FPS},"
                      f"tpad=stop_mode=clone:stop_duration={opciones.union},"
                      f"trim=end={largo:.3f},setpts=PTS-STARTPTS[v{i}]")
        partes.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"apad=whole_dur={largo:.3f},atrim=end={largo:.3f},asetpts=PTS-STARTPTS[a{i}]")
    partes.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
    video = "vc"
    siguiente = n

    if titulo:
        imagen = carpeta / "titulo.png"
        dibujar_titulo(titulo, ancho, alto, formato, opciones.fuente, imagen)
        entradas += ["-loop", "1", "-framerate", FPS, "-t", f"{total:.3f}", "-i", imagen]
        partes.append(f"[{video}][{siguiente}:v]overlay=0:0[vt]")
        video, siguiente = "vt", siguiente + 1

    if opciones.subtitulos != "no":
        eventos = linea_de_tiempo_subtitulos(combo_ids, piezas, opciones.union, opciones.subtitulos,
                                             opciones.mayusculas)
        lista = preparar_subtitulos(eventos, color_rgba(opciones.color), ancho, alto, formato,
                                    opciones.fuente, carpeta)
        entradas += ["-f", "concat", "-safe", "0", "-i", lista]
        partes.append(f"[{siguiente}:v]format=rgba[sub];[{video}][sub]overlay=0:0:eof_action=pass[vs]")
        video, siguiente = "vs", siguiente + 1
    partes.append(f"[{video}]format=yuv420p[vout]")

    partes.append("[ac]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[voz]")
    audio = "voz"
    if musica:
        entradas += ["-stream_loop", "-1", "-i", musica]
        salida_musica = max(total - 1.5, 0)
        partes.append(f"[{siguiente}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"atrim=end={total:.3f},asetpts=PTS-STARTPTS,volume={opciones.volumen_musica},"
                      f"afade=t=in:d=0.8,afade=t=out:st={salida_musica:.3f}:d=1.5[mus]")
        partes.append("[voz][mus]amix=inputs=2:duration=first:normalize=0[mezcla]")
        audio = "mezcla"

    correr_ffmpeg([*entradas, "-filter_complex", ";".join(partes), "-map", "[vout]", "-map", f"[{audio}]",
                   "-t", f"{total:.3f}", "-r", FPS, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                   "-movflags", "+faststart", destino])
    return total


# ---------- principal ----------

def buscar_musica(opciones):
    if opciones.sin_musica:
        return None
    if opciones.musica:
        ruta = Path(opciones.musica)
        if not ruta.exists():
            fallar(f"no encuentro la canción {ruta}.")
        return ruta
    canciones = sorted(p for p in (NEGOCIO / "musica").glob("*") if p.suffix.lower() in EXT_AUDIO)
    return canciones[0] if canciones else None


def huella(combo_ids, piezas, formato, opciones, musica, titulo):
    datos = {"piezas": [(p, (PIEZAS / piezas[p]["archivo"]).stat().st_mtime) for p in combo_ids],
             "formato": formato, "titulo": titulo, "musica": str(musica),
             "estilo": {k: getattr(opciones, k) for k in
                        ("mayusculas", "subtitulos", "color", "recorte_y", "fuente", "union",
                         "volumen_musica", "sin_titulo")}}
    return hashlib.sha1(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()[:12]


def escribir_indice(registro):
    filas = sorted(registro.values(), key=lambda r: r["archivo"])
    with open(ANUNCIOS / "INDICE.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["archivo", "formato", "angulo", "titulo", "gancho", "cuerpos", "cierre", "segundos"])
        for r in filas:
            if (ANUNCIOS / r["archivo"]).exists():
                w.writerow([r["archivo"], r["formato"], r["angulo"], r["titulo"], r["gancho"],
                            " + ".join(r["cuerpos"]), r["cta"], r["segundos"]])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo", type=int, help="arma solo las primeras N combinaciones")
    ap.add_argument("--formatos", default="9x16,4x5")
    ap.add_argument("--mayusculas", action="store_true")
    ap.add_argument("--subtitulos", default="palabra", choices=["palabra", "frase", "no"])
    ap.add_argument("--color", default="#FFD400")
    ap.add_argument("--recorte-y", type=float, default=0.4)
    ap.add_argument("--fuente")
    ap.add_argument("--sin-titulo", action="store_true")
    ap.add_argument("--musica")
    ap.add_argument("--volumen-musica", type=float, default=0.08)
    ap.add_argument("--sin-musica", action="store_true")
    ap.add_argument("--union", type=float, default=0.17)
    ap.add_argument("--rehacer", action="store_true")
    opciones = ap.parse_args()

    ruta_combos = NEGOCIO / "combinaciones.json"
    if not ruta_combos.exists():
        fallar("no hay combinaciones. Corre primero scripts/mezclar.py.")
    combos = leer_json(ruta_combos)[:opciones.solo] if opciones.solo else leer_json(ruta_combos)
    piezas = leer_json(PIEZAS / "piezas.json")
    formatos = [f.strip() for f in opciones.formatos.split(",") if f.strip()]
    for f in formatos:
        if f not in FORMATOS:
            fallar(f"formato '{f}' no existe. Usa 9x16 y/o 4x5.")
    musica = buscar_musica(opciones)
    avisar(f"Música: {musica.name}" if musica else "Sin música de fondo.")

    registro = leer_json(REGISTRO) if REGISTRO.exists() else {}
    hoy = date.today().strftime("%Y%m%d")
    pendientes = [(c, f) for c in combos for f in formatos]
    hechos = saltados = 0
    for n, (combo, formato) in enumerate(pendientes, 1):
        ids = [combo["gancho"], *combo["cuerpos"], combo["cta"]]
        faltan = [p for p in ids if p not in piezas]
        if faltan:
            avisar(f"[{n}/{len(pendientes)}] {combo['id']}: faltan piezas {', '.join(faltan)}, lo salto")
            continue
        gancho = piezas[combo["gancho"]]
        titulo = None if opciones.sin_titulo else gancho.get("titulo")
        clave = f"{'+'.join(ids)}|{formato}"
        sello = huella(ids, piezas, formato, opciones, musica, titulo)
        previo = registro.get(clave)
        if (previo and previo["huella"] == sello and not opciones.rehacer
                and (ANUNCIOS / previo["archivo"]).exists()):
            saltados += 1
            continue
        if previo and (ANUNCIOS / previo["archivo"]).exists():
            (ANUNCIOS / previo["archivo"]).unlink()

        angulo = slug(gancho.get("angulo") or combo["gancho"])
        nombre = f"{hoy}_{angulo}_MOD_{'-'.join(ids)}_{formato}.mp4"
        carpeta = ANUNCIOS / ".temporal"
        shutil.rmtree(carpeta, ignore_errors=True)
        carpeta.mkdir(parents=True)
        avisar(f"[{n}/{len(pendientes)}] {nombre}")
        try:
            segundos = armar(ids, piezas, formato, opciones, musica, titulo, ANUNCIOS / nombre, carpeta)
        except RuntimeError as err:
            avisar(f"  falló:\n{err}")
            continue
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)
        registro[clave] = {"archivo": nombre, "huella": sello, "formato": formato,
                           "angulo": gancho.get("angulo"), "titulo": titulo, "gancho": combo["gancho"],
                           "cuerpos": combo["cuerpos"], "cta": combo["cta"], "segundos": round(segundos, 1)}
        guardar_json(REGISTRO, registro)
        hechos += 1

    escribir_indice(registro)
    avisar(f"\nListo: {hechos} anuncios nuevos" + (f", {saltados} ya estaban hechos" if saltados else "")
           + ". Están en 3_anuncios/ (lista en INDICE.csv).")


if __name__ == "__main__":
    main()
