"""EMBEDDINGS LIBRES EN EL MOMENTO CERO: LA TRADUCCION CONTRA LA TAXONOMIA DE SHOPIFY, SIN LA TIENDA (14-nov-2026).

Orden de Martin del 14-nov, prueba simple. Cada producto que el engranaje 0 v2 separo en los 70 mensajes nuevos, con lo
ya grabado de Gemini, Haiku y DeepSeek, se busca contra la taxonomia de productos de Shopify en castellano, de licencia
abierta: unas catorce mil categorias de cualquier comercio. No entra la tienda: es la traduccion libre de los embeddings,
paralela a la del modelo.

  Se busca dos veces: con la busqueda que escribio el modelo y con el fragmento crudo del cliente.
  Cada categoria se indexa con su hoja y su padre, "Dispositivos de entrada > Ratones y trackballs".
  gemini-embedding-001, 768 numeros, tarea de busqueda, con la clave gratis. Se guardan las cinco primeras.

LA VARA, escrita antes de la primera corrida y sin tocar despues: por cada concepto, las categorias de Shopify que son
correctas, elegidas leyendo la taxonomia. Vale esa categoria o cualquiera que cuelgue de ella. Los productos que la tienda
no vende llevan su categoria real: se mide si la traduccion libre los entiende, no si la tienda los vende.

    python3 banco_pruebas/momento0_shopify.py --correr     convierte y busca, con la clave gratis
    python3 banco_pruebas/momento0_shopify.py              el informe, sin llamar a nada
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI), AQUI]
ARGS = sys.argv[1:]
SALIDA = os.path.join(AQUI, "momento0_shopify.json")
CACHE = os.environ.get("CACHE_SHOPIFY", "/tmp/claude-0/-home-user-Verifika/73b1fa5d-8c2a-5c31-98dc-3d79da7273e1/scratchpad/tax")
URL_TAX = "https://raw.githubusercontent.com/Shopify/product-taxonomy/main/dist/es/categories.txt"
DIM = 768

# ══ LA VARA ═══════════════════════════════════════════════════════════════════
VARA = {
    "auriculares": ["el-2-2-7"],
    "mouse": ["el-7-9-12-11", "el-7-9-12-15"],
    "teclado": ["el-7-9-12-8", "el-7-9-12-15", "el-7-9-12-17"],
    "monitor": ["el-17-1"],
    "notebook": ["el-6-6", "el-6-11-2"],
    "memoria ram": ["el-7-12-3"],
    "ssd": ["el-7-9-14-9"],
    "almacenamiento externo": ["el-7-9-14", "el-7-12-2"],
    "parlante": ["el-2-2-10"],
    "webcam": ["co-2-8"],
    "impresora": ["el-13-4"],
    "silla gamer": ["fr-7-7", "fr-12-2"],
    "router": ["el-12-1", "el-12-10-3"],
    "cargador": ["el-7-15-5"],
    "microfono": ["el-2-2-8"],
    "placa de video": ["el-7-9-10-5"],
    "procesador": ["el-7-9-4"],
    "motherboard": ["el-3-6-2-3"],
    "fuente": ["el-7-9-3"],
    "gabinete": ["el-7-9-5", "el-7-9-8"],
    "cooler": ["el-7-9-7"],
    "tablet": ["el-6-8"],
    # lo que la tienda no vende, con su categoria real
    "mochila": ["lb-1", "aa-5-4-17", "aa-5-4-23"],
    "fundas": ["el-7-8-4-3", "el-7-8-2"],
    "brazo articulado": ["el-2-1-5"],
    "cartuchos": ["el-13-3-1"],
    "iphone": ["el-4-8-5"],
    "zapatillas": ["aa-8-8"],
    "play 5": ["el-19"],
}
# El concepto de los productos que la tienda no vende, por caso.
FUERA = {"M03": "mochila", "M10": "fundas", "M11": "brazo articulado", "M16": "cartuchos", "F01": "iphone",
         "F02": "zapatillas", "F11": "play 5"}


def bien(gid, concepto):
    return any(gid == g or gid.startswith(g + "-") for g in VARA[concepto])


# ══ LA TAXONOMIA ══════════════════════════════════════════════════════════════
def taxonomia():
    f = os.path.join(CACHE, "categories.txt")
    if not os.path.exists(f):
        os.makedirs(CACHE, exist_ok=True)
        urllib.request.urlretrieve(URL_TAX, f)
    out = []
    for linea in open(f, encoding="utf-8"):
        if linea.startswith("gid://"):
            gid, camino = linea.split(":", 2)[1].split("/")[-1].strip(), linea.split(" : ", 1)[1].strip()
            out.append((gid, camino))
    return out


def texto(camino):
    return " > ".join(camino.split(" > ")[-2:])


# ══ LOS EMBEDDINGS ════════════════════════════════════════════════════════════
def emb(textos, tarea):
    """Con la gratis; con la paga si el comando lleva MARTIN_AUTORIZO_LA_PAGA, con el tope diario y anotada en el libro
    a 0,15 dolares el millon de tokens, contando cuatro letras por token."""
    paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
    clave = os.environ["GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"].strip()
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
    out = []
    for i in range(0, len(textos), 100):
        lote = textos[i:i + 100]
        if paga:
            from banco_pruebas import libro_paga as LP
            LP.puede()
            tok = sum(len(t) for t in lote) // 4
            with open(LP.LIBRO, "a", encoding="utf-8") as f:
                f.write(json.dumps({"dia": LP._hoy(), "modelo": "gemini-embedding-001", "entrada": tok, "salida": 0,
                                    "dolares": round(tok * 0.15e-6, 5), "proceso": os.getpid()}) + "\n")
        body = json.dumps({"requests": [{"model": "models/gemini-embedding-001", "content": {"parts": [{"text": t}]},
                                         "taskType": tarea, "outputDimensionality": DIM} for t in lote]}).encode()
        for intento in range(8):
            try:
                req = urllib.request.Request(url, data=body, headers={"x-goog-api-key": clave,
                                                                      "Content-Type": "application/json"})
                out += [x["values"] for x in json.load(urllib.request.urlopen(req, timeout=120))["embeddings"]]
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or intento == 7:
                    raise
                time.sleep(20 * (intento + 1))
        if i and i % 2000 == 0:
            print(f"  {i} de {len(textos)}", flush=True)
    m = np.array(out, dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def pares():
    """(modelo, caso, i, concepto esperado, busqueda, fragmento) de lo grabado por la v2."""
    import engranaje0 as E
    esperado = E._esperado()
    res = json.load(open(os.path.join(AQUI, "engranaje0_embeddings.json"), encoding="utf-8"))
    out = []
    for r in res:
        concepto = FUERA[r["id"]] if r["esperado"] == "ninguno" else esperado[(r["id"], r["i"])]
        out.append((r["modelo"], r["id"], r["i"], concepto, r["texto_busqueda"], r["texto_fragmento"]))
    return out


def correr():
    tax = taxonomia()
    f_tax = os.path.join(CACHE, f"shopify_{DIM}.npy")
    if os.path.exists(f_tax):
        docs = np.load(f_tax)
    else:
        t0 = time.time()
        docs = emb([texto(c) for _, c in tax], "RETRIEVAL_DOCUMENT")
        np.save(f_tax, docs)
        print(f"taxonomia: {len(tax)} categorias en {time.time() - t0:.0f} s")
    ps = pares()
    qs = sorted({q for p in ps for q in p[4:6] if q})
    vq = dict(zip(qs, emb(qs, "RETRIEVAL_QUERY")))
    filas = []
    for m, cid, i, concepto, busq, frag in ps:
        fila = {"modelo": m, "id": cid, "i": i, "concepto": concepto, "texto_busqueda": busq, "texto_fragmento": frag}
        for nombre, q in (("busqueda", busq), ("fragmento", frag)):
            if not q:
                fila[nombre] = None
                continue
            pts = docs @ vq[q]
            top = np.argsort(-pts)[:5]
            fila[nombre] = [[tax[k][0], tax[k][1], round(float(pts[k]), 3)] for k in top]
        filas.append(fila)
    json.dump(filas, open(SALIDA, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(qs)} consultas, {len(filas)} productos")


# ══ EL INFORME ════════════════════════════════════════════════════════════════
def informe():
    filas = json.load(open(SALIDA, encoding="utf-8"))
    print("\nEMBEDDINGS LIBRES CONTRA SHOPIFY, SIN LA TIENDA · vara escrita antes")
    for grupo, cond in (("lo que la tienda vende", lambda r: r["concepto"] not in FUERA.values()),
                        ("lo que la tienda no vende", lambda r: r["concepto"] in FUERA.values())):
        print(f"\n  {grupo}")
        for campo in ("busqueda", "fragmento"):
            for m in ("gemini", "haiku", "deepseek"):
                xs = [r for r in filas if cond(r) and r["modelo"] == m and r[campo]]
                p1 = sum(bien(r[campo][0][0], r["concepto"]) for r in xs)
                p5 = sum(any(bien(c[0], r["concepto"]) for c in r[campo]) for r in xs)
                print(f"    {campo:10} {m:9} primera {p1:>3}, entre cinco {p5:>3}, de {len(xs)}")
    # Las dos juntas: la busqueda del modelo y el fragmento del cliente.
    print("\n  las dos consultas juntas, primera categoria")
    for m in ("gemini", "haiku", "deepseek"):
        xs = [r for r in filas if r["modelo"] == m and r["busqueda"] and r["fragmento"]]
        igual = [r for r in xs if r["busqueda"][0][0] == r["fragmento"][0][0]]
        dist = [r for r in xs if r["busqueda"][0][0] != r["fragmento"][0][0]]
        ib = sum(bien(r["busqueda"][0][0], r["concepto"]) for r in igual)
        db = sum(bien(r["busqueda"][0][0], r["concepto"]) for r in dist)
        dfr = sum(bien(r["fragmento"][0][0], r["concepto"]) for r in dist)
        print(f"    {m:9} coinciden {len(igual):>3}, bien {ib:>3} · no coinciden {len(dist):>3}: acierta la busqueda "
              f"{db}, el fragmento {dfr}")
    print("\n  los que fallan con la busqueda del modelo, primera categoria:")
    for r in filas:
        b = r["busqueda"]
        if b and not bien(b[0][0], r["concepto"]):
            f = r["fragmento"]
            print(f"    {r['modelo']:8} {r['id']} esperado {r['concepto']}\n"
                  f"      busqueda '{r['texto_busqueda']}' -> {b[0][1].split(' > ')[-1]} ({b[0][2]})"
                  f"{'  · bien entre cinco' if any(bien(c[0], r['concepto']) for c in b) else ''}\n"
                  f"      fragmento '{r['texto_fragmento']}' -> {f[0][1].split(' > ')[-1] if f else None}"
                  f"{'  · bien' if f and bien(f[0][0], r['concepto']) else ''}")


def solo_embeddings():
    """El mensaje del cliente entero, tal cual, contra la taxonomia: sin nada del modelo. Por cada producto del mensaje,
    si su categoria esta entre las cinco primeras."""
    import engranaje0 as E
    from nuevas70 import CASOS
    tax = taxonomia()
    docs = np.load(os.path.join(CACHE, f"shopify_{DIM}.npy"))
    esperado = E._esperado()
    msgs = [m for _, m, _ in CASOS]
    vq = emb(msgs, "RETRIEVAL_QUERY")
    filas, total, p1, p5 = [], 0, 0, 0
    for (cid, m, cosas), v in zip(CASOS, vq):
        pts = docs @ v
        top = [[tax[k][0], tax[k][1], round(float(pts[k]), 3)] for k in np.argsort(-pts)[:5]]
        conceptos = [FUERA[cid] if esperado[(cid, i)] == "ninguno" else esperado[(cid, i)]
                     for i in range(len(cosas)) if (cid, i) in esperado]
        res = {c: (bien(top[0][0], c), any(bien(t[0], c) for t in top)) for c in conceptos}
        total, p1, p5 = total + len(res), p1 + sum(a for a, _ in res.values()), p5 + sum(b for _, b in res.values())
        filas.append({"id": cid, "mensaje": m, "conceptos": conceptos, "top": top})
        if conceptos:
            print(f"{cid} {m[:90]}\n   espera {conceptos} -> " + " | ".join(t[1].split(' > ')[-1] for t in top)
                  + "   " + " ".join(f"{c}:{'1' if a else '5' if b else 'NO'}" for c, (a, b) in res.items()))
    json.dump(filas, open(os.path.join(AQUI, "momento0_shopify_mensaje.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print(f"\nEL MENSAJE ENTERO, SOLO EMBEDDINGS: {total} productos, primera {p1}, entre cinco {p5}")


if __name__ == "__main__":
    if "--mensaje" in ARGS:
        solo_embeddings()
        sys.exit()
    if "--correr" in ARGS:
        correr()
    informe()
