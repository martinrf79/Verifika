"""
PEDIDO MULTI — el Provider lee pedidos combinados NUEVOS por codigo.

Caso real (Esteban, 12-jun): "necesito 2 mauses y dos tablets dame los precios
mas bajos" — el Provider no tenia foco ni carrito con eso, el contrato viajaba
sin total y el Solver caia a su respaldo (llamar la calculadora el mismo y
redactar el resultado), el costado debil del sistema.

Esta pieza convierte el mensaje en un pedido estructurado por CODIGO:
  "2 mauses y dos tablets"  ->  [{producto, cantidad}, {producto, cantidad}]

Reglas de eleccion por termino (deterministas, en orden):
  - candidatos = busqueda del catalogo con el termino singularizado, con stock.
  - si el mensaje pide barato/economico -> el de MENOR precio.
  - si hay un solo candidato -> ese.
  - si hay varios y no pidio barato -> AMBIGUO: no se adivina, se devuelven
    los candidatos para que el Solver pregunte (color, modelo).

Flag PEDIDO_MULTI (default off). Testeable offline con search_products
monkeypatcheado, igual que el resto del Provider.
"""
import re
from typing import Optional

from app.core.resolver_pedido import refinar_por_atributo
from app.logger import get_logger

log = get_logger(__name__)

_NUM_PALABRA = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}

# cantidad (digito o palabra) seguida de 1-3 palabras de producto. Las palabras
# admiten DIGITOS para no partir los codigos de modelo ('K380', 'G203'): con la
# clase solo-letras, 'k380' cortaba en la letra y el termino se perdia.
_SEG_RE = re.compile(
    r"\b(\d{1,2}|un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+"
    r"([a-záéíóúñü][a-z0-9áéíóúñü]*(?:\s+[a-z0-9áéíóúñü]+){0,2})",
    re.IGNORECASE)

# Palabras que no son producto: cortan el termino donde aparecen.
_CORTE = frozenset((
    "precio", "precios", "presupuesto", "total", "envio", "envios", "con",
    "para", "los", "las", "mas", "menos", "barato", "baratos", "barata",
    "baratas", "economico", "economicos", "economica", "economicas", "bajo",
    "bajos", "que", "tengas", "tenga", "dame", "pasame", "decime", "porfa",
    "unidades", "unidad", "cada", "y",
    # Unidades de TIEMPO y MEDIDA: nunca son producto en catalogo de
    # electronica. Sin esto '3 meses' (mantener precio 3 meses) o '5 metros'
    # (cable de 5 metros) se leian como '3/5 productos' y cotizaban basura
    # ('mese'->'mesh' ofrecia gabinetes Mesh). Visto vivo 16-jun, charla 1.
    "mes", "meses", "dia", "dias", "semana", "semanas", "ano", "anos",
    "año", "años", "hora", "horas", "minuto", "minutos", "metro", "metros",
    "cm", "mm", "litro", "litros", "kg", "gramos", "gr",
    # Palabras de CANTIDAD/GENERICAS que no nombran un producto: '5 items',
    # '1 compra hace 5 min', 'una cosa', '2 cosas'. Sin esto se leian como
    # 'N <producto>' y el matcheo relajado cotizaba cualquier cosa. Vivo 16-jun.
    "item", "items", "compra", "compras", "cosa", "cosas", "producto",
    "productos", "pieza", "piezas", "articulo", "articulos", "vez", "veces",
))


def _singular(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def _termino(crudo: str) -> str:
    """Recorta el pedazo de texto a las palabras que describen el producto."""
    palabras = []
    for w in crudo.lower().split():
        if w in _CORTE:
            break
        if len(w) > 2:
            palabras.append(_singular(w))
    return " ".join(palabras[:3])


def _candidatos(termino: str, tienda_id: str) -> list[dict]:
    from app.core.tools import search_products
    from app.core.tools_context import set_current_tienda
    set_current_tienda(tienda_id)
    res = search_products(query=termino)
    prods = [p for p in (res.get("productos") or []) if isinstance(p, dict)
             and p.get("id") and isinstance(p.get("precio_ars"),
                                            (int, float))]
    return [p for p in prods if p.get("stock", 0) > 0]


def _corregir_termino(term: str, tienda_id: str) -> Optional[str]:
    """Corrige typos del termino contra el vocabulario REAL del catalogo
    (palabras de nombres y categorias): 'mause' -> 'mouse'. Correccion
    generica por similitud, no lista de casos. Visto 12-jun noche: '2 mauses
    y dos teclados' perdia el renglon de los mouse EN SILENCIO porque el typo
    no matcheaba nada — vender medio pedido es peor que no vender. Devuelve
    el termino corregido o None si no hay correccion con confianza."""
    import difflib
    try:
        from app.storage.firestore_client import get_all_products
        prods = get_all_products(tienda_id=tienda_id)
    except Exception:
        return None
    vocab = set()
    for p in prods or []:
        for w in re.findall(r"[a-záéíóúñü]+", str(p.get("nombre", "")).lower()):
            if len(w) > 3:
                vocab.add(w)
        cat = str(p.get("categoria", "")).lower()
        if len(cat) > 3:
            vocab.add(_singular(cat))
    corregidas = []
    cambio = False
    for w in term.split():
        if w in vocab or len(w) < 4:
            corregidas.append(w)
            continue
        match = difflib.get_close_matches(w, vocab, n=1, cutoff=0.75)
        if match:
            corregidas.append(match[0])
            cambio = True
        else:
            corregidas.append(w)
    return " ".join(corregidas) if cambio else None


def _candidatos_con_typo(term: str, tienda_id: str,
                         trace_id: Optional[str] = None,
                         corregido_out: Optional[list] = None) -> list[dict]:
    """Busqueda del termino con red de typos: si el crudo no matchea nada,
    se corrige contra el vocabulario del catalogo y se reintenta. Si se pasa
    corregido_out (lista), se le appendea el termino corregido cuando hubo
    correccion, para que el llamador pueda medir relevancia contra la lectura
    corregida y no contra el typo crudo."""
    cands = _candidatos(term, tienda_id)
    if cands:
        return cands
    corr = _corregir_termino(term, tienda_id)
    if corr and corr != term:
        cands = _candidatos(corr, tienda_id)
        if cands:
            log.info("pedido_multi_typo_corregido", trace_id=trace_id,
                     de=term, a=corr)
            if corregido_out is not None:
                corregido_out.append(corr)
    return cands


# Tokens que NO distinguen un producto de otro: colores y categorias. Una pista
# del interprete NO debe matchear el termino por compartir solo uno de estos
# (visto: 'mouse G203 negro' pegaba con la pista 'K380 Negro' por el token
# 'negro', y el agregado resolvia al teclado en vez del mouse).
# Colores y atributos puros: NUNCA enlazan una pista con un termino (el peligro
# real, 'negro' cruzaba mouse con teclado). Se excluyen de TODO match de pista.
_COLOR_PISTA = frozenset((
    "negro", "negra", "blanco", "blanca", "gris", "plata", "plateado", "azul",
    "rojo", "verde", "rosa", "violeta", "celeste", "dorado", "beige",
    "gamer", "inalambrico", "mecanico", "lightsync", "bluetooth",
))
# Categorias: genericas (no distinguen modelo) pero SI confirman que la pista es
# de la misma familia que el termino. 'tablet' + pista 'Tablet A9 Gris' deben
# enlazar; 'mouse' + pista 'Tablet...' no (la pista no nombra la categoria).
_CATEGORIA_PISTA = frozenset((
    "mouse", "teclado", "monitor", "auricular", "auriculares", "silla",
    "parlante", "tablet", "webcam", "disco",
))
_GENERICO_PISTA = _COLOR_PISTA | _CATEGORIA_PISTA


def _relevante(cands: list[dict], term: str) -> list[dict]:
    """Descarta candidatos que matchearon FLOJO. Un candidato es relevante si
    comparte con el termino al menos un token DISTINTIVO (con digito, o de 4+
    letras), tolerando typos: 'tecldo'~'teclado' (difflib >=0.8) pega, pero
    'iphone'/'freidora' no se parecen a nada de 'Logitech G Pro X' y se caen.
    Asi 'iphone 15 pro max' deja de ofrecer 'G Pro X' como si viniera al caso.
    Si el termino no tiene token distintivo (categoria corta: 'tv', 'pc'), no se
    filtra: mejor ofrecer que rechazar de mas."""
    import difflib

    def _match(t: str, nt: str) -> bool:
        if t == nt:
            return True
        # Numericos: solo exacto ('5' de Ryzen 5 no pega con '15' de iphone 15).
        if t.isdigit() or nt.isdigit():
            return False
        # Por PREFIJO, no substring: 'tab' es prefijo de 'tablet' (legitimo),
        # pero 'pro' (de 'G Pro X') NO es prefijo de 'compro' -> no pega. El
        # substring suelto colaba 'pro' dentro de 'compro' y ofrecia mice a un
        # pedido de tablet. El token corto (>=3) tiene que ABRIR al largo.
        corto, largo = (t, nt) if len(t) <= len(nt) else (nt, t)
        if len(corto) >= 3 and largo.startswith(corto):
            return True
        if len(t) >= 4 and difflib.get_close_matches(t, [nt], 1, 0.8):
            return True
        return False

    toks = [t for t in re.findall(r"[a-z0-9]+", _norm(term))
            if any(c.isdigit() for c in t) or len(t) >= 4]
    if not toks:
        return list(cands)
    out = []
    for p in cands:
        # Corpus = los MISMOS campos con los que la busqueda matcheo (nombre,
        # categoria, marca). Sin esto un termino de categoria pura ('mouse',
        # 'teclado') cuyo producto no lleva la categoria en el nombre
        # ('Logitech G203 Lightsync') se descartaba aunque la busqueda lo
        # habia traido legitimamente por categoria.
        campos = " ".join(str(p.get(k, "")) for k in
                          ("nombre", "categoria", "marca"))
        name_toks = re.findall(r"[a-z0-9]+", _norm(campos))
        if any(_match(t, nt) for t in toks for nt in name_toks):
            out.append(p)
    return out


def _norm(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.lower()


def _pista_para(term: str, pistas: list[str]) -> Optional[str]:
    """Si el interprete ya resolvio un producto que matchea el termino crudo,
    esa lectura es mas precisa que el termino: se busca con ella. Asi el
    extractor lee IGUAL que el resto del Provider (interprete primero, crudo de
    respaldo). Match solo por tokens DISTINTIVOS: un codigo de modelo (con
    digito) o una palabra larga que no sea color ni categoria. Un color suelto
    ('negro') no alcanza para empatar una pista con un termino de otro producto."""
    toks = {t for t in term.split()
            if any(c.isdigit() for c in t)
            or (len(t) >= 4 and t not in _GENERICO_PISTA)}
    # Token de categoria del termino: generico, pero si aparece en la pista
    # confirma que la pista refina ESTA familia ('tablet' -> 'Tablet A9 Gris').
    # Nunca cruza productos: la pista de otra categoria no nombra esta.
    cats = {t for t in term.split() if t in _CATEGORIA_PISTA}
    for p in pistas:
        p_low = str(p or "").lower()
        if any(tok in p_low for tok in toks):
            return p
        if any(re.search(rf"\b{re.escape(c)}", p_low) for c in cats):
            return p
    return None


def extraer_pedido(mensaje: str, tienda_id: str,
                   interpretacion: Optional[dict] = None,
                   trace_id: Optional[str] = None) -> Optional[dict]:
    """Devuelve {"items": [...], "ambiguos": [...]} o None si el mensaje no
    trae un pedido con cantidades. items: renglones resueltos con id real.
    ambiguos: terminos con varios candidatos donde no corresponde adivinar.
    Lee desde la interpretacion del LLM primero (pistas) y el texto crudo
    como respaldo; todo se valida contra el catalogo real."""
    pistas: list[str] = []
    if interpretacion:
        if interpretacion.get("producto_resuelto"):
            pistas.append(interpretacion["producto_resuelto"])
        pistas += [c for c in (interpretacion.get("candidatos") or []) if c]
    m = (mensaje or "").lower()
    segmentos = []
    # Primero se parte el mensaje por los conectores ("y", comas, puntos):
    # sin esto el primer renglon se come al segundo ("2 mouses y dos tablets"
    # daba un solo segmento "mouses y dos").
    for trozo in re.split(r"\s+y\s+|,|\.|;", m):
        match = _SEG_RE.search(trozo)
        if not match:
            continue
        num, resto = match.groups()
        cant = int(num) if num.isdigit() else _NUM_PALABRA.get(num.lower())
        term = _termino(resto)
        if cant and 0 < cant <= 50 and term:
            # Se guarda tambien el trozo crudo: la relevancia se mide contra el
            # (tiene la marca/modelo que el _termino recorta, ej 'iphone'), no
            # contra el termino pelado ('pro max') que pierde el distintivo.
            segmentos.append((cant, term, trozo))
    if not segmentos:
        return None

    pide_barato = bool(re.search(r"barat|econom|precio[s]?\s+mas\s+bajo", m))
    items, ambiguos = [], []
    vistos = set()
    for cant, term, trozo in segmentos:
        if term in vistos:
            continue
        vistos.add(term)
        try:
            # Interprete primero: si resolvio un producto que matchea este
            # termino, se busca con esa lectura (mas precisa). Crudo de
            # respaldo: si la pista no encuentra, va el termino pelado.
            pista = _pista_para(term, pistas)
            _corr_out: list = []
            cands = (_candidatos(pista, tienda_id) if pista else []) \
                or _candidatos_con_typo(term, tienda_id, trace_id=trace_id,
                                        corregido_out=_corr_out)
            if not cands and pistas and len(segmentos) == 1:
                cands = _candidatos(pistas[0], tienda_id)
        except Exception as e:
            log.warning("pedido_multi_busqueda_error", trace_id=trace_id,
                        termino=term, error=str(e)[:120])
            continue
        if not cands:
            continue
        # Match flojo: si los candidatos no comparten un token distintivo con el
        # termino (typos tolerados), es fuera-de-catalogo disfrazado ('iphone' ->
        # 'G Pro X'). Se descartan: el renglon queda sin candidatos y el bot
        # pregunta/avisa en vez de ofrecer algo que no viene al caso.
        # El texto de relevancia suma el termino YA corregido por typo: sin esto
        # el trozo crudo conserva el typo ('mauses') y _relevante descarta el
        # renglon entero (visto 12-jun: '2 mauses y dos teclados' perdia el
        # mouse en silencio; vender medio pedido es peor que no vender).
        _rel_text = trozo + ((" " + " ".join(_corr_out)) if _corr_out else "")
        cands = _relevante(cands, _rel_text)
        if not cands:
            continue
        # Guarda de termino corto sin token distintivo ("eco", "una"): exigir que
        # aparezca como PALABRA ENTERA en el nombre del candidato, no como prefijo
        # de un token mas largo. Sin esto "eco" (3 letras) pega con "EcoTank" por
        # prefijo y ofrece impresoras a un "una eco" (visto en prod 16-jun,
        # repetido). "ram"/"ssd" pasan: son palabra entera en el nombre.
        _toks_t = re.findall(r"[a-z0-9]+", _norm(term))
        _sin_distintivo = bool(_toks_t) and all(
            (len(t) < 4 and not any(c.isdigit() for c in t)) for t in _toks_t)
        if _sin_distintivo:
            _palabras_t = set(_toks_t)
            cands = [p for p in cands
                     if _palabras_t & set(re.findall(
                         r"[a-z0-9]+", _norm(p.get("nombre", ""))))]
            if not cands:
                continue
        # El cliente trajo un atributo que discrimina ('mouse G203 negro'):
        # angostar por color/modelo antes de declarar ambiguedad. Scope al
        # termino del renglon para no cruzar el color de otro item.
        if len(cands) > 1:
            cands = refinar_por_atributo(cands, term) or cands
        # Nombre EXACTO resuelto por el interprete: gana directo, sin
        # ambiguedad (la pista "Tab A9 Gris" no debe empatar con la Azul).
        exacto = [p for p in cands
                  if pista and str(p.get("nombre", "")).strip().lower()
                  == str(pista).strip().lower()]
        if len(exacto) == 1:
            elegido = exacto[0]
        elif pide_barato:
            elegido = min(cands, key=lambda p: p["precio_ars"])
        elif len(cands) == 1:
            elegido = cands[0]
        else:
            ambiguos.append({"termino": term, "cantidad": cant,
                             "candidatos": [
                                 {"id": p["id"], "nombre": p.get("nombre"),
                                  "precio_ars": p.get("precio_ars")}
                                 for p in cands[:3]]})
            continue
        items.append({"product_id": elegido["id"],
                      "nombre": elegido.get("nombre"),
                      "cantidad": cant,
                      "precio_ars": elegido.get("precio_ars")})

    if not items and not ambiguos:
        return None
    log.info("pedido_multi_extraido", trace_id=trace_id,
             items=[(i["product_id"], i["cantidad"]) for i in items],
             ambiguos=[a["termino"] for a in ambiguos])
    return {"items": items, "ambiguos": ambiguos}


def completar_pedido(pendiente: dict, tienda_id: str,
                     trace_id: Optional[str] = None) -> Optional[dict]:
    """Completa un pedido a medio armar guardado de un turno anterior (flag
    PEDIDO_PENDIENTE): cada termino ambiguo se resuelve al MAS BARATO CON
    STOCK, el mismo criterio determinista de extraer_pedido cuando piden
    barato. Los renglones ya resueltos pasan tal cual. Devuelve
    {"items": [...], "ambiguos": []} o None si nada se pudo resolver."""
    items = []
    for i in (pendiente or {}).get("items") or []:
        if i.get("product_id") and i.get("cantidad"):
            items.append({"product_id": i["product_id"],
                          "nombre": i.get("nombre"),
                          "cantidad": i["cantidad"],
                          "precio_ars": i.get("precio_ars")})
    for amb in (pendiente or {}).get("ambiguos") or []:
        term = amb.get("termino")
        cant = amb.get("cantidad", 1)
        if not term or not cant:
            continue
        try:
            cands = _candidatos_con_typo(term, tienda_id, trace_id=trace_id)
        except Exception as e:
            log.warning("pedido_pendiente_busqueda_error", trace_id=trace_id,
                        termino=term, error=str(e)[:120])
            continue
        if not cands:
            continue
        elegido = min(cands, key=lambda p: p["precio_ars"])
        items.append({"product_id": elegido["id"],
                      "nombre": elegido.get("nombre"),
                      "cantidad": cant,
                      "precio_ars": elegido.get("precio_ars")})
    if not items:
        return None
    log.info("pedido_pendiente_resuelto", trace_id=trace_id,
             items=[(i["product_id"], i["cantidad"]) for i in items])
    return {"items": items, "ambiguos": []}
