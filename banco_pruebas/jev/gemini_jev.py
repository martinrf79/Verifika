"""Gemini con lo que Jev elige del indice, por el mismo camino de traduccion58. Sin tocar el repo.
  control  5 casos sin Jev: la agenda tiene que ser la grabada, si no el entorno no es el de produccion.
  correr   los casos con el recorte de Jev. Un caso sin recorte no se llama: la entrada seria la grabada.
Tope: TOPE_USD de la paga desde que arranca, segun el libro de la paga."""
import asyncio, copy, json, os, sys, time, random, collections
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
REPO = "/home/user/Verifika"; sys.path.insert(0, REPO); os.chdir(REPO)
OUT = os.path.join(D, "gemini_jev.jsonl"); TOPE_USD = 0.40
from banco_pruebas import clon_produccion as C
C.preparar_entorno(); C.instalar()
from app.core import llm_reintento
from app.core.flujo import interprete
puerta, real_interp, real_elegir, real_mensajes = llm_reintento._cliente, interprete.interpretar, interprete.elegir, interprete.mensajes
from banco_pruebas import cableado58 as R
from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
from banco_pruebas.sonda_charlas import nota_casilla
from banco_pruebas.traduccion58 import _explicacion
from banco_pruebas import libro_paga
it = R.instalar(); llm_reintento._cliente = puerta; elegir_mano = it.elegir
import indice_jev as I
from sondas2 import llamar as jev_llamar
from sondas import rank
llm_reintento._cliente = puerta  # fuente.py vuelve a instalar el cableado al importarse: la puerta real se repone al final

def recorte(texto, libreta):
    """Nivel 1: rubros y tema. Nivel 2: los campos que pide, con sus valores. Devuelve el texto para el modelo, o ''."""
    st = I.nivel1() + f"\n\n{libreta}\n\nULTIMO MENSAJE DEL CLIENTE: {texto}"
    q = {f"r_{r}": {"type": "noul", "instructions": f"Lo que pide el ULTIMO MENSAJE, leido con la charla, incluye productos del rubro {I.NOMBRE.get(r, r)}?"} for r in I.RUBROS}
    q["tema"] = {"type": "choice", "criteria": {f["tema"]: I.desc_tema(f) for f in I.FAQ} | {"ninguno": "no pregunta ninguna regla de la tienda"},
                 "instructions": "Que regla de la tienda pregunta el ULTIMO MENSAJE?"}
    a = jev_llamar({"state": st, "model": "jev-latest", "questions": q}, "gemini_jev_n1")["answers"]
    rubros = [r for r in I.RUBROS if a[f"r_{r}"]["noul"] >= .7]
    lineas = []
    for r in rubros[:4]:
        vs = I.valores(r)
        q2 = {k: {"type": "noul", "instructions": f"El ULTIMO MENSAJE pide, pregunta o pone como condicion {(I.SPECS.get(k) or {}).get('etiqueta', k.replace('_', ' '))}?"} for k in vs}
        b = jev_llamar({"state": I.nivel2(r) + f"\n\n{libreta}\n\nULTIMO MENSAJE DEL CLIENTE: {texto}", "model": "jev-latest", "questions": q2}, "gemini_jev_n2")["answers"] if q2 else {}
        campos = [k for k in vs if b.get(k, {}).get("noul", 0) >= .5]
        lineas.append(f"- rubro {r}" + ("; datos que pide, con los valores que tiene la tienda: " + "; ".join(f"{k.replace('_', ' ')}: {' | '.join(vs[k][:12])}" for k in campos) if campos else ""))
    t = a["tema"]["choice"]
    if t != "ninguno" and a["tema"]["probabilities"][t] >= .5: lineas.append(f"- tema de la tienda que pregunta: {t}")
    return ("LO QUE LA FUENTE DE LA TIENDA TIENE PARA ESTE MENSAJE, elegido por el codigo:\n" + "\n".join(lineas)) if lineas else ""

def caso(cid, k, forma, texto, con_jev):
    ch = {c["id"]: c for c in R.charlas()}[cid]; ags = AGENDAS[cid]; uid = f"gj_{cid}"
    C.reiniciar_cliente(uid); respuestas = []
    for i, t in enumerate(ch["turnos"][:k]):
        async def _mano(*a, _ag=ags[i], **kw): return _ag
        async def _expl(p, *a, _ag=ags[i], **kw): return _explicacion(_ag, EXPLICAR)
        it.interpretar, it.explicar, it.elegir = _mano, _expl, elegir_mano
        respuestas.append("\n".join(asyncio.run(C.turno(uid, t["texto"]))))
    extra = {"txt": ""}
    def _mensajes(mensaje, historial, estado, tienda_id):
        m = real_mensajes(mensaje, historial, estado, tienda_id)
        if con_jev:
            lib = interprete.libreta(estado, historial, tienda_id)
            extra["txt"] = extra["txt"] or recorte(mensaje, lib)
            if extra["txt"]:
                u = m[1]["content"]; i = u.rfind("\nULTIMO MENSAJE:")
                m[1]["content"] = u[:i] + "\n" + extra["txt"] + u[i:]
        return m
    interprete.mensajes = _mensajes
    vistas = []
    async def _modelo(*a, **kw):
        for intento in range(4):
            r = await real_interp(*a, **kw)
            if r is not None: vistas.append(r); return r
            await asyncio.sleep(20 * (intento + 1))
        return None
    async def _expl_k(p, *a, **kw): return _explicacion(ags[k], EXPLICAR)
    it.interpretar, it.explicar, it.elegir = _modelo, _expl_k, real_elegir
    texto_r = "\n".join(asyncio.run(C.turno(uid, texto))); interprete.mensajes = real_mensajes
    if not vistas: return None
    malas = [c["n"] for c in ch["turnos"][k]["casillas"] if nota_casilla(c, [], texto_r, respuestas + [texto_r]) is not True]
    return {"charla": cid, "turno": k, "forma": forma, "jev": con_jev, "recorte": extra["txt"], "bien": not malas, "malas": malas, "agenda": vistas[-1], "respuesta": texto_r}

def grabadas():
    g = {}
    for l in open("banco_pruebas/traduccion58_corridas.jsonl"):
        x = json.loads(l)
        if (x.get("modelo") or "prod") == "prod" and not x.get("rep"): g[(x["charla"], x["turno"], x["forma"])] = x
    return g

if __name__ == "__main__":
    modo = sys.argv[1]; G = grabadas(); base = {tuple(json.loads(k)[1:]): v for k, v in json.load(open(os.path.join(D, "base_prod.json"))).items()}
    hechos = {(x["charla"], x["turno"], x["forma"], x["jev"]) for x in map(json.loads, open(OUT))} if os.path.exists(OUT) else set()
    if modo == "control":
        lista = [(c, t, f, False) for (c, t, f) in sorted(G)[::107][:5]]
    else:
        fallan = [k for k, v in base.items() if not v["bien"]]
        complejas = sorted(k for k in base if base[k]["bien"] and len((G[k]["agenda"] or {}).get("preguntas") or []) >= 3)
        random.Random(5).shuffle(complejas)
        lista = [(*k, True) for k in sorted(fallan) + complejas[:int(sys.argv[2]) if len(sys.argv) > 2 else 60]]
    lista = [x for x in lista if x not in hechos]
    g0 = libro_paga.hoy(); print(f"{len(lista)} casos; paga hoy al arrancar {g0:.3f} USD; clave {'PAGA' if os.environ.get('BANCO_CLAVE_PAGA') == 'true' else 'gratis'}", flush=True)
    for c, t, f, j in lista:
        if libro_paga.hoy() - g0 > TOPE_USD: print("TOPE de esta corrida"); break
        r = caso(c, t, f, G[(c, t, f)]["texto"], j)
        if r is None: print(f"{c} T{t} {f}: el modelo no contesto, se corta", flush=True); break
        r["antes"] = base[(c, t, f)]["bien"]; r["igual_grabada"] = r["agenda"] == {k: v for k, v in (G[(c, t, f)]["agenda"] or {}).items() if k != "_crudo"}
        with open(OUT, "a") as o: o.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{c} T{t} {f} jev={j}: antes {'bien' if r['antes'] else 'MAL'} -> {'bien' if r['bien'] else 'MAL ' + ';'.join(r['malas'])} | igual a lo grabado {r['igual_grabada']}", flush=True)
    print(f"paga gastada en esta corrida: {libro_paga.hoy() - g0:.4f} USD")
