"""EL NEXO DE TEMA DE LA FAQ: LOS TRES TEMAS MAS PARECIDOS Y LA PALABRA CLAVE QUE ELIGE.

Pasado de `banco_pruebas/flujo/nexo_tema.py` el 17-nov-2026, orden de Martin, tal cual: el banco importa de aca. El
fragmento del cliente contra cada alias de cada tema da tres candidatos; el codigo elige el primero que comparte una
palabra clave de la FAQ, y Jev confirma lo elegido entre los tres o ninguno.
"""
import functools
import json
import os

from . import rubro as NR

# Calibrado en el banco: tres temas candidatos.
CANDIDATOS = 3


@functools.lru_cache(maxsize=None)
def fuente(tid):
    faq = json.load(open(os.path.join(NR.DATOS, tid, "faq.json"), encoding="utf-8"))
    alias = json.load(open(os.path.join(NR.DATOS, tid, "alias.json"), encoding="utf-8"))["temas"]
    return faq, alias


def docs(faq, alias):
    """[(tema, alias)]: cada forma de preguntar un tema es un documento."""
    return [(f["tema"], a) for f in faq for a in alias.get(f["tema"], [])]



def _una_letra(a, b):
    """Dos letras seguidas dadas vuelta, el error de tipeo de WhatsApp: "fatcura", "tineen". Una letra cambiada no:
    medido el 16-nov, confunde palabras reales, "vieja" con "viaja" y "tiene" con "viene"."""
    if len(a) != len(b) or a == b:
        return False
    d = [i for i in range(len(a)) if a[i] != b[i]]
    return len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]


class Nexo:
    def __init__(self, tid, puntajes):
        """`puntajes`: {"temas", "consultas": {fragmento: [puntaje por tema]}}, de `vectores`."""
        self.tid = tid
        from app.core.flujo.agenda import _VACIAS
        self.vacias = _VACIAS
        faq, alias = fuente(tid)
        self.faq = {f["tema"]: f for f in faq}
        p = puntajes
        self.temas, self.q = p["temas"], p["consultas"]
        # Los alias son formas de preguntar: sirven a los embeddings, pero traen "tenes", "necesito", "venden". La
        # funcion que elige compara contra las palabras clave que la tienda cargo por tema, menos las que el catalogo
        # usa para nombrar productos: "mouse" o "caja" no dicen que el cliente pregunta por la tienda.
        _, ralias, _, modelos = NR.fuente(tid)
        self.vocabulario = {w for k, fs in modelos.items() for x in [k[0], k[1], k[2]] + [f["nombre"] for f in fs]
                            + NR.etiquetas(fs) + ralias.get(k[0], []) for w in NR.n(x).split()}
        self.palabras = {t: {w for w in self._ws(" ".join(self.faq[t].get("keywords", [])))
                             if not any(self._igual(w, v) for v in self.vocabulario)} for t in self.temas}

    def _ws(self, texto):
        return {w for w in NR.n(texto).split() if w not in self.vacias and not w.isdigit()}

    @staticmethod
    def _igual(w, p):
        """Igual, o una empieza con la otra desde cuatro letras, por el plural; o, desde cinco letras, dos letras
        seguidas dadas vuelta, por el tipeo: "fatcura" es "factura". Medido el 16-nov en las formas de WhatsApp de las
        525."""
        if w == p or (min(len(w), len(p)) >= 4 and (w.startswith(p) or p.startswith(w))):
            return True
        return min(len(w), len(p)) >= 5 and _una_letra(w, p)

    def candidatos(self, fragmento):
        """PIEZA 1: los tres temas cuyo alias mas se parece al fragmento."""
        if fragmento not in self.q:
            return []
        return [t for _, t in sorted(zip(self.q[fragmento], self.temas), reverse=True)][:CANDIDATOS]

    def comparte(self, ws, tema):
        return sorted(w for w in ws for p in self.palabras[tema] if self._igual(w, p))

    def elegir(self, fragmento, cands):
        """PIEZA 2: el primer candidato que comparte una palabra con el fragmento; si ninguno, ningun tema."""
        ws = self._ws(fragmento)
        for t in cands:
            if self.comparte(ws, t):
                return t, self.comparte(ws, t)
        return None, []

    def tema(self, fragmento):
        cands = self.candidatos(fragmento)
        elegido, por = self.elegir(fragmento, cands)
        return {"fragmento": fragmento, "candidatos": cands, "elegido": elegido, "por": por,
                "texto": self.texto(elegido) if elegido else None}

    def texto(self, tema):
        """PIEZA 3: el texto de la FAQ con los numeros estampados por `curadas`, como en produccion. Si a la curada le
        falta un valor, la respuesta llana."""
        from app.core.curadas import estampar_valores
        f = self.faq[tema]
        return (estampar_valores(f.get("respuesta_curada") or "", f) or "") or f["respuesta"]



NINGUNO = "ninguno"
DESC_NINGUNO = ("esa parte no pregunta por esta regla de la tienda: pide un producto o un dato del producto, dice a "
                "donde mandarlo, o pregunta algo que la tienda no contesta")



def _desc(nx, t):
    return f"{t.replace('_', ' ')}: {nx.faq[t]['respuesta']}"

