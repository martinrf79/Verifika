"""
Script de onboarding: da de alta una tienda nueva en Firestore.

Uso:
    python scripts/crear_cliente.py \
        --tienda_id "ferreteria_juan" \
        --nombre "Ferretería Juan" \
        --phone_id "123456789012345" \
        --token "EAAxxxx..." \
        --verify_token "verify_juan_2026" \
        --catalogo data/clientes/juan/productos.csv \
        --faq data/clientes/juan/faq.csv

Si --catalogo o --faq no se pasan, solo registra la tienda (carga datos después).
"""
import argparse
import csv
import sys
import os

# Permitir ejecutar desde la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.firestore_client import (
    register_tienda,
    upsert_product,
    upsert_faq,
    set_config,
)


def cargar_productos_csv(path: str, tienda_id: str) -> int:
    """
    Acepta CSV con columnas minimas obligatorias:
        id, nombre, categoria, precio_ars, stock, descripcion
    Y CUALQUIER cantidad de columnas extra (origen, material, garantia_meses,
    voltaje, dimensiones, peso, marca, etc.).
    Las columnas extra se guardan tal cual en Firestore para que el agente las
    pueda usar al responder y el validator pueda verificar contra ellas.
    """
    OBLIGATORIAS = {"id", "nombre", "categoria", "precio_ars", "stock", "descripcion"}
    ok = 0
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Campos obligatorios con su tipo correcto
                producto = {
                    "id": row["id"].strip(),
                    "nombre": row["nombre"].strip(),
                    "categoria": row["categoria"].strip().lower(),
                    "precio_ars": int(float(row["precio_ars"])),
                    "stock": int(row.get("stock", 0)),
                    "descripcion": row.get("descripcion", "").strip(),
                }
                # Campos extra: todo lo que NO esta en obligatorias
                for key, val in row.items():
                    if key in OBLIGATORIAS or not key:
                        continue
                    if val is None or str(val).strip() == "":
                        continue
                    val_limpio = str(val).strip()
                    # Intentar convertir a numero si parece numerico
                    try:
                        if "." in val_limpio:
                            producto[key.strip().lower()] = float(val_limpio)
                        else:
                            producto[key.strip().lower()] = int(val_limpio)
                    except ValueError:
                        producto[key.strip().lower()] = val_limpio
                upsert_product(producto["id"], producto, tienda_id=tienda_id)
                ok += 1
            except (KeyError, ValueError) as e:
                print(f"  fila ignorada ({row.get('id', '?')}): {e}")
    return ok


def cargar_faq_csv(path: str, tienda_id: str) -> int:
    """
    Espera CSV con columnas:
        tema,keywords,respuesta
    keywords separados por comas: "envio,envian,mandan"
    """
    ok = 0
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                tema = row["tema"].strip().lower()
                keywords = [k.strip().lower() for k in row["keywords"].split(",") if k.strip()]
                respuesta = row["respuesta"].strip()
                upsert_faq(tema, {
                    "keywords": keywords,
                    "respuesta": respuesta,
                }, tienda_id=tienda_id)
                ok += 1
            except (KeyError, ValueError) as e:
                print(f"  ⚠ fila ignorada ({row.get('tema', '?')}): {e}")
    return ok


def cargar_faq_json(path: str, tienda_id: str) -> int:
    """
    Espera JSON con lista de objetos, cada uno con:
        tema (str), keywords (list[str]), respuesta (str),
        tipo (str: informativo o cuantitativo),
        valores (list[dict] con concepto, modalidad fijo o rango,
                 monto o monto_min y monto_max, unidad, condicion opcional)
    """
    import json as _json
    ok = 0
    with open(path, encoding="utf-8") as f:
        items = _json.load(f)
    for row in items:
        try:
            tema = row["tema"].strip().lower()
            keywords = [k.strip().lower() for k in row.get("keywords", []) if k and str(k).strip()]
            respuesta = row["respuesta"].strip()
            tipo = row.get("tipo", "informativo").strip().lower()
            valores = row.get("valores", [])
            # Capa de conversion curada (opcional): angulo de venta y siguiente
            # paso, verdaderos. El nucleo lo usa para que la respuesta venda.
            venta = str(row.get("venta", "") or "").strip()
            if tipo not in ("informativo", "cuantitativo"):
                print(f"  fila ignorada ({tema}): tipo invalido {tipo}")
                continue
            upsert_faq(tema, {
                "keywords": keywords,
                "respuesta": respuesta,
                "tipo": tipo,
                "valores": valores,
                "venta": venta,
            }, tienda_id=tienda_id)
            ok += 1
        except (KeyError, ValueError) as e:
            print(f"  fila ignorada ({row.get('tema', '?')}): {e}")
    return ok


def _cmd_crear(args):
    print(f"\n-> Registrando tienda '{args.tienda_id}' ({args.nombre})...")
    register_tienda(
        tienda_id=args.tienda_id,
        phone_number_id=args.phone_id,
        whatsapp_token=args.token,
        nombre=args.nombre,
        verify_token=args.verify_token,
    )
    print("  OK tienda registrada")
    set_config("nombre", args.nombre, tienda_id=args.tienda_id)
    set_config("business_name", args.nombre, tienda_id=args.tienda_id)
    if args.contacto_humano:
        set_config("contacto_humano", args.contacto_humano, tienda_id=args.tienda_id)
    print("  OK config base creada")
    if args.catalogo:
        _cargar_catalogo(args.catalogo, args.tienda_id)
    if args.faq:
        _cargar_faq(args.faq, args.tienda_id)
    print(f"\nOK Tienda '{args.tienda_id}' lista.")


def _cmd_cargar_faq(args):
    _cargar_faq(args.faq, args.tienda_id)


def _cmd_cargar_catalogo(args):
    _cargar_catalogo(args.catalogo, args.tienda_id)


def _cargar_faq(path, tienda_id):
    if not os.path.exists(path):
        print(f"  ERROR FAQ no encontrado: {path}")
        return
    print(f"\n-> Cargando FAQ desde {path}")
    if path.lower().endswith(".json"):
        n = cargar_faq_json(path, tienda_id)
    else:
        n = cargar_faq_csv(path, tienda_id)
    print(f"  OK {n} preguntas cargadas en {tienda_id}")


def _cargar_catalogo(path, tienda_id):
    if not os.path.exists(path):
        print(f"  ERROR catalogo no encontrado: {path}")
        return
    print(f"\n-> Cargando productos desde {path}")
    n = cargar_productos_csv(path, tienda_id)
    print(f"  OK {n} productos cargados en {tienda_id}")


def main():
    parser = argparse.ArgumentParser(description="Gestion de tiendas Verifika")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_crear = sub.add_parser("crear", help="Alta de tienda nueva")
    p_crear.add_argument("--tienda_id", required=True)
    p_crear.add_argument("--nombre", required=True)
    p_crear.add_argument("--phone_id", required=True)
    p_crear.add_argument("--token", required=True)
    p_crear.add_argument("--verify_token", default="")
    p_crear.add_argument("--catalogo", default="")
    p_crear.add_argument("--faq", default="")
    p_crear.add_argument("--contacto_humano", default="")
    p_crear.set_defaults(func=_cmd_crear)

    p_faq = sub.add_parser("cargar_faq", help="Recarga FAQ de tienda existente")
    p_faq.add_argument("--tienda_id", required=True)
    p_faq.add_argument("--faq", required=True, help="Ruta a CSV o JSON")
    p_faq.set_defaults(func=_cmd_cargar_faq)

    p_cat = sub.add_parser("cargar_catalogo", help="Recarga catalogo de tienda existente")
    p_cat.add_argument("--tienda_id", required=True)
    p_cat.add_argument("--catalogo", required=True, help="Ruta a CSV de productos")
    p_cat.set_defaults(func=_cmd_cargar_catalogo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()