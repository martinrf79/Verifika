"""
DASHBOARD del banco de casos. Lee reports/banco_history.jsonl (una linea por
corrida del banco) y muestra el estado actual por componente y la tendencia.

No corre pruebas: solo lee lo que dejo scripts/banco_casos.py. Sin credenciales.

Uso:
  winvenv\\Scripts\\python.exe scripts\\dashboard.py
"""
import os
import json
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "reports", "banco_history.jsonl")


def cargar():
    if not os.path.exists(HIST):
        raise SystemExit(
            "No hay historial todavia. Corre primero scripts/banco_casos.py")
    filas = []
    with open(HIST, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    filas.append(json.loads(line))
                except Exception:
                    pass
    return filas


def barra(ok, total, ancho=20):
    if total <= 0:
        return " " * ancho
    llenos = int(round(ancho * ok / total))
    return "#" * llenos + "-" * (ancho - llenos)


def main():
    filas = cargar()
    ultima = filas[-1]

    print("\n=== DASHBOARD — banco de casos ===\n")
    print(f"  Ultima corrida: {ultima['timestamp']}")
    print(f"  Corridas registradas: {len(filas)}\n")

    print("  Estado actual por componente:")
    pc = ultima.get("por_componente", {})
    for comp, d in sorted(pc.items()):
        ok = d.get("ok", 0)
        falla = d.get("falla", 0)
        pend = d.get("pend", 0)
        listo = d.get("listo", 0)
        total_impl = ok + falla
        pct = (100 * ok // total_impl) if total_impl else 100
        print(f"    {comp:<13} [{barra(ok, total_impl)}] {pct:>3}%  "
              f"ok={ok} falla={falla} pend={pend} listo?={listo}")

    print(f"\n  Combinaciones ultima corrida: "
          f"{ultima.get('combinaciones_generadas', 0)} generadas, "
          f"{ultima.get('combinaciones_fallas', 0)} fallas")
    print(f"  Totales: {ultima.get('total_casos', 0)} casos, "
          f"{ultima.get('fallas', 0)} fallas, "
          f"{ultima.get('pendientes', 0)} pendientes\n")

    # Tendencia: ultimas corridas, fallas y pendientes.
    print("  Tendencia (ultimas 10 corridas):")
    print(f"    {'fecha':<20} {'casos':>6} {'fallas':>7} {'pend':>5} "
          f"{'comb_fallas':>12}")
    for f in filas[-10:]:
        ts = f.get("timestamp", "")[:19]
        print(f"    {ts:<20} {f.get('total_casos', 0):>6} "
              f"{f.get('fallas', 0):>7} {f.get('pendientes', 0):>5} "
              f"{f.get('combinaciones_fallas', 0):>12}")

    # Alarma si la ultima corrida tiene fallas.
    if ultima.get("fallas", 0) or ultima.get("combinaciones_fallas", 0):
        print("\n  ALARMA: la ultima corrida tiene fallas. Revisar el banco.\n")
        return 1
    print("\n  Sin fallas en la ultima corrida.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
