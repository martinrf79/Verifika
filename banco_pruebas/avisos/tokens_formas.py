"""El mismo contenido en cuatro formas, contado con el contador de tokens del modelo de produccion, que es gratis.

  python3 banco_pruebas/avisos/tokens_formas.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contexto  # prepara el entorno: claves y fuente
import httpx
from banco_pruebas.agendas58 import AGENDAS
from app.core.flujo import agenda as A
from app.config import get_settings

KEY = os.environ["GEMINI_API_KEY"]
MODELO = get_settings().GEMINI_MODEL

def contar(texto):
    r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:countTokens?key={KEY}",
                   json={"contents": [{"parts": [{"text": texto}]}]}, timeout=60)
    r.raise_for_status()
    return r.json()["totalTokens"]

def _v(v):
    return json.dumps(v, ensure_ascii=False)

# ── las cuatro formas de una agenda ──
def a_json(ag):
    return json.dumps(ag, ensure_ascii=False)

def a_python(ag):
    out = []
    for p in ag["preguntas"]:
        args = ", ".join(f"{k}={_v(v)}" for k, v in p.items() if k not in ("n", "accion"))
        out.append(f"p{p['n']} = {p['accion']}({args})")
    for k, v in (ag.get("cliente") or {}).items():
        out.append(f"cliente({k}={_v(v)})")
    return "\n".join(out)

def _lista(a):
    partes = [str(a.get("cantidad", 1)), str(a.get("producto", ""))]
    if a.get("color"): partes.append(a["color"])
    if a.get("destino"): partes += ["para", a["destino"]]
    return " ".join(partes)

def _si(p):
    s = p.get("si")
    return f"si {s['de']} da {s['da']}: " if s else ""

def a_controlado(ag):
    out = []
    for p in ag["preguntas"]:
        a, s = p["accion"], _si(p)
        if a == "buscar":
            t = f"buscar {p['rubro']}" + (f", {p['cantidad']}" if p.get("cantidad", 1) != 1 else "") \
                + (f", {p['orden']}" if p.get("orden") not in (None, "nada") else "") \
                + "".join(f", {c}" for c in p.get("condiciones") or []) + (", entre lo mostrado" if p.get("entre_lo_mostrado") else "")
        elif a == "producto":
            pr = p["producto"] if isinstance(p["producto"], str) else " o ".join(p["producto"])
            t = f"consultar {p.get('quiere_saber','precio')} de {pr}" + (f" en {p['color']}" if p.get("color") else "")
        elif a == "envio": t = f"cotizar envio a {p['destino']}"
        elif a == "cuenta":
            t = "sumar el pedido" + (f", tope {p['tope']}" if p.get("tope") else "") + "".join(
                f", {r['porcentaje']}% {r['medio']}" for r in p.get("reparto") or [])
        elif a == "politica": t = f"regla {p['tema']}" + (f", afirma {p['afirma']}" if p.get("afirma") else "")
        elif a == "compatibilidad": t = f"compatible {p['producto']} con {p.get('con','')}"
        elif a == "comprar":
            t = "; ".join([f"anotar {_lista(x)}" for x in p.get("agrega") or []]
                          + [f"cambiar {c.get('es')} " + " ".join(f"{k} {v}" for k, v in c.items() if k != "es") for c in p.get("cambia") or []]
                          + [f"sacar {x}" for x in p.get("saca") or []] + [f"confirmar {x}" for x in p.get("confirma") or []]) or "rehacer el pedido"
            if p.get("reemplaza"): t = "rehacer el pedido: " + t
        elif a == "explicar": t = f"explicar {p['pregunta']}"
        else: t = f"otro: {p['que']}"
        out.append(f"{p['n']}. {s}{t}")
    return "\n".join(out)

def a_comun(ag):
    """Espanol comun: lo mismo dicho como lo diria una persona."""
    frases = []
    for linea in a_controlado(ag).splitlines():
        n, t = linea.split(". ", 1)
        frases.append(f"En la parte {n} del mensaje, el cliente quiere que el sistema haga lo siguiente: {t}.")
    return " ".join(frases)

agendas = [ag for c in AGENDAS.values() for ag in c]
formas = {"JSON": a_json, "espanol comun": a_comun, "espanol controlado": a_controlado, "Python": a_python}
print(f"SALIDA: las {len(agendas)} agendas a mano de la vara")
base = None
for n, f in formas.items():
    t = contar("\n\n".join(f(a) for a in agendas))
    base = base or t
    print(f"  {n:20} {t:6} tokens  {t/len(agendas):6.1f} por turno  {t/base:5.2f} del JSON")

# ── el menu de herramientas en cuatro formas ──
menu = A.ACCIONES
m_json = json.dumps({"herramientas": menu}, ensure_ascii=False)
m_comun = "\n".join(f"Para {k}: {v}" for k, v in menu.items())
m_controlado = "\n".join(f"- {k}: {v}" for k, v in menu.items())
m_python = "\n\n".join(f"def {k}(**datos):\n    \"\"\"{v}\"\"\"" for k, v in menu.items())
print("ENTRADA: el menu de herramientas")
b = None
for n, t in {"JSON": m_json, "espanol comun": m_comun, "espanol controlado": m_controlado, "Python": m_python}.items():
    k = contar(t); b = b or k
    print(f"  {n:20} {k:6} tokens  {k/b:5.2f} del JSON")

# ── la memoria de una charla compleja en cuatro formas ──
x = contexto.contexto("K21", 3, uid="tok")
lib = x["entrada"].split("LO QUE EL CODIGO RECONOCIO")[0]
e = x["estado"]
datos = {"mostrados": [m.get("nombre") for m in e["mostrados"]], "borrador": e.get("borrador"), "busqueda": e.get("busqueda"),
         "abiertas": e.get("abiertas")}
l_json = json.dumps(datos, ensure_ascii=False, default=str)
l_python = "estado = " + repr(datos)
print("ENTRADA: la memoria de K21, turno 4")
b = None
for n, t in {"JSON del estado": l_json, "libreta de hoy, espanol controlado": lib, "Python del estado": l_python}.items():
    k = contar(t); b = b or k
    print(f"  {n:36} {k:6} tokens  {k/b:5.2f} del JSON")
