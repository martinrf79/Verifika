"""LOS EJEMPLOS RESUELTOS DEL INTERPRETE, elegidos por parecido (FICHA 67, 7-oct-2026).

El interprete del tablero recibe, ademas de sus reglas, los ejemplos resueltos
mas parecidos al mensaje: cada uno con su memoria, el mensaje del cliente y las
piezas correctas. Los elige el CODIGO, no el modelo. Medido en la ficha 67 con
la forma de los nexos: el modelo de produccion paso de 9 de 12 a 12 de 12 en la
reserva limpia. Aca va la misma idea en el formato de piezas, asi la ejecucion,
la plata y el cierre son los de siempre.

LA FUENTE es `ejemplos_interprete.json`: las 58 combinaciones de la ficha 58,
los cuatro numeros nuevos y algunas variantes, escritas con sus palabras y no
copiadas de los casos del banco. Una traduccion mal hecha en produccion se
corrige UNA vez y entra ahi como un ejemplo mas: cubre a todos los mensajes
parecidos sin tocar el prompt. `tests/test_ejemplos.py` exige que cada ejemplo
pase la atadura del tablero.

Recuperacion: TF-IDF sobre palabras, sin dependencias. El mensaje se parte en
clausulas solo para buscar: el mensaje entero trae sus tres ejemplos mas
parecidos y cada clausula los suyos, hasta ocho sin repetir. Si la charla
tiene un pedido vigente, van primero los ejemplos de estado "pedido".
"""
import json
import math
import os
import re
import unicodedata

FUENTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ejemplos_interprete.json")

_VACIAS = set("de la el los las y o a en que con un una me te se lo le por para es mi su del al si no hay "
              "cuanto cual sale tenes tiene".split())


def _n(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _toks(t: str) -> list:
    return [w for w in re.findall(r"[a-z0-9]+", _n(t)) if w not in _VACIAS and len(w) > 1]


def _cargar() -> tuple:
    ejemplos = json.load(open(FUENTE, encoding="utf-8"))["ejemplos"]
    docs = [_toks(e["mensaje"] + " " + json.dumps(e["piezas"], ensure_ascii=False)) for e in ejemplos]
    df: dict = {}
    for d in docs:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log((1 + len(docs)) / (1 + f)) + 1 for w, f in df.items()}
    return ejemplos, idf


EJEMPLOS, _IDF = _cargar()


def _vec(toks: list) -> dict:
    v: dict = {}
    for w in toks:
        v[w] = v.get(w, 0) + _IDF.get(w, 0.0)
    nrm = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {w: x / nrm for w, x in v.items()}


_VEC = [_vec(_toks(e["mensaje"])) for e in EJEMPLOS]  # se compara contra el MENSAJE del ejemplo


def _sim(a: dict, b: dict) -> float:
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def clausulas(mensaje: str) -> list:
    partes = re.split(r"[?.!;]|,|\by\b|\bsi\b", _n(mensaje))
    return [p.strip() for p in partes if _toks(p)]


def elegir(mensaje: str, k_total: int = 8, k_clausula: int = 2, k_entero: int = 3, estado: str = "") -> list:
    """Los ejemplos mas parecidos: los del mensaje entero y los de cada clausula, sin repetir. Con un
    `estado` de la charla —"pedido"—, primero los ejemplos de ese estado: "si" o "sip" no tienen
    palabras para parecerse, y lo que deciden es el estado en que llegan."""
    elegidos: list = [i for i, e in enumerate(EJEMPLOS) if estado and e.get("estado") == estado]

    def top(texto, k):
        v = _vec(_toks(texto))
        orden = sorted(range(len(EJEMPLOS)), key=lambda i: -_sim(v, _VEC[i]))
        return [i for i in orden[:k] if _sim(v, _VEC[i]) > 0]

    for texto, k in [(mensaje, k_entero)] + [(c, k_clausula) for c in clausulas(mensaje)]:
        for i in top(texto, k):
            if i not in elegidos:
                elegidos.append(i)
    return [EJEMPLOS[i] for i in elegidos[:k_total]]


def bloque(mensaje: str, estado: str = "") -> str:
    """El texto que va al final del prompt del interprete. Vacio si nada se parece."""
    elegidos = elegir(mensaje, estado=estado)
    if not elegidos:
        return ""
    out = ["EJEMPLOS RESUELTOS, parecidos a este mensaje. La memoria de cada ejemplo es la de ESE ejemplo, no la de "
           "esta charla: copia la forma de partir, no los productos."]
    for e in elegidos:
        out.append(("MEMORIA: " + e["memoria"] + "\n" if e.get("memoria") else "")
                   + f"CLIENTE: {e['mensaje']}\n"
                   + json.dumps({"piezas": e["piezas"]}, ensure_ascii=False))
    return "\n\n".join(out)
