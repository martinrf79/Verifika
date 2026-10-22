"""Calibrar la PRIMERA VUELTA de Gemini (mensaje limpio) con Jev encima.
Fase A: tres consignas en 30 casos dificiles. Se mide: perdida (pedazos sin renglon), invento (montos o modelos que no estan
en el mensaje ni en la libreta) y si Jev, leyendo cada renglon, trae los rubros y reglas correctos (top2 rubros, top3 reglas).
Fase B: la mejor consigna, y Jev baja al nivel 2: campos (top3) y productos (top5) del rubro.
Lo correcto: la agenda a mano de agendas58, resuelta con el codigo de la tienda. Tope de la paga por corrida: TOPE_USD."""
import asyncio, json, os, sys, random, re, collections
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
REPO = "/home/user/Verifika"; sys.path.insert(0, REPO); os.chdir(REPO)
from banco_pruebas import clon_produccion as C
C.preparar_entorno(); C.instalar()
from app.core import llm_reintento
puerta = llm_reintento._cliente
from app.core.flujo import interprete, agenda as A
import indice_jev as I
from fuente import PS, K
from sondas2 import llamar as jev_llamar, GASTO
from sondas import rank
from calibrar import oro as oro_pregunta
from banco_pruebas.agendas58 import AGENDAS
from banco_pruebas import libro_paga
llm_reintento._cliente = puerta
OUT = os.path.join(D, "vuelta1.jsonl"); TOPE_USD = 0.10

RUBROS_TXT = ", ".join(I.NOMBRE.get(r, r) for r in I.RUBROS)
BASE = """Sos el primer paso del interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente.
Reescribi el ULTIMO MENSAJE del cliente como renglones: uno por cada cosa que pide, pregunta, decide o dice, en su orden.
Cada renglon con "cita", las palabras literales del cliente, y "limpio", lo mismo dicho en castellano claro y completo.
Todo el mensaje queda citado. Lo que senala de la charla -"ese", "el segundo", "lo de antes", "de cada uno"- lo decis
en palabras con lo que dice la LIBRETA. No agregues precios, montos, productos ni datos que no esten en el mensaje o en la libreta.
Devolve SOLO el JSON: {"renglones": [{"cita": "...", "limpio": "..."}]}"""
VARIANTES = {
    "v1": BASE,
    "v2": BASE + f"\nNombra cada producto con el rubro de la tienda que corresponde. RUBROS: {RUBROS_TXT}.",
    "v3": BASE + f"\nNombra cada producto con el rubro de la tienda que corresponde. RUBROS: {RUBROS_TXT}.\n"
          "Lo que pide de un producto -que sea inalambrico, de tal origen, para tal uso, tal color, tal precio- va en el mismo "
          "renglon del producto, dicho como condicion. Si una cosa depende de otra -\"si no hay\", \"si anda\"- decilo en el renglon.",
}
VARIANTES["v4"] = VARIANTES["v3"] + ("\nSi dice \"de cada uno\", \"de cada clase\", \"todo\", \"lo demas\" o \"los otros\", nombra en el renglon cada "
    "producto o rubro de la LIBRETA al que se refiere, uno por uno.")

def oro_turno(cid, t):
    g = {"rubros": set(), "temas": set(), "campos": collections.defaultdict(set), "prods": []}
    for p in A.preguntas(AGENDAS[cid][t]):
        o = oro_pregunta(p)
        if o["rubro"]: g["rubros"].add(o["rubro"]); g["campos"][o["rubro"]] |= o["campos"]
        if o["tema"]: g["temas"].add(o["tema"])
        if o["prods"]: g["prods"].append((o["rubro"], o["prods"]))
        for x in (p.get("agrega") or []) if p.get("accion") == "comprar" else []:
            if not (isinstance(x, dict) and isinstance(x.get("producto"), str)) or x["producto"][:2] in ("M-", "L-"): continue
            if x["producto"] in I.RUBROS: g["rubros"].add(x["producto"]); continue
            o = oro_pregunta({"accion": "producto", "producto": x["producto"], "color": x.get("color")})
            if o["rubro"]: g["rubros"].add(o["rubro"])
            if o["prods"]: g["prods"].append((o["rubro"], o["prods"]))
    return g

def _montos(t):
    t = re.sub(r"(\d+)\s*(mil|lucas|k)\b", lambda m: str(int(m.group(1)) * 1000), K.n(t))
    return interprete._plata_en(t)
def invento(limpio, mensaje, libreta):
    plata = _montos(limpio) - _montos(mensaje + " " + libreta)
    base = K.n(mensaje + " " + libreta)
    mods = {K.n(p.get("modelo")) for p in PS if len(K.n(p.get("modelo"))) > 3}
    nuevos = [m for m in mods if re.search(rf"\b{re.escape(m)}\b", K.n(limpio)) and m not in base]
    return sorted(plata), nuevos

def primera(var, mensaje, libreta):
    msgs = [{"role": "system", "content": VARIANTES[var]}, {"role": "user", "content": f"{libreta}\nULTIMO MENSAJE: {mensaje}"}]
    return interprete._json(asyncio.run(interprete._pedir(msgs, "", {"type": "json_object"})))

def jev1(renglon, libreta):
    q = {f"r_{r}": {"type": "noul", "instructions": f"El RENGLON pide o nombra productos del rubro {I.NOMBRE.get(r, r)}?"} for r in I.RUBROS}
    q["tema"] = {"type": "choice", "criteria": {f["tema"]: I.desc_tema(f) for f in I.FAQ} | {"ninguno": "no pregunta una regla de la tienda"}, "instructions": "Que regla de la tienda pregunta el RENGLON?"}
    a = jev_llamar({"state": I.nivel1() + f"\n\n{libreta}\n\nRENGLON DEL CLIENTE: {renglon}", "model": "jev-latest", "questions": q}, "vuelta1_n1")["answers"]
    rub = sorted(I.RUBROS, key=lambda r: -a[f"r_{r}"]["noul"])
    return {"rubros": [r for r in rub if a[f"r_{r}"]["noul"] >= .5] or [r for r in rub[:2] if a[f"r_{r}"]["noul"] >= .3] or rub[:1], "temas": [t for t in rank(a["tema"])[:3] if t != "ninguno"]}

def jev2(renglon, rubro, libreta):
    vs = I.valores(rubro)
    q = {f"c_{k}": {"type": "noul", "instructions": f"El RENGLON pide o pone como condicion {(I.SPECS.get(k) or {}).get('etiqueta', k.replace('_', ' '))}?"} for k in vs}
    q["prod"] = {"type": "choice", "criteria": {str(x["id"]): f"{x['nombre']} ${K.entero(x.get('precio_ars'))}" for x in PS if x["categoria"] == rubro}, "instructions": "Que producto de la tienda nombra o le conviene al RENGLON?"}
    b = jev_llamar({"state": I.nivel2(rubro) + f"\n\n{libreta}\n\nRENGLON DEL CLIENTE: {renglon}", "model": "jev-latest", "questions": q}, "vuelta1_n2")["answers"]
    return {"campos": sorted(vs, key=lambda k: -b[f"c_{k}"]["noul"])[:3], "prods": rank(b["prod"])[:5]}

def casos():
    T = {(t["charla"], t["turno"]): t for t in map(json.loads, open(os.path.join(D, "turnos.jsonl")))}
    base = {tuple(json.loads(k)[1:]): v for k, v in json.load(open(os.path.join(D, "base_prod.json"))).items()}
    G = {}
    for l in open("banco_pruebas/traduccion58_corridas.jsonl"):
        x = json.loads(l)
        if (x.get("modelo") or "prod") == "prod" and not x.get("rep"): G[(x["charla"], x["turno"], x["forma"])] = x["texto"]
    fallan = sorted(k for k, v in base.items() if not v["bien"])
    dificiles = sorted(k for k in base if base[k]["bien"] and len(A.preguntas(AGENDAS[k[0]][k[1]])) >= 3 and k[2] in ("coloquial", "whatsapp", "redactada"))
    random.Random(3).shuffle(dificiles)
    return [(k, G[k], T[(k[0], k[1])]["libreta"]) for k in fallan + dificiles[:17]]

def fase(var, nivel2):
    hechos = {(x["var"], tuple(x["k"]), x["n2"]) for x in map(json.loads, open(OUT))} if os.path.exists(OUT) else set()
    g0 = libro_paga.hoy()
    for k, texto, lib in casos():
        if (var, k, nivel2) in hechos: continue
        if libro_paga.hoy() - g0 > TOPE_USD: print("TOPE"); break
        sal = primera(var, texto, lib); rs = [r for r in sal.get("renglones") or [] if isinstance(r, dict)]
        perdido = A.sin_citar(texto, {"preguntas": [{"cita": r.get("cita", "")} for r in rs]})
        inv = [invento(r.get("limpio", ""), texto, lib) for r in rs]
        sel = [jev1(r.get("limpio", ""), lib) for r in rs]
        g = oro_turno(k[0], k[1]); rub = set().union(*[set(s["rubros"]) for s in sel]) if sel else set(); tem = set().union(*[set(s["temas"]) for s in sel]) if sel else set()
        x = {"var": var, "k": k, "n2": nivel2, "texto": texto, "renglones": rs, "perdido": perdido, "invento": [i for i in inv if i[0] or i[1]],
             "rub_oro": sorted(g["rubros"]), "rub_ok": sorted(g["rubros"] & rub), "rub_mas": sorted(rub - g["rubros"]), "tem_oro": sorted(g["temas"]), "tem_ok": sorted(g["temas"] & tem)}
        if nivel2:
            camp_ok = camp_n = prod_ok = prod_n = 0
            for r in g["rubros"]:
                rr = [rs[i].get("limpio", "") for i, s in enumerate(sel) if r in s["rubros"]]
                got = [jev2(t, r, lib) for t in rr]
                cs = set().union(*[set(x2["campos"]) for x2 in got]) if got else set(); ps = set().union(*[set(x2["prods"]) for x2 in got]) if got else set()
                camp_n += len(g["campos"][r]); camp_ok += len(g["campos"][r] & cs)
                for rb, ids in g["prods"]:
                    if rb == r: prod_n += 1; prod_ok += bool(ids & ps)
            x.update(camp=[camp_ok, camp_n], prod=[prod_ok, prod_n])
        with open(OUT, "a") as o: o.write(json.dumps(x, ensure_ascii=False) + "\n")
        print(f"{var} {k}: renglones {len(rs)} perdido {len(perdido)} invento {len(x['invento'])} rubros {len(x['rub_ok'])}/{len(x['rub_oro'])} (+{len(x['rub_mas'])}) reglas {len(x['tem_ok'])}/{len(x['tem_oro'])}" + (f" campos {x['camp']} prods {x['prod']}" if nivel2 else ""), flush=True)
    print(f"paga en esta fase: {libro_paga.hoy() - g0:.4f} USD", flush=True)

if __name__ == "__main__":
    modo = sys.argv[1]
    if modo == "A":
        for v in (sys.argv[2:] or VARIANTES): fase(v, False)
    else:
        fase(sys.argv[2], True)
