"""Prueba el atajo de saludo (flag SALUDO_DIRECTO) a nivel orchestrator.

Sin Firestore ni DeepSeek: parchea el interpretador (devuelve lo que queremos
probar), las lecturas/escrituras de Firestore y espia al Solver para confirmar
si fue llamado o no.

Garantiza tres cosas:
  1. saludo de alta confianza + flag ON  -> NO llama al Solver, responde saludo.
  2. consulta comercial (pregunta_especifica) + flag ON -> SI llama al Solver.
  3. saludo de alta confianza + flag OFF -> SI llama al Solver (sin atajo).
Asi probamos que el atajo no se mete donde no debe y que apagado no cambia nada.
"""
import os
import sys
import asyncio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ["USE_INTERPRETER"] = "true"
os.environ["USE_LEADS"] = "false"
os.environ["USE_VERIFIKA"] = "false"
os.environ["VERIFICADOR_MODE"] = "off"

import app.core.orchestrator as O

# ─── Espia del Solver: registra si fue invocado, sin pegar a DeepSeek ───
_solver_llamado = {"n": 0}


async def _fake_run_agent(mensaje, history, trace_id, tienda_id=None,
                          user_id=None):
    _solver_llamado["n"] += 1
    return "(respuesta del solver real)", {"tools_called": [], "iterations": 1}


# ─── Parches de Firestore: nada de red ───
O.run_agent = _fake_run_agent
O.get_conversation = lambda user_id, tienda_id=None: {
    "history": [], "estado_conversacion": "saludo",
    "proofs_recientes": [], "ultimo_presupuesto": ""}
O.save_conversation = lambda *a, **k: None
O.log_message = lambda *a, **k: None
# El guardian y la evidencia tocan Firestore; los parcheamos porque acá solo
# nos importa si el Solver fue invocado, no su validacion.
O.validate_response = lambda *a, **k: {"is_clean": True}
O.clean_response = lambda resp, **k: resp
O.get_all_products = lambda *a, **k: []
O.get_all_faq = lambda *a, **k: {}


def _interp(intencion, confianza):
    async def _fake(mensaje, history, trace_id, estado_anterior=None):
        return {"intencion": intencion, "confianza": confianza,
                "producto_resuelto": None, "candidatos": [],
                "estado_conversacion": "saludo", "ofrecer_opciones": None}
    return _fake


async def correr(nombre, flag, intencion, confianza, espera_solver):
    O.settings.SALUDO_DIRECTO = flag
    O.interpretar_mensaje = _interp(intencion, confianza)
    _solver_llamado["n"] = 0
    resp = await O.process_message("u1", "hola buenas", tienda_id="verifika_demo")
    llamo_solver = _solver_llamado["n"] > 0
    ok = llamo_solver == espera_solver
    print(f"  [{'OK' if ok else 'FALLA'}] {nombre}")
    print(f"        flag={flag} intencion={intencion} conf={confianza} "
          f"solver_llamado={llamo_solver} (esperado {espera_solver})")
    print(f"        resp: {resp[:70]}")
    return ok


async def main():
    print("\n=== ATAJO DE SALUDO: no perder efectividad ===\n")
    r = []
    # 1) saludo alta confianza + ON -> atajo, NO solver
    r.append(await correr("saludo alta conf + ON -> sin Solver",
                          True, "saludo", 0.95, espera_solver=False))
    # 2) consulta comercial + ON -> Solver corre igual (atajo no se mete)
    r.append(await correr("consulta comercial + ON -> con Solver",
                          True, "pregunta_especifica", 0.95, espera_solver=True))
    # 3) saludo baja confianza + ON -> no alcanza el umbral, Solver corre
    r.append(await correr("saludo baja conf + ON -> con Solver",
                          True, "saludo", 0.5, espera_solver=True))
    # 4) saludo alta confianza + OFF -> sin atajo, Solver corre (default)
    r.append(await correr("saludo alta conf + OFF -> con Solver",
                          False, "saludo", 0.95, espera_solver=True))
    print(f"\n  Total: {len(r)} casos, {r.count(False)} fallas\n")


if __name__ == "__main__":
    asyncio.run(main())
