"""
BANCO DE CIERRE — el SISTEMA REAL de punta a punta, con la maquina determinista.

Corre el orchestrator REAL (process_message, el mismo de produccion) sobre varias
charlas de cierre multiturno, con la config de config/maquina_determinista.env (la
fuente unica: lo que se prueba aca es lo que se deploya). No cablea piezas a mano;
deja que el orchestrator conecte cada etapa de la venta, igual que en Telegram.

Por turno chequea DOS cosas:
  1. el TEXTO que ve el cliente (no cae a fallback, no re-saluda, hay link al cerrar)
  2. el ESTADO estructurado del turno (telemetria.leer_turno: etapa, total verificado,
     si la confirmacion corto el Solver)

Imprime la charla entera para LEERLA (la planilla esconde regresiones) y guarda el
reporte en reports/cierre_<modelo>.txt con el resumen pasa/falla.

Uso (carga .secrets6.env con las claves via el runner; el preset pisa los flags):
    .\\correr_local.ps1 py scripts\\banco_cierre.py
    .\\correr_local.ps1 py scripts\\banco_cierre.py --solo cierre_completo
"""
import asyncio
import os
import re
import sys
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── 1) Cargar el preset ANTES de importar el orchestrator (config lee env al
#       importar). El preset PISA lo que traiga .secrets6.env: es la verdad unica.
def _cargar_preset(nombre=None):
    # BANCO_PRESET permite correr el MISMO banco sobre otro preset (ej el camino
    # nuevo) sin tocar nada mas. Default: la maquina determinista de siempre.
    nombre = nombre or os.getenv("BANCO_PRESET", "config/maquina_determinista.env")
    p = ROOT / nombre
    if not p.exists():
        print(f"[banco_cierre] FALTA el preset {p}")
        sys.exit(1)
    n = 0
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        linea = raw.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ[k.strip()] = v.strip()
        n += 1
    print(f"[banco_cierre] preset cargado: {n} variables desde {nombre}")


_cargar_preset()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import logging  # noqa: E402
import structlog  # noqa: E402
# Nivel de log configurable: BANCO_LOG=INFO para ver acciones del interprete,
# director y confirmacion al diagnosticar. Default WARNING (corrida limpia).
_nivel = getattr(logging, os.getenv("BANCO_LOG", "WARNING").upper(), logging.WARNING)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(_nivel))

from app.config import get_settings  # noqa: E402
from app.core.orchestrator import process_message  # noqa: E402
from app.core.telemetria import leer_turno  # noqa: E402

settings = get_settings()
# Tienda FIJA. OJO: el runner (modo py) mete el nombre del script en SMOKE_TIENDA,
# asi que NO lo leemos (si no, la tienda seria "scripts\banco_cierre.py" -> catalogo
# vacio y todo cae). Mismo recaudo que charla_cierre.py.
TIENDA = "verifika_prod"

_FALLBACKS = [settings.FALLBACK_MESSAGE, settings.VERIFIKA_FALLBACK_MESSAGE,
              "problema tecnico", "problema técnico"]
_LINK_RE = re.compile(r"https?://\S+")


# ════════════════════════════════════════════════════════════════════
# Escenarios. Cada turno: el mensaje del cliente + que se espera.
#   estado        -> etapa esperada (uno o varios) en telemetria
#   contiene      -> substrings que DEBEN estar en el texto (case-insensitive)
#   no_contiene   -> substrings que NO deben estar
#   confirma      -> True: el turno tiene que preguntar para aclarar
#   total         -> True: el turno tiene que llevar un total verificado por codigo
#   link          -> True: el texto tiene que traer un link de pago (blando: avisa
#                    si falta y hay sospecha de token MP ausente, no rompe la corrida)
# ════════════════════════════════════════════════════════════════════
ESCENARIOS = [
    {
        "id": "cierre_completo",
        "desc": "saludo -> exploracion -> ambiguo(confirma) -> resuelve -> "
                "delta agrega -> delta cantidad -> zona+total -> datos+link",
        "turnos": [
            {"msg": "hola, buenas"},
            {"msg": "que teclados tenes?", "no_contiene": ["hola, ", "buenas!"]},
            {"msg": "dame el precio de 3 teclados, capaz inalambricos, no se "
                    "bien el color", "confirma": True},
            {"msg": "los 3 K380 negros", "total": True},
            {"msg": "sumale un mouse G203 negro", "total": True},
            {"msg": "mejor que sean 2 teclados", "total": True},
            {"msg": "lo quiero, el envio es a Cordoba Capital", "total": True,
             "no_contiene": ["3.000", "$3000"]},
            {"msg": "dale, soy Pedro Gomez, pago por transferencia"},
            {"msg": "mi telefono es 3511234567", "link": True},
        ],
    },
    {
        "id": "puentes_sin_dato",
        "desc": "cuando NO hay dato, el puente mantiene la venta y NO cae a fallback",
        "turnos": [
            {"msg": "hola"},
            {"msg": "hacen envoltorio para regalo?"},
            {"msg": "tenes una impresora 3d marca Zyltech rara que casi nadie "
                    "trae?"},
            {"msg": "y cuando exactamente me llega si compro hoy?"},
        ],
    },
    {
        "id": "memoria_entre_turnos",
        "desc": "la memoria arranca cada turno con el contexto ya dado; "
                "'cuanto era el total' no fabrica un numero de la nada",
        "turnos": [
            {"msg": "hola, busco un mouse gamer"},
            {"msg": "el G203 negro", "total": True},
            {"msg": "sumale un teclado K380 negro", "total": True},
            {"msg": "cuanto me queda en total?", "total": True},
        ],
    },
    # Los 3 mensajes largos de comprension (h01/h02/h03): un solo mensaje denso,
    # con varios aspectos a la vez. Cada uno con memoria limpia (primer mensaje).
    # Aserto duro minimo: no cae a fallback. El valor esta en LEER si responde
    # vendiendo y atiende todos los aspectos sin inventar.
    {
        "id": "h01_auriculares_desconfiado",
        "desc": "auriculares + desconfianza + ver antes + duda de pagos + "
                "santa ana (localidad ambigua) + precio por transferencia",
        "turnos": [
            {"msg": "Hola quiero auriculares pero que sean buenos compre unos "
                    "truchos no me duraron nada, son confiables ustedes me gusta "
                    "verlos antes de comprarlos desconfio de los medios de pago "
                    "tal vez ahora no confie, vivo en santa ana para aca a veces "
                    "no llegan los envios, espero me hagan precio si pago por "
                    "transferencia"},
        ],
    },
    {
        "id": "h02_tablet_no_china",
        "desc": "tablet + tiene plata + paga rapipago + no quiere china + precio",
        "turnos": [
            {"msg": "Hola tengo muca plata pa gastar en table pago con rapipago "
                    "no me venda chino dale haceme precio"},
        ],
    },
    {
        "id": "h03_parlantes_potentes",
        "desc": "parlantes potentes + decepcion previa + baratos + paga contado",
        "turnos": [
            {"msg": "quiero parlantes de esos que se escuchan de la otra cuadra "
                    "antes me compre unos y no se escuchan bien recomendame unos "
                    "baratos pago contado aca"},
        ],
    },
]


def _check(turno_cfg, texto, tele):
    """Devuelve (lista de fallas duras, lista de avisos blandos)."""
    fallas, avisos = [], []
    low = (texto or "").lower()

    for fb in _FALLBACKS:
        if fb and fb.lower() in low:
            fallas.append(f"cayo a fallback ('{fb[:30]}...')")
            break

    est_esp = turno_cfg.get("estado")
    if est_esp:
        est_esp = [est_esp] if isinstance(est_esp, str) else est_esp
        if tele.get("estado") not in est_esp:
            fallas.append(f"estado={tele.get('estado')} esperaba {est_esp}")

    for sub in turno_cfg.get("contiene", []):
        if sub.lower() not in low:
            fallas.append(f"falta '{sub}'")
    for sub in turno_cfg.get("no_contiene", []):
        if sub.lower() in low:
            fallas.append(f"no debia traer '{sub}'")

    if turno_cfg.get("confirma"):
        if not (tele.get("short_circuit") or "?" in (texto or "")):
            fallas.append("esperaba pregunta de confirmacion y no la hubo")

    if turno_cfg.get("total"):
        if not (tele.get("presupuesto_codigo") or tele.get("verdad")):
            fallas.append("esperaba total verificado por codigo y no lo hay")

    if turno_cfg.get("link"):
        if not _LINK_RE.search(texto or ""):
            avisos.append("no aparecio link (revisar MP_ACCESS_TOKEN / red)")

    return fallas, avisos


async def correr(escenarios, out_lines):
    def emitir(s=""):
        print(s)
        out_lines.append(s)

    total_fallas = 0
    for esc in escenarios:
        user = f"banco_cierre_{esc['id']}_{int(time.time())}"
        emitir("\n" + "=" * 72)
        emitir(f"ESCENARIO {esc['id']} — {esc['desc']}")
        emitir(f"  user={user} tienda={TIENDA}")
        emitir("=" * 72)
        for i, t in enumerate(esc["turnos"], 1):
            msg = t["msg"]
            t0 = time.time()
            try:
                resp = await process_message(
                    user_id=user, raw_message=msg, tienda_id=TIENDA,
                    canal="telegram")
            except Exception as e:
                emitir(f"\n[{i}] CLIENTE: {msg}")
                emitir(f"    ERROR: {type(e).__name__}: {e}")
                total_fallas += 1
                break
            tele = leer_turno(user)
            fallas, avisos = _check(t, resp, tele)
            dt = round(time.time() - t0, 1)
            emitir(f"\n[{i}] CLIENTE: {msg}")
            emitir(f"    BOT ({dt}s, etapa={tele.get('estado')}): {str(resp).strip()}")
            if avisos:
                emitir("    AVISO: " + " | ".join(avisos))
            if fallas:
                total_fallas += len(fallas)
                emitir("    FALLA: " + " | ".join(fallas))
            else:
                emitir("    ok")
            await asyncio.sleep(float(os.getenv("BANCO_PAUSA", "0.6")))

    emitir("\n" + "=" * 72)
    veredicto = "VERDE — sin fallas duras" if total_fallas == 0 else \
        f"ROJO — {total_fallas} fallas duras"
    emitir(f"RESULTADO: {veredicto}")
    emitir("=" * 72)
    return total_fallas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", default=None, help="id de un escenario")
    args = ap.parse_args()
    escenarios = ESCENARIOS
    if args.solo:
        escenarios = [e for e in ESCENARIOS if e["id"] == args.solo]
        if not escenarios:
            print(f"No existe el escenario '{args.solo}'. Hay: "
                  f"{[e['id'] for e in ESCENARIOS]}")
            sys.exit(1)

    print(f"\n=== BANCO DE CIERRE — sistema real (process_message) ===")
    print(f"    solver={settings.LLM_PROVIDER} modelo={settings.DEEPSEEK_MODEL} "
          f"interprete={settings.INTERPRETER_PROVIDER}")

    out_lines = []
    fallas = asyncio.run(correr(escenarios, out_lines))

    rep = ROOT / "reports" / f"cierre_{settings.LLM_PROVIDER}.txt"
    rep.parent.mkdir(exist_ok=True)
    rep.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"\n[banco_cierre] reporte -> {rep}")
    sys.exit(1 if fallas else 0)


if __name__ == "__main__":
    main()
