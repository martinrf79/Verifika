"""EL MARCADOR — lo que el codigo reconoce en el mensaje, antes del modelo (20-oct-2026).

El modelo elige entre lo que la tienda tiene, no adivina. El marcador recorre el mensaje y anota cada pedazo que
reconoce en la fuente: un modelo del catalogo, un rubro, un tema de la FAQ, algo que la tienda no vende, un porcentaje
o un monto. Todo sale de la fuente de la tienda; las unicas palabras fijas son numeros escritos en letras.

Es una tabla corta que va en el mensaje al modelo. No decide nada: lo que el marcador no reconoce, el modelo lo copia
del cliente y el codigo lo verifica despues.
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


def tabla(mensaje: str, tienda_id: str) -> str:
    marcas = marcar(mensaje, tienda_id)
    if not marcas:
        return "LO QUE EL CODIGO RECONOCIO EN EL MENSAJE: nada."
    return "LO QUE EL CODIGO RECONOCIO EN EL MENSAJE:\n" + "\n".join(f'- "{d}" es {e}' for d, e in marcas)
