"""EL VERIFICADOR DE AFIRMACIONES — cada cosa que dice la respuesta, contra la fuente de la tienda (29-oct-2026, FICHA 83).

Sin modelo. La fuente es lo que devolvieron las herramientas, la charla y el mensaje del cliente. Lo que controla:
  datos        cada monto, medida con unidad, link, CBU o alias tiene que estar en la fuente.
  producto     cada producto que nombra tiene que estar en la fuente.
  atributo     en una oracion que nombra un solo producto, cada palabra que el catalogo ata a un campo —"inalambrico",
               "rgb", "negro"— tiene que cumplirla ese producto; con "no" o "sin" delante, al reves.
  superlativo  "el mas barato": el primero de su rubro en ese orden, en la tienda o entre los de la fuente.
  stock        "hay stock", "no hay", "sin stock": contra el stock del producto.
  regla        31-oct, orden de Martin: una oracion sin producto que habla de un tema de la FAQ, por las frases del
               propio tema, y niega o restringe —"no hay descuento por cantidad", "solo Mercado Pago"— cuando la regla
               de ningun tema nombrado lo hace.
Medido en `banco_pruebas/alucinaciones.py`, 31-oct: caza 99,3% de las inyectadas; marca 2 de 164 respuestas grabadas, las dos
reglas negadas de verdad: K13, sin descuento por cantidad, y K21, sin el origen.
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
    """Los productos que nombra un texto, uno por modelo: el que la identidad certifica. Un monto no es parte de un
    nombre: el "3" de "$3.100.500" con "1TB SSD" era la IdeaPad 3, 1-nov."""
    ws = [w for w in re.findall(r"[a-z0-9]+", K.n(re.sub(r"\$\s?\d[\d.,]*", " ", texto))) if w not in K._RELLENO]
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


# LA TIENDA NIEGA O RESTRINGE UNA REGLA: "no tenemos", "no contamos con", "no hay", o "solo" pegado al tema. "Sin
# problemas", "solo me falta tu localidad" o "no vendemos teclados Samsung", que es de productos, no son una regla.
_NIEGA_REGLA = r"\b(?:no|ni)\s+(?:\w+\s+)?(?:hay|tenemos|tengo|contamos|cuento|hacemos|hago|aceptamos|acepto|trabajamos|" \
    r"trabajo|manejamos|manejo|ofrecemos|ofrezco|damos|doy|emitimos|cobramos|podemos|puedo)\b"
_SOLO = r"\b(?:solo|solamente|unicamente)\b(?!\s+(?:me|te|nos|le|les|se)\b)"; _RESTRINGE = rf"{_NIEGA_REGLA}|{_SOLO}|\bno\b"


def _reglas(o: str, tienda_id: str) -> list:
    """Una oracion que niega o restringe un tema de la FAQ, con el tema despues de la negacion en la misma parte de la
    oracion, cuando la regla de ese tema no niega ni restringe nada."""
    faq, out, temas = K.fc.get_all_faq(tienda_id=tienda_id) or {}, [], K.agente.indice(tienda_id)["temas"]
    for parte in re.split(r"[,;:]|\bpero\b", o):
        for m in re.finditer(rf"{_NIEGA_REGLA}|{_SOLO}", parte):
            # Lo que niega "no tenemos" va en la parte; lo que restringe "solo", en las cuatro palabras siguientes.
            resto = parte[m.end():] if not re.fullmatch(_SOLO, m.group(0)) else " ".join(parte[m.end():].split()[:4])
            nombrados = {t: K.n((faq.get(t) or {}).get("respuesta")) for t, d in temas.items()
                         if any(re.search(rf"\b{re.escape(f)}\b", resto) for f in d.get("frases") or [])}
            # NEGAR OTRA COSA NO CONTRADICE LA REGLA: "no tenemos promo de 50% off" con la promo del 10%.
            # LA REGLA VA EN EL HALLAZGO, 1-nov: con solo el tema, en K13 el modelo volvia a negar el mayorista.
            out += [("regla", f"{parte.strip()[:80]}; la regla dice: " + " ".join(str((faq.get(t) or {}).get(
                "respuesta") or "") for t in sorted(nombrados)))] if nombrados and not any(
                x not in re.findall(r"\d+", r) for x in re.findall(r"\d+", resto) for r in nombrados.values()) and \
                not any(re.search(_RESTRINGE, r) for r in nombrados.values()) else []
    return out


# LO QUE EL BOT DICE QUE HIZO, 3-nov, examen real: "te armé el presupuesto" sin presupuesto, c3391d; "acá te paso los
# datos para el pago" sin CBU ni link, b8bb00. Solo lo que dice hecho ahora: "así te armo el presupuesto" es futuro.
_HECHO_PRESUPUESTO = r"(?<!\bque )(?<!\bque te )(?<!\bque lo )\b(?:te\s+)?(?:arme|hice|prepare|actualice)\b[^.]{0,30}\bpresupuesto|\b(?:aca|ahi)\s+te\s+(?:paso|dejo)\s+" \
    r"(?:el\s+)?presupuesto"
_HECHO_DATOS = r"\b(?:aca|ahi)\s+te\s+(?:paso|dejo|envio|mando)\b[^.]*\bdatos\b|\bestos\s+son\s+los\s+datos\b|" \
    r"\baca\s+(?:tenes|van)\s+los\s+datos\b"


def _hechos(o: str, respuesta: str) -> list:
    """Lo que la oracion dice hecho y la respuesta entera no trae: el presupuesto, o los datos para pagar."""
    out = []
    if re.search(_HECHO_PRESUPUESTO, o) and "Presupuesto:" not in respuesta:
        out.append(("hecho", "dice que armo el presupuesto y no esta"))
    if re.search(_HECHO_DATOS, o) and not _pagos(respuesta):
        out.append(("hecho", "dice que pasa los datos de pago y no estan: los pega la herramienta cobrar"))
    return out


# LO QUE LA TIENDA DICE QUE NO TIENE, O QUE SOLO TIENE, 3-nov: "solo tengo teclados con cable" con el K380 inalambrico
# en stock, badf4f. Un rubro con sus atributos, contra el catalogo con stock. La marca no: "no vendemos teclados Samsung"
# es cierto o no por la identidad, no por un atributo.
_NO_HAY = r"\b(?:no|ni)\s+(?:\w+\s+)?(?:hay|tenemos|tengo|vendemos|vendo|contamos con|trabajamos)\b"
_SOLO_HAY = r"\b(?:solo|solamente|unicamente)\s+(?:hay|tenemos|tengo|vendemos|vendo|trabajamos)\b"


def _existencia(o: str, tienda_id: str) -> list:
    out, todos = [], K.productos(tienda_id)
    for parte in re.split(r"[,;:]|\bpero\b", o):
        for m in re.finditer(rf"{_NO_HAY}|{_SOLO_HAY}", parte):
            ws = re.findall(r"[a-z0-9]+", parte[m.end():])
            rubros = MK._rubros(ws, tienda_id)
            if len(rubros) != 1:
                continue
            rubro = [x for x in todos if x.get("categoria") == rubros[0][1] and K.con_stock(x)]
            filtros = [f for w in ws if w not in K._RELLENO and len(w) > 2 and "campo" in (f := K.atar(w, rubro,
                       tienda_id)) and f["campo"] in _ATRIBUTOS and not f.get("niega")]
            if re.fullmatch(_SOLO_HAY, m.group(0)):
                otros = [x for x in rubro if filtros and not all(K.cumple(x, f) for f in filtros)]
                out += [("existencia", f"dice que solo hay {rubros[0][0]} {' '.join(f['valor'] for f in filtros)}, y "
                                       f"esta {otros[0]['nombre']}")] if otros else []
            elif filtros and (hay := [x for x in rubro if all(K.cumple(x, f) for f in filtros)]):
                out.append(("existencia", f"dice que no hay {rubros[0][0]} {' '.join(f['valor'] for f in filtros)}, y "
                                          f"esta {hay[0]['nombre']}"))
    return out


def _compat_general(oracion: str, o: str, tienda_id: str) -> list:
    """"La mayoria de los mouses USB andan en la Play", bf4a05: una clase entera que anda con un equipo, sin un producto
    que lo respalde. Sin ficha que lo diga, no se afirma; negarlo o dudar no afirma nada."""
    from app.core.compatibilidad import etiqueta_plataforma, plataformas_del_mensaje
    out = []
    for parte in re.split(r"[,;:]|\bpero\b", o):
        # LA CLASE ENTERA: "la mayoria de", "todos los", "cualquier". "Para saber que memoria le sirve a tu notebook" no
        # generaliza nada.
        if not re.search(rf"\b{_VERBO}\b", parte) or re.search(r"\b(no|ni|quizas|capaz|puede|podria)\b", parte) or \
                not re.search(r"\b(la mayoria|casi todos|casi todas|todos los|todas las|cualquier|en general)\b", parte) \
                or not MK._rubros(re.findall(r"[a-z0-9]+", parte), tienda_id):
            continue
        out += [("compatibilidad", f"afirma que anda con {etiqueta_plataforma(x, tienda_id)} sin un producto que lo "
                                   "diga") for x in plataformas_del_mensaje(parte, tienda_id)]
    return out


def _medios(o: str, tienda_id: str) -> list:
    """"Ademas de transferencia, aceptamos Mercado Pago", 96b39f: los medios que la tienda dice que acepta tienen que ser
    todos los de su FAQ, tema formas_pago. Uno que no toma, tampoco."""
    from .agente import medios_de_la_tienda, menciones, no_lo_toma
    # La lista va despues del verbo, y el verbo no lleva un pronombre que hable de otra cosa: "la tarjeta de debito, la
    # aceptamos por Mercado Pago" no enumera los medios.
    v = re.search(r"(?<!\bla )(?<!\blo )(?<!\blas )(?<!\blos )\b(?:aceptamos|acepto|tomamos|trabajamos con|podes pagar "
                  r"con|los medios son)\b", o)
    if not v:
        return []
    dichos = [m for m, neg in menciones(o) if not neg]
    bases, _ = medios_de_la_tienda(tienda_id)
    if not dichos or not bases:
        return []
    out = [("regla", f"la tienda no toma {m}") for m in dichos if no_lo_toma(m, tienda_id)]
    faltan = bases - {m.split()[0] if m.startswith("tarjeta") else m for m in dichos}
    return out + ([("regla", f"los medios de pago quedan incompletos: falta {', '.join(sorted(faltan))}")] if faltan
                  and len(dichos) > 1 or faltan and re.search(r"\bademas\b", o) else [])


# LO QUE DICE DE TODA LA TIENDA, 3-nov, e35851: "todos nuestros productos tienen garantía oficial de 12 meses", con
# garantias de 12 a 120 meses. Una medida dicha de todos tiene que ser la de cada producto, en el campo de su unidad.
_TODOS = r"\b(?:todos|todas)\s+(?:nuestros|nuestras|los|las)\s+(?:productos|equipos|articulos)\b|\btodo lo que vendemos\b"
_CAMPO_UNIDAD = {"meses": "garantia_meses", "g": "peso_gramos", "kg": "peso_gramos"}


def _de_todos(o: str, tienda_id: str) -> list:
    if not re.search(_TODOS, o):
        return []
    out = []
    for m in _medidas(o):
        n, unidad = m.split()
        campo = _CAMPO_UNIDAD.get(unidad)
        valores = {x.get(campo) for x in K.productos(tienda_id) if campo and x.get(campo) not in (None, "")}
        n = int(n) * (1000 if unidad == "kg" else 1)
        if valores and valores != {n}:
            out.append(("regla", f"dice que todos tienen {m}, y van de {min(valores)} a {max(valores)}"))
    return out


def sin_marcadas(respuesta: str, fuente: str, tienda_id: str, pegados: list = ()) -> str:
    """La respuesta sin las oraciones que el verificador marca: lo que siguio marcado despues de corregir no le llega al
    cliente. Lo que el codigo pego tal cual queda entero."""
    lineas = [x if x.strip() and any(x in y for y in pegados) else " ".join(
        o for o in re.split(r"(?<=[.!?])\s+", x) if not verificar(o, fuente, tienda_id, pegados)) for x in respuesta.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lineas)).strip()


def verificar(respuesta: str, fuente: str, tienda_id: str, pegados: list = ()) -> list:
    """Los hallazgos de una respuesta contra su fuente: [(clase, detalle)]. Lo que el codigo pego tal cual desde una
    herramienta —el presupuesto, el cobro— no lo escribio el modelo: se saca antes de mirar."""
    completa = respuesta
    for x in sorted(pegados, key=len, reverse=True):
        if len(x) > 40:
            respuesta = respuesta.replace(x, " ")
    hallazgos = [("dato", str(x)) for x in inventados(respuesta, fuente)]
    f = K.n(fuente)
    todos = K.productos(tienda_id)
    antes = []
    for oracion in _ORACION.split(respuesta):
        o = K.n(oracion)
        nombrados = _productos(oracion, tienda_id)
        for _, p in nombrados:
            if not _en_fuente(p, f):
                hallazgos.append(("producto", p["nombre"]))
        # EL SUJETO DE LA ORACION DE ANTES, 3-nov: "El mas economico es el Zeus X. Es compatible con PS5", b8bb00. Una
        # oracion sin producto que sigue a una que nombra uno solo habla de ese.
        sujeto, antes = (nombrados or (antes if re.match(r"\W*(es|tiene|viene|anda|funciona|sirve|trae)\b", o) else [])), \
            nombrados
        # UNA PREGUNTA O UN "SI BUSCAS..." NO AFIRMAN: "¿queres uno inalambrico o el G203?" no dice que el G203 lo sea.
        # El "si" condiciona solo hasta la coma: "si buscas uno inalambrico, no tengo" afirma lo que sigue.
        if "?" in oracion:
            continue
        hallazgos += _hechos(o, completa)
        hallazgos += _existencia(re.sub(r"^\W*si\b[^,]*,", "", o), tienda_id)
        if re.match(r"\W*si\b", o):
            continue
        hallazgos += _medios(o, tienda_id) + _de_todos(o, tienda_id)
        if not sujeto:
            hallazgos += _reglas(o, tienda_id) + _compat_general(oracion, o, tienda_id)
        nombrados = sujeto
        if len({q["id"] for _, q in nombrados}) != 1:
            continue
        p = nombrados[0][1]
        rubro = [x for x in todos if x.get("categoria") == p.get("categoria")]
        ws = re.findall(r"[a-z0-9]+", o)
        propias = set(K.n(f"{p.get('categoria')} {p.get('marca')} {p.get('modelo')} {p.get('nombre')}").split())
        for i, w in enumerate(ws):
            if w in K._RELLENO or w in propias or w in _NIEGA or len(w) < 3 or w.isdigit():
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
