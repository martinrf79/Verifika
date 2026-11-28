"""LOS CANDIDATOS DEL DATO 1 POR EMBEDDINGS, SOBRE LA BASE DE JERGA (28-nov-2026).

Etapa 1, paso 2: para una fila que el codigo no da por clara, traer los conceptos mas cercanos para que Luna elija.
El indice no es el catalogo: son las expresiones de `tienda.jsonl` y `general.jsonl`, cada una con su concepto. Se
busca la fila entera y cada pedazo de una a tres palabras con contenido, y el puntaje de un concepto es el mejor de sus
expresiones: asi cinco formas de decir mouse no ocupan los cinco lugares.

Embeddings locales, multilingual-e5-large cuantizado en ONNX, sin costo ni tope. Los de Gemini de produccion no
entran por la gratis: su tope es de 1.000 textos por dia, medido el 28-nov, y la base son unos 9.000. Pasar a los de
Gemini es una decision para cuando esto vaya al bot. Cada texto se calcula una vez y queda en `vectores_cache.npz`.
Necesita `onnxruntime`, `tokenizers` y `huggingface_hub`, que no estan en requirements.txt porque es solo del banco.

    python3 vectores.py "esa caja donde va toda la compu"
"""
import os, sys
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import tabla as T  # noqa: E402
import nexo as N  # noqa: E402

MODELO = "Xenova/multilingual-e5-large"
CACHE = os.path.join(AQUI, "vectores_cache.npz")
_SES = None


def _modelo():
    global _SES
    if _SES is None:
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(hf_hub_download(MODELO, "tokenizer.json"))
        tok.enable_truncation(64)
        tok.enable_padding()
        _SES = (tok, ort.InferenceSession(hf_hub_download(MODELO, "onnx/model_quantized.onnx")))
    return _SES


def _calcular(textos):
    """e5 pide el prefijo "query: " en los dos lados cuando la comparacion es entre textos del mismo tipo."""
    tok, ses = _modelo()
    enc = tok.encode_batch(["query: " + t for t in textos])
    ids = np.array([e.ids for e in enc], dtype=np.int64)
    m = np.array([e.attention_mask for e in enc], dtype=np.int64)
    ent = {"input_ids": ids, "attention_mask": m}
    if "token_type_ids" in {i.name for i in ses.get_inputs()}:
        ent["token_type_ids"] = np.zeros_like(ids)
    h = ses.run(None, ent)[0]
    v = (h * m[..., None]).sum(1) / m.sum(1, keepdims=True)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


class Cache:
    def __init__(self):
        self.v = {}
        if os.path.exists(CACHE):
            z = np.load(CACHE, allow_pickle=True)
            self.v = dict(zip(z["t"].tolist(), z["v"]))
        self.sucio = False

    def guardar(self):
        if self.sucio:
            t = list(self.v)
            np.savez_compressed(CACHE, t=np.array(t, dtype=object), v=np.stack([self.v[x] for x in t]))
            self.sucio = False

    def de(self, textos):
        falta = [t for t in dict.fromkeys(textos) if t not in self.v]
        for i in range(0, len(falta), 64):
            lote = falta[i:i + 64]
            for t, v in zip(lote, _calcular(lote)):
                self.v[t] = v.astype(np.float32)
            self.sucio = True
        self.guardar()
        return np.stack([self.v[t] for t in textos])


class Indice:
    def __init__(self, cache=None):
        self.cache = cache or Cache()
        tienda, general, _tr, _va = T.cargar()
        filas = [(N.forma(x["expresion"]), x["concepto"]) for x in tienda]
        filas += [(N.forma(x["expresion"]), x["enlace"] or x["valor"]) for x in general]
        filas = [(e, c) for e, c in dict.fromkeys(filas) if e and e not in N.VACIAS]
        self.exp = [e for e, _ in filas]
        self.con = [c for _, c in filas]
        self.M = self.cache.de(self.exp)

    @staticmethod
    def pedazos(fila):
        f = N.forma(fila)
        pal = [p for p in f.split() if p not in N.VACIAS]
        out = [f]
        for n in (1, 2, 3):
            out += [" ".join(pal[i:i + n]) for i in range(len(pal) - n + 1)]
        return [x for x in dict.fromkeys(out) if x]

    def _rank(self, ps, solo_tienda):
        Q = self.cache.de(ps)
        S = Q @ self.M.T                       # pedazos x expresiones
        mejor = {}
        for j in np.argsort(-S.max(axis=0))[:400]:
            c = self.con[j]
            if solo_tienda and not T.valido_tienda(c):
                continue
            i = int(S[:, j].argmax())
            p = float(S[i, j])
            if c not in mejor or p > mejor[c]["puntaje"]:
                mejor[c] = {"concepto": c, "puntaje": round(p, 3), "expresion": self.exp[j], "pedazo": ps[i]}
        return sorted(mejor.values(), key=lambda x: -x["puntaje"])

    def candidatos(self, fila, k=5, solo_tienda=True, contexto=""):
        """La fila entera contra la base: medido el 28-nov sobre los tramos que el codigo no da por claros, el bueno
        queda entre los 5 en 84 de 90 del examen, contra 83 buscando por pedazos sueltos, que dejan que una palabra
        exacta, "tablita", tape el sentido de la frase.

        contexto: el rubro que el cliente dijo en otra fila, "pendrive". "Grande" solo no dice si es capacidad o
        pulgadas: se busca tambien "pendrive grande", y se alternan los dos rankings, primero el del contexto.
        Negacion: si la fila niega, cada orden con opuesto suma su opuesto, "no sean carisimos" es el mas barato."""
        sola = self._rank([N.forma(fila)], solo_tienda)
        # en la busqueda con contexto no entran rubros: el rubro ya lo dijo la otra fila, aca solo desambigua
        con = [x for x in self._rank([N.forma(contexto + " " + fila)], solo_tienda)
               if not x["concepto"].startswith("rubro:")] if contexto else []
        listas = [con, sola] if contexto else [sola]
        out, vistos = [], set()
        for fila_i in range(max(len(x) for x in listas)):
            for lst in listas:
                if fila_i < len(lst) and lst[fila_i]["concepto"] not in vistos:
                    out.append(lst[fila_i])
                    vistos.add(lst[fila_i]["concepto"])
        if set(N.forma(fila).split()) & N.NIEGAN:
            neg = []
            for x in out:
                neg.append(x)
                o = N.OPUESTO.get(x["concepto"])
                if o and o not in vistos:
                    neg.append(dict(x, concepto=o, expresion="negado: " + x["expresion"]))
                    vistos.add(o)
            out = neg
        return out[:k]


if __name__ == "__main__":
    ix = Indice()
    for t in sys.argv[1:]:
        print(t)
        for c in ix.candidatos(t):
            print("   ", c)
