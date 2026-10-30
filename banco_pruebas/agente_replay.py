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


class Grabado:
    """El modelo falso: por turno, las llamadas grabadas en orden y despues la respuesta, las veces que la pidan."""
    def __init__(self):
        self.cola, self.final = [], ""
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def turno(self, g: dict) -> None:
        self.cola, self.final = list(g.get("pasos") or []), g.get("respuesta") or ""

    def _crear(self, **k):
        return _respuesta(self.cola.pop(0)) if self.cola else _respuesta(texto=self.final)


def _paga():
    """El modelo de produccion con la clave paga, cada llamada al libro y contra el tope del dia."""
    from openai import OpenAI
    from app.config import get_settings
    from banco_pruebas import libro_paga
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("--vivo va con la paga: MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD"].split()[0], base_url=get_settings().GEMINI_BASE_URL)
    return libro_paga.envolver(cli)


def instalar(vivo: bool = False):
    """El clon del bot con el modelo falso y los parecidos grabados, o con el modelo de produccion y los embeddings de
    verdad. Devuelve el modelo falso y la lista donde quedan los turnos del agente."""
    from banco_pruebas import clon_produccion as C
    C.instalar()
    from app.core import llm_reintento
    from app.core.flujo import agente
    falso = Grabado()
    if vivo:
        cli = _paga()
        llm_reintento._cliente = lambda: cli
    else:
        llm_reintento._cliente = lambda: falso
        tabla = json.load(open(PARECIDOS, encoding="utf-8"))
        agente._parecidos = lambda consulta, tipo, tienda_id: [tuple(x) for x in tabla.get(f"{tipo}|{consulta}", [])]
    vistos = []
    responder = agente.responder

    async def _espia(*a, **k):
        r = await responder(*a, **k)
        vistos.append(r)
        return r
    agente.responder = _espia
    return falso, vistos


def correr(ids: list = None, vivo: bool = False) -> dict:
    """{"turnos", "bien", "llamadas", "iguales", "filas"} de las charlas grabadas por el agente vivo."""
    from banco_pruebas import clon_produccion as C
    from banco_pruebas.sonda_charlas import nota_casilla
    falso, vistos = instalar(vivo)
    vara = {c["id"]: c for c in json.load(open(os.path.join(AQUI, "vara_58.json"), encoding="utf-8"))["charlas"]}
    out = {"turnos": 0, "bien": 0, "llamadas": 0, "iguales": 0, "filas": []}
    for ch, grabados in _charlas().items():
        if ids and ch not in ids:
            continue
        uid = f"agente_{ch}"
        C.reiniciar_cliente(uid)
        respuestas = []
        for g in grabados:
            falso.turno(g)
            vistos.clear()
            texto = "\n".join(asyncio.run(C.turno(uid, g["mensaje"])))
            respuestas.append(texto)
            casillas = vara[ch]["turnos"][g["turno"]]["casillas"]
            malas = [k["n"] for k in casillas if nota_casilla(k, [], texto, respuestas) is not True]
            vivos = (vistos[-1].get("pasos") if vistos else None) or []
            distintas = [p["herramienta"] for p, v in zip(g.get("pasos") or [], vivos) if p["devuelve"] != v["devuelve"]]
            out["turnos"] += 1
            out["bien"] += not malas
            out["llamadas"] += len(g.get("pasos") or [])
            out["iguales"] += len(g.get("pasos") or []) - len(distintas) - max(0, len(g.get("pasos") or []) - len(vivos))
            out["filas"].append({"id": ch, "turno": g["turno"], "malas": malas, "distintas": distintas,
                                 "texto": texto, "pasos_vivos": vivos, "pasos": g.get("pasos") or []})
    return out


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
    r = correr([a for a in args if not a.startswith("--")], vivo="--vivo" in args)
    if "--vivo" in args:
        with open(os.path.join(AQUI, "agente_vivo.jsonl"), "a", encoding="utf-8") as fh:
            for f in r["filas"]:
                fh.write(json.dumps({k: f[k] for k in ("id", "turno", "malas", "texto", "pasos_vivos")},
                                    ensure_ascii=False) + "\n")
    for f in r["filas"]:
        if f["malas"] or f["distintas"]:
            print(f"{f['id']} t{f['turno'] + 1}: MAL {f['malas']} · distintas {f['distintas']}")
            if "--ver" in args:
                print("  " + f["texto"][:600].replace("\n", "\n  "))
    print(f"\nEL AGENTE VIVO CON LO GRABADO: {r['bien']} de {r['turnos']} turnos bien · {r['iguales']} de "
          f"{r['llamadas']} llamadas a herramientas devuelven lo mismo que en el banco")
