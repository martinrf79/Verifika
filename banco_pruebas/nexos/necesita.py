"""Paso 1: a cada modelo, que necesita para contestar. Paso 2 en otro archivo."""
import json, os, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
EXP = os.path.dirname(os.path.abspath(__file__))
G, D = "gemini-3.1-flash-lite", "deepseek-chat"
CASOS = [("K01","grab_1",1),("K02","grab_1",1),("K07","grab_1",1),("K08","grab_1",1),("K09","grab_1",1),
         ("K12","grab_1",2),("K18","grab_1",1),("K19","grab_1",1),("K17","grab_1",3),("K10","grab_1",8),
         ("G04","grab_ds_g1",6),("G06","grab_ds_g1",9),("G07","grab_ds_g1",9)]
lock = threading.Lock()

def cli(m):
    if "deepseek" in m:
        from banco_pruebas import libro_paga
        libro_paga.puede()
        return libro_paga.envolver(OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"].strip(), base_url="https://api.deepseek.com"))
    if os.environ.get("BANCO_CLAVE_PAGA", "").lower() == "true":  # Martin la pidio en esta sesion, 4-oct
        from banco_pruebas import libro_paga
        libro_paga.puede()
        return libro_paga.envolver(OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD"].strip(),
                                          base_url="https://generativelanguage.googleapis.com/v1beta/openai/"))
    k = os.environ["GEMINI_API_KEY"].split()[0]
    assert k != os.environ.get("GEMINI_API_KEY_PROD","").strip(), "solo gratis"
    return OpenAI(api_key=k, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

def llamar(m, msgs, temp=0.2):
    espera = 15
    for i in range(7):
        try:
            if "gemini" in m:
                with lock: time.sleep(4.5)
            r = cli(m).chat.completions.create(model=m, messages=msgs, temperature=temp)
            return r.choices[0].message.content or ""
        except Exception as e:
            if i < 6 and any(x in str(e) for x in ("429","503","500","RESOURCE","overloaded","timed out")):
                time.sleep(espera); espera = min(espera*2, 120); continue
            raise

def charla(cid, et, n):
    filas = [json.loads(x) for x in open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "banco_pruebas", "sonda_charlas_corridas.jsonl"))]
    f = next(x for x in filas if x["etiqueta"] == et and x["id"] == cid)
    out = []
    for t in f["turnos"][:n-1]:
        out.append(f"CLIENTE: {t['texto']}")
        out.append(f"VENDEDOR: {t['respuesta']}")
    out.append(f"CLIENTE (ultimo mensaje): {f['turnos'][n-1]['texto']}")
    return "\n\n".join(out)

PIDE = ("Sos el vendedor de una tienda online de tecnologia de Argentina. Abajo esta la charla con un cliente. "
        "TODAVIA NO LE CONTESTES. Vos no tenes acceso al catalogo ni a las politicas: el sistema de la tienda te va a "
        "pasar los datos que le pidas, y nada mas. Decime que informacion exacta necesitas que te pase el sistema "
        "para contestar bien y completo el ULTIMO mensaje del cliente. Una linea por dato, con el criterio exacto "
        "para buscarlo (por ejemplo: 'los 2 mouse mas baratos con stock, con nombre, precio y stock'). Incluí tambien "
        "lo que necesitas recordar de la charla, dicho en concreto. Solo la lista.")

if __name__ == "__main__":
    out = {}
    def una(c, m):
        cid, et, n = c
        ch = charla(cid, et, n)
        r = llamar(m, [{"role":"system","content":PIDE},{"role":"user","content":ch}])
        return f"{cid}_t{n}", m, ch, r
    with ThreadPoolExecutor(6) as ex:
        futs = [ex.submit(una, c, m) for c in CASOS for m in (G, D)]
        for f in futs:
            k, m, ch, r = f.result()
            out.setdefault(k, {"charla": ch})[m] = r
            print("listo", k, m, flush=True)
    json.dump(out, open(f"{EXP}/pedidos.json","w"), ensure_ascii=False, indent=1)
