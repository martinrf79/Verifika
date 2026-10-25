"""LA IDENTIDAD DE LO QUE NOMBRA LA LECTURA — lo que un articulo dicho es en la tienda, sin modelo (FICHA 76 y 81).

Fue el paso de la ficha nativa a la agenda, FICHA 76; desde el 25-oct la lectura de los dos ejes, `lectura.py`, la
reemplaza, FICHA 81, y de aca usa lo que no depende de la forma de la salida:
  _que       un articulo dicho a lo que es: su renglon L-n, un numero de lo mostrado, un modelo que la tienda identifica y
             que el cliente nombro o leyo, un rubro, o las palabras libres que el ejecutor pregunta.
  _vistos    las familias que nombra el mensaje y las que el cliente leyo: el modelo de lenguaje no elige productos.
  _rubro     el rubro de la lista cerrada, o el que nombran las palabras.
  _refs      los numeros de la libreta que nombra un texto.
"""
import re

from . import catalogo as K

NADA = "nada"
OTRO = "otro"
NINGUNO = "ninguno"


def _rubros(tienda_id: str) -> list:
    from app.core import agente
    return sorted(agente.indice(tienda_id)["rubros"])


def _temas_de(tienda_id: str) -> list:
    from app.core import agente
    return list(agente.indice(tienda_id)["temas"])


VACIO = ("", "sin decir", "ninguna", "ninguno", "ningun", "null", "none", "no especificado", "no especificada", "n/a",
         "nada", "no", "no aplica", "nuevo", "sin especificar", "cualquiera")
_REF = re.compile(r"\b([MLR])-?(\d+)\b")


def _lista(x) -> list:
    return x if isinstance(x, list) else ([] if x in (None, "") else [x])


def _dicho(v) -> str:
    """El valor, o "" si es relleno: "sin decir", "ninguna", null."""
    return "" if K.n(v) in VACIO else str(v).strip()


def _refs(texto, nums: dict) -> list:
    """Los numeros de la libreta que nombra un texto, como los escribe la libreta: "M2" y "M-2" son "M-2"."""
    out = []
    for m in _REF.finditer(str(texto or "")):
        r = f"{m.group(1)}-{m.group(2)}"
        if r in nums and r not in out:
            out.append(r)
    return out



def _orden(*vs) -> str:
    return next((K.n(v) for v in vs if K.n(v) in K.ORDEN), NADA)




def _rubro(texto: str, tienda_id: str, dicho: str = "") -> str:
    """El rubro que eligio el modelo de la lista cerrada; si no eligio, el que nombra el texto."""
    from .marcador import _rubros
    if dicho and dicho in _rubros_de(tienda_id):
        return dicho
    if K.n(dicho) == NINGUNO:
        return ""
    lexico = _rubros(K.n(texto).split(), tienda_id)
    return K.solo_rubro(texto, tienda_id) or (lexico[0][1] if lexico else "") or K.rubro(texto, tienda_id)


def _rubros_de(tienda_id: str) -> set:
    return set(_rubros(tienda_id))



def _es_modelo(texto: str, color: str, tienda_id: str, vistos: set = None) -> bool:
    """Nombra un modelo: el marcador lo reconoce por una palabra del modelo mismo, y la identidad lo certifica.
    "mouse inalambrico" es una busqueda aunque la identidad aproxime uno. Con `vistos`, el modelo tiene que ser uno que
    el cliente nombro o leyo: el modelo de lenguaje no elige productos, FICHA 76."""
    from .marcador import _productos
    if not _productos(re.findall(r"[a-z0-9]+", K.n(texto)), tienda_id):
        return False
    idt = K.identificar(texto, color, tienda_id)
    return idt["veredicto"] == "exists" and (vistos is None or _familia(idt["producto"]) in vistos)


def _nombra_varios(texto: str, tienda_id: str, vistos: set = None) -> bool:
    """Nombra un modelo que la identidad no puede certificar porque son varios —"Redragon Cobra" es el Cobra M711 y el
    King Cobra—, todos nombrados por el cliente. No es una busqueda: el borrador pregunta cual, con su espera."""
    from .marcador import _productos
    if not _productos(re.findall(r"[a-z0-9]+", K.n(texto)), tienda_id):
        return False
    idt = K.identificar(texto, "", tienda_id)
    return idt["veredicto"] == "ambiguous" and bool(idt.get("opciones")) \
        and (vistos is None or all(_familia(p) in vistos for p in idt["opciones"]))


def _familia(p: dict) -> str:
    """La marca y la linea del modelo: la Fury Beast de 32 es de la familia de la de 16 que el cliente vio."""
    return " ".join([K.n(p.get("marca"))] + K.n(p.get("modelo")).split()[:2]).strip()


def _vistos(estado: dict, resuelto: list, mensaje: str, tienda_id: str) -> tuple:
    """(las familias que nombra el mensaje, las que el cliente leyo: lo mostrado y lo que ya tiene el pedido)."""
    from .marcador import _productos
    ids = [m["id"] for m in estado.get("mostrados") or []] + [a["id"] for x in resuelto for a in x.get("articulos") or []]
    leidos = {_familia(K.por_id(i, tienda_id)) for i in ids}
    dichos = set()
    for tramo, _ in _productos([w for w in re.findall(r"[a-z0-9]+", K.n(mensaje)) if w not in K._RELLENO], tienda_id):
        idt = K.identificar(tramo, "", tienda_id)
        dichos |= {_familia(p) for p in ([idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or [])}
    return dichos - {""}, leidos - {""}


def _aceptado(vistos: tuple, orden: str) -> set:
    """Los modelos que la ficha puede poner en el pedido: los que nombro el cliente, y los que leyo si no pidio un
    orden. Con un orden —"lo mejor"— el producto lo elige el orden, no el modelo de lenguaje."""
    dichos, leidos = vistos
    return dichos | (leidos if orden == NADA else set())


def _que(it: dict, nums: dict, renglones: dict, tienda_id: str, vistos: set = None) -> dict:
    """Lo que es un articulo de la ficha: {"L"} su renglon, {"ref"} un numero de lo mostrado, {"modelo"} un producto
    que la tienda identifica, {"rubro"} una clase, o {"libre"} las palabras, que el ejecutor pregunta."""
    texto = str(it.get("producto") or "")
    refs = _refs(f"{it.get('renglon') or ''} {texto}", nums)
    L = next((r for r in refs if r[0] == "L" and r in renglones), "")
    M = next((r for r in refs if r[0] == "M"), "")
    if L:
        return {"L": L}
    if M:
        p = K.por_id(nums[M], tienda_id) if isinstance(nums.get(M), str) else {}
        if vistos is None or not p or _familia(p) in vistos:
            return {"ref": M}
        return {"rubro": p.get("categoria") or ""}  # con un orden, lo mostrado no lo elige el modelo
    if _es_modelo(texto, _dicho(it.get("color")), tienda_id, vistos) or _nombra_varios(texto, tienda_id, vistos):
        return {"modelo": texto}
    rub = _rubro(texto, tienda_id, str(it.get("rubro") or ""))
    return {"rubro": rub} if rub else {"libre": texto}
