"""
CHARLA SOBRE FIRESTORE SIMULADO — corre el camino vivo de punta a punta con la
base local real y el LLM vivo de produccion (Gemini; sin clave cae al
compositor). Sin credenciales de Google.

Uso:
    python3 banco_pruebas/charla_sim.py                    # guion de ejemplo
    python3 banco_pruebas/charla_sim.py guion.txt [g2.txt ...]  # un mensaje por linea

Cada respuesta pasa por el JUEZ de invariantes (banco_pruebas/juez.py) y el
OBSERVADOR captura los eventos radar del camino vivo (los mismos que en prod se
leen en Cloud Logging). Cada corrida deja su reporte en banco_pruebas/corridas/:
ese archivo es la EVIDENCIA, se commitea y es el registro de avances.

Tier gratis de Gemini (15 req/min): BANCO_PAUSA_S=25 pausa entre turnos.
Si alguna respuesta viola un invariante, el proceso termina con codigo != 0.
"""
import asyncio
import datetime as _dt
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas import observador
from banco_pruebas.sim_firestore import install

TIENDA = "verifika_prod"
_CORRIDAS = Path(__file__).resolve().parent / "corridas"

_GUION_DEMO = [
    "hola, tenes mouse?",
    "cual es el mas barato?",
    "y un teclado barato? sumalo",
    "cuanto sale todo con envio a Cordoba capital pagando por transferencia?",
    "es seguro comprar por internet?",
]


def _leer_guion(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def _campos_radar(e: dict) -> str:
    """Campos del evento que sirven de evidencia, sin ruido de infra."""
    fuera = {"event", "level", "timestamp", "severity", "message", "logger"}
    pares = [f"{k}={e[k]!r}" for k in e if k not in fuera]
    return ", ".join(pares)


async def _correr_guion(nombre: str, mensajes: list[str], pausa_s: float,
                        reporte: list[str]) -> int:
    from app.core.orchestrator import process_message
    from banco_pruebas.juez import juzgar, juzgar_charla

    user = f"sim_{nombre}_{int(time.time())}"
    problemas_total = 0
    turnos: list[observador.Turno] = []
    respuestas: list[str] = []

    for i, msg in enumerate(mensajes, 1):
        print(f"[{i}] CLIENTE: {msg}")
        reporte.append(f"\n## Turno {i}\n\nCLIENTE: {msg}\n")
        t0 = time.time()
        with observador.turno() as t:
            try:
                resp = await process_message(user, msg, tienda_id=TIENDA,
                                             canal="sim")
            except Exception as e:
                import traceback
                resp = f"<<ERROR {type(e).__name__}: {e}>>"
                traceback.print_exc()
        turnos.append(t)
        respuestas.append(resp)
        ms = int((time.time() - t0) * 1000)
        print(f"    BOT ({ms} ms): {resp}\n")
        reporte.append(f"BOT ({ms} ms):\n\n```\n{resp}\n```\n")

        if resp.startswith("<<ERROR"):
            problemas_total += 1
            reporte.append("- **JUEZ: ERROR de ejecucion**")
        else:
            fallas = juzgar(resp, tienda_id=TIENDA)
            for p in fallas:
                print(f"    [JUEZ] PROBLEMA: {p}")
                reporte.append(f"- **JUEZ: {p}**")
                problemas_total += 1
            if not fallas:
                reporte.append("- JUEZ: limpio")
        for e in t.radares():
            linea = f"RADAR `{e.get('event')}` [{e.get('level')}] " \
                    f"{_campos_radar(e)}"
            print(f"    [{linea}]")
            reporte.append(f"- {linea}")
        if pausa_s and i < len(mensajes):
            await asyncio.sleep(pausa_s)

    for p in juzgar_charla(respuestas):
        print(f"    [JUEZ-CHARLA] PROBLEMA: {p}")
        reporte.append(f"\n- **JUEZ-CHARLA: {p}**")
        problemas_total += 1

    conteo = observador.resumen_radares(turnos)
    reporte.append("\n## Resumen\n")
    reporte.append(f"- Juez: {problemas_total} problema(s)"
                   if problemas_total else "- Juez: tanda limpia")
    if conteo:
        reporte.append("- Radares de la corrida:")
        for ev, n in conteo.items():
            reporte.append(f"  - `{ev}`: {n}")
    else:
        reporte.append("- Radares de la corrida: ninguno")
    return problemas_total


async def main() -> int:
    observador.instalar()
    info = install()

    guiones: list[tuple[str, list[str]]] = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.exists():
            guiones.append((p.stem, _leer_guion(p)))
    if not guiones:
        guiones = [("demo", _GUION_DEMO)]

    pausa_s = float(os.environ.get("BANCO_PAUSA_S", "0") or 0)
    modelo = os.environ.get("GEMINI_MODEL", "")
    print(f"[sim] Firestore simulado: {info['productos']} productos, "
          f"{info['faq']} FAQ. Memoria en RAM. Pausa {pausa_s}s.\n")

    _CORRIDAS.mkdir(exist_ok=True)
    fecha = _dt.datetime.now()
    problemas_total = 0
    for nombre, mensajes in guiones:
        observador.limpiar()
        reporte = [
            f"# Corrida {nombre} — {fecha:%Y-%m-%d %H:%M}",
            f"\nEntorno: sim_firestore ({info['productos']} productos, "
            f"{info['faq']} FAQ), camino vivo por process_message"
            + (f", modelo {modelo}" if modelo else "")
            + (f", pausa {pausa_s}s" if pausa_s else "") + ".",
        ]
        problemas = await _correr_guion(nombre, mensajes, pausa_s, reporte)
        problemas_total += problemas
        salida = _CORRIDAS / f"{fecha:%Y%m%d}_{nombre}.md"
        salida.write_text("\n".join(reporte) + "\n", encoding="utf-8")
        print(f"[reporte] {salida}")

    if problemas_total:
        print(f"[JUEZ] TANDA CON {problemas_total} PROBLEMA(S)")
    else:
        print("[JUEZ] tanda limpia")
    return problemas_total


if __name__ == "__main__":
    raise SystemExit(1 if asyncio.run(main()) else 0)
