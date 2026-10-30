"""EL VERIFICADOR DE AFIRMACIONES — cada cosa que dice la respuesta, contra la fuente de la tienda (29-oct-2026, FICHA 83).

Sin modelo. La fuente es lo que devolvieron las herramientas, la charla y el mensaje del cliente. Lo que controla:
  datos        cada monto, medida con unidad, link, CBU o alias tiene que estar en la fuente.
  producto     cada producto que nombra tiene que estar en la fuente.
  atributo     en una oracion que nombra un solo producto, cada palabra que el catalogo ata a un campo —"inalambrico",
               "rgb", "negro"— tiene que cumplirla ese producto; con "no" o "sin" delante, al reves.
  superlativo  "el mas barato": el primero de su rubro en ese orden, en la tienda o entre los de la fuente.
  stock        "hay stock", "no hay", "sin stock": contra el stock del producto.
Medido en `banco_pruebas/alucinaciones.py`: caza 99% de las alucinaciones inyectadas con 0,6% de falsas alarmas.
"""
import re

from . import catalogo as K
from . import marcador as MK

_NIEGA = ("no", "sin", "ni")
_ORACION = re.compile(r"(?<=[.!?\n])\s+|\n+")
_UNIDAD = r"(dpi|gb|tb|hz|mhz|w|mah|g|kg|mm|cm|pulgadas|meses|horas|dias)"


def _montos(texto: str) -> set:
    return {int(re.sub(r"\D", "", m)) for m in re.findall(r"\$\s?\d[\d.]*", texto) if re.sub(r"\D", "", m)}


def _medidas(texto: str) -> set:
    return {f"{re.sub(r'[^0-9]', '', m.group(1))} {m.group(2)}" for m in re.finditer(rf"\b(\d[\d.,]*)\s?{_UNIDAD}\b",
                                                                                         K.n(texto))}


def _pagos(texto: str) -> set:
    """Los datos de pago de un texto: links, numeros largos como un CBU y alias."""
    return {x.rstrip(".,;:!?") for x in re.findall(r"https?://\S+?(?=[\s)\]]|$)|\b\d{10,}\b", texto)} | \
        {m.lower() for m in re.findall(r"(?i)\balias:?\s*\**\s*([a-z0-9][a-z0-9._-]{3,})", texto)}


def inventados(respuesta: str, fuente: str) -> list:
    """Los montos, medidas y datos de pago de la respuesta que no salieron de la fuente."""
    validos = _montos(fuente) | {int(re.sub(r"\D", "", m)) for m in re.findall(r"= ([\d.]+)", fuente)}
    # Una medida vale si su numero esta en la fuente, aunque sin la unidad: "DDR4 3200" en el nombre es 3200 MHz.
    numeros = set(re.findall(r"\d+", re.sub(r"(?<=\d)[.,](?=\d)", "", K.n(fuente))))
    pagos = _pagos(fuente)
    return sorted(m for m in _montos(respuesta) if m not in validos) + \
        sorted(m for m in _medidas(respuesta) if m.split()[0] not in numeros) + \
        sorted(m for m in _pagos(respuesta) if m not in pagos)


def _productos(texto: str, tienda_id: str) -> list:
    """Los productos que nombra un texto, uno por modelo: el que la identidad certifica."""
    ws = [w for w in re.findall(r"[a-z0-9]+", K.n(texto)) if w not in K._RELLENO]
    out = []
    for tramo, _ in MK._productos(ws, tienda_id):
        # Una medida sola no nombra un producto: "25w" de la potencia de un parlante no es el cargador de 25W.
        if all(re.fullmatch(r"\d+[a-z]{0,3}", w) for w in tramo.split()):
            continue
        idt = K.identificar(tramo, "", tienda_id)
        if idt["veredicto"] == "exists":
            out.append((tramo, idt["producto"]))
    return out


def _en_fuente(p: dict, fuente: str) -> bool:
    return any(K.n(x) in fuente for x in (p.get("nombre"), f"{p.get('marca')} {p.get('modelo')}", p.get("modelo")) if x)


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


_VERBO = r"(sirve|sirven|anda|andan|funciona|funcionan|va|van|es compatible|son compatibles|conecta|conectan|entra|entran)"


def _compatibilidad(p: dict, oracion: str, o: str, tienda_id: str) -> list:
    """"El M170 anda con la Mac": cada equipo que la oracion nombra, contra la ficha de compatibilidad del producto. Lo
    que la ficha no dice que anda no se afirma; negarlo cuando anda, tampoco. "No lo puedo confirmar" no afirma nada."""
    from app.core.compatibilidad import etiqueta_plataforma, evaluar, plataformas_del_mensaje
    from app.core.guia_compra import _RE_COMPATIBILIDAD
    if not _RE_COMPATIBILIDAD.search(o):
        return []
    niega = bool(re.search(rf"\b(no|ni)\s+(\w+\s+){{0,2}}{_VERBO}\b", o))
    duda = not niega and re.search(rf"\b(no|ni)\b.*\b{_VERBO}\b", o)
    return [("compatibilidad", f"{p['nombre']}: {'no ' * niega}{etiqueta_plataforma(x, tienda_id)}")
            for x in plataformas_del_mensaje(oracion, tienda_id) if not duda
            and (evaluar(p, x, tienda_id)[0] == "compatible") == niega]


def sin_marcadas(respuesta: str, fuente: str, tienda_id: str, pegados: list = ()) -> str:
    """La respuesta sin las oraciones que el verificador marca: lo que siguio marcado despues de corregir no le llega al
    cliente. Lo que el codigo pego tal cual queda entero."""
    lineas = [x if x.strip() and any(x in y for y in pegados) else " ".join(
        o for o in re.split(r"(?<=[.!?])\s+", x) if not verificar(o, fuente, tienda_id, pegados)) for x in respuesta.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


def verificar(respuesta: str, fuente: str, tienda_id: str, pegados: list = ()) -> list:
    """Los hallazgos de una respuesta contra su fuente: [(clase, detalle)]. Lo que el codigo pego tal cual desde una
    herramienta —el presupuesto, el cobro— no lo escribio el modelo: se saca antes de mirar."""
    for x in sorted(pegados, key=len, reverse=True):
        if len(x) > 40:
            respuesta = respuesta.replace(x, " ")
    hallazgos = [("dato", str(x)) for x in inventados(respuesta, fuente)]
    f = K.n(fuente)
    todos = K.productos(tienda_id)
    for oracion in _ORACION.split(respuesta):
        o = K.n(oracion)
        nombrados = _productos(oracion, tienda_id)
        for _, p in nombrados:
            if not _en_fuente(p, f):
                hallazgos.append(("producto", p["nombre"]))
        # UNA PREGUNTA O UN "SI BUSCAS..." NO AFIRMAN: "¿queres uno inalambrico o el G203?" no dice que el G203 lo sea.
        if len({q["id"] for _, q in nombrados}) != 1 or "?" in oracion or re.match(r"\W*si\b", o):
            continue
        p = nombrados[0][1]
        rubro = [x for x in todos if x.get("categoria") == p.get("categoria")]
        ws = re.findall(r"[a-z0-9]+", o)
        propias = set(K.n(f"{p.get('categoria')} {p.get('marca')} {p.get('modelo')} {p.get('nombre')}").split())
        for i, w in enumerate(ws):
            if w in K._RELLENO or w in propias or len(w) < 3 or w.isdigit():
                continue
            filtro = K.atar(w, rubro, tienda_id)
            if "campo" not in filtro or not (filtro["campo"] in _ATRIBUTOS or filtro.get("si_no")):
                continue
            niega = any(x in _NIEGA for x in ws[max(0, i - 3):i])
            # Un color vale si el modelo lo tiene en alguna variante, no solo la que se nombro.
            variantes = K._colores_de(p, todos) or [p] if filtro["campo"] == "color" else [p]
            if any(K.cumple(v, filtro) for v in variantes) == niega:
                hallazgos.append(("atributo", f"{p['nombre']}: {'no ' if niega else ''}{w}"))
        for orden, (clave, sentido) in K.ORDEN.items():
            if re.search(rf"\b{orden}\b|\b{orden.replace('mas ', '')}\s+de\s+(todos|la tienda)\b", o):
                vistos = [x for x in rubro if _en_fuente(x, f)]
                if not (_primero(p, clave, sentido, rubro) or _primero(p, clave, sentido, vistos)):
                    hallazgos.append(("superlativo", f"{p['nombre']}: {orden}"))
        hallazgos += _compatibilidad(p, oracion, o, tienda_id)
        if re.search(r"\b(no (hay|queda|quedan)\b|no (tenemos|tengo|tiene) (stock|mas)\b|sin stock|agotad)", o) and \
                K.con_stock(p) and not re.search(r"\b(en|color)\s+\w+", o):
            hallazgos.append(("stock", f"{p['nombre']}: dice que no hay"))
        elif re.search(r"\b(hay stock|tenemos stock|disponible)\b", o) and not K.con_stock(p):
            hallazgos.append(("stock", f"{p['nombre']}: dice que hay"))
    return list(dict.fromkeys(hallazgos))
