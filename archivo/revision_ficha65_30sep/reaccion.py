"""Como reacciona el modelo a lo que vuelve de una herramienta, segun como se redacta. Scratch."""
import json, sys
sys.path.insert(0, "/home/user/Verifika")
from banco_pruebas import clon_produccion
clon_produccion.preparar_entorno(); clon_produccion.instalar()
import logging; logging.disable(logging.CRITICAL)
from app.core import agente as A
from app.core.llm_reintento import _cliente, _modelo
from concurrent.futures import ThreadPoolExecutor

T = "verifika_prod"
cli, mod = _cliente(), _modelo()
SIS, ESQ = A.sistema(T), A.esquema(T)
REPS = 5

def paso(mensaje, llamada, vuelve):
    """El modelo hace su primera llamada de verdad; la herramienta devuelve `vuelve`. ¿Que hace despues?"""
    msgs = [{"role": "system", "content": SIS}, {"role": "user", "content": mensaje}]
    r = cli.chat.completions.create(model=mod, messages=msgs, temperature=0.2, tools=ESQ, tool_choice="auto")
    m = r.choices[0].message
    if not m.tool_calls:
        return {"primera": None, "calls": [], "texto": (m.content or "")[:300]}
    primera = [(c.function.name, c.function.arguments) for c in m.tool_calls]
    msgs.append({"role": "assistant", "content": m.content or "", "tool_calls": [c.model_dump() for c in m.tool_calls]})
    for c in m.tool_calls:
        msgs.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(vuelve, ensure_ascii=False)})
    r = cli.chat.completions.create(model=mod, messages=msgs, temperature=0.2, tools=ESQ, tool_choice="auto")
    m = r.choices[0].message
    calls = [(c.function.name, c.function.arguments) for c in (m.tool_calls or [])]
    return {"primera": primera, "calls": calls, "texto": (m.content or "")[:300]}


PARL = ("buscar", {"rubro": "parlante", "condiciones": [{"campo": "caracteristicas_extra", "operador": "contiene", "valor": "resistente al agua"}]})
MON = ("buscar", {"rubro": "monitor"})
filas_mon = A.h_buscar(T, rubro="monitor")
filas_mon.pop("es_una_muestra", None)

E = {
 # E1: el aviso de pedido mal escrito
 "e1_actual": ("busco un parlante que se pueda mojar", PARL,
               {"no_cierra": ["en parlante, caracteristicas_extra no dice 'resistente al agua'; ahi la fuente escribe: 2.0 | 2.1"],
                "que_hacer": "corregi el pedido con esto y volve a llamar"}),
 "e1_meta": ("busco un parlante que se pueda mojar", PARL,
             {"pedido_mal_escrito": "caracteristicas_extra no guarda eso en parlantes. Esto NO es un dato del producto: no se lo digas al cliente. Volve a llamar buscar con otro dato."}),
 "e1_sugerencia": ("busco un parlante que se pueda mojar", PARL,
             {"pedido_mal_escrito": "caracteristicas_extra no guarda eso en parlantes. Esto NO es un dato del producto: no se lo digas al cliente.",
              "proba_con": {"campo": "resistencia_agua", "operador": "igual", "valor": "si"}}),
 # E2: la muestra, segun como se nombre
 "e2_nada": ("cual es el monitor mas grande que tengan", MON, filas_mon),
 "e2_muestra": ("cual es el monitor mas grande que tengan", MON, {**filas_mon, "es_una_muestra": f"5 de {filas_mon.get('cuantos_habia')}, sin ordenar: no sirve para decir cual es el mas o el menos de algo, ni que no haya otros"}),
 "e2_mostradas": ("cual es el monitor mas grande que tengan", MON, {**filas_mon, "orden": "ninguno", "filas_mostradas": f"5 de {filas_mon.get('cuantos_habia')}"}),
}

def una(item):
    k, (msg, ll, v) = item
    return k, [paso(msg, ll, v) for _ in range(REPS)]

with ThreadPoolExecutor(6) as ex:
    res = dict(ex.map(una, E.items()))
json.dump(res, open("/tmp/claude-0/-home-user-Verifika/9485093e-efa9-58bd-a799-27a093938332/scratchpad/reaccion.json", "w"), ensure_ascii=False, indent=1)
for k, v in res.items():
    print("=====", k)
    for x in v:
        print("   1ra:", [(n, a[:90]) for n, a in (x["primera"] or [])], "\n      luego:", [(n, a[:110]) for n, a in x["calls"]], "| texto:", x["texto"].replace("\n", " ")[:170])
