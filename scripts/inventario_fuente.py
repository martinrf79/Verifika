#!/usr/bin/env python3
"""
INVENTARIO DE LA FUENTE DE VERDAD (paso 1) — que tiene la fuente, que le falta
y donde el codigo lee algo que la fuente no da.

No opina: mide. Corre offline sobre el repo y, con --vivo, compara contra el
Firestore de produccion (solo lectura, clave claude-lector en GCP_SA_KEY_B64).
Es la herramienta que reemplaza al "me parece que el catalogo esta completo".

Uso:
    python scripts/inventario_fuente.py
    python scripts/inventario_fuente.py --vivo
    python scripts/inventario_fuente.py --md INVENTARIO_FUENTE.md

Escala: el reporte es por CATEGORIA y por CAMPO, nunca por producto, asi una
tienda de 880 o de 20.000 productos se lee igual de rapido.
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.fuente_producto import (  # noqa: E402
    aplica, normalizar_producto, specs_config,
)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Campos que el CAMINO VIVO lee del producto. Si uno no llega a Firestore, la
# ficha responde en hueco: por eso el inventario los chequea uno por uno.
CAMPOS_QUE_LEE_EL_CODIGO = [
    ("nombre", "ficha, universo, cita"), ("categoria", "enum del universo"),
    ("precio_ars", "presupuesto, calculadora"), ("stock", "guardia de stock"),
    ("descripcion", "ficha"), ("origen", "ficha: procedencia"),
    ("garantia_detalle", "ficha: garantia"), ("garantia_meses", "verificador"),
    ("material", "ficha"), ("peso_gramos", "ficha: medidas"),
    ("dimensiones", "ficha: medidas"), ("contenido_caja", "ficha: que trae"),
    ("uso_recomendado", "ficha: uso"), ("caracteristicas_extra", "ficha: specs"),
    ("marca", "buscador"), ("modelo", "certificador de modelo puntual"),
    ("color", "buscador, variantes"), ("tags", "buscador: sinonimos"),
    ("descripcion_rica", "buscador: score"),
]


def _dir_tienda(tienda_id):
    return os.path.join(RAIZ, "data", "clientes", tienda_id)


def leer_csv(tienda_id):
    ruta = os.path.join(_dir_tienda(tienda_id), "productos.csv")
    with open(ruta, encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def leer_json(tienda_id, nombre):
    ruta = os.path.join(_dir_tienda(tienda_id), nombre)
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def campos_vivos(tienda_id):
    """{campo: cantidad de productos que lo traen} en el Firestore REAL.
    Solo lectura, por REST con la clave de claude-lector."""
    import base64
    import collections
    import json as _json
    import requests
    from google.oauth2 import service_account
    import google.auth.transport.requests

    b64 = os.getenv("GCP_SA_KEY_B64", "")
    if not b64:
        raise RuntimeError("falta GCP_SA_KEY_B64 para el modo --vivo")
    ca = os.getenv("REQUESTS_CA_BUNDLE", "/root/.ccr/ca-bundle.crt")
    # La clave se decodifica en memoria y nunca toca disco.
    info = _json.loads(base64.b64decode(b64))
    cred = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
    cred.refresh(google.auth.transport.requests.Request())
    proyecto = os.getenv("GCP_PROJECT", "memory-engine-v1")
    base = (f"https://firestore.googleapis.com/v1/projects/{proyecto}/"
            f"databases/(default)/documents/tiendas/{tienda_id}/productos")
    headers = {"Authorization": f"Bearer {cred.token}"}
    campos, total, token = collections.Counter(), 0, None
    while True:
        url = base + "?pageSize=300" + (f"&pageToken={token}" if token else "")
        data = requests.get(url, headers=headers, verify=ca, timeout=60).json()
        for doc in data.get("documents", []):
            total += 1
            for k in (doc.get("fields") or {}):
                campos[k] += 1
        token = data.get("nextPageToken")
        if not token:
            break
    return total, campos


def inventario(tienda_id, vivo=False):
    filas = leer_csv(tienda_id)
    prods = [normalizar_producto(dict(r), tienda_id) for r in filas]
    cats = sorted({p["categoria"] for p in prods})
    cfg = specs_config(tienda_id)
    lineas = []
    esc = lineas.append

    esc(f"# Inventario de la fuente de verdad — {tienda_id}")
    esc("")
    esc(f"Productos en el repo: **{len(prods)}** | categorias: **{len(cats)}** "
        f"| specs preguntables: **{len(cfg)}**")
    esc("")

    # ── 1. CAMPOS que el codigo lee vs los que la fuente da ──────────────
    esc("## 1. Campos del producto: lo que el codigo lee vs lo que la fuente da")
    esc("")
    total_vivo, campos_vivo = (None, None)
    if vivo:
        try:
            total_vivo, campos_vivo = campos_vivos(tienda_id)
            esc(f"Firestore vivo: **{total_vivo}** productos.")
            esc("")
        except Exception as e:
            esc(f"_(modo vivo no disponible: {str(e)[:120]})_")
            esc("")
    cab = "| campo | lo usa | en el CSV | en Firestore |"
    esc(cab)
    esc("|---|---|---|---|")
    huecos = []
    for campo, uso in CAMPOS_QUE_LEE_EL_CODIGO:
        con = sum(1 for p in prods if str(p.get(campo) or "").strip())
        col_vivo = "-"
        if campos_vivo is not None:
            n = campos_vivo.get(campo, 0)
            col_vivo = f"{n}/{total_vivo}"
            if n == 0 and con:
                huecos.append(campo)
        esc(f"| {campo} | {uso} | {con}/{len(prods)} | {col_vivo} |")
    esc("")
    if huecos:
        esc(f"**HUECO:** el CSV trae {', '.join(huecos)} y Firestore NO. El "
            "codigo los lee y le vuelve vacio. Se cierra recargando el catalogo "
            "por la ingesta normalizada.")
        esc("")

    # ── 2. SPECS preguntables: cobertura por categoria ───────────────────
    esc("## 2. Specs preguntables: que puede contestar la fuente")
    esc("")
    esc("Cada celda = productos de esa categoria con el dato / productos donde "
        "la spec aplica. Un `-` es que la spec no aplica a esa categoria. "
        "Donde dice 0 el bot contesta el honesto 'la ficha no lo especifica': "
        "no es un bug, es el hueco de datos a llenar en la fuente.")
    esc("")
    esc("| spec | " + " | ".join(cats) + " | total |")
    esc("|---" * (len(cats) + 2) + "|")
    pendientes = []
    for s in cfg:
        celdas, con_tot, apl_tot = [], 0, 0
        for c in cats:
            apl = [p for p in prods if p["categoria"] == c and aplica(s, c)]
            if not apl:
                celdas.append("-")
                continue
            con = sum(1 for p in apl if s["id"] in p["specs"])
            con_tot += con
            apl_tot += len(apl)
            celdas.append(f"{con}/{len(apl)}" if con else f"**0**/{len(apl)}")
        esc(f"| {s['id']} | " + " | ".join(celdas) +
            f" | {con_tot}/{apl_tot} |")
        if apl_tot and not con_tot:
            pendientes.append((s["id"], s["etiqueta"], apl_tot))
    esc("")
    if pendientes:
        esc("**Specs que la fuente NO responde en ningun producto** (el bot es "
            "honesto y no vende con ellas; llenarlas es dato del proveedor, no "
            "codigo):")
        for sid, et, n in pendientes:
            esc(f"- `{sid}` ({et}) — aplicaria a {n} productos")
        esc("")

    # ── 3. FAQ, base de conocimiento, no vendidas ────────────────────────
    esc("## 3. El resto de la fuente")
    esc("")
    faq = leer_json(tienda_id, "faq.json") or []
    bc = leer_json(tienda_id, "base_conocimiento.json") or {}
    nv = leer_json(tienda_id, "no_vendidas.json") or {}
    n_faq = len(faq) if isinstance(faq, (list, dict)) else 0
    esc(f"- FAQ: **{n_faq}** temas")
    cat_bc = bc.get("categorias") if isinstance(bc, dict) else None
    esc(f"- Base de conocimiento: **{len(cat_bc or [])}** categorias de criterio")
    lista_nv = nv.get("no_vendidas") if isinstance(nv, dict) else nv
    esc(f"- Categorias no vendidas: **{len(lista_nv or [])}**")
    esc(f"- Specs preguntables: **{len(cfg)}**")
    esc("")

    # ── 4. Fichas con la spec fantasma (calidad del dato) ────────────────
    esc("## 4. Calidad del dato: spec fantasma depurada")
    esc("")
    sucias = 0
    for cru, lim in zip(filas, prods):
        a = [x.strip() for x in (cru.get("caracteristicas_extra") or "").split(",") if x.strip()]
        b = [x.strip() for x in (lim.get("caracteristicas_extra") or "").split(",") if x.strip()]
        if len(a) != len(b):
            sucias += 1
    esc(f"Fichas del CSV que traian una spec de OTRO producto pegada: "
        f"**{sucias}/{len(prods)}**. La ingesta las depura dejando la spec "
        "avalada por el nombre del propio producto.")
    esc("")
    return "\n".join(lineas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tienda", default=os.getenv("TIENDA_ID", "verifika_prod"))
    ap.add_argument("--vivo", action="store_true",
                    help="compara contra el Firestore de produccion (lectura)")
    ap.add_argument("--md", default="", help="ruta donde escribir el reporte")
    args = ap.parse_args()
    reporte = inventario(args.tienda, vivo=args.vivo)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(reporte + "\n")
        print(f"reporte escrito en {args.md}")
    print(reporte)


if __name__ == "__main__":
    main()
