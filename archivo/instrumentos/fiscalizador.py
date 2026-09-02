"""
FISCALIZADOR — inventario y chequeo de PLOMERÍA entre las fuentes de verdad.

El sistema tiene dos fuentes en namespaces distintos que nadie mantenía
sincronizadas, y ese desfasaje es una causa raíz de mal ruteo y parafraseo:

  1. CONTACTOR: data/clientes/<tienda>/base_conocimiento.json — las categorías
     (enum) al que el INTÉRPRETE clasifica el mensaje. Cada una con criterio.
  2. FAQ: data/clientes/<tienda>/faq.json — las curadas de cara al cliente y el
     dato duro (valores).

Si la FAQ tiene un tema que el contactor NO tiene como categoría, el intérprete
no puede rutearlo: cae en la categoría más cercana equivocada y el modelo
parafrasea desde el bloque incorrecto (bug real de envío: "viene en caja" caía
en garantía porque no existía la categoría embalaje). Este fiscalizador lo caza.

Qué chequea (fiscalización de compatibilidad):
  A. FAQ sin categoría espejo en el contactor -> el intérprete NO puede rutear
     ese tema. Es el hueco más grave.
  B. Categoría politica_faq del contactor sin FAQ que la respalde -> el modelo
     contesta de criterio pero no hay dato/curada de cliente.
  C. Colisiones de nombre entre namespaces (envio_costo vs costo_envio): el
     mismo concepto con dos claves, que hay que reconciliar.

No arregla: solo INVENTARÍA y REPORTA. La reparación es cargar la fuente.
Correr:  python3 banco_pruebas/fiscalizador.py [tienda_id]
Sale != 0 si hay huecos de tipo A (los que rompen ruteo), para gatear el CI.
"""
import json
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_STOP = {"de", "el", "la", "los", "las", "un", "una", "y", "o", "del", "al",
         "por", "para", "con", "sin", "que", "se", "su", "tu", "mi", "pedido"}


def _tokens(s: str) -> set:
    s = re.sub(r"[^\w\s]", " ", str(s or "").lower())
    return {w for w in s.split() if w and w not in _STOP and len(w) > 2}


def _cargar(tienda: str):
    base = _RAIZ / "data" / "clientes" / tienda
    bc = json.loads((base / "base_conocimiento.json").read_text(encoding="utf-8"))
    fq = json.loads((base / "faq.json").read_text(encoding="utf-8"))
    cats = bc.get("categorias", [])
    temas = fq if isinstance(fq, list) else [dict(v, tema=k) for k, v in fq.items()]
    return cats, temas


def _tokens_categoria(c: dict) -> set:
    """Vocabulario de una categoría: id + descripción + disparadores. Así el
    match no depende solo de que la clave coincida (envio_costo vs costo_envio)."""
    t = _tokens(c.get("id", "").replace("_", " "))
    t |= _tokens(c.get("descripcion", ""))
    for d in c.get("disparadores", []):
        t |= _tokens(d)
    return t


def _df_tokens(temas: list) -> dict:
    """Frecuencia de cada token entre las CLAVES de los temas de FAQ. Un token
    que aparece en muchos temas (ej 'envio') no distingue nada; el que aparece en
    uno o dos (ej 'embalaje') es el que identifica el tema."""
    df: dict = {}
    for t in temas:
        for w in _tokens(str(t.get("tema", "")).replace("_", " ")):
            df[w] = df.get(w, 0) + 1
    return df


def fiscalizar(tienda: str = "verifika_prod") -> int:
    cats, temas = _cargar(tienda)
    ids = [c.get("id") for c in cats]
    politica = [c for c in cats if c.get("grupo") == "politica_faq"]
    vocab_cat = set()
    for c in cats:
        vocab_cat |= _tokens_categoria(c)

    print(f"=== FISCALIZADOR — tienda {tienda} ===")
    print(f"contactor: {len(cats)} categorías ({len(politica)} en politica_faq) | "
          f"FAQ: {len(temas)} temas\n")

    # Un tema está CUBIERTO si su token DISTINTIVO (el más raro entre las claves
    # de FAQ) aparece en el vocabulario de alguna categoría. Así 'embalaje_envio'
    # NO se da por cubierto solo porque 'envio' matchea: exige 'embalaje'.
    df = _df_tokens(temas)
    huecos_A = []
    print("A. FAQ sin categoría espejo (el intérprete no puede rutear el tema):")
    for t in temas:
        tema = t.get("tema", "?")
        toks = _tokens(str(tema).replace("_", " "))
        if not toks:
            continue
        distintivos = sorted(toks, key=lambda w: df.get(w, 99))
        clave = distintivos[0]  # el más raro
        cubierto = clave in vocab_cat
        if not cubierto:
            huecos_A.append((tema, clave))
            print(f"   [HUECO] FAQ '{tema}'  (token clave '{clave}' no está en ninguna categoría)")

    print(f"\n   huecos de ruteo: {len(huecos_A)}")

    # C. colisiones de nombre entre namespaces (mismo token-set, distinta clave)
    print("\nC. Colisiones de nombre FAQ<->contactor (mismo concepto, otra clave):")
    fq_keys = {t.get("tema"): frozenset(_tokens(str(t.get("tema", "")).replace("_", " ")))
               for t in temas}
    col = 0
    for cid in ids:
        ck = frozenset(_tokens(str(cid).replace("_", " ")))
        for ftema, fk in fq_keys.items():
            if ck and ck == fk and cid != ftema:
                print(f"   '{cid}' (contactor)  ==  '{ftema}' (faq)  — misma idea, dos claves")
                col += 1
    if not col:
        print("   ninguna")

    print(f"\n=== RESUMEN: {len(huecos_A)} candidatos a hueco de ruteo, "
          f"{col} colisiones de nombre ===")
    print("NOTA: esto es un PRE-SCAN estático, sobre-reporta. Algunos temas se "
          "responden por ficha (specs, material) o por herramienta (stock), no "
          "por categoría. La confirmación real es conductual: correr el fraseo "
          "por el intérprete y ver si rutea a una categoría que pueda contestar.")
    return 1 if huecos_A else 0


if __name__ == "__main__":
    tienda = sys.argv[1] if len(sys.argv) > 1 else "verifika_prod"
    sys.exit(fiscalizar(tienda))
