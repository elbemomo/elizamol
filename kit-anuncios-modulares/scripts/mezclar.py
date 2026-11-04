"""Decide qué combinaciones de piezas se van a armar: negocio/combinaciones.json

    python3 scripts/mezclar.py --cantidad 30
    python3 scripts/mezclar.py --cantidad 30 --cuerpos 2-3

Cada anuncio = 1 gancho + cuerpos (en orden problema → mecanismo → prueba → oferta)
+ 1 cierre, de 20 a 30 segundos, y nunca solo con el problema.
"""
import argparse
import itertools
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import NEGOCIO, ORDEN_ROLES, PIEZAS, avisar, fallar, guardar_json, leer_json  # noqa: E402

UNION = 0.17


def orden_rol(rol):
    return ORDEN_ROLES.index(rol) if rol in ORDEN_ROLES else len(ORDEN_ROLES)


def rango(texto):
    if "-" in texto:
        a, b = texto.split("-", 1)
        return range(int(a), int(b) + 1)
    return range(int(texto), int(texto) + 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cantidad", type=int, default=30)
    ap.add_argument("--cuerpos", default="2", help="cuántos cuerpos por anuncio: 2, o un rango 2-3")
    ap.add_argument("--min", type=float, default=20.0, help="duración mínima en segundos")
    ap.add_argument("--max", type=float, default=30.0, help="duración máxima en segundos")
    ap.add_argument("--semilla", type=int, default=7)
    args = ap.parse_args()

    ruta = PIEZAS / "piezas.json"
    if not ruta.exists():
        fallar("no hay piezas cortadas. Corre primero scripts/separar.py.")
    piezas = leer_json(ruta)
    ganchos = sorted(p for p, d in piezas.items() if d["tipo"] == "gancho")
    cuerpos = sorted((p for p, d in piezas.items() if d["tipo"] == "cuerpo"),
                     key=lambda p: (orden_rol(piezas[p]["rol"]), p))
    ctas = sorted(p for p, d in piezas.items() if d["tipo"] == "cta")
    if not (ganchos and cuerpos and ctas):
        fallar("se necesita al menos un gancho, un cuerpo y un cierre cortados.")

    def duracion(ids):
        return sum(piezas[i]["duracion"] for i in ids) + UNION * (len(ids) - 1)

    posibles = {g: [] for g in ganchos}
    for k in rango(args.cuerpos):
        for grupo in itertools.combinations(cuerpos, k):
            roles = {piezas[c]["rol"] for c in grupo}
            if not roles & {"mecanismo", "oferta"}:
                continue
            for g in ganchos:
                for cta in ctas:
                    ids = [g, *grupo, cta]
                    d = duracion(ids)
                    if args.min <= d <= args.max:
                        posibles[g].append((list(grupo), cta, d))

    total_posibles = sum(len(v) for v in posibles.values())
    if total_posibles == 0:
        fallar(f"ninguna combinación dura entre {args.min:.0f} y {args.max:.0f} s. "
               "Prueba --cuerpos 2-3 o ajusta --min/--max.")

    azar = random.Random(args.semilla)
    for lista in posibles.values():
        azar.shuffle(lista)
    uso_cuerpos, uso_ctas, usados = Counter(), Counter(), set()
    elegidas = []
    while len(elegidas) < args.cantidad and any(posibles.values()):
        for g in ganchos:  # vuelta por todos los ganchos para repartir parejo
            if len(elegidas) >= args.cantidad or not posibles[g]:
                continue
            mejor = min(posibles[g], key=lambda x: (sum(uso_cuerpos[c] for c in x[0]), uso_ctas[x[1]]))
            posibles[g].remove(mejor)
            grupo, cta, d = mejor
            clave = (g, tuple(grupo), cta)
            if clave in usados:
                continue
            usados.add(clave)
            uso_cuerpos.update(grupo)
            uso_ctas[cta] += 1
            elegidas.append({"gancho": g, "cuerpos": grupo, "cta": cta, "duracion": round(d, 1)})

    for n, combo in enumerate(elegidas, 1):
        combo["id"] = f"A{n:03d}"
    guardar_json(NEGOCIO / "combinaciones.json", elegidas)

    avisar(f"{len(elegidas)} combinaciones elegidas (había {total_posibles} posibles).")
    if len(elegidas) < args.cantidad:
        avisar("No alcanzó la cantidad pedida: prueba --cuerpos 2-3 o graba más piezas.")
    for combo in elegidas[:5]:
        avisar(f"  {combo['id']}: {combo['gancho']} + {' + '.join(combo['cuerpos'])} + "
               f"{combo['cta']} ({combo['duracion']} s)")
    if len(elegidas) > 5:
        avisar("  ...")


if __name__ == "__main__":
    main()
