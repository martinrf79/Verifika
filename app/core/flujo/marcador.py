"""EL MARCADOR — lo que el codigo reconoce en el mensaje, antes del modelo (20-oct-2026).

El modelo elige entre lo que la tienda tiene, no adivina. El marcador recorre el mensaje y anota cada pedazo que
reconoce en la fuente: un modelo del catalogo, un rubro, un tema de la FAQ, algo que la tienda no vende, un porcentaje
o un monto. Todo sale de la fuente de la tienda; las unicas palabras fijas son numeros escritos en letras.

Desde la ficha nativa, FICHA 76, no va al modelo: el rubro y el tema se le ofrecen como listas cerradas en el esquema.
Lo usan el paso de la ficha a la agenda, `ficha.py`, y la forma normal, `normal.py`, para atar palabras a la fuente.
"""
import re

from app.core import agente

from . import catalogo as K

_NUMEROS = {"diez": 10, "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
            "ochenta": 80, "noventa": 90, "cien": 100, "mitad": 50}
# Dos porcentajes que suman cien, con hasta cuatro palabras en el medio: "70 transferencia y 30 mercado pago".
_N = r"(\d{1,2}|" + "|".join(_NUMEROS) + r")"
_PAR = re.compile(r"\b" + _N + r"\s*%?(?:\s*[a-z/,-]+){0,4}?\s*[\s/,-]\s*" + _N
                  + r"\b(?!\s*(?:mil|k|lucas|gb|tb|hz|w|pulgadas)\b)")
_MONTO = re.compile(r"\$?\s*(\d[\d.,]*)\s*(millones|millon|mil|k|lucas)\b|\$\s*(\d[\d.,]*)")


def _numero(t: str) -> int:
    return _NUMEROS.get(t) or K.entero(t)


def _modelo(p: dict) -> str:
    return f"{p.get('categoria', '').capitalize()} {p.get('marca') or ''} {p.get('modelo') or p['nombre']}".strip()


def _propias(p: dict) -> set:
    return set(K.n(f"{p.get('categoria')} {p.get('marca')} {p.get('modelo')} {p.get('color')}").split())


def _productos(ws: list, tienda_id: str) -> list:
    """Cada tramo de hasta cuatro palabras que nombra un modelo, sin pisarse: primero los que dan uno solo, despues
    los que dan dos o tres. El tramo tiene que traer una palabra con letras del modelo mismo —"G305", "Stinger"—:
    "mouse inalambrico" es una busqueda. Las puntas que no son del producto se recortan: "cuanto sale g305" es "g305"."""
    de_modelo = {w for p in K.productos(tienda_id) for w in K.n(p.get("modelo")).split() if re.search(r"[a-z]", w)}
    hallados, usadas, vistos = [], set(), {}
    for una in (True, False):
        for tam in range(min(4, len(ws)), 0, -1):
            for i in range(len(ws) - tam + 1):
                if set(range(i, i + tam)) & usadas or not de_modelo & set(ws[i:i + tam]):
                    continue
                tramo = " ".join(ws[i:i + tam])
                if tramo not in vistos:
                    idt = K.identificar(tramo, "", tienda_id)
                    vistos[tramo] = [idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or []
                ps = vistos[tramo]
                if not ps or (len(ps) == 1) != una or len(ps) > 3 or not all(
                        set(K.n(p.get("modelo")).split()) & de_modelo & set(ws[i:i + tam]) for p in ps):
                    continue
                propias = set().union(*map(_propias, ps))
                a, b = i, i + tam
                while ws[a] not in propias:
                    a += 1
                while ws[b - 1] not in propias:
                    b -= 1
                usadas |= set(range(i, i + tam))
                if una:
                    colores = [v["color"] for v in K._colores_de(ps[0], K.productos(tienda_id)) if v.get("color")]
                    es = f"el producto {_modelo(ps[0])}" + (f", en {' o '.join(colores)}" if len(colores) > 1 else "")
                else:
                    es = "puede ser " + " o ".join(_modelo(p) for p in ps)
                hallados.append((a, " ".join(ws[a:b]), es))
    return [(d, e) for _, d, e in sorted(hallados)]


def _rubros(ws: list, tienda_id: str) -> list:
    """Cada palabra que nombra un rubro por su nombre —"memorias" es memoria ram— y cada alias de la tienda dicho
    entero —"placa madre", "auris"—."""
    alias = (agente._alias(tienda_id).get("rubros") or {})
    por_palabra = {}
    for r in agente.indice(tienda_id)["rubros"]:
        for w in K.n(r).split():
            if len(w) > 3:
                por_palabra.setdefault(w[:5], set()).add(r)
    out = [(w, next(iter(por_palabra[w[:5]]))) for w in dict.fromkeys(ws)
           if len(w) > 3 and len(por_palabra.get(w[:5]) or ()) == 1]
    texto = f" {' '.join(ws)} "
    for r, frases in alias.items():
        for f in frases:
            f = " ".join(w for w in re.findall(r"[a-z0-9]+", K.n(f)) if w not in ("el", "la", "los", "las"))
            if f and f" {f} " in texto and all(f != d for d, _ in out):
                out.append((f, r))
    return out


def _temas(texto: str, tienda_id: str) -> dict:
    """Los temas de la FAQ o de un alias de la tienda cuya frase aparece entera en el mensaje, y los de cada alias cuyas
    palabras propias, dos o mas, estan todas en el mensaje: "es gratis el envio" es costo_envio en cualquier orden. Una
    palabra es propia si aparece en pocos temas; "tienen" o "cuanto" no distinguen ninguno."""
    ws = re.findall(r"[a-z0-9]+", K.n(texto))
    t, dichas = f" {' '.join(ws)} ", set(ws)
    alias = agente._alias(tienda_id).get("temas") or {}
    frases = {tema: [" ".join(re.findall(r"[a-z0-9]+", f)) for f in d["frases"]]
              for tema, d in agente.indice(tienda_id)["temas"].items()}
    cuantos = {}
    for tema in frases:
        for w in {w for f in frases[tema] + [K.n(x) for x in alias.get(tema) or []] for w in re.findall(r"[a-z0-9]+", f)}:
            cuantos[w] = cuantos.get(w, 0) + 1
    out = {}
    for tema, fs in frases.items():
        for f in fs:
            if f and f" {f} " in t:
                out.setdefault(f, []).append(tema)
        for f in alias.get(tema) or []:
            entera = " ".join(re.findall(r"[a-z0-9]+", K.n(f)))
            propias = [w for w in entera.split() if len(w) > 3 and cuantos.get(w, 0) <= 3]
            if tema in sum(out.values(), []):
                continue
            if entera and f" {entera} " in t:
                out.setdefault(entera, []).append(tema)
            elif len(propias) > 1 and set(propias) <= dichas:
                out.setdefault(" ".join(propias), []).append(tema)
    return out


def marcar(mensaje: str, tienda_id: str) -> list:
    """[(lo que dijo, lo que es)], en el orden en que aparece cada tipo."""
    from app.core.guia_compra import _no_vendidas
    n = K.n(mensaje)
    ws = re.findall(r"[a-z0-9]+", n)
    out = _productos([w for w in ws if w not in K._RELLENO], tienda_id)
    out += [(w, f"el rubro {r}") for w, r in _rubros(ws, tienda_id)]
    for cosa, alternativa in _no_vendidas(tienda_id).items():
        if re.search(rf"\b{re.escape(K.n(cosa))}", n):
            out.append((cosa, "algo que la tienda no vende" + (f"; lo mas parecido: {alternativa}" if alternativa else "")))
    # "Si pregunta": una palabra de la FAQ tambien aparece en un pedido —"con envio", "partes chinas"—, y ahi no es
    # una politica. La consigna lo dice con ejemplos.
    out += [(f, "SOLO si pregunta una regla de la tienda, el tema " + " o ".join(ts))
            for f, ts in _temas(mensaje, tienda_id).items()]
    for m in _PAR.finditer(n):
        a, b = _numero(m.group(1)), _numero(m.group(2))
        if a + b == 100:
            out.append((m.group(0).strip(), f"{a} y {b} por ciento"))
    for m in _MONTO.finditer(n):
        if m.group(2) or m.group(3):
            out.append((m.group(0).strip(), f"{K._monto(m.group(1) or m.group(3), m.group(2) or ''):,} pesos".replace(",", ".")))
    return out


# ══ LA RESPUESTA CORTA: lo que contesta una pregunta del bot, leido contra lo que esa pregunta espera ══════════════
# Orden de Martin del 21 y 23-oct: cada pregunta del bot guarda que espera —un color, si o no, cual de varios, el
# nombre—, y la respuesta se lee solo contra esa lista cerrada. Las palabras fijas tienen su defecto aca y cada tienda
# las cambia en "respuestas" de su `alias.json`, decision 47: {"si": [...], "no": [...], "ordinales": {"frase": n},
# "presentacion": [...]}. La equipo la lee la compatibilidad, con su vocabulario: ver `ejecutor.atar_esperas`.

RESPUESTAS = {
    "si": "si sii dale ok oka okey listo perfecto bueno va joya correcto exacto asi esta bien dejalo deja genial "
          "barbaro de una seguro claro buenisimo".split(),
    "no": ["no", "nop", "nah", "para nada", "mejor no", "todavia no", "ninguno", "ninguna"],
    "ordinales": {"primero": 0, "primera": 0, "1": 0, "segundo": 1, "segunda": 1, "2": 1, "tercero": 2, "tercera": 2,
                  "3": 2, "cuarto": 3, "cuarta": 3, "4": 3, "ultimo": -1, "ultima": -1},
    "presentacion": ["me llamo", "mi nombre es", "a nombre de", "soy", "es"],
}
_VOCAB = {}


def vocabulario_respuestas(tienda_id: str) -> dict:
    """Las palabras de la respuesta corta: el defecto, con lo que la tienda cambie en sus alias."""
    if tienda_id not in _VOCAB:
        propio = agente._alias(tienda_id).get("respuestas") or {}
        v = {k: propio.get(k) or d for k, d in RESPUESTAS.items()}
        v["si"], v["no"] = [K.n(x) for x in v["si"]], [K.n(x) for x in v["no"]]
        v["ordinales"] = {K.n(f): int(i) for f, i in v["ordinales"].items()}
        v["presentacion"] = [K.n(x) for x in v["presentacion"]]
        _VOCAB[tienda_id] = v
    return _VOCAB[tienda_id]


def _sacar(texto: str, frases) -> tuple:
    """El texto sin las frases dichas enteras, y cuales estaban."""
    t, dichas = f" {texto} ", []
    for f in sorted(frases, key=len, reverse=True):
        if f and f" {f} " in t:
            dichas.append(f)
            t = t.replace(f" {f} ", " ")
    return " ".join(t.split()), dichas


def _mismo(w: str, opcion: str) -> bool:
    """Una palabra dice la opcion, con su genero o su plural: "negra" es "negro", "blancos" es "blanco"."""
    return w == opcion or (len(opcion) > 3 and w.rstrip("s")[:-1] == opcion[:-1] and len(w.rstrip("s")) == len(opcion))


def respuesta(texto: str, espera: dict, tienda_id: str):
    """Lo que la respuesta corta contesta, de lo que la pregunta espera, o None si no lo dice de una sola forma:
    "si" o "no"; uno de los colores; una de las opciones, por su lugar —"el primero"— o por la palabra que solo ella
    tiene —"el King"—; o el nombre del cliente, si es solo un nombre que la tienda no reconoce como otra cosa."""
    from .agenda import _VACIAS
    v = vocabulario_respuestas(tienda_id)
    t = " ".join(re.findall(r"[a-z0-9]+", K.n(texto)))
    tipo, opciones = espera.get("tipo"), [str(o) for o in espera.get("opciones") or []]
    if tipo == "si_no":
        resto, nos = _sacar(t, v["no"])
        resto, sis = _sacar(resto, v["si"])
        if any(w not in _VACIAS for w in resto.split()) or bool(nos) == bool(sis):
            return None
        return "no" if nos else "si"
    if tipo == "color":
        ws = t.split()
        dichos = [o for o in opciones if any(_mismo(w, K.n(o)) for w in ws)]
        return dichos[0] if len(dichos) == 1 else None
    if tipo == "cual":
        _, lugares = _sacar(t, v["ordinales"])
        if len(lugares) == 1 and -len(opciones) <= v["ordinales"][lugares[0]] < len(opciones):
            return opciones[v["ordinales"][lugares[0]]]
        ws = set(t.split()) - _VACIAS
        propias = [set(K.n(o).split()) for o in opciones]
        comunes = set.intersection(*propias) if propias else set()
        dichos = [o for o, p in zip(opciones, propias) if ws & (p - comunes)]
        return dichos[0] if len(dichos) == 1 and not lugares else None
    if tipo == "nombre":
        resto, _ = _sacar(t, v["presentacion"])
        ws = resto.split()
        if not 0 < len(ws) <= 4 or any(w in _VACIAS or w in v["si"] or w in v["no"] or w.isdigit() for w in ws) \
                or marcar(resto, tienda_id):
            return None
        # Como lo escribio: "martina gomez" queda con mayusculas, "Martín" con su tilde.
        crudas = [w for w in re.findall(r"[^\W\d_]+", str(texto)) if K.n(w) in ws]
        return " ".join(w[:1].upper() + w[1:] for w in crudas) or None
    return None
