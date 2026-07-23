"""
FILTRO DETERMINISTA ANTI-DUPLICADO — refuerzo FINAL del flujo de mensaje.

Saca contenido duplicado que se pudo colar en cualquier paso (el solver que
repite un bloque, el cierre que re-suma el cuerpo, un acople doble). Es la red
de ultimo momento, corre despues de componer y antes de mandarle la respuesta
al cliente.

CONSERVADOR a proposito: solo saca duplicados EXACTOS y CONTIGUOS -o la respuesta
entera repetida en dos mitades identicas-. Nunca reordena, nunca toca un
casi-duplicado, nunca borra una linea legitima (dos productos al mismo precio son
lineas DISTINTAS porque cambia el nombre). Asi refuerza sin entorpecer.
"""
import re


def _norm(s: str) -> str:
    """Clave de comparacion: colapsa espacios y baja a minusculas. No se usa
    para mostrar, solo para decidir si dos trozos son el MISMO texto."""
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def deduplicar_respuesta(texto: str) -> str:
    """Saca los duplicados exactos y contiguos de la respuesta. Idempotente."""
    t = (texto or "").strip()
    if not t:
        return t

    # ── 1) BLOQUES (parrafos separados por linea en blanco) ──────────────────
    bloques = re.split(r"\n\s*\n", t)
    norm = [_norm(b) for b in bloques]

    # 1a) respuesta ENTERA repetida: la lista de bloques es X + X -> deja X.
    #     Es el caso mas grave (todo el mensaje dos veces, guion 59/60 T2).
    nb = len(bloques)
    if nb >= 2 and nb % 2 == 0 and norm[:nb // 2] == norm[nb // 2:] and any(norm[:nb // 2]):
        bloques = bloques[:nb // 2]

    # 1b) bloques identicos repetidos. Contiguos siempre; y NO contiguos SOLO si
    # el bloque tiene sustancia (varias lineas o largo): el presupuesto que el
    # solver mostro y el cierre repite en su "Resumen" queda una sola vez (caso
    # real modo lead). Un bloque corto (una coletilla) puede repetirse legitimo,
    # asi que ese solo se dedup si es CONTIGUO.
    out_b: list[str] = []
    vistos_sust: set[str] = set()
    for b in bloques:
        nb_ = _norm(b)
        if not nb_:
            out_b.append(b)
            continue
        if out_b and nb_ == _norm(out_b[-1]):
            continue  # contiguo identico
        sustancial = "\n" in b.strip() or len(nb_) > 40
        if sustancial and nb_ in vistos_sust:
            continue  # bloque con sustancia ya mostrado antes (no contiguo)
        out_b.append(b)
        if sustancial:
            vistos_sust.add(nb_)
    t = "\n\n".join(out_b)

    # ── 2) LINEAS contiguas identicas con sustancia ──────────────────────────
    lineas = t.split("\n")
    out_l: list[str] = []
    for l in lineas:
        n = _norm(l)
        if out_l and n and len(n) > 3 and n == _norm(out_l[-1]):
            continue
        out_l.append(l)
    return "\n".join(out_l).strip()
