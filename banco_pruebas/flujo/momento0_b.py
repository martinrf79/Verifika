"""LA LLAMADA 0 SOBRE OTRAS 70, CON JERGA MAS DURA: EL MODELO MAS LOS EMBEDDINGS (15-nov-2026).

Orden de Martin del 15-nov. Los 70 mensajes de `nuevas70b.py`, con su vara escrita antes.
  la llamada 0  el prompt del engranaje 0 tal cual, con Gemini, el modelo de produccion, por la clave gratis. Si la gratis
                se traba, Martin autorizo la paga.
                v1, dos acciones: separar y traducir, fragmento y busqueda. Es la llamada 0 que pidio Martin el 15-nov.
                v2, siete: lo mismo mas cantidad, destino, plata, orden y condiciones. El destino del asado salio de aca.
  embeddings    con la paga: lo que tradujo el modelo en cada linea, y su fragmento, contra los rubros de la tienda con sus
                alias, el mismo documento de `nexo_rubro`.

LA VARA, por mensaje y por rubro, como `momento0_suma.py`:
  trae   el rubro esperado esta entre los que da la busqueda para ese mensaje.
  sobra  un rubro que da la busqueda y el mensaje no pide; lo que la tienda no vende suma aca.
Se cuenta para lo que tradujo el modelo con el primer rubro, con los tres primeros, para los fragmentos, y para los dos.
EL DESTINO, escrito antes de correr, en DESTINOS: los lugares que el cliente nombro para enviar. En la v1 los saca el
codigo, `normal.lugares` sobre los fragmentos del modelo; en la v2, el mismo codigo sobre el campo destino.
  acierta  un lugar esperado que el codigo encuentra.
  inventa  un lugar que el codigo encuentra y el cliente no nombro para enviar.

    python3 banco_pruebas/flujo/momento0_b.py --correr v1     # la llamada 0 con la gratis
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/flujo/momento0_b.py --embeddings
    python3 banco_pruebas/flujo/momento0_b.py [v1|v2] [--ver] # califica, sin gasto
"""
import collections
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO  # noqa: E402

import engranaje0 as E  # noqa: E402
import nexo_rubro as NR  # noqa: E402
from nuevas70b import CASOS  # noqa: E402

SALIDA = os.path.join(GRABADO, "momento0_b_corridas.jsonl")
PUNTAJES = os.path.join(GRABADO, "momento0_b_puntajes.json")
DESTINOS = {"B01": ["Lomas de Zamora"], "B07": ["Merlo"], "B10": ["Quilmes"], "B14": ["Mar del Plata"], "B47": ["Tigre"],
            "B55": ["Jujuy", "Formosa", "Rio Gallegos"], "B56": ["Lanus"], "B57": ["Cordoba"], "B58": ["Rosario"],
            "B60": ["Salta", "Tucuman"], "B61": ["La Plata"], "B64": ["Ushuaia"]}


def correr(v):
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
    cli = OpenAI(api_key=os.environ["GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"].split()[0],
                 base_url=s.GEMINI_BASE_URL)
    hechas = set()
    if os.path.exists(SALIDA):
        hechas = {r["id"] for r in map(json.loads, open(SALIDA)) if r.get("salida") is not None and r["v"] == v}
    falta = [c for c in CASOS if c[0] not in hechas]
    print(f"[gemini {v}, {s.GEMINI_MODEL}, clave {'paga' if paga else 'gratis'}: {len(falta)} por correr]", flush=True)
    for cid, texto, _ in falta:
        fila = {"modelo": "gemini", "v": v, "id": cid, "clave": "paga" if paga else "gratis"}
        for intento in range(5):
            try:
                t0 = time.time()
                r = cli.chat.completions.create(
                    model=s.GEMINI_MODEL, reasoning_effort="low",
                    messages=[{"role": "system", "content": E.PROMPT[v]},
                              {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}"}],
                    response_format={"type": "json_schema", "json_schema": {"name": "lineas", "strict": True,
                                                                            "schema": E.esquema(v)}})
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


def salidas(v="v2"):
    out = {}
    if os.path.exists(SALIDA):
        for r in map(json.loads, open(SALIDA)):
            if r.get("salida") is not None and r["v"] == v:
                out[r["id"]] = r["salida"]
    return out


def lineas(sal):
    return [l for l in sal.get("lineas") or [] if str(l.get("busqueda") or "").strip()]


def embeddings():
    import embeddings as EMB
    _, alias, rubros, _ = NR.fuente()
    cache = EMB.cargar()
    qs = sorted({str(l.get(k) or "") for v in ("v1", "v2") for s in salidas(v).values() for l in lineas(s)
                 for k in ("busqueda", "fragmento")} - {""})
    dr = EMB.pedir([NR.doc_rubro(r, alias) for r in rubros], EMB.DOCUMENTO, cache)
    vq = EMB.pedir(qs, EMB.CONSULTA, cache)
    out = {q: [round(sum(a * b for a, b in zip(x, d)), 4) for d in dr] for q, x in zip(qs, vq)}
    json.dump({"rubros": rubros, "consultas": out}, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(qs)} consultas, {sum(len(q) for q in qs)} caracteres")


def destinos(sal, v):
    """Los lugares que encuentra el codigo: en la v1 sobre los fragmentos, en la v2 sobre el campo destino."""
    from app.core.flujo.normal import lugares
    campo = "fragmento" if v == "v1" else "destino"
    return [f for l in sal.get("lineas") or [] for f, _ in lugares(str(l.get(campo) or ""))]


def calificar(v="v2", ver=False):
    NR.instalar()
    p = json.load(open(PUNTAJES, encoding="utf-8"))

    def rank(q):
        return [r for _, r in sorted(zip(p["consultas"][q], p["rubros"]), reverse=True)] if q else []

    sal = salidas(v)
    c = collections.Counter()
    falla, no_vende, sin_salida, dest = [], [], [], []
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
        hallados = {E.n(x) for x in destinos(sal[cid], v)}
        esperados = {E.n(x) for x in DESTINOS.get(cid, [])}
        bien = {e for e in esperados if any(e in h or h in e for h in hallados)}
        inventa = {h for h in hallados if not any(e in h or h in e for e in esperados)}
        c["destinos"] += len(esperados)
        c["destino acierta"] += len(bien)
        c["destino inventa"] += len(inventa)
        if esperados - bien or inventa:
            dest.append((cid, sorted(esperados - bien), sorted(inventa)))
        for raices, r in cosas:
            if r == "ninguno":
                suyas = [l for l in ls if any(E.n(x) in E.n(l.get("fragmento")) + " " + E.n(l.get("busqueda"))
                                              for x in raices)]
                no_vende.append((cid, raices[0], [(l["busqueda"], rank(l["busqueda"])[0]) for l in suyas]))
    print(f"\nLA LLAMADA 0 SOBRE OTRAS 70, JERGA DURA · gemini {v} · {len(sal)} mensajes con salida"
          + (f", sin salida {sin_salida}" if sin_salida else ""))
    print(f"  de {c['pide']} rubros pedidos")
    for nombre in ("tradujo, primero", "tradujo, tres", "fragmentos", "tradujo y fragmentos"):
        print(f"    {nombre:22} trae {c[nombre + ' trae']:>3} · sobran {c[nombre + ' sobra']:>3}")
    print(f"\n  destinos, de {c['destinos']} que nombro el cliente: el codigo acierta {c['destino acierta']} · inventa "
          f"{c['destino inventa']}")
    for cid, falta, inv in dest:
        print(f"    {cid} no encuentra {falta} · inventa {inv}")
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
    v = "v1" if "v1" in sys.argv else "v2"
    if "--correr" in sys.argv:
        correr(v)
    elif "--embeddings" in sys.argv:
        embeddings()
    else:
        calificar(v, "--ver" in sys.argv)
