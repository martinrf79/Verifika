"""
BANCO DORADO del CERTIFICADOR de identidad. Tiene que dar 100%.

Tres clases de veredicto sobre el catalogo real (verifika_prod):
  exists    -> el cliente nombro un producto que esta, exacto.
  ambiguous -> nombro algo con varias variantes reales (color/modelo): preguntar.
  not_found -> NO existe. Resultado VALIDO, no error. Incluye las trampas: el
               Zyltech 3D, la placa base que no debe caer en placa de video, el
               'Steel' que no debe traer una RAM, un modelo inexistente (RTX 5070).

Uso:
    $env:BANCO_PRESET="config/camino_nuevo.env"
    .\correr_local.ps1 py scripts\prueba_certificador.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for raw in (ROOT / os.getenv("BANCO_PRESET", "config/camino_nuevo.env")).read_text(encoding="utf-8-sig").splitlines():
    l = raw.strip()
    if l and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1); os.environ[k.strip()] = v.strip()
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import logging
import structlog
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

from app.core.certificador import certificar  # noqa: E402

TIENDA = "verifika_prod"

# (termino, status esperado). Para 'exists' opcional: substring que debe estar
# en el nombre certificado (para chequear que NO certifico otra cosa).
CASOS = [
    # ── EXISTE (exacto) ──
    ("Teclado Logitech K380 Negro", "exists", "K380"),
    ("Monitor Samsung Odyssey G9 49", "exists", "G9"),
    ("Mouse Logitech G203 Lightsync Negro", "exists", "G203"),
    ("Microfono Shure MV7 Negro", "exists", "MV7"),
    ("Procesador Intel Core i9-14900K", "exists", "14900K"),
    ("Motherboard Asus TUF B650-Plus WiFi", "exists", "B650"),
    ("Placa de video Asus ROG Strix RTX 4080 Super", "exists", "4080"),
    ("Silla gamer Redragon Coeus Negro y rojo", "exists", "Coeus"),
    # ── AMBIGUO (variantes reales) ──
    ("Notebook Lenovo Legion 5 Core i7", "ambiguous", None),
    ("Impresora Epson EcoTank L3250", "ambiguous", None),
    # ── NO EXISTE (resultado valido, incluye trampas) ──
    ("impresora 3d Zyltech", "not_found", None),
    ("iPad Pro de Apple", "not_found", None),
    ("placa base ASRock B450M Steel Legend", "not_found", None),
    ("Placa de video RTX 5070", "not_found", None),
    # El Dell G15 SI existe: la identidad existe (ambiguo por color). Lo "tactil"
    # es COMPATIBILIDAD/atributo, otro eje, no identidad. El certificador no debe
    # negar el producto por un atributo que no tiene.
    ("Notebook Dell G15 Core i5", "ambiguous", None),
    ("amoladora Bosch", "not_found", None),
    ("heladera Samsung no frost", "not_found", None),
]


def main():
    ok = 0
    fallos = []
    print(f"\n=== BANCO DORADO CERTIFICADOR — {TIENDA} ===\n")
    for term, esperado, substr in CASOS:
        v = certificar(term, TIENDA)
        got = v.get("status")
        bien = got == esperado
        # chequeo extra para exists: que no haya certificado OTRO producto
        if bien and esperado == "exists" and substr:
            nombre = (v.get("item") or {}).get("nombre", "")
            if substr.lower() not in nombre.lower():
                bien = False
        detalle = ""
        if got == "exists":
            detalle = (v.get("item") or {}).get("nombre", "")
        elif got == "ambiguous":
            detalle = " | ".join(c.get("nombre", "") for c in v.get("candidates", []))
        marca = "OK  " if bien else "FALLA"
        print(f"[{marca}] '{term[:48]}'  esperado={esperado}  got={got}")
        if detalle:
            print(f"          -> {detalle[:110]}")
        if bien:
            ok += 1
        else:
            fallos.append((term, esperado, got, detalle))

    print(f"\n=== {ok}/{len(CASOS)} ===")
    if fallos:
        print("FALLOS:")
        for t, e, g, d in fallos:
            print(f"  '{t}' esperaba {e}, dio {g}  {d[:80]}")
        sys.exit(1)
    print("VERDE: el certificador es confiable sobre estos casos.")


if __name__ == "__main__":
    main()
