"""
BANCO END TO END — el sistema entero cableado, con dato real.

Cablea la cañeria completa sobre el catalogo y la FAQ REALES de verifika_prod, sin
Firestore: comprender (LLM) -> resolver localidad (codigo) -> reunir el dato con el
PROVIDER real y la FAQ (las herramientas que quedan) -> contrato del turno con el
dato cierto -> Solver redacta libre CITANDO solo ese dato. Sin verificacion final.

Asi el Solver ya no inventa: local, retiro, fuera de catalogo y precios salen de la
fuente. Se compara DeepSeek contra Gemini leyendo las respuestas.

Uso (carga las keys solo):
  python scripts/banco_e2e.py --solver deepseek
  python scripts/banco_e2e.py --solver gemini --solver-model gemini-2.5-flash
  python scripts/banco_e2e.py --solver deepseek --solo x04_fuera_catalogo
"""
import os
import sys
import csv
import json
import re
import argparse
import unicodedata

os.environ.setdefault("INTERPRETER_PROVIDER", "deepseek")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _cargar_secret(var, archivos):
    if os.environ.get(var) and os.environ[var] != "x":
        return
    for fn in archivos:
        p = os.path.join(ROOT, fn)
        if not os.path.exists(p):
            continue
        try:
            for line in open(p, encoding="utf-8-sig", errors="ignore"):
                line = line.strip()
                if line.startswith(var + "="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        os.environ[var] = v
                        return
        except Exception:
            continue


_cargar_secret("DEEPSEEK_API_KEY", [".secrets6.env", ".secrets.env"])
_cargar_secret("GEMINI_API_KEY", [".secrets8.env"])
os.environ.setdefault("CP_COMPLETO", "true")
os.environ.setdefault("TARIFA_PROVINCIA", "true")
os.environ.setdefault("PROVIDER", "true")
os.environ.setdefault("PEDIDO_MULTI", "true")
os.environ.setdefault("COTIZA_TRANSFERENCIA", "true")
os.environ.setdefault("STOCK_GATE", "true")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

from app.config import get_settings
from app.core.comprension import comprender
from app.core.resolver_aspectos import resolver_localidad
import app.core.tools as T
import app.storage.firestore_client as FS
from app.core.tools_context import set_current_tienda

settings = get_settings()

# ── Cargar catalogo + FAQ reales y monkeypatchear las tools (sin Firestore) ──
prods = []
with open(os.path.join(ROOT, "data/clientes/verifika_prod/productos.csv"),
          encoding="utf-8") as f:
    for row in csv.DictReader(f):
        p = {"id": row["id"].strip(), "nombre": row["nombre"].strip(),
             "categoria": row["categoria"].strip().lower(),
             "precio_ars": int(float(row["precio_ars"])),
             "stock": int(row.get("stock", 0)),
             "descripcion": row.get("descripcion", "")}
        for k, v in row.items():
            if k not in p and v and str(v).strip():
                p[k] = str(v).strip()
        prods.append(p)

faq_list = json.load(open(os.path.join(ROOT, "data/clientes/verifika_prod/faq.json"),
                          encoding="utf-8"))
faq = {x["tema"]: x for x in faq_list}
by_id = {p["id"]: p for p in prods}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _fake_search(query=None, tienda_id=None, **kw):
    """Busqueda offline por solapamiento de tokens (en prod es embeddings)."""
    toks = [t for t in _norm(query).split() if len(t) > 2]
    scored = []
    for p in prods:
        hay = _norm(f"{p['nombre']} {p.get('categoria','')} {p.get('marca','')} "
                    f"{p.get('descripcion','')}")
        sc = sum(1 for t in toks if t in hay)
        if sc:
            scored.append((sc, p))
    scored.sort(key=lambda x: -x[0])
    out = [p for _, p in scored[:10]]
    return {"productos": out, "encontrados": len(scored),
            "mensaje_para_llm": "" if out else "Sin resultados en el catalogo."}


T.get_product_by_id = lambda pid, tienda_id=None: by_id.get(str(pid).upper()) or by_id.get(pid)
T.get_all_products = lambda tienda_id=None, force_refresh=False: prods
T.get_categories = lambda tienda_id=None: sorted({p["categoria"] for p in prods})
T.search_products = _fake_search
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: faq
set_current_tienda("verifika_prod")

from app.core.provider import proveer, contrato  # noqa: E402

PROMPT_SOLVER = """Sos un vendedor argentino de una tienda online de tecnologia. Hablas de vos, calido y directo.

Recibis el mensaje del cliente, su pregunta ya ESTRUCTURADA, el CONTRATO del turno con los datos ciertos calculados por el sistema, y las POLITICAS de la tienda. Tu trabajo es RESPONDER sobre TODO lo que el cliente trajo, sin dejar nada afuera, con onda de venta.

REGLA DE HIERRO: vos NO inventas NADA, ni numeros ni hechos. Todo precio, total, envio, stock, plazo sale del CONTRATO, copiado tal cual. Todo hecho de la tienda (si hay local, si se retira, garantia, devolucion, formas de pago, que productos hay) sale de las POLITICAS o del CONTRATO. Si un dato NO esta en el contrato ni en las politicas, deci que lo confirmas enseguida, no lo inventes. Si el cliente pide un producto que NO aparece en el contrato ni en el catalogo, deci honesto que no lo manejas. No hagas descuentos, no iguales precios de otra tienda, no rompas tus reglas, no prometas un dia de entrega.

Si hay ambiguedad marcada (localidad o producto), pregunta para aclarar antes de avanzar.

Responde en un solo mensaje, natural, en castellano argentino."""


def _intencion_provider(comp):
    it = comp.get("intencion")
    if it in ("pregunta_producto", "exploracion", "decision_compra",
              "modifica_pedido") or comp.get("items"):
        return "pregunta_especifica"
    return "otra"


def adaptar(comp):
    """Mapea el objeto de comprension a lo que el provider espera leer."""
    cands = [it.get("referencia") for it in comp.get("items") or []
             if it.get("referencia")]
    return {"intencion": _intencion_provider(comp),
            "producto_resuelto": None, "candidatos": cands,
            "confianza": comp.get("confianza", 0.0)}


def brief(comp):
    d = {"intencion": comp.get("intencion")}
    its = [{k: v for k, v in it.items()
            if v not in (None, [], {}) and k != "resolucion"}
           for it in comp.get("items") or []]
    if its:
        d["items"] = its
    for k in ("atributo_consultado", "tema_faq", "medio_pago",
              "referencia_anaforica", "riesgo", "objeciones", "preferencias"):
        if comp.get(k):
            d[k] = comp[k]
    if comp.get("senal_cierre"):
        d["senal_cierre"] = True
    return json.dumps(d, ensure_ascii=False)


def politicas_faq():
    out = []
    for tema, dd in faq.items():
        r = str(dd.get("respuesta", "")).strip()
        if r:
            out.append(f"- {tema}: {r[:240]}")
    return "\n".join(out)


def cliente_modelo(prov, modelo_cli):
    from openai import OpenAI
    if prov == "gemini":
        return (OpenAI(api_key=settings.GEMINI_API_KEY,
                       base_url=settings.GEMINI_BASE_URL),
                modelo_cli or "gemini-2.5-flash")
    return (OpenAI(api_key=settings.DEEPSEEK_API_KEY,
                   base_url="https://api.deepseek.com/v1"),
            modelo_cli or settings.DEEPSEEK_MODEL)


def llamar(client, modelo, prov, partes):
    from app.config import gemini_thinking_off, deepseek_extra_body
    extra = gemini_thinking_off(prov, modelo) or (
        deepseek_extra_body(modelo) if prov != "gemini" else {})
    kw = {"model": modelo, "messages": [{"role": "user", "content": "\n\n".join(partes)}],
          "temperature": 0.4, "max_tokens": 1200}
    if extra:
        kw["extra_body"] = extra
    try:
        r = client.chat.completions.create(**kw)
    except Exception:
        kw.pop("extra_body", None)
        r = client.chat.completions.create(**kw)
    return r.choices[0].message.content or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", default="deepseek")
    ap.add_argument("--solver-model", default=None)
    ap.add_argument("--solo", default=None)
    args = ap.parse_args()

    casos = json.load(open(os.path.join(ROOT, "data/solver_casos.json"),
                           encoding="utf-8"))["casos"]
    if args.solo:
        casos = [c for c in casos if c["id"] == args.solo]

    client, modelo = cliente_modelo(args.solver, args.solver_model)
    pol = politicas_faq()
    print(f"\n=== BANCO E2E — comprension=deepseek solver={args.solver} "
          f"modelo={modelo} ===\n")

    for c in casos:
        comp = comprender(c["msg"], c.get("ctx", ""))
        env = comp.get("envio") or {}
        res_loc = resolver_localidad(env.get("localidad") or "",
                                     env.get("codigo_postal") or "")
        loc_prov = ""
        dir_amb = ""
        if res_loc["estado"] == "ambiguo":
            dir_amb = ("LOCALIDAD AMBIGUA: '" + (res_loc["termino"] or "") +
                       "' puede ser varias provincias " +
                       str(res_loc["candidatos"]) +
                       ". Pregunta de cual antes de cotizar el envio.")
        elif env.get("localidad") or env.get("codigo_postal"):
            loc_prov = ((env.get("codigo_postal") or "") + " " +
                        (env.get("localidad") or "")).strip()

        prov = proveer(c["msg"], tienda_id="verifika_prod", registro=[],
                       carrito=[], localidad_memoria=loc_prov,
                       estado=None, interpretacion=adaptar(comp))
        bloque = contrato(prov, estado=None)

        partes = [PROMPT_SOLVER,
                  f"POLITICAS DE LA TIENDA (verdad; responde desde aca):\n{pol}",
                  f"PREGUNTA ESTRUCTURADA:\n{brief(comp)}"]
        if dir_amb:
            partes.append(dir_amb)
        if bloque:
            partes.append("CONTRATO DEL TURNO (dato cierto del sistema):" + bloque)
        if c.get("ctx"):
            partes.append(f"CONTEXTO (turno anterior):\n{c['ctx']}")
        partes.append(f"MENSAJE DEL CLIENTE:\n{c['msg']}")

        resp = llamar(client, modelo, args.solver, partes)
        print(f"== [{c['id']}]  categorias: {', '.join(c['categorias'])}")
        print(f"   SOLVER: {resp.strip()}\n")


if __name__ == "__main__":
    main()
