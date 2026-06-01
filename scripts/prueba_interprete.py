"""
PRUEBA DEL INTERPRETADOR (carril modelo, local, usa DeepSeek).

Corre el Interpretador REAL contra el set de preguntas reales con ruido
(data/preguntas_reales.jsonl). NO toca Firestore ni Cloud Run: el Interpretador
solo necesita DeepSeek y el mensaje. Mide como interpreta typos, ambiguedad,
indecision, multi intencion y los casos donde el cliente cambia de opinion.

Para cada pregunta imprime intencion, confianza, producto resuelto, candidatos,
estado y ofrecer_opciones, y evalua contra la expectativa si la pregunta la trae:
  - esp_intencion: la intencion esperada (ej saludo, decision_compra).
  - esp_pregunta: True si el sistema NO deberia estar seguro y deberia preguntar
    (confianza baja, o candidatos, o ofrecer_opciones). Caza el sobreconfianza.

Las preguntas sin expectativa salen como OBS (observacion): se miran a ojo.

Uso:
  winvenv\\Scripts\\python.exe scripts\\prueba_interprete.py            (todas)
  winvenv\\Scripts\\python.exe scripts\\prueba_interprete.py --limit 5   (las primeras 5)
"""
import os
import sys
import json
import asyncio
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Flag de embeddings: --embeddings activa la busqueda semantica. Se detecta
# antes de importar la app para cargar la clave de OpenAI y el provider a tiempo.
EMB = "--embeddings" in sys.argv


def _cargar_env(path, default_key=None):
    if not os.path.exists(path):
        return False
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
        elif default_key and line.startswith("sk-"):
            os.environ[default_key] = line
    return True


def cargar_secrets():
    if not _cargar_env(os.path.join(ROOT, ".secrets.env"), "DEEPSEEK_API_KEY"):
        raise SystemExit("Falta .secrets.env en la raiz del proyecto")
    if EMB:
        # Clave de OpenAI para los embeddings, sin imprimirla.
        if not _cargar_env(os.path.join(ROOT, ".secrets4.env")):
            raise SystemExit("Falta .secrets4.env con OPENAI_API_KEY para --embeddings")
        os.environ["EMBEDDINGS_PROVIDER"] = "openai"


cargar_secrets()
if not os.environ.get("DEEPSEEK_API_KEY", "").startswith("sk-"):
    raise SystemExit("No se encontro DEEPSEEK_API_KEY valida en .secrets.env")

# Silenciar el log INFO del interpretador para ver solo el resultado.
import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

sys.path.insert(0, ROOT)
import csv
from app.core.interpretador import interpretar_mensaje, UMBRAL_CONFIANZA_ALTA
from app.config import get_settings
import app.storage.firestore_client as FS

# Tienda a usar: --tienda <nombre>, default verifika_demo. Permite correr el
# mismo set de preguntas contra el catalogo chico o el de 2000 (verifika_2k).
TIENDA = "verifika_demo"
if "--tienda" in sys.argv:
    TIENDA = sys.argv[sys.argv.index("--tienda") + 1]

# Cargar el catalogo local y anclar el interprete a el (fuente de verdad), sin
# Firestore. Activa el flag de anclaje, que es lo que estamos probando.
_prods = []
with open(os.path.join(ROOT, f"data/clientes/{TIENDA}/productos.csv"),
          encoding="utf-8") as _f:
    for _row in csv.DictReader(_f):
        _p = {"id": _row["id"].strip(), "nombre": _row["nombre"].strip(),
              "categoria": _row["categoria"].strip().lower(),
              "precio_ars": int(float(_row["precio_ars"])),
              "stock": int(_row.get("stock", 0)),
              "descripcion": _row.get("descripcion", "")}
        for _k, _v in _row.items():
            if _k not in _p and _v and str(_v).strip():
                _p[_k] = str(_v).strip()
        _prods.append(_p)
FS.get_all_products = lambda tienda_id=None, force_refresh=False: _prods
NOMBRES = {p["nombre"] for p in _prods}
NOMBRE_CAT = {p["nombre"]: p["categoria"] for p in _prods}
get_settings().INTERPRETE_ANCLA_CATALOGO = True

# Embeddings: si --embeddings, adjuntamos el vector de cada producto y prendemos
# el blend semantico en la busqueda.
if EMB:
    _emb_path = os.path.join(ROOT, f"data/clientes/{TIENDA}/embeddings.json")
    if not os.path.exists(_emb_path):
        raise SystemExit(f"Faltan embeddings: corre generar_embeddings.py --tienda {TIENDA}")
    with open(_emb_path, encoding="utf-8") as _ef:
        _vecs = json.load(_ef)
    _n = 0
    for _p in _prods:
        v = _vecs.get(_p["id"])
        if v:
            _p["embedding"] = v
            _n += 1
    get_settings().EMBEDDINGS_ON = True
    print(f"Embeddings activos: {_n}/{len(_prods)} productos con vector")


def leer_preguntas(path):
    """Lee preguntas. .jsonl: una por linea con sus etiquetas. .txt: una pregunta
    por linea, sin etiqueta (preguntas reales pegadas tal cual)."""
    qs = []
    with open(path, encoding="utf-8") as f:
        if path.lower().endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if line:
                    qs.append(json.loads(line))
        else:
            for i, line in enumerate(f, 1):
                t = line.strip()
                if t and not t.startswith("#"):
                    qs.append({"id": f"r{i:03d}", "texto": t, "categoria": "real"})
    return qs


def evaluar(q, r):
    """Devuelve (estado, detalle). estado: OK | REVISAR | OBS."""
    intencion = r.get("intencion")
    confianza = r.get("confianza", 0.0)
    candidatos = r.get("candidatos", []) or []
    ofrecer = r.get("ofrecer_opciones")
    pregunta_ok = (confianza < UMBRAL_CONFIANZA_ALTA or bool(candidatos)
                   or bool(ofrecer))

    checks = []
    estado = "OBS"
    if "esp_intencion" in q:
        ok = (intencion == q["esp_intencion"])
        checks.append(f"int={intencion}{'==' if ok else '!='}{q['esp_intencion']}")
        estado = "OK" if ok else "REVISAR"
    if q.get("esp_pregunta"):
        checks.append(f"pregunta={'si' if pregunta_ok else 'NO'}")
        if estado != "REVISAR":
            estado = "OK" if pregunta_ok else "REVISAR"
    return estado, " ".join(checks)


def evaluar_producto(q, r, nombres):
    """Mide si la RESOLUCION de producto es correcta segun esp_producto:
    NINGUNO: no debe resolver ni ofrecer producto.
    MULTIPLE: no debe resolver uno solo, debe ofrecer o dar candidatos.
    nombre exacto: debe resolver a ese producto real."""
    if "esp_producto" not in q:
        return "OBS", ""
    esp = q["esp_producto"]
    prod = r.get("producto_resuelto")
    cand = r.get("candidatos", []) or []
    ofr = r.get("ofrecer_opciones")
    if esp == "NINGUNO":
        ok = (prod is None and not cand)
        return ("OK" if ok else "REVISAR"), f"esp=NINGUNO prod={prod} cand={len(cand)}"
    if esp == "MULTIPLE":
        ok = (prod is None and (len(cand) >= 2 or bool(ofr)))
        return ("OK" if ok else "REVISAR"), f"esp=MULTIPLE"
    ok = (prod == esp)
    return ("OK" if ok else "REVISAR"), f"esp={esp}"


def evaluar_categoria(q, r):
    """Para preguntas con sinonimos: chequea que lo resuelto u ofrecido caiga en
    la categoria esperada. Mide si el sistema aterriza en la categoria correcta
    cuando el cliente no usa las palabras del catalogo."""
    if "esp_categoria" not in q:
        return None, ""
    cat = q["esp_categoria"]
    nombres = ([r["producto_resuelto"]] if r.get("producto_resuelto") else []) \
        + (r.get("candidatos") or [])
    cats = {NOMBRE_CAT.get(nm) for nm in nombres if nm in NOMBRE_CAT}
    ok = bool(nombres) and cat in cats
    return ("OK" if ok else "REVISAR"), f"esp_cat={cat} got={sorted(c for c in cats if c)}"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tienda", default="verifika_demo")
    ap.add_argument("--embeddings", action="store_true")
    ap.add_argument("--preguntas",
                    default=os.path.join(ROOT, "data", "preguntas_reales.jsonl"),
                    help="Ruta a .jsonl etiquetado o .txt con una pregunta por linea")
    args = ap.parse_args()

    qs = leer_preguntas(args.preguntas)
    if args.limit:
        qs = qs[:args.limit]

    print(f"\n=== PRUEBA DEL INTERPRETADOR — {len(qs)} preguntas reales ===\n")
    resultados = []
    for q in qs:
        try:
            r = await interpretar_mensaje(q["texto"], history=[],
                                          trace_id=q["id"],
                                          tienda_id=TIENDA)
        except Exception as e:
            r = {"intencion": "ERROR", "confianza": 0.0, "error": str(e)[:80]}
        estado, detalle = evaluar(q, r)
        prod_estado, prod_detalle = evaluar_producto(q, r, NOMBRES)
        cat_estado, cat_detalle = evaluar_categoria(q, r)
        resultados.append((q, r, estado, prod_estado, cat_estado))
        prod = r.get("producto_resuelto")
        cand = r.get("candidatos", []) or []
        ofr = r.get("ofrecer_opciones")
        # Candidatos que NO son productos reales del catalogo: alucinaciones.
        inventados = [c for c in cand if c not in NOMBRES]
        prod_real = (prod is None) or (prod in NOMBRES)
        marca_ancla = "cand_INVENTADO" if inventados else "cand_real"
        if not prod_real:
            marca_ancla += " prod_INVENTADO"
        sello = cat_estado if cat_estado else prod_estado
        print(f"  [int {estado:>7} | res {sello:>7}] {q['id']} "
              f"{q['categoria']:<11} int={r.get('intencion'):<18} "
              f"conf={r.get('confianza')}")
        print(f"            txt: {q['texto'][:70]}")
        print(f"            prod={prod} cand={cand[:3]} "
              f"ofrecer={'si' if ofr else 'no'} | {marca_ancla} | "
              f"{prod_detalle}{cat_detalle}")

    # Resumen
    por_cat = {}
    for q, r, estado, _pe, _ce in resultados:
        d = por_cat.setdefault(q["categoria"], {"OK": 0, "REVISAR": 0, "OBS": 0})
        d[estado] += 1
    n_ok = sum(1 for _, _, e, _, _ in resultados if e == "OK")
    n_rev = sum(1 for _, _, e, _, _ in resultados if e == "REVISAR")
    n_obs = sum(1 for _, _, e, _, _ in resultados if e == "OBS")
    labeled = n_ok + n_rev

    # Resolucion de producto
    p_ok = sum(1 for _, _, _, pe, _ in resultados if pe == "OK")
    p_rev = sum(1 for _, _, _, pe, _ in resultados if pe == "REVISAR")
    p_lab = p_ok + p_rev
    fallos_prod = [q["id"] for q, _, _, pe, _ in resultados if pe == "REVISAR"]

    # Resolucion por categoria (preguntas con sinonimos)
    c_ok = sum(1 for _, _, _, _, ce in resultados if ce == "OK")
    c_rev = sum(1 for _, _, _, _, ce in resultados if ce == "REVISAR")
    c_lab = c_ok + c_rev
    fallos_cat = [q["id"] for q, _, _, _, ce in resultados if ce == "REVISAR"]

    print("\n  Por categoria (intencion):")
    for cat, d in sorted(por_cat.items()):
        print(f"    {cat:<14} OK={d['OK']} REVISAR={d['REVISAR']} OBS={d['OBS']}")
    print(f"\n  Intencion: {len(resultados)} | OK={n_ok} REVISAR={n_rev} OBS={n_obs}")
    if labeled:
        print(f"  Acierto de intencion: {100 * n_ok // labeled}% ({n_ok}/{labeled})")
    if p_lab:
        print(f"  Acierto de RESOLUCION de producto: {100 * p_ok // p_lab}% "
              f"({p_ok}/{p_lab})")
        if fallos_prod:
            print(f"  Fallos de resolucion: {fallos_prod}")
    if c_lab:
        print(f"  Acierto de CATEGORIA (sinonimos): {100 * c_ok // c_lab}% "
              f"({c_ok}/{c_lab})")
        if fallos_cat:
            print(f"  Fallos de categoria: {fallos_cat}")

    # Foto de distribucion (sirve para preguntas reales SIN etiqueta).
    total = len(resultados)
    resueltos = sum(1 for _, r, _, _, _ in resultados if r.get("producto_resuelto"))
    ofrecidos = sum(1 for _, r, _, _, _ in resultados
                    if not r.get("producto_resuelto")
                    and (r.get("candidatos") or r.get("ofrecer_opciones")))
    sin_prod = total - resueltos - ofrecidos
    inventados = sum(
        1 for _, r, _, _, _ in resultados
        if (r.get("producto_resuelto") and r["producto_resuelto"] not in NOMBRES)
        or any(c not in NOMBRES for c in (r.get("candidatos") or [])))
    ids_inv = [q["id"] for q, r, _, _, _ in resultados
               if (r.get("producto_resuelto") and r["producto_resuelto"] not in NOMBRES)
               or any(c not in NOMBRES for c in (r.get("candidatos") or []))]
    print(f"\n  Distribucion: resueltos={resueltos} ofrecidos={ofrecidos} "
          f"sin_producto={sin_prod} de {total}")
    print(f"  Productos INVENTADOS (no existen en catalogo): {inventados}"
          + (f" -> {ids_inv[:10]}" if ids_inv else " (ninguno, OK)"))
    print()

    # Volcado para el dashboard / seguimiento.
    reportes_dir = os.path.join(ROOT, "reports")
    os.makedirs(reportes_dir, exist_ok=True)
    out = [{"id": q["id"], "categoria": q["categoria"], "texto": q["texto"],
            "intencion": r.get("intencion"), "confianza": r.get("confianza"),
            "producto_resuelto": r.get("producto_resuelto"),
            "candidatos": r.get("candidatos", []),
            "ofrecer_opciones": r.get("ofrecer_opciones"),
            "estado_intencion": estado, "estado_producto": prod_estado,
            "estado_categoria": cat_estado}
           for (q, r, estado, prod_estado, cat_estado) in resultados]
    with open(os.path.join(reportes_dir, "interprete_resultados.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("  Resultados en reports/interprete_resultados.json\n")


if __name__ == "__main__":
    asyncio.run(main())
