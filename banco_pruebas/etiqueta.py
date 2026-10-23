"""LA ETIQUETA DESPUES DE LOS CANDIDATOS — el flujo de Martin del 23-oct, medido sobre las 48.

1. La primera traduccion: el modelo parte y nombra con los nombres de la tienda. Es la consigna unida de `actos.py`, y
   sus respuestas ya estan guardadas: no se vuelve a pagar.
2. El codigo busca por significado cada parte traducida, en la tienda —rubro, tema, producto— y en la charla —lo
   mostrado y los renglones del borrador—, y trae los candidatos con su parecido.
3. La segunda llamada etiqueta: con cada parte y sus candidatos a la vista, el modelo dice que quiere hacer el cliente
   con ella, de la misma lista de actos, o que la parte es un detalle de otra.

La vara es la de `actos.py`: los actos que pide el oro, sin faltar ni sobrar, con `actos.TAMBIEN`. Se compara contra
el acto de la primera traduccion sobre los mismos turnos, 34 de 48 con la regla del codigo.

    python3 banco_pruebas/etiqueta.py [--ver] [--codigo]              con la gratis
    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.10 python3 banco_pruebas/etiqueta.py ...
"""
import asyncio
import collections
import json
import os
import re
import sys
import time

VER, CODIGO = "--ver" in sys.argv, "--codigo" in sys.argv
sys.argv = [sys.argv[0]]
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import actos as A  # noqa: E402  — la vara, el entorno y la primera traduccion
import modos as MO  # noqa: E402  — la primera traduccion guardada
from banco_pruebas import libro_paga  # noqa: E402
from app.core import agente  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo import interprete  # noqa: E402

TID = A.P.TID
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.10"))
EMBEDDINGS = "gemini-embedding-001"
# Fuera del repo: son varios megas y se rearman solos.
VECTORES = os.path.expanduser("~/.cache/verifika/etiqueta_vectores.json")
DETALLE = "detalle"

# ══ LOS CANDIDATOS ═══════════════════════════════════════════════════════════

_VEC: dict = {}


def _cargar() -> None:
    if not _VEC and os.path.exists(VECTORES):
        _VEC.update(json.load(open(VECTORES, encoding="utf-8")))


def vectores(textos: list) -> list:
    """Cada texto como vector, guardado en disco: lo ya pedido no se vuelve a pedir."""
    from app.core.llm_reintento import _cliente
    _cargar()
    faltan = [t for t in dict.fromkeys(textos) if t not in _VEC]
    for i in range(0, len(faltan), 90):
        for intento in range(12):
            try:
                r = _cliente().embeddings.create(model=EMBEDDINGS, input=faltan[i:i + 90])
                break
            except Exception as e:  # noqa: BLE001 — la gratis corta a 100 por minuto: se espera y se sigue
                if "429" not in str(e) or intento == 11:
                    raise
                time.sleep(35)
        _VEC.update(zip(faltan[i:i + 90], (d.embedding for d in r.data)))
        os.makedirs(os.path.dirname(VECTORES), exist_ok=True)
        json.dump(_VEC, open(VECTORES, "w", encoding="utf-8"))
    return [_VEC[t] for t in textos]


def _coseno(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b)) / ((sum(x * x for x in a) ** .5) * (sum(y * y for y in b) ** .5))


_TIENDA: dict = {}


def tienda() -> dict:
    """La tienda como documentos: cada rubro con sus alias, cada tema con su respuesta y sus alias, cada modelo con su
    rubro y su descripcion. Se arma una vez, como se armaria al subir catalogo y FAQ."""
    if not _TIENDA:
        from app.storage import firestore_client as fc
        i, al = agente.indice(TID), agente._alias(TID)
        faq = fc.get_all_faq(tienda_id=TID) or {}
        fams = {}
        for p in K.productos(TID):
            f = str(p.get("nombre") or "").rsplit(" ", 1)[0] if p.get("color") else str(p.get("nombre") or "")
            fams.setdefault(f, f"{p.get('categoria')} {f}: {str(p.get('descripcion') or '')[:160]}")
        docs = {"rubro": {r: f"{r}: " + ", ".join((al.get("rubros") or {}).get(r, [])) for r in i["rubros"]},
                "tema": {t: f"{t.replace('_', ' ')}: {(faq.get(t) or {}).get('respuesta') or ''} "
                         + ", ".join((al.get("temas") or {}).get(t, [])) for t in i["temas"]},
                "producto": fams}
        for g, d in docs.items():
            _TIENDA[g] = dict(zip(d, vectores(list(d.values()))))
    return _TIENDA


def _charla(libreta: str) -> dict:
    """Lo mostrado y los renglones de la libreta, cada uno con su numero."""
    out = {}
    for linea in libreta.splitlines():
        m = re.match(r"\s+([ML]-\d+) (.+)", linea)
        if m:
            out[m.group(1)] = m.group(2)[:200]
    return out


def candidatos(partes: list, libreta: str) -> list:
    """Por cada parte, los dos mas parecidos de cada capa de la tienda y de la charla, con su parecido."""
    charla = _charla(libreta)
    vc = dict(zip(charla, vectores(list(charla.values())))) if charla else {}
    idx = tienda()
    out = []
    for q in vectores([str(p.get("texto") or "") for p in partes]):
        c = {g: sorted(((k, _coseno(v, q)) for k, v in d.items()), key=lambda x: -x[1])[:2] for g, d in idx.items()}
        c["charla"] = sorted(((k, _coseno(v, q)) for k, v in vc.items()), key=lambda x: -x[1])[:2]
        out.append(c)
    return out


def _dicho(partes: list, cands: list, charla: dict) -> str:
    r = []
    for i, (p, c) in enumerate(zip(partes, cands), 1):
        dest = str(p.get("destino") or "")
        r.append(f"{i}. {p.get('texto')}" + (f" · destino: {dest}" if K.n(dest) not in ("", "sin decir") else "")
                 + (f" · cantidad: {p['cantidad']}" if p.get("cantidad") else ""))
        if c["charla"]:
            r.append("   en la charla se parece a: " + "; ".join(f"{k} {charla[k][:90]} ({s:.2f})" for k, s in c["charla"]))
        r.append("   en la tienda: " + "; ".join(f"{g} {k} ({s:.2f})" for g in ("rubro", "tema", "producto")
                                                   for k, s in c[g]))
    return "\n".join(r)


# ══ LA SEGUNDA LLAMADA ═══════════════════════════════════════════════════════

CONSIGNA = """Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente.
Otro paso ya tradujo el ULTIMO MENSAJE del cliente en PARTES. El programa busco cada parte en la tienda y en la charla
y trae los candidatos con su parecido, de 0 a 1. Los candidatos son pistas: pueden estar mal.
Para cada parte, en su orden, deci que quiere hacer el cliente con ella:
- "acto": uno de la lista;
- "depende_de": el numero de la parte de la que depende, 0 si no depende de nada;
- "detalle_de": si la parte no pide nada por si misma y es un detalle de otra parte —a donde va, para quien, cuanto
  quiere gastar en eso—, el numero de esa parte, y su acto es "detalle". Si no, 0.
Si la parte habla de algo que ya esta en el BORRADOR de la libreta —un L-n—, decidir algo sobre eso es cambiar, no
llevar ni mirar. Lo que pregunta de un producto o una clase de producto de la tienda no es saber general.
ACTOS:
{actos}{ejemplos}"""

FORMATO = {"type": "json_schema", "json_schema": {"name": "etiqueta", "schema": {
    "type": "object", "required": ["partes"], "properties": {"partes": {"type": "array", "items": {
        "type": "object", "required": ["n", "acto", "depende_de", "detalle_de"], "properties": {
            "n": {"type": "integer"}, "acto": {"type": "string", "enum": list(A.ACTOS) + [DETALLE]},
            "depende_de": {"type": "integer"}, "detalle_de": {"type": "integer"}}}}}}}}


def consigna() -> str:
    ej = "\nEJEMPLOS, de a pares que se parecen y son otro acto:\n" + "\n".join(
        f'- "{t}" -> {a}' + (f" ({c})" if c else "") for t, a, c in A.EJEMPLOS)
    return CONSIGNA.format(actos="\n".join(f"- {a}: {d}" for a, d in A.ACTOS.items()), ejemplos=ej)


async def etiquetar(tu: dict, partes: list) -> tuple:
    estado, historial = A.P.estado_de(tu["mem"])
    lib = interprete.libreta(estado, historial, TID)
    cands = candidatos(partes, lib)
    dicho = _dicho(partes, cands, _charla(lib))
    msgs = [{"role": "system", "content": consigna()},
            {"role": "user", "content": f"{lib}\nULTIMO MENSAJE: {A.limpio(tu['msg'])}\n\nPARTES:\n{dicho}"}]
    r = interprete._json(await interprete._pedir(msgs, "etiqueta", FORMATO))
    return [p for p in r.get("partes") or [] if isinstance(p, dict)], dicho


def main() -> None:
    desde = libro_paga.gastado(libro_paga._hoy())
    cuenta = collections.Counter()
    for ch in A.CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                print(f"TOPE de la corrida: {TOPE} dolares")
                break
            r = MO.guardada(tu)
            if r is None:
                cuenta["sin traduccion guardada"] += 1
                continue
            partes = [p for p in r.get("partes") or [] if isinstance(p, dict)]
            oro = [x for x in tu["oro"] if not x.get("opt")]
            quiere = {A.DEL_ORO[x["tipo"]] for x in oro}
            tambien = A.TAMBIEN.get((ch["id"], i), [])
            primera = A.definir([dict(p) for p in partes], tu["mem"]) if CODIGO else partes
            antes = {p.get("acto") for p in primera}
            et, dicho = asyncio.run(etiquetar(tu, partes))
            nuevas = [{**p, "acto": e.get("acto")} for p, e in zip(partes, et)]
            if CODIGO:
                nuevas = A.definir(nuevas, tu["mem"])
            puso = {p["acto"] for p in nuevas} - {DETALLE}
            b_antes, b_desp = antes == quiere or antes in tambien, puso == quiere or puso in tambien
            cuenta["antes"] += b_antes
            cuenta["despues"] += b_desp
            cuenta["arregla"] += b_desp and not b_antes
            cuenta["rompe"] += b_antes and not b_desp
            cuenta["turnos"] += 1
            if VER and (b_antes != b_desp or not b_desp):
                marca = "ARREGLA" if b_desp else ("ROMPE" if b_antes else "sigue mal")
                print(f"--- {ch['id']} t{i} {marca}: {A.limpio(tu['msg'])[:150]}")
                print(f"    quiere {sorted(quiere)} · primera {sorted(antes)} · etiqueta {sorted(puso)}")
                for p, e in zip(partes, et):
                    print(f"      {p.get('acto'):14} -> {e.get('acto'):14}"
                          + (f" de {e['detalle_de']}" if e.get("detalle_de") else "") + f" {p.get('texto')}")
    print(f"\nLA ETIQUETA DESPUES DE LOS CANDIDATOS{', con la regla del codigo' if CODIGO else ''}, "
          f"{cuenta['turnos']} turnos de 48")
    print(f"  el acto de la primera traduccion: BIEN {cuenta['antes']}")
    print(f"  la etiqueta con los candidatos:   BIEN {cuenta['despues']} · arregla {cuenta['arregla']}"
          f" · rompe {cuenta['rompe']}")
    print(f"Gasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    main()
