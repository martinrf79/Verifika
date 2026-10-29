"""EL VERIFICADOR DE AFIRMACIONES — cada cosa que dice la respuesta, contra la fuente de la tienda (29-oct-2026, FICHA 83).

Pedido de Martin del 29-oct: una arquitectura libre se saco hace meses, con DeepSeek, porque las alucinaciones no se
distinguian de las respuestas buenas. Antes de llevar el buscador al bot, un verificador por afirmacion, sin modelo, y
medido con alucinaciones inyectadas en `alucinaciones.py`.

Cada respuesta se parte en oraciones. Lo que se controla:
  datos        cada monto, medida con unidad, link, CBU o alias tiene que estar en la fuente: lo que devolvieron las
               herramientas, la charla o el mensaje del cliente. Es el candado del buscador.
  producto     cada producto que nombra tiene que estar en la fuente.
  atributo     en una oracion que nombra un solo producto, cada palabra que el catalogo ata a un campo —"inalambrico",
               "rgb", "negro", "con cable"— tiene que cumplirla ese producto, con `catalogo.atar` y `catalogo.cumple`;
               con "no" o "sin" delante, al reves.
  superlativo  "el mas barato", "el mas liviano": el producto tiene que ser el primero de su rubro en ese orden, en todo
               el catalogo con stock o entre los de su rubro que estan en la fuente.
  stock        "hay stock", "no hay", "sin stock": contra el stock del producto.
Devuelve una lista de hallazgos; vacia es que no encontro nada que la fuente contradiga.
"""
import re

from app.core.flujo import catalogo as K
from app.core.flujo import marcador as MK

TID = "verifika_prod"
_NIEGA = ("no", "sin", "ni")
_ORACION = re.compile(r"(?<=[.!?\n])\s+|\n+")


def _productos(texto: str) -> list:
    """Los productos que nombra un texto, uno por modelo: el que la identidad certifica."""
    ws = [w for w in re.findall(r"[a-z0-9]+", K.n(texto)) if w not in K._RELLENO]
    out = []
    for tramo, _ in MK._productos(ws, TID):
        # Una medida sola no nombra un producto: "25w" de la potencia de un parlante no es el cargador de 25W.
        if all(re.fullmatch(r"\d+[a-z]{0,3}", w) for w in tramo.split()):
            continue
        idt = K.identificar(tramo, "", TID)
        if idt["veredicto"] == "exists":
            out.append((tramo, idt["producto"]))
    return out


def _en_fuente(p: dict, fuente: str) -> bool:
    return any(K.n(x) in fuente for x in (p.get("nombre"), f"{p.get('marca')} {p.get('modelo')}", p.get("modelo")) if x)


def _propias(p: dict) -> set:
    return set(K.n(f"{p.get('categoria')} {p.get('marca')} {p.get('modelo')} {p.get('nombre')}").split())


def _primero(p: dict, clave: str, sentido: int, entre: list) -> bool:
    """El producto es el primero en ese orden, por modelo: otro color del mismo modelo cuenta como el mismo."""
    con = [x for x in entre if K.con_stock(x) and x.get(clave) not in (None, "")]
    if not con:
        return True
    mejor = min(con, key=lambda x: sentido * float(x.get(clave) or 0))
    mismo = (mejor.get("marca"), mejor.get("modelo")) == (p.get("marca"), p.get("modelo"))
    return mismo or sentido * float(p.get(clave) or 0) <= sentido * float(mejor.get(clave) or 0)


# Los campos que son un atributo del producto, de valor corto. Los de texto libre —tags, descripcion, o bluetooth, que
# trae frases como "si, tambien por cable"— atan cualquier palabra; bluetooth vale solo por su si o no. La marca no:
# una marca en la oracion suele ser de otro producto, y la del nombrado ya la certifica la identidad.
_ATRIBUTOS = set(K.PRIORIDAD) - {"tags", "modelo", "nombre", "descripcion", "marca", "bluetooth"}


def verificar(respuesta: str, fuente: str, pegados: list = ()) -> list:
    """Los hallazgos de una respuesta contra su fuente: [(clase, detalle)]. Lo que el codigo pego tal cual desde una
    herramienta —el presupuesto, el cobro— no lo escribio el modelo: se saca antes de mirar."""
    import buscador_agente as B
    for x in sorted(pegados, key=len, reverse=True):
        if len(x) > 40:
            respuesta = respuesta.replace(x, " ")
    hallazgos = [("dato", str(x)) for x in B.inventados(respuesta, [fuente])]
    f = K.n(fuente)
    todos = K.productos(TID)
    for oracion in _ORACION.split(respuesta):
        o = K.n(oracion)
        nombrados = _productos(oracion)
        for tramo, p in nombrados:
            if not _en_fuente(p, f):
                hallazgos.append(("producto", p["nombre"]))
        # UNA PREGUNTA O UN "SI BUSCAS..." NO AFIRMAN: "¿queres uno inalambrico o el G203?" no dice que el G203 lo sea.
        # Ahi se controlan los datos y los productos, no los atributos, los superlativos ni el stock.
        if len({q["id"] for _, q in nombrados}) != 1 or "?" in oracion or re.match(r"\W*si\b", o):
            continue
        p = nombrados[0][1]
        rubro = [x for x in todos if x.get("categoria") == p.get("categoria")]
        ws = re.findall(r"[a-z0-9]+", o)
        propias = _propias(p)
        # LOS ATRIBUTOS: cada palabra que el catalogo ata a un campo del rubro, contra el producto.
        for i, w in enumerate(ws):
            if w in K._RELLENO or w in propias or len(w) < 3 or w.isdigit():
                continue
            filtro = K.atar(w, rubro, TID)
            if "campo" not in filtro or not (filtro["campo"] in _ATRIBUTOS or filtro.get("si_no")):
                continue
            niega = any(x in _NIEGA for x in ws[max(0, i - 3):i])
            # Un color vale si el modelo lo tiene en alguna variante, no solo la que se nombro.
            variantes = K._colores_de(p, todos) or [p] if filtro["campo"] == "color" else [p]
            cumple = any(K.cumple(v, filtro) for v in variantes)
            if cumple == niega:
                hallazgos.append(("atributo", f"{p['nombre']}: {'no ' if niega else ''}{w}"))
        # LOS SUPERLATIVOS: el primero de su rubro en ese orden, en la tienda o entre los que estan en la fuente.
        for orden, (clave, sentido) in K.ORDEN.items():
            if re.search(rf"\b{orden}\b|\b{orden.replace('mas ', '')}\s+de\s+(todos|la tienda)\b", o):
                vistos = [x for x in rubro if _en_fuente(x, f)]
                if not (_primero(p, clave, sentido, rubro) or _primero(p, clave, sentido, vistos)):
                    hallazgos.append(("superlativo", f"{p['nombre']}: {orden}"))
        # EL STOCK.
        if re.search(r"\b(no (hay|queda|quedan)\b|no (tenemos|tengo|tiene) (stock|mas)\b|sin stock|agotad)", o) and \
                K.con_stock(p) and \
                not re.search(r"\b(en|color)\s+\w+", o):
            hallazgos.append(("stock", f"{p['nombre']}: dice que no hay"))
        elif re.search(r"\b(hay stock|tenemos stock|disponible)\b", o) and not K.con_stock(p):
            hallazgos.append(("stock", f"{p['nombre']}: dice que hay"))
    return list(dict.fromkeys(hallazgos))
