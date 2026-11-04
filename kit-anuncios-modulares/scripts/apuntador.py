"""Deja el guion listo para leer en cámara: negocio/teleprompter.txt

    python3 scripts/apuntador.py
"""
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun import NEGOCIO, avisar, leer_guion, piezas_del_guion  # noqa: E402

CONSEJOS = """\
ANTES DE GRABAR
  · Apaga el video HDR (iPhone: Ajustes > Cámara > Grabar video > Video HDR).
  · Celular en vertical, a la altura de tus ojos. Misma ropa, luz y encuadre todo el rato.
  · Lee cada bloque de corrido y quédate 2 segundos callada/o antes del siguiente.
  · ¿Te equivocaste? Para, 2 segundos de silencio y repite el bloque entero.
    Siempre se usa la ÚLTIMA vez que lo dijiste: no hay que borrar nada.
  · Los códigos (G01, C03...) son para ti: no los digas en voz alta.
  · Pasa el video al computador por cable, AirDrop o Google Drive (por WhatsApp pierde calidad).
"""

TITULOS = {"gancho": "GANCHOS", "cuerpo": "CUERPOS", "cta": "CIERRES (llamado a la acción)"}


def main():
    guion = leer_guion()
    lineas = [f"TELEPROMPTER · {guion.get('negocio', 'Mi negocio')}", "", CONSEJOS]
    tipo_actual = None
    for pieza in piezas_del_guion(guion):
        if pieza["tipo"] != tipo_actual:
            tipo_actual = pieza["tipo"]
            lineas += ["", "=" * 60, TITULOS[tipo_actual], "=" * 60]
        lineas += ["", f"[{pieza['id']}]  (no se lee)", ""]
        lineas += textwrap.wrap(pieza["texto"], width=42)
        lineas += ["", "        · · · 2 segundos de silencio · · ·"]
    lineas += ["", "FIN. ¡Listo! Pásale el video a Claude.", ""]

    destino = NEGOCIO / "teleprompter.txt"
    destino.write_text("\n".join(lineas), encoding="utf-8")
    avisar(f"Teleprompter listo: {destino}")


if __name__ == "__main__":
    main()
