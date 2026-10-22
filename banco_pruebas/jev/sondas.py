"""Hasta donde selecciona Jev. Cada sonda con lo correcto calculado por el codigo de la tienda, no a ojo.
Todas las preguntas de una sonda van en una llamada con la fuente como estado: la fuente se cobra una vez."""
import json, os, random, re, sys, collections
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from fuente import PS, FAQ, FUENTE, K, llamar, n
TID = "verifika_prod"; RND = random.Random(11)
RUBROS = sorted({p["categoria"] for p in PS})
STOCK = [p for p in PS if K.con_stock(p)]
def crit(rubro, solo_stock=False):
    return {str(p["id"]): f"{p['nombre']} ${K.entero(p.get('precio_ars'))} stock {K.entero(p.get('stock'))}"
            for p in PS if p["categoria"] == rubro and (K.con_stock(p) or not solo_stock)}
LOTE = 40
def jev(qs, state=FUENTE):
    out = {}
    items = list(qs.items())
    for i in range(0, len(items), LOTE):
        out.update(llamar({"state": state, "model": "jev-latest", "questions": dict(items[i:i + LOTE])})["answers"])
    return out
def rank(a): return [k for k, _ in sorted(a["probabilities"].items(), key=lambda kv: -kv[1])]
NOM = {str(p["id"]): p["nombre"] for p in PS}

def s1_variante():
    """El producto exacto entre variantes casi iguales: capacidad, color, version."""
    casos = []
    grupos = collections.defaultdict(list)
    for p in PS: grupos[(p["categoria"], p.get("marca"), re.sub(r"\d+\s*(gb|tb)", "", n(p.get("modelo") or "")))].append(p)
    pares = [g for g in grupos.values() if len(g) >= 3]
    for g in RND.sample(pares, min(40, len(pares))):
        p = RND.choice(g)
        casos.append((f"¿Tenés el {p.get('marca')} {p.get('modelo')} en {p.get('color')}?", p["categoria"], str(p["id"])))
    a = jev({f"q{i}": {"type": "choice", "criteria": crit(r), "instructions": f"El cliente pregunta: «{t}». A que producto exacto del CATALOGO se refiere?"} for i, (t, r, _) in enumerate(casos)})
    ok1 = sum(a[f"q{i}"]["choice"] == g for i, (_, _, g) in enumerate(casos)); ok3 = sum(g in rank(a[f"q{i}"])[:3] for i, (_, _, g) in enumerate(casos))
    mal = [(t, NOM[a[f"q{i}"]["choice"]]) for i, (t, _, g) in enumerate(casos) if a[f"q{i}"]["choice"] != g]
    return f"variante exacta: top1 {ok1}/{len(casos)}, top3 {ok3}", mal[:6]

def s2_filtros():
    """Las condiciones: que proporcion de los 5 primeros de Jev las cumple, segun catalogo.atar/cumple."""
    casos = []
    for r in RUBROS:
        del_r = [p for p in STOCK if p["categoria"] == r]
        marcas = sorted({p.get("marca") for p in del_r if p.get("marca")})
        precios = sorted(K.entero(p.get("precio_ars")) for p in del_r)
        med = precios[len(precios) // 2]; tope = int(round(med, -3))
        for cond, texto in [(marcas[0], f"busco {r} de la marca {marcas[0]}"), (f"que no sea {marcas[-1]}", f"quiero {r}, que no sea {marcas[-1]}"),
                            (f"menos de {tope}", f"necesito {r} por menos de ${tope:,}".replace(",", ".")), ("blanco", f"tenes {r} en color blanco?")]:
            f = K.atar(cond, [p for p in PS if p["categoria"] == r], TID)
            if "sin_campo" in f: continue
            buenos = {str(p["id"]) for p in del_r if K.cumple(p, f)}
            if buenos and len(buenos) < len(del_r): casos.append((texto, r, buenos, cond))
    a = jev({f"q{i}": {"type": "choice", "criteria": crit(r, True), "instructions": f"El cliente pide: «{t}». Que producto del CATALOGO le mostrarias que cumpla todo lo que pide?"} for i, (t, r, _, _) in enumerate(casos)})
    por = collections.defaultdict(lambda: [0, 0, 0])
    for i, (t, r, buenos, cond) in enumerate(casos):
        k = "marca" if cond == casos[i][3] and not cond.startswith(("que no", "menos", "blanco")) else cond.split()[0]
        top5 = rank(a[f"q{i}"])[:5]; por[k][0] += sum(x in buenos for x in top5); por[k][1] += 5; por[k][2] += a[f"q{i}"]["choice"] in buenos
    return "filtros, de los 5 primeros cuantos cumplen y el primero: " + "; ".join(f"{k} {v[0]}/{v[1]} top1 {v[2]}/{v[1]//5}" for k, v in por.items()), []

def s3_orden():
    """El mas barato, el mas caro y el mas liviano de cada rubro, contra catalogo.buscar."""
    casos = []
    for r in RUBROS:
        for orden, txt in [("mas barato", "el mas barato"), ("mas caro", "el mas caro"), ("mas liviano", "el mas liviano")]:
            fil = K.buscar(r, [], orden, 1, TID)["filas"]
            if not fil: continue
            g = fil[0]; mismos = {str(p["id"]) for p in STOCK if p["categoria"] == r and p.get("modelo") == g.get("modelo") and p.get("marca") == g.get("marca")}
            if orden == "mas liviano" and not g.get("peso_gramos"): continue
            casos.append((f"cual es {txt} de {r} que tengan en stock?", r, mismos, orden))
    a = jev({f"q{i}": {"type": "choice", "criteria": crit(r, True), "instructions": f"El cliente pregunta: «{t}». Que producto del CATALOGO es?"} for i, (t, r, _, _) in enumerate(casos)})
    c = collections.Counter()
    for i, (_, _, g, o) in enumerate(casos):
        c[o + " total"] += 1; c[o] += a[f"q{i}"]["choice"] in g; c[o + " top5"] += bool(set(rank(a[f"q{i}"])[:5]) & g)
    return "orden: " + "; ".join(f"{o} top1 {c[o]}/{c[o+' total']} top5 {c[o+' top5']}" for o in ("mas barato", "mas caro", "mas liviano")), []

def s4_espera():
    """Respuesta corta a una pregunta del bot: elegir la opcion. Las opciones salen del catalogo."""
    casos = []
    for r in RND.sample(RUBROS, 10):
        fil = K.buscar(r, [], "mas barato", 3, TID)["filas"]
        if len(fil) < 3: continue
        bot = "Te muestro: " + "; ".join(f"{i}) {p['nombre']} ${K.entero(p['precio_ars'])}" for i, p in enumerate(fil, 1)) + ". ¿Cuál te gusta?"
        op = {str(i): p["nombre"] for i, p in enumerate(fil, 1)}; op["ninguno"] = "ninguno de esos, o no se sabe cual"
        caro = max(range(3), key=lambda i: K.entero(fil[i]["precio_ars"]))
        for resp, g in [("el del medio", "2"), ("el ultimo", "3"), ("el primero", "1"), ("el mas caro de esos", str(caro + 1)),
                        (f"el {fil[1].get('marca')}" if fil[1].get("marca") not in (fil[0].get("marca"), fil[2].get("marca")) else None, "2"),
                        ("ninguno me convence", "ninguno"), ("dale", "ninguno")]:
            if resp: casos.append((bot, resp, op, g))
    a = jev({f"q{i}": {"type": "choice", "criteria": op, "instructions": f"El vendedor dijo: «{b}». El cliente contesta: «{r}». Que opcion eligio?"} for i, (b, r, op, _) in enumerate(casos)}, state="Charla de una tienda de tecnologia.")
    c = collections.Counter(); mal = []
    for i, (_, r, _, g) in enumerate(casos):
        k = r if not r.startswith("el ") or r in ("el del medio", "el ultimo", "el primero", "el mas caro de esos") else "por marca"
        c[k + "#"] += 1; ok = a[f"q{i}"]["choice"] == g; c[k] += ok
        if not ok: mal.append((r, a[f"q{i}"]["choice"], g))
    ks = sorted({k[:-1] for k in c if k.endswith("#")})
    return "espera: " + "; ".join(f"{k} {c[k]}/{c[k+'#']}" for k in ks), mal[:6]

def s5_ruido():
    """Mensajes sin pedido: cuantos rubros o reglas marca con 0.5 o mas."""
    msgs = ["hola", "gracias!", "jaja buenisimo", "que dia es hoy?", "contame un chiste", "ok", "despues te escribo",
            "mi perro se llama Toby", "como salio boca?", "uh me olvide", "perdon me equivoque de chat", "buen dia"]
    qs = {}
    for i, m in enumerate(msgs):
        for r in RUBROS: qs[f"m{i}_r_{r}"] = {"type": "noul", "instructions": f"El mensaje del cliente «{m}» pide o pregunta por productos del rubro {r}?"}
        for f in FAQ: qs[f"m{i}_f_{f['tema']}"] = {"type": "noul", "instructions": f"El mensaje del cliente «{m}» pregunta algo que responde la regla \"{f['tema']}\"?"}
    a = jev(qs)
    fp = {m: [k.split("_", 2)[2] for k, v in a.items() if k.startswith(f"m{i}_") and v["noul"] >= .5] for i, m in enumerate(msgs)}
    return f"ruido: {sum(1 for v in fp.values() if not v)}/{len(msgs)} mensajes sin nada marcado", [(m, v) for m, v in fp.items() if v][:6]


def linea_rica(p):
    sp = "; ".join(f"{k}: {str(v)[:40]}" for k, v in (p.get("specs") or {}).items() if v)
    return (f"{p['id']} | {p['categoria']} | {p['nombre']} | ${K.entero(p.get('precio_ars'))} | stock {K.entero(p.get('stock'))}"
            + (f" | peso {p['peso_gramos']} g" if p.get("peso_gramos") else "") + (f" | origen {p['origen']}" if p.get("origen") else "") + (f" | {sp}" if sp else ""))
RICA = "CATALOGO CON DATOS:\n" + "\n".join(linea_rica(p) for p in PS) + "\n\nREGLAS:\n" + "\n".join(f"{f['tema']}: {f['respuesta']}" for f in FAQ)

def s2b_filtros_justos():
    """Lo mismo que s2, pero contando contra lo posible: si cumplen 3, el maximo es 3."""
    import types
    casos = []
    for r in RUBROS:
        del_r = [p for p in STOCK if p["categoria"] == r]
        marcas = sorted({p.get("marca") for p in del_r if p.get("marca")})
        for cond, texto in [(marcas[0], f"busco {r} de la marca {marcas[0]}"), ("blanco", f"tenes {r} en color blanco?")]:
            f = K.atar(cond, [p for p in PS if p["categoria"] == r], TID)
            if "sin_campo" in f: continue
            buenos = {str(p["id"]) for p in del_r if K.cumple(p, f)}
            if buenos and len(buenos) < len(del_r): casos.append((texto, r, buenos, cond))
    a = jev({f"q{i}": {"type": "choice", "criteria": crit(r, True), "instructions": f"El cliente pide: «{t}». Que producto del CATALOGO le mostrarias que cumpla todo lo que pide?"} for i, (t, r, _, _) in enumerate(casos)})
    got = pos = 0
    for i, (t, r, b, c) in enumerate(casos):
        k = min(5, len(b)); got += sum(x in b for x in rank(a[f"q{i}"])[:k]); pos += k
    return f"filtros justos, marca y color: de los primeros k cumplen {got}/{pos}", []

def s3b_orden_rico():
    """El mas liviano y el mas pesado con el peso en la fuente."""
    casos = []
    for r in RUBROS:
        for orden in ("mas liviano", "mas pesado"):
            con = [p for p in STOCK if p["categoria"] == r and p.get("peso_gramos")]
            if len(con) < 3: continue
            g = K.buscar(r, [], orden, 1, TID)["filas"][0]
            mismos = {str(p["id"]) for p in con if float(p["peso_gramos"]) == float(g["peso_gramos"])}
            casos.append((f"cual es el {orden} de {r} que tengan?", r, mismos, orden))
    a = jev({f"q{i}": {"type": "choice", "criteria": crit(r, True), "instructions": f"El cliente pregunta: «{t}». Que producto del CATALOGO CON DATOS es?"} for i, (t, r, _, _) in enumerate(casos)}, state=RICA)
    c = collections.Counter()
    for i, (_, _, g, o) in enumerate(casos):
        c[o + "#"] += 1; c[o] += a[f"q{i}"]["choice"] in g; c[o + "5"] += bool(set(rank(a[f"q{i}"])[:5]) & g)
    return "orden con peso en la fuente: " + "; ".join(f"{o} top1 {c[o]}/{c[o+'#']} top5 {c[o+'5']}" for o in ("mas liviano", "mas pesado")), []

def s6_specs():
    """Productos que tienen un dato tecnico: inalambrico, bluetooth, RGB, origen. Lo correcto: catalogo.atar/cumple."""
    casos = []
    for r in RUBROS:
        del_r = [p for p in STOCK if p["categoria"] == r]
        for cond, txt in [("inalambrico", "que sea inalambrico"), ("bluetooth", "que tenga bluetooth"), ("rgb", "con luces RGB"),
                          ("mecanico", "que sea mecanico"), ("estados unidos", "que sea de origen Estados Unidos")]:
            f = K.atar(cond, [p for p in PS if p["categoria"] == r], TID)
            if "sin_campo" in f: continue
            b = {str(p["id"]) for p in del_r if K.cumple(p, f)}
            if 0 < len(b) < len(del_r): casos.append((f"busco {r} {txt}", r, b))
    a = jev({f"q{i}": {"type": "choice", "criteria": crit(r, True), "instructions": f"El cliente pide: «{t}». Que producto del CATALOGO CON DATOS cumple lo que pide?"} for i, (t, r, _) in enumerate(casos)}, state=RICA)
    got = pos = t1 = 0; mal = []
    for i, (t, r, b) in enumerate(casos):
        k = min(5, len(b)); h = sum(x in b for x in rank(a[f"q{i}"])[:k]); got += h; pos += k; t1 += a[f"q{i}"]["choice"] in b
        if a[f"q{i}"]["choice"] not in b: mal.append((t, NOM[a[f"q{i}"]["choice"]]))
    return f"specs con la fuente rica: top1 cumple {t1}/{len(casos)}, de los primeros k cumplen {got}/{pos}", mal[:8]

def s1b_largo():
    global LOTE; LOTE = 4
    """La variante exacta con la fuente rica, mucho mas larga: se degrada?"""
    RND.seed(11); casos = []
    grupos = collections.defaultdict(list)
    for p in PS: grupos[(p["categoria"], p.get("marca"), re.sub(r"\d+\s*(gb|tb)", "", n(p.get("modelo") or "")))].append(p)
    pares = [g for g in grupos.values() if len(g) >= 3]
    for g in RND.sample(pares, min(40, len(pares))):
        p = RND.choice(g); casos.append((f"¿Tenés el {p.get('marca')} {p.get('modelo')} en {p.get('color')}?", p["categoria"], str(p["id"])))
    a = jev({f"q{i}": {"type": "choice", "criteria": crit(r), "instructions": f"El cliente pregunta: «{t}». A que producto exacto del CATALOGO se refiere?"} for i, (t, r, _) in enumerate(casos)}, state=RICA)
    return f"variante exacta con fuente rica ({len(RICA)} caracteres): top1 {sum(a[f'q{i}']['choice'] == g for i, (_, _, g) in enumerate(casos))}/{len(casos)}", []


def s7_pedazos():
    """Partir eligiendo: el codigo corta el mensaje en pedazos y Jev dice que pedazo pide cada cosa. Lo correcto: la cita del modelo en traducciones que salieron bien."""
    from fuente import REPO
    from app.core.flujo.agenda import palabras
    filas = [json.loads(l) for l in open(os.path.join(REPO, "banco_pruebas/traduccion58_corridas.jsonl"))]
    casos = []
    for r in filas:
        if (r.get("modelo") or "prod") != "prod" or r.get("rep") or not r["bien"] or r["forma"] not in ("original", "coloquial", "whatsapp"): continue
        ps = [p for p in (r["agenda"] or {}).get("preguntas") or [] if p.get("cita") and p.get("accion") not in ("otro",)]
        if len(ps) < 3: continue
        trozos = [t.strip() for t in re.split(r"[.,;?!]+|\by\b|\bpero\b", r["texto"]) if len(palabras(t)) >= 1]
        if len(trozos) < 3: continue
        op = {f"t{i}": t for i, t in enumerate(trozos)}
        for p in ps:
            cw = set(palabras(p["cita"]))
            oro = {f"t{i}" for i, t in enumerate(trozos) if palabras(t) and len(set(palabras(t)) & cw) / len(set(palabras(t))) >= .6}
            if not oro: continue
            desc = p["accion"] + " " + " ".join(str(p.get(k)) for k in ("rubro", "producto", "tema", "destino") if p.get(k))
            if p["accion"] == "comprar": desc = "comprar o anotar en el pedido " + json.dumps(p.get("agrega") or p.get("saca") or p.get("cambia") or "", ensure_ascii=False)[:120]
            if p["accion"] == "cuenta": desc = "cuenta o forma de pago " + json.dumps(p.get("reparto") or "", ensure_ascii=False)
            casos.append((r["texto"], op, oro, desc, p["accion"]))
    a = jev({f"q{i}": {"type": "choice", "criteria": op, "instructions": f"Mensaje del cliente: «{t}». Que pedazo del mensaje es el que pide: {d}?"} for i, (t, op, _, d, _) in enumerate(casos)}, state="Mensajes de clientes de una tienda de tecnologia.")
    c = collections.Counter(); mal = []
    for i, (t, op, oro, d, acc) in enumerate(casos):
        ok = a[f"q{i}"]["choice"] in oro; c[acc + "#"] += 1; c[acc] += ok
        if not ok: mal.append((d[:60], op[a[f"q{i}"]["choice"]], [op[o] for o in oro]))
    tot = sum(c[k] for k in c if not k.endswith("#")); n_ = sum(c[k] for k in c if k.endswith("#"))
    return f"pedazos: {tot}/{n_}; " + "; ".join(f"{k[:-1]} {c[k[:-1]]}/{c[k]}" for k in sorted(c) if k.endswith("#")), mal[:8]

if __name__ == "__main__":
    for s in sys.argv[1:] or ["s1_variante", "s2_filtros", "s3_orden", "s4_espera", "s5_ruido"]:
        res, mal = globals()[s]()
        print(res); [print("   ", m) for m in mal]
