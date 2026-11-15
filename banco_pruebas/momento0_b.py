"""LA LLAMADA 0 SOBRE OTRAS 70, CON JERGA MAS DURA: EL MODELO MAS LOS EMBEDDINGS (15-nov-2026).

Orden de Martin del 15-nov. Los 70 mensajes de `nuevas70b.py`, con su vara escrita antes.
  la llamada 0  el prompt v2 del engranaje 0 tal cual, `engranaje0.PROMPT["v2"]` y su esquema, con Gemini, el modelo de
                produccion, por la clave gratis. Si la gratis se traba, Martin autorizo la paga.
  embeddings    con la paga: lo que tradujo el modelo en cada linea, y su fragmento, contra los rubros de la tienda con sus
                alias, el mismo documento de `nexo_rubro`.

LA VARA, por mensaje y por rubro, como `momento0_suma.py`:
  trae   el rubro esperado esta entre los que da la busqueda para ese mensaje.
  sobra  un rubro que da la busqueda y el mensaje no pide; lo que la tienda no vende suma aca.
Se cuenta para lo que tradujo el modelo con el primer rubro, con los tres primeros, para los fragmentos, y para los dos.

    python3 banco_pruebas/momento0_b.py --correr        # la llamada 0 con la gratis
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/momento0_b.py --embeddings
    python3 banco_pruebas/momento0_b.py [--ver]         # califica, sin gasto
"""
import collections
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI), AQUI]

import engranaje0 as E  # noqa: E402
import nexo_rubro as NR  # noqa: E402
from nuevas70b import CASOS  # noqa: E402

SALIDA = os.path.join(AQUI, "momento0_b_corridas.jsonl")
PUNTAJES = os.path.join(AQUI, "momento0_b_puntajes.json")


def correr():
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"].split()[0],
                 base_url=s.GEMINI_BASE_URL)
    hechas = set()
    if os.path.exists(SALIDA):
        hechas = {r["id"] for r in map(json.loads, open(SALIDA)) if r.get("salida") is not None}
    falta = [c for c in CASOS if c[0] not in hechas]
    print(f"[gemini v2, {s.GEMINI_MODEL}, clave {'paga' if paga else 'gratis'}: {len(falta)} por correr]", flush=True)
    for cid, texto, _ in falta:
        fila = {"modelo": "gemini", "v": "v2", "id": cid, "clave": "paga" if paga else "gratis"}
        for intento in range(5):
            try:
                t0 = time.time()
                r = cli.chat.completions.create(
                    model=s.GEMINI_MODEL, reasoning_effort="low",
                    messages=[{"role": "system", "content": E.PROMPT["v2"]},
                              {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}"}],
                    response_format={"type": "json_schema", "json_schema": {"name": "lineas", "strict": True,
                                                                            "schema": E.esquema("v2")}})
                crudo = r.choices[0].message.content or ""
                t = re.sub(r"^```(?:json)?|```$", "", crudo.strip(), flags=re.M).strip()
                try:
                    salida = json.loads(t[t.find("{"):t.rfind("}") + 1])
                except Exception:  # noqa: BLE001
                    salida = None
                fila["segundos"] = round(time.time() - t0, 2)
                if E.valido(salida):
                    fila.update({"salida": salida, "reintentos": intento})
                    break
                fila["invalida"] = crudo[:500]
            except Exception as ex:  # noqa: BLE001
                fila["error"] = f"{type(ex).__name__}: {str(ex)[:200]}"
                print(f"  {cid} intento {intento}: {fila['error']}", flush=True)
                time.sleep(20 * (intento + 1))
        with open(SALIDA, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        time.sleep(4)


def salidas():
    out = {}
    if os.path.exists(SALIDA):
        for r in map(json.loads, open(SALIDA)):
            if r.get("salida") is not None:
                out[r["id"]] = r["salida"]
    return out


def lineas(sal):
    return [l for l in sal.get("lineas") or [] if str(l.get("busqueda") or "").strip()]


def embeddings():
    if not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
        raise SystemExit("los embeddings van con la paga: falta MARTIN_AUTORIZO_LA_PAGA=<fecha>")
    import llamada1_modelos as L
    _, alias, rubros, _ = NR.fuente()
    cache = json.load(open(NR.CACHE)) if os.path.exists(NR.CACHE) else {}
    qs = sorted({str(l.get(k) or "") for s in salidas().values() for l in lineas(s) for k in ("busqueda", "fragmento")}
                - {""})
    clave = os.environ["GEMINI_API_KEY_PROD"].strip()
    dr = L._emb([NR.doc_rubro(r, alias) for r in rubros], "RETRIEVAL_DOCUMENT", clave, cache)
    vq = L._emb(qs, "RETRIEVAL_QUERY", clave, cache)
    json.dump(cache, open(NR.CACHE, "w"))
    out = {q: [round(sum(a * b for a, b in zip(x, d)), 4) for d in dr] for q, x in zip(qs, vq)}
    json.dump({"rubros": rubros, "consultas": out}, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(qs)} consultas, {sum(len(q) for q in qs)} caracteres")


def calificar(ver=False):
    p = json.load(open(PUNTAJES, encoding="utf-8"))

    def rank(q):
        return [r for _, r in sorted(zip(p["consultas"][q], p["rubros"]), reverse=True)] if q else []

    sal = salidas()
    c = collections.Counter()
    falla, no_vende, sin_salida = [], [], []
    for cid, texto, cosas in CASOS:
        if cid not in sal:
            sin_salida.append(cid)
            continue
        ls = lineas(sal[cid])
        pide = {r for _, r in cosas if r and r != "ninguno"}
        c["pide"] += len(pide)
        t1 = {rank(l["busqueda"])[0] for l in ls}
        t3 = {r for l in ls for r in rank(l["busqueda"])[:3]}
        f1 = {rank(l.get("fragmento"))[0] for l in ls if l.get("fragmento")}
        for nombre, da in (("tradujo, primero", t1), ("tradujo, tres", t3), ("fragmentos", f1),
                           ("tradujo y fragmentos", t1 | f1)):
            c[nombre + " trae"] += len(pide & da)
            c[nombre + " sobra"] += len(da - pide)
        if pide - t1:
            falla.append((cid, sorted(pide - t1), [(l["busqueda"], rank(l["busqueda"])[:3]) for l in ls],
                          sorted(pide - t3)))
        for raices, r in cosas:
            if r == "ninguno":
                suyas = [l for l in ls if any(E.n(x) in E.n(l.get("fragmento")) + " " + E.n(l.get("busqueda"))
                                              for x in raices)]
                no_vende.append((cid, raices[0], [(l["busqueda"], rank(l["busqueda"])[0]) for l in suyas]))
    print(f"\nLA LLAMADA 0 SOBRE OTRAS 70, JERGA DURA · gemini v2 · {len(sal)} mensajes con salida"
          + (f", sin salida {sin_salida}" if sin_salida else ""))
    print(f"  de {c['pide']} rubros pedidos")
    for nombre in ("tradujo, primero", "tradujo, tres", "fragmentos", "tradujo y fragmentos"):
        print(f"    {nombre:22} trae {c[nombre + ' trae']:>3} · sobran {c[nombre + ' sobra']:>3}")
    print("\n  donde lo que tradujo, con el primer rubro, no trae lo pedido:")
    for cid, falta, ls, falta3 in falla:
        print(f"    {cid} falta {falta}{' y con tres tambien ' + str(falta3) if falta3 else ', con tres aparece'}")
        if ver:
            for b, r3 in ls:
                print(f"        '{b}' -> {r3}")
    print("\n  lo que la tienda no vende, a que rubro va la linea del modelo:")
    for cid, nombre, ls in no_vende:
        print(f"    {cid} {nombre}: {ls or 'sin linea propia'}")


if __name__ == "__main__":
    if "--correr" in sys.argv:
        correr()
    elif "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar("--ver" in sys.argv)
