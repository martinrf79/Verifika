"""
Prueba de BUSQUEDA_RELAJADA + FAQ_MATCH_PALABRAS sobre verifika_prod.

Nacio del molino multiturno del 10-jun (gemini-2.5-flash): 58 turnos, 0
fallbacks, 0 alucinaciones... y 0 ventas. El catalogo dice "gaming" y el
cliente dice "gamer": la busqueda por substring daba 0 sobre una categoria
con 52 productos y la tool ordenaba negar stock. En FAQ, "costo de envio a
cordoba" no contiene el substring "costo envio" y ganaba el tema generico
'envios' (sin precio) sobre 'costo_envio'.

Correr con el lanzador (carga .secrets6.env):
    .\\correr_local.ps1  ->  o directo: venv-win\\Scripts\\python.exe scripts\\prueba_busqueda_relajada.py
Requiere credenciales de Firestore (lee verifika_prod, no escribe nada).
"""
import os
import sys
from pathlib import Path

os.environ["BUSQUEDA_RELAJADA"] = "true"
os.environ["FAQ_MATCH_PALABRAS"] = "true"
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.tools_context import set_current_tienda
from app.core.tools import search_products, query_faq

TIENDA = "verifika_prod"
set_current_tienda(TIENDA)

ok = 0
fallas = []


def check(nombre: str, cond: bool, detalle: str = ""):
    global ok
    if cond:
        ok += 1
        print(f"[OK ] {nombre}")
    else:
        fallas.append(nombre)
        print(f"[FALLA] {nombre}  {detalle}")


print("=== BUSQUEDA RELAJADA (search_products) ===")

# La clase que mato las ventas: palabra del cliente no figura textual pero la
# categoria tiene productos -> se ofrecen igual, marcados match parcial.
r = search_products(categoria="mouse", query="gamer")
check("mouse gamer ofrece productos", r["encontrados"] > 0,
      f"encontrados={r['encontrados']}")
check("mouse gamer marcado match parcial", r.get("match_exacto") is False)
check("mouse gamer instruye ofrecer", "OFRECELOS" in r.get("mensaje_para_llm", ""))

r = search_products(categoria="teclado", query="mecanico")
check("teclado mecanico ofrece productos", r["encontrados"] > 0)

r = search_products(categoria="monitor", query="27 pulgadas")
check("monitor 27 pulgadas ofrece productos", r["encontrados"] > 0)

# Categoria inventada por el modelo se mapea a una real y el resto va a la query.
r = search_products(categoria="teclado mecanico", query="redragon")
nombres = " ".join(p.get("nombre", "") for p in r.get("productos", []))
check("categoria inventada mapeada (redragon)", "Redragon" in nombres,
      f"encontrados={r['encontrados']}")

# Plural en la categoria.
r = search_products(categoria="mouses")
check("categoria en plural resuelve", r["encontrados"] > 0)

# Lo que NO existe sigue negandose honesto, con las categorias reales a mano.
r = search_products(query="proyector")
check("proyector inexistente da 0", r["encontrados"] == 0)
check("negativa trae categorias reales", "mouse" in r.get("mensaje_para_llm", ""))

# Match exacto sigue siendo exacto (no se degrada lo que ya andaba).
r = search_products(categoria="ssd", query="samsung 1tb")
check("ssd samsung 1tb matchea exacto", r["encontrados"] > 0
      and r.get("match_exacto", True) is True)

print("\n=== FAQ MATCH POR PALABRAS (query_faq) ===")

# El cajon con el numero le gana al generico.
r = query_faq("costo de envio a cordoba")
check("costo de envio -> costo_envio", r.get("tema") == "costo_envio",
      f"tema={r.get('tema')}")
check("costo_envio es cuantitativo", r.get("tipo") == "cuantitativo")

r = query_faq("cuanto sale el envio a La Plata")
check("cuanto sale el envio -> costo_envio", r.get("tema") == "costo_envio",
      f"tema={r.get('tema')}")

r = query_faq("cuantos dias tengo para la devolucion")
check("devolucion encuentra tema", r.get("tema") == "devoluciones",
      f"tema={r.get('tema')}")

r = query_faq("cuantas cuotas sin interes")
check("cuotas sin interes -> cuotas", r.get("tema") == "cuotas",
      f"tema={r.get('tema')}")

r = query_faq("lo puedo retirar por el local")
check("retiro local encuentra la negativa real", r.get("tema") == "retiro_local",
      f"tema={r.get('tema')}")

print(f"\n{ok}/{ok + len(fallas)} OK")
if fallas:
    print("FALLAS:", fallas)
    sys.exit(1)
