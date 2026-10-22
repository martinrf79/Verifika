"""Jev elige: acciones del menu, secciones de la libreta, a que senala y si contesta lo abierto. Vara: agendas58."""
import json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "/home/user/Verifika")
from app.core.flujo.agenda import ACCIONES, referencias, preguntas
AQUI = os.path.dirname(os.path.abspath(__file__))
T = [json.loads(l) for l in open(os.path.join(AQUI, "turnos.jsonl"))]
DESC = {"buscar": "busca productos sin un modelo concreto, por rubro, marca, precio u orden",
        "producto": "pregunta precio, stock, color o un dato de un producto concreto, nombrado o senalado",
        "envio": "pregunta cuanto sale o cuanto tarda el envio a un lugar",
        "cuenta": "pide el total, un presupuesto, o dice como reparte el pago",
        "politica": "pregunta una regla de la tienda: factura, garantia, cuotas, devoluciones, promociones",
        "compatibilidad": "pregunta si un producto anda con un equipo o con otra cosa",
        "comprar": "decide llevar algo, arma, cambia, saca o confirma el pedido",
        "explicar": "pregunta un saber general de tecnologia, no de la tienda",
        "otro": "saluda, da un dato de si mismo, corrige lo que dijo, pide un humano o habla de otra cosa"}
SECC = {"MOSTRADO": "la lista de productos que el vendedor ya le mostro",
        "BORRADOR": "el pedido que el cliente viene armando, con sus renglones",
        "ABIERTO": "lo que el vendedor le pregunto y el cliente no contesto",
        "BUSCO": "la ultima busqueda y sus condiciones"}

def estado(t):
    return f"{t['libreta']}\n\nULTIMO MENSAJE DEL CLIENTE: {t['mensaje']}"

def oro(t):
    ps = preguntas(t["agenda"]); acc = {p["accion"] for p in ps}
    refs = {r for p in ps for r in referencias(p)}
    sec = set()
    if any(r[0] == "M" for r in refs) or any(p.get("entre_lo_mostrado") for p in ps): sec.add("MOSTRADO")
    if any(r[0] == "L" for r in refs) or any(p["accion"] == "comprar" and any(p.get(k) for k in ("saca","cambia","confirma","acepta","total","reemplaza")) for p in ps) \
       or ("cuenta" in acc and "BORRADOR" in t["libreta"]): sec.add("BORRADOR")
    if any(p.get("responde") for p in ps): sec.add("ABIERTO")
    return acc, sec, refs

def preguntas_jev(t):
    q = {f"a_{a}": {"type": "noul", "instructions": f"En el ULTIMO MENSAJE el cliente {d}? Mira solo el ultimo mensaje; la libreta es contexto."} for a, d in DESC.items()}
    for s, d in SECC.items():
        if f"- {s}" in t["libreta"]:
            q[f"s_{s}"] = {"type": "noul", "instructions": f"Para entender que pide el ULTIMO MENSAJE, hace falta leer la seccion {s} de la libreta, {d}?"}
    nums = {k: v for k, v in t["numeros"].items() if k[0] in "ML"}
    if nums:
        crit = {k: (re.search(rf"^\s*{k} (.*)$", t["libreta"], re.M) or [None, v])[1][:120] for k in nums}
        crit["ninguno"] = "el ultimo mensaje no senala nada de la libreta"
        q["ref"] = {"type": "choice", "criteria": crit, "instructions": "A que producto mostrado (M) o renglon del pedido (L) de la libreta senala el ULTIMO MENSAJE? Si nombra un producto nuevo o no senala nada, ninguno."}
    for k in t["numeros"]:
        if k[0] == "R":
            q[f"r_{k}"] = {"type": "noul", "instructions": f"El ULTIMO MENSAJE contesta la pregunta abierta {k} del vendedor?"}
    return q

def llamar(body):
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"].strip(), "Content-Type": "application/json"})
    for i in range(5):
        try: return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < 4: time.sleep(3 * 2 ** i); continue
            raise

def uno(i):
    t = T[i]; t0 = time.time()
    r = llamar({"state": estado(t), "model": "jev-latest", "questions": preguntas_jev(t)})
    return {"i": i, "charla": t["charla"], "turno": t["turno"], "ans": r["answers"], "tok": r["usage"]["input_tokens"], "ms": int((time.time()-t0)*1000)}

if __name__ == "__main__":
    out = os.path.join(AQUI, "jev_resp.jsonl")
    with ThreadPoolExecutor(6) as ex, open(out, "w") as f:
        for x in ex.map(uno, range(len(T))): f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print("ok")
