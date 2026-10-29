"""LAS HERRAMIENTAS DEL MODELO — la segunda llamada: el modelo llama a las herramientas del menu con las lineas, los candidatos y la libreta, y el
codigo cumple (28-oct-2026, FICHA 83).

Pedido de Martin del 28-oct, despues de `entrevista_respuesta.py`: el modelo dijo que este paso, para el, es llamar
funciones con argumentos, lo que mejor sabe hacer por entrenamiento, todas en una vuelta, con los candidatos a la vista y
una salida para lo que la tienda no vende. Se prueba directo, como seria en el bot:

  la entrada   el mensaje, la libreta de la charla, las lineas que separo la primera llamada y los candidatos de la
               busqueda de cada linea, con los datos clave de cada producto. Las lineas y los candidatos, los mismos de
               `responder_lineas.py`.
  la salida    llamadas a herramientas reales de la API, una por cosa que hace falta, cada una con su cita y su por que.
               Las herramientas son el menu cerrado de `agenda.py`, mas no_lo_vendemos y repreguntar. El producto solo
               de los candidatos o de la libreta: lista cerrada en el esquema.
  la vara      las casillas del turno en `vara_58.json`, por el webhook entero. Los turnos de antes, con la agenda a
               mano. Contra la agenda a mano, la lectura grabada de hoy y el codigo con las lineas.

Dos pasos: `--llamar` le pide al modelo y guarda lo que contesto en `herramientas_modelo.jsonl`, lo ya preguntado no se
vuelve a pedir; sin `--llamar`, corre lo guardado sin modelo.

    python3 banco_pruebas/herramientas_modelo.py --llamar [--hasta 10] [C27 K20 ...]           con la gratis
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/herramientas_modelo.py --llamar      con la paga, al libro
    python3 banco_pruebas/herramientas_modelo.py [--ver]                                        sin modelo
"""
import asyncio
import collections
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import responder_lineas as RL  # noqa: E402  — prepara el clon, la vara, el indice y los embeddings
from banco_pruebas import cableado58 as C58  # noqa: E402
from app.core.flujo import agenda as A  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import estado as E  # noqa: E402
from app.core.flujo import ficha as F  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from app.core.flujo import lectura as L  # noqa: E402

ARGS = RL.ARGS
TID = RL.TID
P = RL.P
GRABADO = os.path.join(AQUI, "herramientas_modelo.jsonl")
VER = "--ver" in ARGS
SOLO = [a for a in ARGS if re.match(r"^[CKJ]\d\d$", a)]
HASTA = int(ARGS[ARGS.index("--hasta") + 1]) if "--hasta" in ARGS else 0

CONSIGNA = """Sos el interprete de una tienda online de tecnologia de Argentina que vende por WhatsApp. No le contestas
al cliente. Con su mensaje, lo que ya paso en la charla, las lineas en que separaste el mensaje y los candidatos que trajo
la busqueda, llamas a las herramientas que el codigo necesita para poder contestar. El codigo cumple exacto y pone
todos los precios, el stock, los envios y los totales: vos no calculas ni afirmas datos.

- Llama todas las herramientas que hagan falta en una sola respuesta, en el orden del mensaje.
- Un producto se nombra solo como esta en los candidatos o por su numero de la libreta: M-2, L-1.
- Lo que ya se mostro o ya esta en el pedido se senala por su numero de la libreta.
- Si la tienda no tiene la clase de producto que pide, no_lo_vendemos. Si no podes decidir sin preguntarle algo al
  cliente, repreguntar.
- Lo que depende de otra cosa —"si hay", "si no", "si sale menos de"— lleva depende_de con el numero de la llamada de
  la que depende, contando desde 1, y vale_si.
- En cada llamada, "cita" son las palabras literales del cliente, y "por" una frase corta de por que.{reglas}

LA TIENDA. Clases de producto: {rubros}. Reglas de la tienda: {temas}.

EJEMPLOS, en palabras:
Cliente: "pasame los dos teclados mas baratos y uno a Mendoza" -> buscar(rubro teclado, cantidad 2, orden mas barato);
  comprar(agrega teclado, cantidad 1, destino Mendoza).
Cliente: "el monitor que me mostraste, el segundo, tiene HDMI? si tiene, anotame uno" -> producto(M-2, quiere_saber
  HDMI); comprar(agrega M-2, cantidad 1, depende_de 1, vale_si si).
Cliente: "venden heladeras?" -> no_lo_vendemos(que heladeras).
Cliente: "mejor sacame el de Salta y el otro mandalo a Jujuy" -> comprar(saca L-2; cambia L-1 destino Jujuy).
Cliente: "si me paso de 200 mil sacame la webcam, y cuanto queda todo?" -> cuenta(tope 200000, si_pasa webcam)."""

# LA VUELTA 2, 28-oct, con el ok de Martin: tres reglas por las clases que fallaron en la primera —el modelo elegia el
# producto cuando el codigo elige por el orden, repetia lo de turnos anteriores y perdia datos al pasarlos a la compra—,
# y elegir entre productos por una condicion dentro de la regla de lo que depende. Va a su propio archivo.
V2 = "--v2" in ARGS
REGLAS_V2 = """
- Solo lo que pide ESTE mensaje. Lo que esta en la libreta ya se hizo: no lo vuelvas a pedir; lo senalas por su numero
  solo si este mensaje lo cambia, lo saca, lo confirma o pregunta por el.
- Con un orden —el mas barato, el mejor— o sin un modelo que el cliente nombro, en comprar va la clase de producto, no
  un candidato: el producto lo elige el codigo.
- Cada dato que dio el cliente pasa entero: cantidad, color y destino en cada articulo de comprar; la marca y lo que pide
  que tenga van en condiciones de buscar.
- Elegir entre productos por una condicion —"entre el A y el B, el que sea X"— es producto de cada uno con quiere_saber X,
  y comprar de cada uno con depende_de su llamada."""
if V2:
    GRABADO = os.path.join(AQUI, "herramientas_modelo_v2.jsonl")

_TXT, _ENT = {"type": "string"}, {"type": "integer"}
_COMUN = {"cita": _TXT, "por": _TXT, "depende_de": _ENT, "vale_si": {"type": "string", "enum": ["si", "no"]}}
_REPARTO = {"type": "array", "items": {"type": "object", "properties": {"medio": _TXT, "porcentaje": _ENT},
                                       "required": ["medio", "porcentaje"]}}
_ART = {"type": "object", "properties": {"producto": _TXT, "cantidad": _ENT, "color": _TXT, "destino": _TXT}}


def herramientas(productos: list, refs: list) -> list:
    """El menu cerrado de `agenda.py` como herramientas de la API, con los productos de este mensaje como lista cerrada."""
    rubros = F._rubros(TID) + ["toda la tienda"]
    lista = list(dict.fromkeys(productos + refs)) or ["ninguno"]

    def h(nombre, desc, props, req=()):
        return {"type": "function", "function": {"name": nombre, "description": desc, "parameters": {
            "type": "object", "properties": {**props, **_COMUN}, "required": ["cita", *req]}}}
    return [
        h("buscar", A.ACCIONES["buscar"], {"rubro": {"type": "string", "enum": rubros}, "cantidad": _ENT,
          "orden": _TXT, "condiciones": {"type": "array", "items": _TXT}, "entre_lo_mostrado": {"type": "boolean"}},
          ["rubro"]),
        h("producto", A.ACCIONES["producto"], {"producto": {"type": "string", "enum": lista}, "quiere_saber": _TXT,
          "color": _TXT, "afirma": _TXT}, ["producto"]),
        h("envio", A.ACCIONES["envio"], {"destino": _TXT}, ["destino"]),
        h("cuenta", A.ACCIONES["cuenta"], {"tope": _ENT, "si_pasa": _TXT, "reparto": _REPARTO}),
        h("politica", A.ACCIONES["politica"], {"tema": {"type": "string", "enum": F._temas_de(TID)}, "afirma": _TXT},
          ["tema"]),
        h("compatibilidad", A.ACCIONES["compatibilidad"], {"producto": _TXT, "con": _TXT,
          "falta_modelo": {"type": "boolean"}}, ["producto"]),
        h("comprar", A.ACCIONES["comprar"], {"agrega": {"type": "array", "items": _ART},
          "saca": {"type": "array", "items": _TXT}, "cambia": {"type": "array", "items": {
              "type": "object", "properties": {"es": _TXT, **_ART["properties"]}}},
          "confirma": {"type": "array", "items": _TXT}, "acepta": {"type": "array", "items": _TXT}, "total": _ENT,
          "reemplaza": {"type": "boolean"}, "reparto": _REPARTO}),
        h("explicar", A.ACCIONES["explicar"], {"pregunta": _TXT}, ["pregunta"]),
        h("otro", A.ACCIONES["otro"], {"que": {"type": "string", "enum": [
            "saludo", "dato", "corrige", "humano", "fuera_de_tema", "catalogo"]}}, ["que"]),
        h("no_lo_vendemos", "la clase de producto que pide no esta en la tienda: \"que\", la clase en una o dos palabras, "
          "sin marca: \"celulares\".",
          {"que": _TXT}, ["que"]),
        h("repreguntar", "lo que hay que preguntarle al cliente para poder seguir, en una pregunta corta.",
          {"pregunta": _TXT}, ["pregunta"]),
    ]


# ══ LA ENTRADA: las lineas con sus candidatos ════════════════════════════════

def candidatos(lineas: list, ind) -> tuple:
    """(el texto de las lineas con sus candidatos, los nombres de producto que puede nombrar)."""
    todos = K.productos(TID)
    out, nombres = [], []
    for i, x in enumerate(lineas, 1):
        texto, cosa = str(x.get("texto") or ""), str(x.get("cosa") or "")
        extra = [f"cantidad {x['cantidad']}" if x.get("cantidad") else "", f"destino {x['destino']}" if x.get("destino")
                 else "", f"si {x['si']}" if x.get("si") else "", f"tema {x['tema']}" if x.get("tema") else ""]
        out.append(f"{i}. {texto}" + "".join(f"; {e}" for e in extra if e))
        cands = []
        # Lo que nombra el cliente y la tienda certifica va primero: el modelo de lenguaje no elige productos.
        for t in (cosa, texto):
            if t and F._es_modelo(t, "", TID):
                cands.append(("producto", K.identificar(t, "", TID)["producto"]))
                break
        if cosa and not re.match(r"^[MLR]-\d+$", cosa):
            for (tipo, nombre), _ in ind.candidatos(texto, cosa, tipos=("rubro", "producto", "tema"))[0]:
                if tipo == "producto":
                    idt = K.identificar(nombre, "", TID)
                    if idt.get("producto"):
                        cands.append(("producto", idt["producto"]))
                else:
                    cands.append((tipo, nombre))
        for tipo, c in cands:
            if tipo == "producto":
                nombre = f"{c.get('marca')} {c.get('modelo')}"
                nombres.append(nombre)
                out.append(f"   candidato producto: {nombre} — {interprete.datos(c, todos)[:220]}")
            else:
                out.append(f"   candidato {'clase' if tipo == 'rubro' else 'regla'}: {c}")
    return "\n".join(out), nombres


def entrada(msg: str, est: dict, h: list, lineas: list, todo: str, ind) -> tuple:
    texto, nombres = candidatos(lineas, ind)
    refs = list(interprete.numeros(est))
    user = (f"{interprete.libreta(est, h, TID)}\n\nULTIMO MENSAJE DEL CLIENTE: {msg}\n\nLAS LINEAS QUE SEPARASTE:\n{texto}"
            + (f"\nPARA TODO: {todo}" if todo else ""))
    return user, herramientas(nombres, refs)


def casos() -> list:
    """(conjunto, id de la charla, turno, mensaje, estado, historial, lineas, todo)."""
    todos = list(P._turnos_sueltos())
    primeros = [t for t in todos if "vacia" in interprete.libreta(t[3], t[4], TID)]
    charla = [t for t in todos if "vacia" not in interprete.libreta(t[3], t[4], TID)]
    grab = [json.loads(x) for x in open(os.path.join(AQUI, "momento0_cosa_tema.jsonl"), encoding="utf-8")]
    s91 = [g["salida"] for g in grab if g["examen"] == "91"]
    s78 = [g["salida"] for g in grab if g["examen"] == "78"]
    out = []
    for (f, cid, msg, est, h), s in zip(primeros, s91):
        if f == "58":
            out.append(("primeros", cid.split()[0], 0, msg, est, h, s.get("lineas") or [], str(s.get("todo") or "")))
    for g in map(json.loads, open(RL.NUEVAS, encoding="utf-8")):
        out.append(("fuera de muestra", g["id"], 0, g["mensaje"], E.leer({}), [], g["lineas"].get("lineas") or [],
                    str(g["lineas"].get("todo") or "")))
    for (f, cid, msg, est, h), s in zip(charla, s78):
        if f == "58" and "error" not in s:
            ch, t = cid.split(" t")
            out.append(("con charla", ch, int(t), msg, est, h, s.get("lineas") or [], str(s.get("todo") or "")))
    # --sin-charla: solo los primeros mensajes, cuyos embeddings ya estan guardados.
    return [c for c in out if (not SOLO or c[1] in SOLO) and not ("--sin-charla" in ARGS and c[0] == "con charla")]


# ══ LA LLAMADA ═══════════════════════════════════════════════════════════════

def _cliente():
    from openai import OpenAI
    from app.config import get_settings
    paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA") and os.environ.get("GEMINI_API_KEY_PROD"))
    clave = (os.environ["GEMINI_API_KEY_PROD"] if paga else os.environ["GEMINI_API_KEY"]).split()[0]
    return OpenAI(api_key=clave, base_url=get_settings().GEMINI_BASE_URL), paga, get_settings().GEMINI_MODEL


def llamar() -> None:
    from banco_pruebas import libro_paga
    cli, paga, modelo = _cliente()
    hechos = {(r["conjunto"], r["id"], r["turno"]) for r in map(json.loads, open(GRABADO, encoding="utf-8"))
              if "error" not in r} if os.path.exists(GRABADO) else set()
    pend = [c for c in casos() if c[:3] not in hechos]
    pend = pend[:HASTA] if HASTA else pend
    ind = RL.Indice()
    ind.preparar([str(x.get(k) or "") for c in pend for x in c[6] for k in ("texto", "cosa")])
    sistema = CONSIGNA.format(rubros=", ".join(F._rubros(TID)), temas=", ".join(F._temas_de(TID)),
                              reglas=REGLAS_V2 if V2 else "")
    print(f"a pedir {len(pend)} · {'PAGA' if paga else 'gratis'}", flush=True)
    for conj, ch, t, msg, est, h, lineas, todo in pend:
        user, tools = entrada(msg, est, h, lineas, todo, ind)
        fila = {"conjunto": conj, "id": ch, "turno": t, "mensaje": msg}
        for intento in range(6):
            try:
                if paga:
                    libro_paga.puede()
                t0 = time.time()
                r = cli.chat.completions.create(model=modelo, temperature=0, tools=tools, tool_choice="required",
                                                messages=[{"role": "system", "content": sistema},
                                                          {"role": "user", "content": user}])
                u = r.usage
                if paga:
                    libro_paga.anotar(modelo, u.prompt_tokens, u.completion_tokens)
                fila.update(seg=round(time.time() - t0, 2), entrada=u.prompt_tokens, salida=u.completion_tokens,
                            llamadas=[{"nombre": c.function.name, "args": json.loads(c.function.arguments or "{}")}
                                      for c in r.choices[0].message.tool_calls or []])
                fila.pop("error", None)
                break
            except libro_paga.TopeDiario:
                raise
            except Exception as e:  # noqa: BLE001 — la gratis se traba: se espera y se reintenta
                fila["error"] = f"{type(e).__name__}: {str(e)[:160]}"
                time.sleep(20 * (intento + 1))
        with open(GRABADO, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"  {conj} {ch} t{t}: {[x['nombre'] for x in fila.get('llamadas') or []]} {fila.get('seg')}s "
              f"{fila.get('entrada')}+{fila.get('salida')} {fila.get('error') or ''}", flush=True)


# ══ DE LAS LLAMADAS A LA AGENDA ══════════════════════════════════════════════

def a_agenda(llamadas: list, est: dict = None) -> dict:
    """Cada llamada es una pregunta de la agenda, con su accion y sus datos. no_lo_vendemos es buscar esa clase, que el
    ejecutor contesta que no la tiene; repreguntar va a las dudas, que el turno pregunta si el codigo no pregunto."""
    ps, dudas = [], []
    for i, c in enumerate(llamadas, 1):
        a = dict(c["args"])
        dep, vale = a.pop("depende_de", None), a.pop("vale_si", None) or "si"
        a.pop("por", None)
        nombre = c["nombre"]
        if nombre == "repreguntar":
            dudas.append(a.get("pregunta") or "")
            continue
        if nombre == "no_lo_vendemos":
            nombre, a = "buscar", {"cita": a.get("cita"), "rubro": a.get("que") or "", "orden": "nada"}
        q = {"n": i, "accion": nombre, **{k: v for k, v in a.items() if v not in (None, "", [])}}
        if dep and 0 < int(dep) < i:
            q["si"] = {"de": int(dep), "da": vale}
        ps.append(q)
    return {"preguntas": ps, "cliente": {}, "responde": "", "respuesta": "", "dudas": dudas}


def main() -> None:
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    interp = C58.instalar()
    grab = {(r["conjunto"], r["id"], r["turno"]): r for r in map(json.loads, open(GRABADO, encoding="utf-8"))
            if "llamadas" in r}
    hoy = {(r["fuente"], r["id"]): r.get("salida") for r in
           map(json.loads, open(os.path.join(AQUI, "primera_ejes", "sueltos_rep0.jsonl"), encoding="utf-8"))}
    hoy.update({("58", f"{g['id']} t0"): g["hoy"] for g in map(json.loads, open(RL.NUEVAS, encoding="utf-8"))})
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    ind = RL.Indice()
    nota, tot, seg, toks = collections.Counter(), collections.Counter(), collections.defaultdict(list), []
    filas = []
    for conj, ch, t, msg, est, h, lineas, todo in casos():
        g = grab.get((conj, ch, t))
        if not g:
            continue
        previas = list(AGENDAS.get(ch) or [])[:t]
        if len(previas) < t:
            continue
        charla = {"id": ch, "turnos": vara[ch]["turnos"][:t + 1]}
        ind.preparar([str(x.get(k) or "") for x in lineas for k in ("texto", "cosa")])
        salida, _ = RL.a_salida(lineas, todo, ind) if t == 0 else (None, None)
        agendas = {"a mano": (AGENDAS.get(ch) or [{}] * (t + 1))[t] if ch in AGENDAS else None,
                   "lectura de hoy": L.a_agenda(hoy[("58", f"{ch} t{t}")], est, TID, msg)
                   if hoy.get(("58", f"{ch} t{t}")) else None,
                   "codigo con lineas": L.a_agenda(salida, E.leer({}), TID, msg) if salida else None,
                   "segunda llamada": a_agenda(g["llamadas"], est)}
        fila = {"conjunto": conj, "id": ch, "turno": t, "msg": msg, "llamadas": g["llamadas"]}
        tot[conj] += 1
        seg[conj].append(g["seg"])
        toks.append((g["entrada"], g["salida"]))
        for nombre, ag in agendas.items():
            if ag is None:
                continue
            res = C58.correr(charla, previas + [ag], interp, EXPLICAR)[-1]
            malas = [n for n, ok in res["casillas"] if ok is not True]
            nota[(conj, nombre)] += not malas
            nota[(conj, nombre, "n")] += 1
            fila[nombre] = {"malas": malas, "respuesta": res["respuesta"]}
        filas.append(fila)
    with open(GRABADO.replace(".jsonl", "_corrida.jsonl"), "w", encoding="utf-8") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    print("\nLA SEGUNDA LLAMADA · casillas del turno · bien de los que tiene cada una")
    for conj in tot:
        s = sorted(seg[conj])
        print(f"  {conj}, {tot[conj]} · demora mediana {s[len(s) // 2]}s, la mas lenta {s[-1]}s")
        for nombre in ("a mano", "lectura de hoy", "codigo con lineas", "segunda llamada"):
            if nota[(conj, nombre, "n")]:
                print(f"    {nombre:18} {nota[(conj, nombre)]} de {nota[(conj, nombre, 'n')]}")
    if toks:
        e, s = sum(x for x, _ in toks) / len(toks), sum(y for _, y in toks) / len(toks)
        print(f"  tokens por llamada: entrada {e:.0f}, salida {s:.0f}")
    for f in filas:
        sl = f.get("segunda llamada") or {}
        if sl.get("malas") and (VER or SOLO):
            print(f"\n{f['id']} t{f['turno']} {f['conjunto']}: {f['msg'][:160]}")
            print("  " + " · ".join(f"{k} {'bien' if not f[k]['malas'] else 'MAL'}" for k in
                                    ("a mano", "lectura de hoy", "codigo con lineas") if k in f)
                  + f" · segunda MAL: {'; '.join(sl['malas'])}")
            for c in f["llamadas"]:
                print(f"   - {c['nombre']} {json.dumps(c['args'], ensure_ascii=False)[:260]}")
            print("   " + sl["respuesta"][:500].replace("\n", "\n   "))
    if C58.LLAMADAS_AL_MODELO:
        print(f"ERROR: {len(C58.LLAMADAS_AL_MODELO)} intentos de llamar al modelo")


if __name__ == "__main__":
    llamar() if "--llamar" in ARGS else main()
