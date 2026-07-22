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

    # 1b) bloques contiguos identicos (ej. el presupuesto pegado dos veces).
    out_b: list[str] = []
    for b in bloques:
        nb_ = _norm(b)
        if out_b and nb_ and nb_ == _norm(out_b[-1]):
            continue
        out_b.append(b)
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
