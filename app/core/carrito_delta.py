"""
CARRITO_DELTA — el codigo muta el carrito existente por codigo, no el Solver.

El Provider ya recalcula el carrito que tiene, arma pedidos combinados nuevos y
completa pedidos a medio armar. Pero el CAMBIO sobre el carrito vigente
("agrega un mouse", "saca el teclado", "mejor 3 en vez de 2") hoy lo ejecuta el
Solver: el contrato le dice "parti de estos ids, saca o cambia cantidades" y el
modelo decide. Justo lo que no queremos: el cambio de cantidad o de articulo
depende del LLM.

Esta pieza lee el delta del mensaje y muta el carrito por codigo. Tres
operaciones, detectadas por verbo y recortadas en segmentos:

  - AGREGAR: "agrega un mouse", "sumale 2 teclados". Resuelve el producto contra
    el CATALOGO (reusa pedido_multi.extraer_pedido: typos, barato, ambiguedad).
    Si el producto ya esta en el carrito, suma cantidad; si no, agrega la linea.
  - SACAR: "saca el teclado", "quita un mouse". Apunta contra el CARRITO. Con
    cantidad menor a la que hay, descuenta; si no, borra la linea.
  - CAMBIAR CANTIDAD: "mejor 3 en vez de 2", "que sean 3", "poneme 5 mouses".
    Apunta contra el carrito y fija la cantidad nueva.

El objetivo es resolver el carrito SIN el LLM. Para apuntar a una linea del
carrito se usa un matcher propio que SI usa la categoria ("el teclado", "el
mouse"), al reves de resolver_pedido, que trata esas palabras como stopwords
porque sirve para el catalogo entero. Ante ambiguedad real NO se adivina: se
listan las opciones y se ordena preguntar.

Funcion PURA salvo la busqueda del catalogo para los agregados (igual que
extraer_pedido); se testea offline con search_products monkeypatcheado. Detras
del flag CARRITO_DELTA (default off). Alimenta el estado unico, que recalcula
con los ids nuevos.
"""
import re
import unicodedata
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)

# Numero en digito o palabra, para cantidades.
_NUM_PALABRA = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
}
_NUMW = r"\d{1,2}|un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez"

# Verbos que abren cada operacion. Se buscan por posicion en el mensaje para
# cortar en segmentos: cada verbo manda sobre el texto hasta el verbo siguiente.
_RE_AGREGAR = re.compile(
    r"\b(agreg\w*|sumale|sumal\w*|suma\b|añad\w*|anad\w*|incorpor\w*"
    r"|tambien\s+(?:quiero|llevo|sumo)|ademas\s+(?:quiero|llevo|sumo))",
    re.IGNORECASE)
_RE_SACAR = re.compile(
    r"\b(saca\w*|saque\w*|quit\w*|elimin\w*|borr\w*|sin\b|ya\s+no\s+(?:quiero|va))",
    re.IGNORECASE)
_RE_CANTIDAD = re.compile(
    r"((?:" + _NUMW + r")\s+en\s+(?:vez|lugar)\s+de"
    r"|mejor\s+(?:" + _NUMW + r")"
    r"|que\s+sean\b|que\s+sea\b"
    r"|dej\w*\s+(?:en\s+)?(?:" + _NUMW + r")"
    r"|cambi\w*\s+a\s+(?:" + _NUMW + r")"
    r"|pon[eé]\w*\s+(?:" + _NUMW + r"))",
    re.IGNORECASE)

# Patrones para sacar la cantidad NUEVA de un segmento de cambio, en orden de
# prioridad: el numero antes de "en vez de" gana al de despues.
_SET_PATTERNS = [
    re.compile(r"(" + _NUMW + r")\s+en\s+(?:vez|lugar)\s+de", re.IGNORECASE),
    re.compile(r"mejor\s+(" + _NUMW + r")", re.IGNORECASE),
    re.compile(r"que\s+sean?\s+(" + _NUMW + r")", re.IGNORECASE),
    re.compile(r"dej\w*\s+(?:en\s+)?(" + _NUMW + r")", re.IGNORECASE),
    re.compile(r"cambi\w*\s+a\s+(" + _NUMW + r")", re.IGNORECASE),
    re.compile(r"pon[eé]\w*\s+(" + _NUMW + r")", re.IGNORECASE),
    re.compile(r"\b(" + _NUMW + r")\b", re.IGNORECASE),  # respaldo: primer numero
]

# Palabras que NO son producto al apuntar contra el carrito. A diferencia de
# resolver_pedido, las categorias (teclado, mouse) NO estan: el cliente refiere
# una linea del carrito por su categoria, y ahi tiene que pegar.
_CONECTORES = frozenset((
    "de", "el", "la", "los", "las", "un", "una", "uno", "con", "para", "por",
    "y", "que", "del", "al", "es", "su", "lo", "mi", "me", "te", "se", "ese",
    "esa", "eso", "este", "esta", "esto", "otro", "otra", "en", "vez", "lugar",
    "mejor", "mas", "menos", "sea", "sean", "deja", "dejame", "dejalo",
    "cambia", "cambialo", "cambiame", "pone", "poneme", "ponele", "ponme",
    "saca", "sacame", "sacale", "quita", "quitame", "elimina", "borra",
    "agrega", "agregame", "suma", "sumale", "tambien", "ademas", "sin",
    "quiero", "llevo", "unidad", "unidades", "cada",
))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.lower()


def _num(tok: str) -> Optional[int]:
    tok = tok.lower()
    if tok.isdigit():
        return int(tok)
    return _NUM_PALABRA.get(tok)


def _termino(seg: str) -> str:
    """Las palabras del segmento que describen el producto: saca numeros,
    verbos y conectores, singulariza."""
    out = []
    for w in re.findall(r"[a-z0-9áéíóúñü]+", _norm(seg)):
        if w.isdigit() or w in _NUM_PALABRA or w in _CONECTORES:
            continue
        out.append(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return " ".join(out)


def _resolver_en_carrito(seg: str, carrito: list[dict]) -> tuple[str, object]:
    """Apunta el segmento a una linea del carrito.

    Returns:
        ("ok", item) si resuelve una sola; ("ambiguo", [items]) si varias;
        ("ninguno", None) si no apunta a nada. Con un solo item en el carrito y
        sin termino util, ese item gana (anafora: "saca uno", "que sean 3").
    """
    if not carrito:
        return ("ninguno", None)
    seg_norm = _norm(seg)
    term = _termino(seg)
    term_toks = [t for t in term.split() if len(t) >= 3]

    # Superlativo de precio sobre el carrito ("saca el mas caro").
    if re.search(r"mas\s+(?:barat|economic|accesibl|bajo)", seg_norm):
        validos = [it for it in carrito
                   if isinstance(it.get("precio_ars"), (int, float))]
        if validos:
            return ("ok", min(validos, key=lambda it: it["precio_ars"]))
    if re.search(r"mas\s+(?:car|premium|cost)", seg_norm):
        validos = [it for it in carrito
                   if isinstance(it.get("precio_ars"), (int, float))]
        if validos:
            return ("ok", max(validos, key=lambda it: it["precio_ars"]))

    if term_toks:
        pega = []
        for it in carrito:
            # Nombre Y categoria: el cliente refiere la linea por su categoria
            # ("el mouse"), que no esta en el nombre ("Logitech G203").
            texto_it = _norm(it.get("nombre", "")) + " " + _norm(it.get("categoria", ""))
            it_toks = set(re.findall(r"[a-z0-9]+", texto_it))
            if any(t in texto_it for t in term_toks) \
                    or any(t in term_toks for t in it_toks):
                pega.append(it)
        if len(pega) == 1:
            return ("ok", pega[0])
        if len(pega) > 1:
            return ("ambiguo", pega)

    # Sin termino que apunte: con un solo item en el carrito, es ese.
    if not term_toks and len(carrito) == 1:
        return ("ok", carrito[0])
    return ("ninguno", None)


def _cant_nueva(seg: str) -> Optional[int]:
    """La cantidad nueva de un segmento de cambio, por prioridad de patron."""
    for pat in _SET_PATTERNS:
        m = pat.search(seg)
        if m:
            n = _num(m.group(1))
            if n and 1 <= n <= 50:
                return n
    return None


def _cant_en_segmento(seg: str) -> Optional[int]:
    """Primera cantidad chica del segmento (para 'saca 2 teclados')."""
    m = re.search(r"\b(" + _NUMW + r")\b", _norm(seg))
    if m:
        n = _num(m.group(1))
        if n and 1 <= n <= 50:
            return n
    return None


def _segmentos(msg_norm: str) -> list[tuple[int, str]]:
    """Marcadores de operacion por posicion, ordenados. Un solo marcador de
    cantidad (el primero): el resto del cambio vive en su segmento."""
    marcas: list[tuple[int, str]] = []
    for m in _RE_AGREGAR.finditer(msg_norm):
        marcas.append((m.start(), "agregar"))
    for m in _RE_SACAR.finditer(msg_norm):
        marcas.append((m.start(), "sacar"))
    cant_marcada = False
    for m in _RE_CANTIDAD.finditer(msg_norm):
        if cant_marcada:
            continue
        marcas.append((m.start(), "cantidad"))
        cant_marcada = True
    marcas.sort()
    return marcas


def mutar_carrito(mensaje: str, carrito: list[dict], *,
                  tienda_id: str,
                  interpretacion: Optional[dict] = None,
                  trace_id: Optional[str] = None) -> Optional[dict]:
    """Aplica el delta del mensaje sobre el carrito y devuelve el carrito nuevo.

    Args:
        mensaje: texto crudo del cliente.
        carrito: lista [{id, nombre, cantidad, precio_ars?}] vigente.
        tienda_id: para resolver los agregados contra el catalogo.

    Returns:
        None si el mensaje no trae ninguna operacion de delta (el carrito sigue
        igual). Si trae, dict con:
          - "carrito": la lista nueva [{id, nombre, cantidad, precio_ars?}]
          - "cambios": [{op, id, nombre, de, a}] lo que efectivamente cambio
          - "ambiguos": [{op, termino, candidatos}] referencias sin resolver
          - "no_encontrado": [{op, termino}] referencias que no apuntan a nada
    """
    msg_norm = _norm(mensaje)
    marcas = _segmentos(msg_norm)
    if not marcas:
        return None

    # Trabajo sobre una copia ordenada por id; conservo el orden original.
    items = [dict(it) for it in (carrito or []) if it.get("id")]
    # Enriquezco con categoria (y precio si falta) desde el catalogo para poder
    # apuntar "el mouse" / "el teclado" a su linea. Best-effort: si el catalogo
    # no responde, se apunta solo por nombre.
    try:
        from app.core.tools import get_product_by_id
        for it in items:
            p = get_product_by_id(it["id"], tienda_id=tienda_id)
            if p:
                it.setdefault("nombre", p.get("nombre"))
                it["categoria"] = p.get("categoria")
                if it.get("precio_ars") is None:
                    it["precio_ars"] = p.get("precio_ars")
    except Exception as e:
        log.warning("carrito_delta_enriquecer_error", trace_id=trace_id,
                    error=str(e)[:120])
    orden = [it["id"] for it in items]
    por_id = {it["id"]: it for it in items}

    cambios: list[dict] = []
    ambiguos: list[dict] = []
    no_encontrado: list[dict] = []

    for i, (pos, op) in enumerate(marcas):
        fin = marcas[i + 1][0] if i + 1 < len(marcas) else len(msg_norm)
        seg = msg_norm[pos:fin]

        if op == "agregar":
            try:
                from app.core.pedido_multi import extraer_pedido
                ped = extraer_pedido(seg, tienda_id,
                                     interpretacion=interpretacion,
                                     trace_id=trace_id)
            except Exception as e:
                log.warning("carrito_delta_agregar_error", trace_id=trace_id,
                            error=str(e)[:140])
                ped = None
            if not ped:
                continue
            for it in ped.get("items") or []:
                pid = it["product_id"]
                if pid in por_id:
                    de = por_id[pid].get("cantidad", 1)
                    por_id[pid]["cantidad"] = de + it["cantidad"]
                    cambios.append({"op": "agregar", "id": pid,
                                    "nombre": it.get("nombre"),
                                    "de": de, "a": por_id[pid]["cantidad"]})
                else:
                    nuevo = {"id": pid, "nombre": it.get("nombre"),
                             "cantidad": it["cantidad"],
                             "precio_ars": it.get("precio_ars")}
                    por_id[pid] = nuevo
                    orden.append(pid)
                    cambios.append({"op": "agregar", "id": pid,
                                    "nombre": it.get("nombre"),
                                    "de": 0, "a": it["cantidad"]})
            for amb in ped.get("ambiguos") or []:
                ambiguos.append({"op": "agregar", "termino": amb["termino"],
                                 "candidatos": amb["candidatos"]})

        elif op == "sacar":
            estado, res = _resolver_en_carrito(seg, list(por_id.values()))
            term = _termino(seg)
            if estado == "ambiguo":
                ambiguos.append({"op": "sacar", "termino": term,
                                 "candidatos": [
                                     {"id": it["id"], "nombre": it.get("nombre")}
                                     for it in res]})
            elif estado == "ninguno":
                no_encontrado.append({"op": "sacar", "termino": term})
            else:
                pid = res["id"]
                de = por_id[pid].get("cantidad", 1)
                cant = _cant_en_segmento(seg)
                if cant and cant < de:
                    por_id[pid]["cantidad"] = de - cant
                    cambios.append({"op": "sacar", "id": pid,
                                    "nombre": res.get("nombre"),
                                    "de": de, "a": de - cant})
                else:
                    del por_id[pid]
                    orden = [x for x in orden if x != pid]
                    cambios.append({"op": "sacar", "id": pid,
                                    "nombre": res.get("nombre"),
                                    "de": de, "a": 0})

        elif op == "cantidad":
            estado, res = _resolver_en_carrito(seg, list(por_id.values()))
            term = _termino(seg)
            nueva = _cant_nueva(seg)
            if nueva is None:
                continue
            if estado == "ambiguo":
                ambiguos.append({"op": "cantidad", "termino": term,
                                 "candidatos": [
                                     {"id": it["id"], "nombre": it.get("nombre")}
                                     for it in res]})
            elif estado == "ninguno":
                no_encontrado.append({"op": "cantidad", "termino": term})
            else:
                pid = res["id"]
                de = por_id[pid].get("cantidad", 1)
                if nueva != de:
                    por_id[pid]["cantidad"] = nueva
                    cambios.append({"op": "cantidad", "id": pid,
                                    "nombre": res.get("nombre"),
                                    "de": de, "a": nueva})

    if not cambios and not ambiguos and not no_encontrado:
        return None

    # Salida limpia: la categoria fue solo para apuntar, no va al carrito.
    nuevo_carrito = [
        {k: por_id[pid][k] for k in ("id", "nombre", "cantidad", "precio_ars")
         if k in por_id[pid]}
        for pid in orden if pid in por_id]
    log.info("carrito_delta_aplicado", trace_id=trace_id,
             cambios=[(c["op"], c["id"], c["de"], c["a"]) for c in cambios],
             ambiguos=len(ambiguos), no_encontrado=len(no_encontrado),
             items=len(nuevo_carrito))
    return {"carrito": nuevo_carrito, "cambios": cambios,
            "ambiguos": ambiguos, "no_encontrado": no_encontrado}
