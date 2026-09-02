#!/usr/bin/env python3
"""
PLANILLA DE CARGA DE SPECS — genera `specs_por_modelo.csv`, la lista de lo que
falta cargar para que el bot no conteste "no tengo ese dato".

Una fila por MODELO distinto, no por producto: en verifika_prod son 482 filas
para 880 productos, y una tienda de 20.000 productos con 900 modelos sigue
siendo 900 filas. Solo aparecen las columnas de specs que a esa categoria le
faltan de verdad: lo que la ficha ya responde y lo que resuelve la capa de
categoria no se pide dos veces.

La celda que se deja vacia NO rompe nada: esa spec sigue saliendo honesta. Se
puede llenar de a poco, por categoria, y cada vez que se recarga el catalogo el
bot contesta con lo que haya cargado.

Uso:
    python scripts/planilla_specs.py                 # genera y no pisa lo cargado
    python scripts/planilla_specs.py --resumen       # solo cuenta que falta
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.fuente_producto import (  # noqa: E402
    _norm, aplica, normalizar_producto, specs_config,
)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def modelos(tienda_id):
    """{(marca, modelo, categoria): producto representativo} del catalogo."""
    ruta = os.path.join(RAIZ, "data", "clientes", tienda_id, "productos.csv")
    out = {}
    with open(ruta, encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            p = normalizar_producto(dict(fila), tienda_id)
            clave = (str(p.get("marca") or "").strip(),
                     str(p.get("modelo") or "").strip(),
                     str(p.get("categoria") or "").strip())
            out.setdefault(clave, p)
    return out


def faltantes(tienda_id):
    """[(clave, [spec_ids que faltan])] con las specs que aplican y ninguna
    capa responde todavia."""
    cfg = specs_config(tienda_id)
    out = []
    for clave, p in modelos(tienda_id).items():
        faltan = [s["id"] for s in cfg
                  if aplica(s, p["categoria"]) and s["id"] not in p["specs"]]
        out.append((clave, p, faltan))
    return out


def generar(tienda_id, ruta_csv):
    """Escribe la planilla. Si ya existe, CONSERVA lo cargado y solo agrega las
    filas y columnas nuevas: nunca se pierde trabajo hecho a mano."""
    cargado = {}
    if os.path.exists(ruta_csv):
        with open(ruta_csv, encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                clave = (_norm(fila.get("marca")), _norm(fila.get("modelo")),
                         _norm(fila.get("categoria")))
                cargado[clave] = {k: v for k, v in fila.items()
                                  if k not in ("marca", "modelo", "categoria")
                                  and str(v or "").strip()}
    datos = faltantes(tienda_id)
    columnas = ["marca", "modelo", "categoria"]
    for _clave, _p, faltan in datos:
        for sid in faltan:
            if sid not in columnas:
                columnas.append(sid)
    for valores in cargado.values():
        for sid in valores:
            if sid not in columnas:
                columnas.append(sid)
    filas = []
    for (marca, modelo, cat), _p, faltan in sorted(datos, key=lambda x: (x[0][2], x[0][0], x[0][1])):
        previo = cargado.get((_norm(marca), _norm(modelo), _norm(cat)), {})
        fila = {"marca": marca, "modelo": modelo, "categoria": cat}
        for sid in columnas[3:]:
            fila[sid] = previo.get(sid, "")
        filas.append(fila)
    with open(ruta_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)
    return len(filas), columnas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tienda", default=os.getenv("TIENDA_ID", "verifika_prod"))
    ap.add_argument("--resumen", action="store_true")
    args = ap.parse_args()
    datos = faltantes(args.tienda)
    total = sum(len(f) for _c, _p, f in datos)
    por_cat = {}
    por_spec = {}
    for (_ma, _mo, cat), _p, faltan in datos:
        por_cat[cat] = por_cat.get(cat, 0) + len(faltan)
        for sid in faltan:
            por_spec[sid] = por_spec.get(sid, 0) + 1
    print(f"Modelos distintos: {len(datos)} | celdas de spec sin responder: {total}")
    print("\nPor categoria:")
    for cat, n in sorted(por_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat:24s} {n:5d}")
    print("\nPor spec:")
    for sid, n in sorted(por_spec.items(), key=lambda x: -x[1]):
        print(f"  {sid:20s} {n:5d} modelos")
    if not args.resumen:
        ruta = os.path.join(RAIZ, "data", "clientes", args.tienda,
                            "specs_por_modelo.csv")
        filas, columnas = generar(args.tienda, ruta)
        print(f"\nPlanilla escrita: {ruta}")
        print(f"  {filas} filas, columnas: {', '.join(columnas)}")


if __name__ == "__main__":
    main()
