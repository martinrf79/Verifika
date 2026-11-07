"""LAS CHARLAS GRABADAS POR EL AGENTE VIVO, SIN MODELO — la bateria del agente (30-oct-2026, FICHA 83).

El 30-oct, por orden de Martin, el agente del banco paso al bot, `app/core/flujo/agente.py`. Esta es su vara sin
modelo: las 26 charlas que el buscador grabo con su propia memoria, `buscador_charlas.jsonl`, pasan por el webhook
entero del clon, turno por turno. Un modelo falso devuelve lo que devolvio el modelo de verdad: cada llamada a una
herramienta, en orden, y despues la respuesta. Las herramientas corren de nuevo con el codigo vivo, y se cuenta:
  bien      los turnos cuyas casillas de `vara_58.json` pasan con lo que lee el cliente;
  iguales   las llamadas a herramientas que devuelven lo mismo que en el banco: que lo llevado a app/ hace lo medido.

Los embeddings no se piden: los rubros y temas mas parecidos de cada consulta grabada estan en `agente_parecidos.json`,
armado una vez con los vectores guardados del banco.

    python3 banco_pruebas/agente_replay.py [--ver] [K21 ...]
    python3 banco_pruebas/agente_replay.py --parecidos        rearma agente_parecidos.json, con numpy y los vectores
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/agente_replay.py --vivo [K21 ...]
                                                              las mismas charlas con el modelo de produccion, al libro
    python3 banco_pruebas/agente_replay.py --gratis [K21 ...]  lo mismo con la clave gratis de Gemini, el mismo modelo
    ... --gratis --regrabar K10                                 y esas charlas pasan a ser lo grabado: cuando el codigo
                                                              cambia lo que lee el modelo, se graba de nuevo con el
    ... --gratis --etiqueta base86_1                            cada charla se guarda en agente_vivo.jsonl apenas
                                                              termina, con su etiqueta; si la cuota se corta, la misma
                                                              orden al dia siguiente sigue desde la que falta, y
                                                              --regrabar graba cuando estan todas. puerta.py compara
                                                              las etiquetas charla por charla, 2-nov, FICHA 86.
"""
import asyncio
import collections
import json
import os
import sys
from types import SimpleNamespace

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path.insert(0, REPO)
GRABADO = os.path.join(AQUI, "buscador_charlas.jsonl")
PARECIDOS = os.path.join(AQUI, "agente_parecidos.json")
VIVO = os.path.join(AQUI, "agente_vivo.jsonl")
VISTOS_PARECIDOS: dict = {}


def _charlas() -> dict:
    out = collections.defaultdict(list)
    for r in map(json.loads, open(GRABADO, encoding="utf-8")):
        out[r["id"]].append(r)
    return {k: sorted(v, key=lambda r: r["turno"]) for k, v in out.items()}


def _respuesta(paso: dict = None, texto: str = ""):
    """Una respuesta del modelo como la da el cliente de OpenAI: una llamada a una herramienta, o el texto."""
    llamadas = [SimpleNamespace(id="x", type="function", function=SimpleNamespace(
        name=paso["herramienta"], arguments=json.dumps(paso["pide"], ensure_ascii=False)))] if paso else None
    mensaje = SimpleNamespace(content=None if paso else texto, tool_calls=llamadas, role="assistant")
    mensaje.model_dump = lambda **k: {"role": "assistant", "content": mensaje.content or ""}
    return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)],
                           usage=SimpleNamespace(prompt_tokens=0, completion_tokens=0))


def traducir(pasos: list, memoria: dict, mensaje: str) -> list:
    """EL MODELO SIMULADO DEL PASO 2, FICHA 89, 6-nov, orden de Martin: las charlas se grabaron cuando el modelo mandaba
    el pedido entero a `presupuesto`. Cada llamada vieja pasa a la herramienta de hoy: sin anotar, `cotizar` con lo
    mismo; anotada, `pedido` con solo la diferencia contra la libreta guardada, y las palabras del cliente como cita,
    sin numeros para que la cantidad sea la que mando el modelo. Mide el codigo del paso 2, no al modelo: eso lo
    confirma una regrabacion con el modelo."""
    import re
    from app.core.flujo import agente as A
    from app.core.flujo import catalogo as K
    ultima = max([i for i, p in enumerate(pasos) if p["herramienta"] == "presupuesto" and p["pide"].get("anotar")],
                 default=-1)
    cita = " ".join(w for w in mensaje.split() if not re.search(r"\d", w) and K.n(w) not in A._CUANTOS)
    out = []
    for i, p in enumerate(pasos):
        a = dict(p["pide"])
        if p["herramienta"] != "presupuesto":
            out.append(p)
            continue
        extra = {k: a[k] for k in ("pago", "tope") if a.get(k)}
        if i != ultima:
            out.append({**p, "herramienta": "cotizar", "pide": {**extra, "renglones": a.get("renglones") or []},
                        "traducida": True})
            continue
        hay = [dict(r) for r in A.estado_de(memoria)["borrador"].get("renglones") or []]
        cmd = {**extra}
        for r in [r for r in a.get("renglones") or [] if isinstance(r, dict) and r.get("producto")]:
            idr, dr, nr = A._id_de(r["producto"], C_TIENDA), K.n(r.get("destino")), K.entero(r.get("cantidad")) or 1
            igual = [h for h in hay if A._id_de(h["que"], C_TIENDA) == idr and K.n(h["destino"]) == dr]
            mismo = igual or [h for h in hay if A._id_de(h["que"], C_TIENDA) == idr]
            if mismo:
                h = mismo[0]
                hay.remove(h)
                cambio = {k: v for k, v in {"cantidad": nr if nr != (K.entero(h["cantidad"]) or 1) else None,
                                            "destino": r.get("destino") if not igual and r.get("destino") else None}.items() if v}
                if cambio:
                    cmd.setdefault("cambia", []).append({"es": h["L"], **cambio, "cita": cita})
                continue
            cmd.setdefault("agrega", []).append({k: v for k, v in {
                "producto": r["producto"], "cantidad": nr, "destino": r.get("destino"), "color": r.get("color"),
                "cita": cita}.items() if v})
        if a.get("renglones"):
            cmd["saca"] = [h["L"] for h in hay] or None
        cmd = {k: v for k, v in cmd.items() if v}
        out.append({**p, "herramienta": "pedido", "pide": cmd or {"confirma": [
            h["L"] for h in A.estado_de(memoria)["borrador"].get("renglones") or []]}, "traducida": True})
    return out


C_TIENDA = "verifika_prod"


def _sin_numeros(texto: str) -> str:
    """Lo que devuelve una herramienta sin los numeros de cita, P1, R1, y sin el total que se suma a "hay mas": lo
    grabado es de antes de la respuesta atada, 7-nov."""
    import re
    t = re.sub(r" de \d+(?: \([^)]*\))?, hay mas", ", hay mas", re.sub(r"(?m)^(\s*)[PRENDS]\d+: ", r"\1", str(texto or "")))
    return t.replace(" No tenemos productos que cumplan lo que buscaste.", "").replace("D1: ", "")


def final_atada(texto: str, k: dict) -> dict:
    """LA RESPUESTA ATADA SIMULADA, 7-nov, FICHA 90: el texto grabado del modelo pasa a una llamada a `responder`. Cita los
    productos que el texto nombra, con las columnas que el texto dice; las reglas, envios y cantidades que devolvieron las
    herramientas del turno; el presupuesto y el cobro si estaban pegados. El saludo y la pregunta son las oraciones del
    texto que no traen un dato. Mide lo que hace el codigo con una redaccion razonable, no lo que escribe el modelo."""
    import re
    from app.core.flujo import agente as A
    from app.core.flujo import catalogo as K
    from app.core.flujo import tabla as T
    msgs = k.get("messages") or []
    cols = next((t["function"]["parameters"]["properties"]["bloques"]["items"]["properties"]["mostrar"]["items"]["enum"]
                 for t in k.get("tools") or [] if t["function"]["name"] == "responder"), [])
    n = K.n(texto)
    tool = "\n".join(str(m.get("content") or "") for m in msgs if m.get("role") in ("tool", "user"))
    hoja = str(msgs[0].get("content") or "") if msgs else ""
    bloques = []
    for cita, fila in re.findall(r"(?m)^\s*(P\d+): (.*)$", tool):
        nombre = re.search(r"nombre: ([^;]+)", fila)
        pid = re.search(r"(?:^|; )id: ([^;]+)", fila)
        if not (nombre or pid):
            continue
        f = T.ficha(pid.group(1), C_TIENDA) if pid else {}
        if not f:
            f = T.ficha((T.tabla(C_TIENDA).execute("SELECT id FROM productos WHERE nombre = ?", (nombre.group(1),)).fetchone() or [""])[0], C_TIENDA)
        # El texto nombra el producto sin el color, o con parte del nombre: el 80% de sus palabras.
        ws = [w for w in K.n(f.get("nombre") or "").split() if w != K.n(f.get("color"))]
        precio = f"${int(f['precio']):,}".replace(",", ".") if f.get("precio") else "-"
        if not f or (sum(w in set(re.findall(r"[a-z0-9]+", n)) for w in ws) < 0.8 * len(ws) and precio not in texto):
            continue
        mostrar = [c for c in cols if c in f and c not in ("precio", "stock") and len(str(f[c])) > 2 and K.n(str(f[c])) in n]
        bloques.append({"cita": cita, "mostrar": mostrar, "por": ""})
    for cita in dict.fromkeys(re.findall(r"(?m)^\s*([RENDS]\d+): ", tool)):
        if cita[0] != "P":
            bloques.append({"cita": cita, "mostrar": [], "por": ""})
    for cita, linea in re.findall(r"(?m)^(R\d+): (.*)$", hoja):
        ws = {w for w in re.findall(r"[a-z0-9]+", K.n(linea)) if len(w) > 4}
        if ws and len(ws & set(re.findall(r"[a-z0-9]+", n))) >= 0.5 * len(ws) and not any(b["cita"] == cita for b in bloques):
            bloques.append({"cita": cita, "mostrar": [], "por": ""})
    if "presupuesto" in n or "[[presupuesto" in n:
        bloques.append({"cita": "PRESUPUESTO", "mostrar": [], "por": ""})
    if "para pagar por" in n or "[[cobro" in n:
        bloques.append({"cita": "COBRO", "mostrar": [], "por": ""})
    oraciones = [o.strip() for linea in texto.split("\n") if not re.match(r"\s*([-*•]|\d+x |Presupuesto|Subtotal|Total|Envio|Pago dividido|\[\[)", linea)
                 for o in re.findall(r"[^.!?]+[.!?]?", re.sub(r"\s*\([^)]*\)", "", linea)) if o.strip()]
    limpias = [o for o in oraciones if not A.datos_en_libre({"saludo": o}, C_TIENDA)]
    dicen = [o for o in limpias if not o.endswith("?")]
    preguntas = [o for o in limpias if o.endswith("?")]
    pregunta = next((o for o in preguntas if re.search(r"transfer|mercado ?pago|pag", K.n(o))), preguntas[-1] if preguntas else "")
    return {"saludo": " ".join(dicen[:2]), "bloques": bloques, "pregunta": pregunta}


class Grabado:
    """El modelo falso: por turno, las llamadas grabadas en orden y despues la respuesta, las veces que la pidan."""
    def __init__(self):
        self.cola, self.final, self.mensaje, self.memoria = [], "", "", None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def turno(self, g: dict) -> None:
        self.cola, self.final, self.mensaje = list(g.get("pasos") or []), g.get("respuesta") or "", g.get("mensaje") or ""
        self.memoria = None

    def _traducidas(self) -> list:
        return traducir(self.cola, self.memoria, self.mensaje) if self.memoria is not None else self.cola

    def _crear(self, **k):
        """TODAS LAS LLAMADAS GRABADAS EN UNA SOLA RESPUESTA, como las manda el modelo de verdad, 5-nov: de a una, un
        turno con muchas llamadas pasaba las vueltas del agente y salia sin respuesta, K20 t1 regrabado."""
        if not self.cola:
            # Un dict es lo que el modelo manda a responder, tal cual; un texto, lo que dijo el modelo antes de la atada.
            return _respuesta({"herramienta": "responder",
                               "pide": self.final if isinstance(self.final, dict) else final_atada(self.final, k)})
        cola = self._traducidas()
        r = _respuesta(cola[0])
        r.choices[0].message.tool_calls = [_respuesta(p).choices[0].message.tool_calls[0] for p in cola]
        self.cola = []
        return r


def _paga(gratis: bool = False):
    """El modelo de produccion con la clave paga, cada llamada al libro y contra el tope del dia. Con la gratis, el
    mismo modelo con GEMINI_API_KEY, que no cuesta y no va al libro: 30-oct, Martin."""
    from openai import OpenAI
    from app.config import get_settings
    from banco_pruebas import libro_paga
    if gratis:
        return OpenAI(api_key=os.environ["GEMINI_API_KEY"].split()[0], base_url=get_settings().GEMINI_BASE_URL)
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("--vivo va con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    s = get_settings()
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD"].split()[0], base_url=s.GEMINI_BASE_URL)
    # Los embeddings del buscador tambien con la paga, como en produccion: con la gratis agotada daban 429.
    s.GEMINI_API_KEY = os.environ["GEMINI_API_KEY_PROD"]
    return libro_paga.envolver(cli)


def _precargar(agente, tienda_id: str) -> None:
    """Los vectores de los rubros, temas y consultas ya medidos, del disco: la gratis deja mil textos por dia, y cada
    corrida volvia a pedir los cientos de la base. El 30-oct se agoto asi. A Google va solo lo que falta, con reintentos."""
    import time
    import numpy as np
    for f in ("buscar_mejoras_emb.npz", "responder_lineas_emb.npz"):
        z = np.load(os.path.join(AQUI, f), allow_pickle=False)
        for k, v in zip(z["claves"].tolist(), z["vectores"].astype(float)):
            tarea, _, texto = k.partition("|")
            agente._VEC[(tarea, texto)] = (v / (np.linalg.norm(v) or 1.0)).tolist()
    textos = [t for t, _ in agente._base(tienda_id)]
    for espera in (0,) + (65,) * 3:
        time.sleep(espera)
        try:
            agente._vectores(textos, "RETRIEVAL_DOCUMENT")
            agente._CAIDOS["hasta"] = 0.0
            return
        except Exception as e:  # noqa: BLE001
            print(f"embeddings: {type(e).__name__}, reintento")
    raise SystemExit("los embeddings no cargan con esta clave: no se corre")


def instalar(vivo: bool = False, gratis: bool = False):
    """El clon del bot con el modelo falso y los parecidos grabados, o con el modelo de produccion y los embeddings de
    verdad. Devuelve el modelo falso y la lista donde quedan los turnos del agente."""
    from banco_pruebas import clon_produccion as C
    C.instalar()
    from app.core import llm_reintento
    from app.core.flujo import agente
    falso = Grabado()
    if vivo and os.environ.get("REPLAY_OPENROUTER"):
        # OPENROUTER CON UN MODELO GRATIS, CLAUDE.md seccion 4: para medir el codigo y lo que recibe el modelo cuando la
        # cuota de Gemini se agoto. Los embeddings, con la paga, 7-nov, orden de Martin: son centavos.
        from openai import OpenAI
        from app.config import get_settings
        cli = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"].split()[0], base_url="https://openrouter.ai/api/v1")
        llm_reintento._cliente = lambda: cli
        llm_reintento._modelo = lambda: os.environ["REPLAY_OPENROUTER"]
        if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            raise SystemExit("los embeddings van con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
        get_settings().GEMINI_API_KEY = os.environ["GEMINI_API_KEY_PROD"]
        _precargar(agente, C.TIENDA)
    elif vivo:
        cli = _paga(gratis)
        llm_reintento._cliente = lambda: cli
        _precargar(agente, C.TIENDA)
        # Lo que dieron los embeddings de verdad queda anotado: si se regraba, el replay sin modelo lo usa.
        parecidos_vivos = agente._parecidos

        def _anota(consulta, tipo, tienda_id):
            r = parecidos_vivos(consulta, tipo, tienda_id)
            VISTOS_PARECIDOS[f"{tipo}|{consulta}"] = [[k, round(x, 4)] for k, x in r[:3]]
            return r
        agente._parecidos = _anota
    else:
        llm_reintento._cliente = lambda: falso
        tabla = json.load(open(PARECIDOS, encoding="utf-8"))
        agente._parecidos = lambda consulta, tipo, tienda_id: [tuple(x) for x in tabla.get(f"{tipo}|{consulta}", [])]
    vistos = []
    responder = agente.responder

    async def _espia(*a, **k):
        falso.memoria = a[2] if len(a) > 2 else k.get("memoria")  # el modelo simulado traduce contra esta libreta
        falso.mensaje = a[0] if a else k.get("mensaje") or ""
        r = await responder(*a, **k)
        vistos.append(r)
        return r
    agente.responder = _espia
    return falso, vistos


def guardadas(etiqueta: str) -> dict:
    """{id: [fila por turno]} de las charlas ya corridas con esa etiqueta."""
    out: dict = {}
    if os.path.exists(VIVO):
        for r in map(json.loads, open(VIVO, encoding="utf-8")):
            if r.get("etiqueta") == etiqueta:
                out.setdefault(r["id"], []).append(r)
    return out


# LA GRATIS CORTA POR MINUTO, 2-nov: sin pausa, la base del paso 0 se corto en la novena charla con 429 y la clave
# contestaba de nuevo enseguida. Con la gratis, una pausa entre turnos; y una charla cortada se repite despues de un
# minuto, hasta dos veces, antes de dar la cuota del dia por terminada.
PAUSA_GRATIS_S, ESPERA_CORTE_S, INTENTOS = 6, 65, 3


def _una(ch: str, grabados: list, falso, vistos, vara: dict, pausa: float) -> list:
    """Las filas de una charla entera, turno por turno."""
    import time
    from banco_pruebas import clon_produccion as C
    from banco_pruebas.sonda_charlas import nota_casilla
    uid = f"agente_{ch}"
    C.reiniciar_cliente(uid)
    respuestas, filas = [], []
    for g in grabados:
        time.sleep(pausa)
        falso.turno(g)
        vistos.clear()
        texto = "\n".join(asyncio.run(C.turno(uid, g["mensaje"])))
        respuestas.append(texto)
        casillas = vara[ch]["turnos"][g["turno"]]["casillas"]
        malas = [k["n"] for k in casillas if nota_casilla(k, [], texto, respuestas) is not True]
        vivos = (vistos[-1].get("pasos") if vistos else None) or []
        # LO TRADUCIDO NO SE COMPARA, paso 2: es otra herramienta, y lo que devuelve es lo que se mide en las casillas.
        distintas = [p["herramienta"] for p, v in zip(g.get("pasos") or [], vivos)
                     if p["herramienta"] == v["herramienta"] and _sin_numeros(p["devuelve"]) != _sin_numeros(v["devuelve"])]
        traducidas = sum(p["herramienta"] != v["herramienta"] for p, v in zip(g.get("pasos") or [], vivos))
        filas.append({"id": ch, "turno": g["turno"], "malas": malas, "distintas": distintas, "traducidas": traducidas,
                      "texto": texto, "pasos_vivos": vivos, "pasos": g.get("pasos") or [],
                      "mensaje": g["mensaje"], "respuesta": vistos[-1].get("respuesta") if vistos else None})
    return filas


def correr(ids: list = None, vivo: bool = False, gratis: bool = False, etiqueta: str = "") -> dict:
    """{"turnos", "bien", "llamadas", "iguales", "filas"} de las charlas grabadas por el agente vivo. Con etiqueta, cada
    charla entera se guarda apenas termina y las ya guardadas no se corren; una charla con un turno sin respuesta del
    modelo se repite despues de un minuto, y si sigue sin respuesta corta la corrida: es la cuota, y se sigue otro dia."""
    import time
    falso, vistos = instalar(vivo, gratis)
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    out = {"turnos": 0, "bien": 0, "llamadas": 0, "iguales": 0, "filas": [], "cortada": False}
    hechas = guardadas(etiqueta) if etiqueta else {}
    for ch, grabados in _charlas().items():
        if (ids and ch not in ids) or ch in hechas:
            continue
        for intento in range(INTENTOS if etiqueta else 1):
            if intento:
                print(f"{ch}: un turno sin respuesta del modelo, se repite en {ESPERA_CORTE_S} segundos", flush=True)
                time.sleep(ESPERA_CORTE_S)
            VISTOS_PARECIDOS.clear()
            filas = _una(ch, grabados, falso, vistos, vara, PAUSA_GRATIS_S if gratis else 0)
            if all(f["respuesta"] is not None for f in filas):
                break
        if etiqueta and any(f["respuesta"] is None for f in filas):
            print(f"{ch}: sin respuesta del modelo {INTENTOS} veces, no se guarda y la corrida se corta", flush=True)
            out["cortada"] = True
            break
        for f in filas:
            n = len(f["pasos"]) - f["traducidas"]
            out["turnos"] += 1
            out["bien"] += not f["malas"]
            out["llamadas"] += n
            out["iguales"] += n - len(f["distintas"]) - max(0, n - len(f["pasos_vivos"]) + f["traducidas"])
        out["filas"] += filas
        if etiqueta:
            with open(VIVO, "a", encoding="utf-8") as fh:
                for f in filas:
                    fh.write(json.dumps({**{k: f[k] for k in ("id", "turno", "malas", "texto", "pasos_vivos",
                                                              "mensaje", "respuesta")},
                                         "clave": "gratis" if gratis else "paga", "etiqueta": etiqueta,
                                         "parecidos": dict(VISTOS_PARECIDOS)}, ensure_ascii=False) + "\n")
            print(f"{ch}: guardada, {sum(not f['malas'] for f in filas)} de {len(filas)} turnos bien", flush=True)
    return out


def regrabar(filas: list) -> None:
    """Las charlas corridas con el modelo pasan a ser lo grabado, en el mismo formato. Solo enteras: si un turno no tuvo
    respuesta del modelo, no se graba nada."""
    for f in filas:
        VISTOS_PARECIDOS.update(f.get("parecidos") or {})
    if not filas or any(f["respuesta"] is None for f in filas):
        raise SystemExit("no se regraba: algun turno quedo sin respuesta del modelo")
    if any(not v for v in VISTOS_PARECIDOS.values()):
        raise SystemExit("no se regraba: los embeddings fallaron en alguna busqueda")
    nuevas = {f["id"] for f in filas}
    viejas = [r for r in map(json.loads, open(GRABADO, encoding="utf-8")) if r["id"] not in nuevas]
    with open(GRABADO, "w", encoding="utf-8") as fh:
        for r in viejas + [{"id": f["id"], "turno": f["turno"], "mensaje": f["mensaje"], "respuesta": f["respuesta"],
                            "pasos": [{k: p[k] for k in ("herramienta", "pide", "devuelve")} for p in f["pasos_vivos"]],
                            "regrabado": f.get("etiqueta") or "30-oct"} for f in filas]:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tabla = json.load(open(PARECIDOS, encoding="utf-8"))
    tabla.update(VISTOS_PARECIDOS)
    json.dump(tabla, open(PARECIDOS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"regrabadas: {sorted(nuevas)}; {len(VISTOS_PARECIDOS)} consultas a los parecidos")


def parecidos() -> None:
    """Los rubros y temas mas parecidos de cada consulta grabada, con los vectores guardados del banco."""
    import numpy as np
    from banco_pruebas import clon_produccion as C
    C.instalar()
    from app.core.flujo import agente
    vec = {}
    for f in ("buscar_mejoras_emb.npz", "responder_lineas_emb.npz"):
        z = np.load(os.path.join(AQUI, f), allow_pickle=False)
        vec.update(zip(z["claves"].tolist(), z["vectores"].astype(np.float32)))

    def _vectores(textos, tarea):
        out = []
        for t in textos:
            v = vec[f"{tarea}|{t}"]
            out.append((v / np.linalg.norm(v)).tolist())
        return out
    agente._vectores = _vectores
    consultas = sorted({p["pide"].get("consulta") or "" for rs in _charlas().values() for r in rs
                        for p in r.get("pasos") or [] if p["herramienta"] == "buscar"})
    tabla, faltan = {}, 0
    for q in consultas:
        for tipo in ("rubro", "tema"):
            try:
                tabla[f"{tipo}|{q}"] = [[k, round(s, 4)] for k, s in agente._parecidos(q, tipo, C.TIENDA)[:3]]
            except KeyError:
                faltan += 1
    json.dump(tabla, open(PARECIDOS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(consultas)} consultas, {len(tabla)} entradas, {faltan} sin vector guardado")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--parecidos" in args:
        parecidos()
        raise SystemExit
    gratis = "--gratis" in args
    etiqueta = args[args.index("--etiqueta") + 1] if "--etiqueta" in args else ""
    if etiqueta:
        args.remove(etiqueta)
    elif "--vivo" in args or gratis:
        raise SystemExit("con el modelo va --etiqueta: cada charla se guarda apenas termina")
    pedidas = [a for a in args if not a.startswith("--")]
    r = correr(pedidas, vivo="--vivo" in args or gratis, gratis=gratis, etiqueta=etiqueta)
    if "--regrabar" in args:
        hechas = guardadas(etiqueta)
        faltan = sorted(set(pedidas or _charlas()) - set(hechas))
        if faltan:
            raise SystemExit(f"no se regraba todavia: faltan {faltan}; la misma orden otro dia sigue")
        regrabar([f for ch in sorted(hechas) if not pedidas or ch in pedidas
                  for f in sorted(hechas[ch], key=lambda x: x["turno"])])
    for f in r["filas"]:
        if f["malas"] or f["distintas"]:
            print(f"{f['id']} t{f['turno'] + 1}: MAL {f['malas']} · distintas {f['distintas']}")
            if "--ver" in args:
                print("  " + f["texto"][:600].replace("\n", "\n  "))
    if r.get("cortada"):
        print("\nCORTADA: la cuota no alcanzo. Lo guardado queda; la misma orden otro dia sigue desde la que falta.")
    print(f"\nEL AGENTE VIVO CON LO GRABADO: {r['bien']} de {r['turnos']} turnos bien · {r['iguales']} de "
          f"{r['llamadas']} llamadas a herramientas devuelven lo mismo que en el banco")
