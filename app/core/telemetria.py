"""
TELEMETRIA DE TURNO — registro en memoria del ultimo process_message.

Flag TELEMETRIA_TURNO. El orchestrator escribe aca un resumen chico del turno
(que tools corrieron, con que args, cuantos resultados devolvieron, estado y
outcome) y los molinos lo leen para volcarlo al CSV. Responde la pregunta que
los logs dispersos no responden rapido: ¿el modelo NO llamo la tool, o la
llamo y el resultado se perdio en el camino?

Solo memoria de proceso. No persiste, no toca red, no suma tokens.
"""
import json
import re
import threading

_lock = threading.Lock()
_ultimo_turno: dict = {}
# Telemetria por usuario, para molinos que corren conversaciones en paralelo.
# Acotado: los molinos usan decenas de user_id, no crece sin limite.
_por_usuario: dict[str, dict] = {}


def _contar_resultados(result) -> int | None:
    """Mejor esfuerzo: cuantos items devolvio la tool. None si no aplica."""
    if not isinstance(result, dict):
        return None
    if "encontrados" in result:
        try:
            return int(result["encontrados"])
        except (TypeError, ValueError):
            pass
    for v in result.values():
        if isinstance(v, list):
            return len(v)
    return None


def registrar_turno(tools_called: list[dict], estado: str | None = None,
                    outcome: str | None = None,
                    presupuesto_codigo: bool = False,
                    short_circuit: bool = False,
                    verdad: str | None = None,
                    user_id: str | None = None) -> None:
    """Guarda el resumen del turno recien procesado. Pisa el anterior."""
    resumen = []
    for t in tools_called or []:
        try:
            raw = json.dumps(t.get("result"), ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            raw = str(t.get("result"))
        args_full = json.dumps(t.get("args") or {}, ensure_ascii=False)
        resumen.append({
            "tool": t.get("name"),
            "args": args_full[:120],
            "n": _contar_resultados(t.get("result")),
            "raw": raw[:4000],
            # Numeros del resultado COMPLETO (el raw se trunca): el arnes los
            # usa como fuente para validar que los montos esten respaldados.
            "nums": sorted(set(re.findall(r"\d[\d\.,]*", raw)))[:300],
            # IDs de producto de los ARGS completos (args se trunca a 120):
            # el arnes los usa para auditar que el carrito no mute de identidad.
            "ids": re.findall(r'"product_id":\s*"([^"]+)"', args_full),
        })
    datos = {
        "tools": resumen,
        "estado": estado,
        "outcome": outcome,
        "presupuesto_codigo": presupuesto_codigo,
        "short_circuit": short_circuit,
        "verdad": verdad,
    }
    with _lock:
        _ultimo_turno.clear()
        _ultimo_turno.update(datos)
        if user_id:
            _por_usuario[user_id] = datos


def leer_turno(user_id: str | None = None) -> dict:
    """Resumen del ultimo turno (copia). Con user_id, el de ESE usuario:
    necesario cuando el molino corre conversaciones en paralelo."""
    with _lock:
        if user_id:
            return dict(_por_usuario.get(user_id, {}))
        return dict(_ultimo_turno)


def tools_compacto(user_id: str | None = None) -> str:
    """Una linea legible para el CSV: tool(args)=n | tool(args)=n."""
    t = leer_turno(user_id)
    if not t:
        return ""
    partes = [f"{x['tool']}({x['args']})={x['n']}" for x in t.get("tools", [])]
    pre = []
    if t.get("short_circuit"):
        pre.append("short_circuit")
    if t.get("presupuesto_codigo"):
        pre.append("presupuesto_codigo")
    cuerpo = " | ".join(partes) if partes else "SIN_TOOLS"
    return (" ".join(pre) + " " if pre else "") + cuerpo
