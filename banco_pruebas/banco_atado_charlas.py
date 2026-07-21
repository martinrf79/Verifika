"""
BANCO ATADO — CHARLAS MULTI-TURNO por el FLUJO ATADO (21-jul).

Corre guiones de varios turnos por app.core.hub_atado (interprete + solver
atados, SIN la pila de guardas de interprete_libre), con la memoria persistida
entre turnos en el Firestore simulado. Cada respuesta pasa por el JUEZ
determinista (banco_pruebas/juez.py): si alucina plata, stock, promesa o deja
un marcador sin estampar, la corrida lo marca.

Foco de esta tanda: guiones que COMBINAN dificultad y memoria en una misma
charla (52, 53, 54), que es lo que de verdad rompe.

Uso:
    python3 banco_pruebas/banco_atado_charlas.py g1.txt [g2.txt ...]
    BANCO_PAUSA_S=22 controla la pausa entre turnos (tier gratis de Gemini).
Deja el reporte de cada charla en banco_pruebas/corridas/.
"""
import asyncio
import datetime as _dt
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install

TIENDA = "verifika_prod"
_CORRIDAS = Path(__file__).resolve().parent / "corridas"


def _leer_guion(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


async def _correr(nombre: str, mensajes: list[str], pausa_s: float,
                  reporte: list[str]) -> int:
    from app.core.hub_atado import procesar_atado
    from app.storage.firestore_client import reset_conversation
    from banco_pruebas.juez import juzgar, juzgar_charla

    user = f"atado_{nombre}_{int(time.time())}"
    try:
        reset_conversation(user, tienda_id=TIENDA)
    except Exception:
        pass

    problemas = 0
    respuestas: list[str] = []
    for i, msg in enumerate(mensajes, 1):
        print(f"[{i}] CLIENTE: {msg}")
        reporte.append(f"\n## Turno {i}\n\nCLIENTE: {msg}\n")
        t0 = time.time()
        try:
            resp = await procesar_atado(user, msg, TIENDA, "sim", f"a{i:02d}")
        except Exception as e:
            import traceback
            resp = f"<<ERROR {type(e).__name__}: {e}>>"
            traceback.print_exc()
        ms = int((time.time() - t0) * 1000)
        respuestas.append(resp)
        print(f"    BOT ({ms} ms): {resp}\n")
        reporte.append(f"BOT ({ms} ms):\n\n```\n{resp}\n```\n")
        if resp.startswith("<<ERROR"):
            problemas += 1
            reporte.append("- **JUEZ: ERROR de ejecucion**")
        else:
            fallas = juzgar(resp, tienda_id=TIENDA, mensaje=msg)
            for p in fallas:
                print(f"    [JUEZ] {p}")
                reporte.append(f"- **JUEZ: {p}**")
                problemas += 1
            if not fallas:
                reporte.append("- JUEZ: limpio")
        if pausa_s and i < len(mensajes):
            await asyncio.sleep(pausa_s)

    for p in juzgar_charla(respuestas):
        print(f"    [JUEZ-CHARLA] {p}")
        reporte.append(f"\n- **JUEZ-CHARLA: {p}**")
        problemas += 1
    reporte.append("\n## Resumen\n")
    reporte.append(f"- Juez: {problemas} problema(s)" if problemas
                   else "- Juez: charla limpia")
    return problemas


async def main() -> int:
    info = install()
    guiones = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.exists():
            guiones.append((p.stem, _leer_guion(p)))
    if not guiones:
        print("Pasá al menos un guion. Ej: banco_pruebas/guiones/52_*.txt")
        return 1

    pausa_s = float(os.environ.get("BANCO_PAUSA_S", "22") or 0)
    print(f"[atado] sim: {info['productos']} prod, {info['faq']} FAQ. "
          f"Flujo ATADO por hub_atado, sin guardas. Pausa {pausa_s}s.\n")
    _CORRIDAS.mkdir(exist_ok=True)
    fecha = _dt.datetime.now()
    total = 0
    for nombre, mensajes in guiones:
        reporte = [f"# Corrida ATADA {nombre} — {fecha:%Y-%m-%d %H:%M}",
                   f"\nEntorno: sim_firestore, flujo atado (hub_atado, sin "
                   f"guardas), pausa {pausa_s}s.\n"]
        problemas = await _correr(nombre, mensajes, pausa_s, reporte)
        total += problemas
        salida = _CORRIDAS / f"{fecha:%Y%m%d}_atado_{nombre}.md"
        salida.write_text("\n".join(reporte) + "\n", encoding="utf-8")
        print(f"[reporte] {salida}\n")
    print(f"[JUEZ] {'TANDA CON ' + str(total) + ' PROBLEMA(S)' if total else 'tanda limpia'}")
    return total


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
