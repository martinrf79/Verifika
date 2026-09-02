"""
BANCO ATADO — CHARLAS MULTI-TURNO por el CAMINO VIVO DE PRODUCCION.

Corre guiones de varios turnos por la MISMA funcion que atiende el webhook de
WhatsApp (`app.main._process_and_reply_whatsapp`, via banco_pruebas/
clon_produccion.py), con la memoria persistida entre turnos en el Firestore
doble cargado con el catalogo, la FAQ y la config REALES. Cada respuesta pasa
por el JUEZ determinista (banco_pruebas/juez.py): si alucina plata, stock,
promesa o deja un marcador sin estampar, la corrida lo marca.

CAMBIO DEL 31-jul: antes esto llamaba a `procesar_atado` directo y se salteaba
tres cosas que en produccion SI pasan -el antijailbreak, el RESET_CODE y la
particion del mensaje en partes-. El banco daba verde y la primera charla real
rompia. Ahora el turno entra y sale por donde entra y sale en la nube, y el
reporte muestra las PARTES tal como las recibe el cliente.

Uso:
    python3 banco_pruebas/banco_atado_charlas.py g1.txt [g2.txt ...]
    BANCO_PAUSA_S=22 controla la pausa entre turnos (tier gratis de Gemini).
    La clave la elige UN solo lugar, `clon_produccion.preparar_entorno`, y el
    default es la GRATIS. Esta linea decia que con GEMINI_API_KEY_PROD en el
    entorno tomaba la paga sola: era verdad hasta el 4-ago y es exactamente el
    reflejo que gasto ~40 dolares, asi que se corrige acá también.
Deja el reporte de cada charla en banco_pruebas/corridas/.
"""
import asyncio
import datetime as _dt
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas import clon_produccion

# El entorno se prepara ANTES de importar nada de app: app.config lee las envs
# al importarse y despues ya es tarde.
clon_produccion.preparar_entorno()

TIENDA = "verifika_prod"
_CORRIDAS = Path(__file__).resolve().parent / "corridas"


def _leer_guion(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


async def _correr(nombre: str, mensajes: list[str], pausa_s: float,
                  reporte: list[str]) -> int:
    from banco_pruebas.juez import juzgar, juzgar_charla

    user = f"atado_{nombre}_{int(time.time())}"
    clon_produccion.reiniciar_cliente(user)

    problemas = 0
    respuestas: list[str] = []
    for i, msg in enumerate(mensajes, 1):
        print(f"[{i}] CLIENTE: {msg}")
        reporte.append(f"\n## Turno {i}\n\nCLIENTE: {msg}\n")
        t0 = time.time()
        try:
            partes = await clon_produccion.turno(user, msg)
        except Exception as e:
            import traceback
            partes = [f"<<ERROR {type(e).__name__}: {e}>>"]
            traceback.print_exc()
        ms = int((time.time() - t0) * 1000)
        # El cliente recibe partes; el juez lee el texto entero. Las dos cosas
        # importan: un corte malo se ve en las partes, una contradiccion entre
        # partes solo se ve leyendolas juntas.
        resp = "\n\n".join(partes)
        respuestas.append(resp)
        print(f"    BOT ({ms} ms, {len(partes)} parte/s): {resp}\n")
        reporte.append(f"BOT ({ms} ms) — {len(partes)} mensaje/s como los recibe "
                       f"el cliente:\n")
        for n, p in enumerate(partes, 1):
            reporte.append(f"\nmensaje {n}:\n\n```\n{p}\n```\n")
        if resp.startswith("<<ERROR"):
            problemas += 1
            reporte.append("- **JUEZ: ERROR de ejecucion**")
        elif clon_produccion.es_fallback(resp):
            # Produccion tapa la excepcion con una disculpa. Sin esto, el banco
            # contaba como respuesta limpia lo que en la vida real es una caida.
            problemas += 1
            print("    [JUEZ] FALLBACK de produccion: el turno exploto")
            reporte.append("- **JUEZ: FALLBACK de produccion, el turno exploto "
                           "y el cliente recibio una disculpa**")
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
    info = clon_produccion.instalar()
    guiones = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.exists():
            guiones.append((p.stem, _leer_guion(p)))
    if not guiones:
        print("Pasá al menos un guion. Ej: banco_pruebas/guiones/52_*.txt")
        return 1

    pausa_s = float(os.environ.get("BANCO_PAUSA_S", "22") or 0)
    banner = (f"[clon] {info['productos']} productos, {info['faq']} FAQ, config "
              f"{info['config_tienda']}. Camino VIVO de WhatsApp. "
              f"Solver {info['solver_model']}, interprete {info['interprete']}, "
              f"clave {info['clave']}, cierre modo {info['modo_cierre']}. "
              f"Pausa {pausa_s}s.")
    print(banner + "\n")
    _CORRIDAS.mkdir(exist_ok=True)
    fecha = _dt.datetime.now()
    total = 0
    for nombre, mensajes in guiones:
        reporte = [f"# Corrida ATADA {nombre} — {fecha:%Y-%m-%d %H:%M}",
                   f"\nEntorno: {banner}\n"]
        problemas = await _correr(nombre, mensajes, pausa_s, reporte)
        total += problemas
        salida = _CORRIDAS / f"{fecha:%Y%m%d}_atado_{nombre}.md"
        salida.write_text("\n".join(reporte) + "\n", encoding="utf-8")
        print(f"[reporte] {salida}\n")
    print(f"[JUEZ] {'TANDA CON ' + str(total) + ' PROBLEMA(S)' if total else 'tanda limpia'}")
    return total


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
