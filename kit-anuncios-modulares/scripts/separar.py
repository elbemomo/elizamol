"""Encuentra cada bloque del guion en la grabación y lo corta.

    python3 scripts/separar.py
    python3 scripts/separar.py --umbral 0.65          # si no encuentra piezas
    python3 scripts/separar.py --solo G03,C07          # recorta solo esas

Si un bloque se grabó varias veces, se usa la ÚLTIMA toma. Deja los cortes en
2_piezas/, los datos en 2_piezas/piezas.json y un resumen en 2_piezas/REPORTE.md.
"""
import argparse
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import (FPS, GRABACIONES, PIEZAS, avisar, correr_ffmpeg, fallar, ffmpeg,  # noqa: E402
                   guardar_json, info_medio, leer_guion, leer_json, piezas_del_guion, tiene_filtro,
                   tokens)

ALTO_MAXIMO = 1920
FUNDIDO = 0.015
TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
           "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


# ---------- palabras del guion y de la grabación ----------

def palabras_visibles(texto):
    """Palabras tal como se muestran en el subtítulo, cada una con sus tokens."""
    salida = []
    for trozo in texto.split():
        tk = tokens(trozo)
        if tk or not salida:
            salida.append({"t": trozo, "tk": tk})
        else:
            salida[-1]["t"] += " " + trozo  # signos sueltos se pegan a la palabra anterior
    return salida


def tokens_de_clip(clip):
    """Lista plana de (token, índice de palabra) de un clip transcrito."""
    plano = []
    for n, palabra in enumerate(clip["palabras"]):
        for tk in tokens(palabra["p"]):
            plano.append((tk, n))
    return plano


# ---------- búsqueda de tomas ----------

def buscar_tomas(guion_tk, clip_tk, umbral):
    """Todas las ventanas de la grabación que se parecen al bloque, agrupadas por toma."""
    n = len(guion_tk)
    if n == 0:
        return []
    texto = [t for t, _ in clip_tk]
    inicios = set(guion_tk[:3])
    largos = range(max(1, round(n * 0.7)), round(n * 1.35) + 2)
    candidatos = []
    for s in range(len(texto)):
        if texto[s] not in inicios:
            continue
        for largo in largos:
            ventana = texto[s:s + largo]
            if len(ventana) < largos.start:
                break
            parecido = SequenceMatcher(None, guion_tk, ventana, autojunk=False).ratio()
            if parecido >= umbral:
                candidatos.append((parecido, s, s + len(ventana)))

    tomas = []
    for cand in sorted(candidatos, key=lambda c: c[1]):
        if tomas and cand[1] < tomas[-1]["fin"]:
            grupo = tomas[-1]
            grupo["fin"] = max(grupo["fin"], cand[2])
            if cand[0] > grupo["mejor"][0]:
                grupo["mejor"] = cand
        else:
            tomas.append({"fin": cand[2], "mejor": cand})
    return [t["mejor"] for t in tomas]


def recortar_bordes(guion_tk, clip_tk, s, e):
    """Ajusta la ventana a la primera y la última palabra que de verdad coinciden."""
    ventana = [t for t, _ in clip_tk[s:e]]
    bloques = [b for b in SequenceMatcher(None, guion_tk, ventana, autojunk=False)
               .get_matching_blocks() if b.size]
    a = s + bloques[0].b
    b = s + bloques[-1].b + bloques[-1].size - 1
    coinciden = sum(bl.size for bl in bloques)
    de_mas = (b - a + 1) - coinciden
    return a, b, de_mas


# ---------- tiempos de subtítulos ----------

def tiempos_por_palabra(visibles, clip, clip_tk, a, b):
    """Da a cada palabra del guion el tiempo de la palabra dicha que le corresponde."""
    guion_tk, duenos = [], []
    for n, v in enumerate(visibles):
        for tk in v["tk"]:
            guion_tk.append(tk)
            duenos.append(n)
    dichos = clip_tk[a:b + 1]
    tiempo_tk = [None] * len(guion_tk)
    sm = SequenceMatcher(None, guion_tk, [t for t, _ in dichos], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("equal", "replace") and j2 > j1:
            for k in range(i1, i2):
                j = j1 + (k - i1) * (j2 - j1) // (i2 - i1)
                palabra = clip["palabras"][dichos[j][1]]
                tiempo_tk[k] = (palabra["i"], palabra["f"])

    tiempos = [None] * len(visibles)
    for k, t in enumerate(tiempo_tk):
        if t is None:
            continue
        n = duenos[k]
        tiempos[n] = (min(tiempos[n][0], t[0]), max(tiempos[n][1], t[1])) if tiempos[n] else t

    # Las palabras que no se oyeron se reparten entre sus vecinas.
    inicio_bloque = clip["palabras"][dichos[0][1]]["i"]
    fin_bloque = clip["palabras"][dichos[-1][1]]["f"]
    n = 0
    while n < len(tiempos):
        if tiempos[n] is not None:
            n += 1
            continue
        m = n
        while m < len(tiempos) and tiempos[m] is None:
            m += 1
        desde = tiempos[n - 1][1] if n > 0 else inicio_bloque
        hasta = tiempos[m][0] if m < len(tiempos) else fin_bloque
        paso = max(hasta - desde, 0.05 * (m - n)) / (m - n)
        for k in range(n, m):
            tiempos[k] = (desde + paso * (k - n), desde + paso * (k - n + 1))
        n = m
    return tiempos


def a_tiempo_de_pieza(t, tramos):
    """Pasa un tiempo de la grabación al tiempo dentro de la pieza ya cortada."""
    acumulado = 0.0
    for ini, fin in tramos:
        if t <= fin:
            return acumulado + max(0.0, t - ini)
        acumulado += fin - ini
    return acumulado


# ---------- silencios reales ----------

def silencios(video):
    """Tramos en silencio del audio, para afinar dónde empieza y termina la voz."""
    res = subprocess.run([ffmpeg(), "-hide_banner", "-nostats", "-i", str(video), "-vn",
                          "-af", "silencedetect=n=-35dB:d=0.2", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    inicios = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", res.stderr)]
    finales = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", res.stderr)]
    return list(zip(inicios, finales))


def afinar_bordes(tramos_mudos, primera, ultima, antes, despues):
    """La transcripción suele marcar la primera palabra antes de tiempo: se corrige con el audio."""
    voz_ini = max((fin for ini, fin in tramos_mudos if antes < fin < primera["f"]), default=None)
    voz_fin = min((ini for ini, fin in tramos_mudos if ultima["i"] < ini < despues), default=None)
    return voz_ini, voz_fin


# ---------- corte ----------

def cortar(video, info, tramos, destino):
    desde = max(0.0, tramos[0][0] - 2.0)
    alto = min(ALTO_MAXIMO, info["alto"] - info["alto"] % 2)
    ancho = round(info["ancho"] * alto / info["alto"] / 2) * 2
    filtros_video = []
    if info["hdr"] and tiene_filtro("zscale") and tiene_filtro("tonemap"):
        filtros_video.append(TONEMAP)
    filtros_video += [f"fps={FPS}", f"scale={ancho}:{alto}", "setsar=1", "format=yuv420p"]

    k = len(tramos)
    partes = [f"[0:v]{','.join(filtros_video)},split={k}" + "".join(f"[vs{i}]" for i in range(k)),
              f"[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit={k}"
              + "".join(f"[as{i}]" for i in range(k))]
    for i, (ini, fin) in enumerate(tramos):
        a, b = ini - desde, fin - desde
        largo = fin - ini
        partes.append(f"[vs{i}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        partes.append(f"[as{i}]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d={FUNDIDO},afade=t=out:st={largo - FUNDIDO:.3f}:d={FUNDIDO}[a{i}]")
    partes.append("".join(f"[v{i}][a{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=1[v][a]")

    correr_ffmpeg(["-ss", f"{desde:.3f}", "-i", video, "-filter_complex", ";".join(partes),
                   "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "17", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", destino])
    return ancho, alto


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--umbral", type=float, default=0.75, help="qué tan parecido al guion (0 a 1)")
    ap.add_argument("--margen-inicio", type=float, default=0.12, help="segundos antes de la 1ª palabra")
    ap.add_argument("--margen-fin", type=float, default=0.30, help="segundos después de la última")
    ap.add_argument("--hueco", type=float, default=0.9, help="silencios internos más largos se sacan")
    ap.add_argument("--solo", help="IDs separados por coma, por ejemplo G01,C04")
    args = ap.parse_args()

    ruta_tx = PIEZAS / "transcripcion.json"
    if not ruta_tx.exists():
        fallar("falta la transcripción. Corre primero scripts/transcribir.py.")
    clips = leer_json(ruta_tx)["clips"]
    guion = leer_guion()
    solo = {x.strip().upper() for x in args.solo.split(",")} if args.solo else None

    ruta_datos = PIEZAS / "piezas.json"
    datos = leer_json(ruta_datos) if ruta_datos.exists() else {}
    planos = [tokens_de_clip(c) for c in clips]
    infos = [info_medio(GRABACIONES / c["archivo"]) for c in clips]
    mudos = [silencios(GRABACIONES / c["archivo"]) for c in clips]

    faltan, revisar, largos, con_hueco = [], [], [], []
    hubo_hdr = any(i["hdr"] for i in infos)
    for pieza in piezas_del_guion(guion):
        pid = pieza["id"]
        if solo and pid.upper() not in solo:
            continue
        visibles = palabras_visibles(pieza["texto"])
        guion_tk = [tk for v in visibles for tk in v["tk"]]

        tomas = []
        for c, plano in enumerate(planos):
            for parecido, s, e in buscar_tomas(guion_tk, plano, args.umbral):
                tomas.append((c, s, e, parecido))
        if not tomas:
            avisar(f"✗ {pid}: no la encontré")
            faltan.append(pid)
            datos.pop(pid, None)
            continue
        c, s, e, parecido = max(tomas, key=lambda t: (t[0], t[1]))  # la última toma manda
        clip, plano, info = clips[c], planos[c], infos[c]
        a, b, de_mas = recortar_bordes(guion_tk, plano, s, e)
        w_a, w_b = plano[a][1], plano[b][1]
        palabras = clip["palabras"]

        antes = palabras[w_a - 1]["f"] if w_a > 0 else 0.0
        despues = palabras[w_b + 1]["i"] if w_b + 1 < len(palabras) else float("inf")
        voz_ini, voz_fin = afinar_bordes(mudos[c], palabras[w_a], palabras[w_b], antes, despues)
        inicio = (voz_ini if voz_ini is not None else palabras[w_a]["i"]) - args.margen_inicio
        fin = (voz_fin if voz_fin is not None else palabras[w_b]["f"]) + args.margen_fin
        if w_a > 0:
            inicio = max(inicio, antes + 0.03)
        if w_b + 1 < len(palabras):
            fin = min(fin, despues - 0.03)
        inicio, fin = max(0.0, inicio), min(info["duracion"] or fin, fin)

        tramos, sacado, desde = [], 0.0, inicio
        for k in range(w_a, w_b):
            hueco = palabras[k + 1]["i"] - palabras[k]["f"]
            if hueco > args.hueco:
                tramos.append((desde, palabras[k]["f"] + 0.25))
                desde = palabras[k + 1]["i"] - 0.25
                sacado += hueco - 0.5
        tramos.append((desde, fin))

        tiempos = tiempos_por_palabra(visibles, clip, plano, a, b)
        destino = PIEZAS / f"{pid}.mp4"
        try:
            ancho, alto = cortar(GRABACIONES / clip["archivo"], info, tramos, destino)
        except RuntimeError as err:
            avisar(f"✗ {pid}: el corte falló\n{err}")
            faltan.append(pid)
            continue
        duracion = info_medio(destino)["duracion"]

        subtitulos = []
        for v, (ti, tf) in zip(visibles, tiempos):
            i = min(a_tiempo_de_pieza(ti, tramos), duracion)
            f = min(max(i + 0.05, a_tiempo_de_pieza(tf, tramos)), duracion)
            subtitulos.append({"t": v["t"], "i": round(i, 3), "f": round(f, 3)})

        dudosa = parecido < 0.85 or de_mas >= 2
        datos[pid] = {"tipo": pieza["tipo"], "rol": pieza.get("rol"), "angulo": pieza.get("angulo"),
                      "titulo": pieza.get("titulo"), "archivo": destino.name,
                      "duracion": round(duracion, 3), "ancho": ancho, "alto": alto,
                      "parecido": round(parecido, 2), "tomas": len(tomas), "revisar": dudosa,
                      "silencio_sacado": round(sacado, 1), "palabras": subtitulos}
        nota = f"{duracion:.1f} s · parecido {parecido:.0%}" + (f" · {len(tomas)} tomas" if len(tomas) > 1 else "")
        avisar(f"{'⚠' if dudosa else '✓'} {pid}: {nota}")
        if dudosa:
            revisar.append(pid)
        if pieza["tipo"] == "gancho" and duracion > 4.0:
            largos.append(f"{pid} ({duracion:.1f} s)")
        if sacado > 0:
            con_hueco.append(f"{pid} ({sacado:.1f} s)")

    guardar_json(ruta_datos, datos)
    escribir_reporte(guion, datos, faltan, revisar, largos, con_hueco, hubo_hdr)
    avisar(f"\n{len(datos)} piezas listas en 2_piezas/. Resumen en 2_piezas/REPORTE.md")


def escribir_reporte(guion, datos, faltan, revisar, largos, con_hueco, hubo_hdr):
    total = len(piezas_del_guion(guion))
    lineas = ["# Reporte del corte", "", f"**{len(datos)} de {total} piezas listas.**", ""]
    if faltan:
        lineas += ["## No las encontré", "",
                   "No se grabaron o se dijeron muy distinto al guion: " + ", ".join(faltan), ""]
    if revisar:
        lineas += ["## Escúchalas antes de armar", "",
                   "Se parecen menos al guion o tienen alguna palabra de más: " + ", ".join(revisar), ""]
    if largos:
        lineas += ["## Ganchos de más de 4 segundos", "",
                   "Funcionan, pero conviene acortarlos la próxima vez: " + ", ".join(largos), ""]
    if con_hueco:
        lineas += ["## Silencios que saqué", "",
                   "Te quedaste pensando a mitad de bloque y saqué el hueco: " + ", ".join(con_hueco), ""]
    if hubo_hdr:
        lineas += ["## Tu grabación venía en HDR", "",
                   "Ya la convertí. La próxima vez apaga el Video HDR del celular.", ""]
    lineas += ["## Detalle", "", "| Pieza | Tipo | Duración | Parecido | Tomas |", "|---|---|---|---|---|"]
    for pid, d in datos.items():
        lineas.append(f"| {pid} | {d['tipo']} | {d['duracion']:.1f} s | {d['parecido']:.0%} | {d['tomas']} |")
    (PIEZAS / "REPORTE.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
