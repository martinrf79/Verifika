"""
BANCO — SOLVER SIN HERRAMIENTAS (21-jul, pedido de Martin).

La foto del OTRO extremo: Gemini respondiendo SOLO, con el prompt y el
CONTEXTO LLENO en el mensaje (catalogo entero + FAQ), sin una sola tool
determinista, sin guardas, sin sellado. La tesis a probar: con el dato en
contexto, el modelo responde bien la prosa y el razonamiento; a ver DONDE
alucina igual (numeros, productos, politica) aunque el dato este delante.

No es el sistema final. Es la medicion cruda para decidir que atar y que no.

Uso:  python3 banco_pruebas/banco_solver_sin_tools.py
Corre sobre el catalogo y la FAQ REALES del repo (sim_firestore). Espacia las
llamadas para no pasar el limite por minuto de la key gratis de Gemini.
"""
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install

TIENDA = "verifika_prod"
_PACE_SEG = float(os.getenv("BANCO_PACE_SEG", "6"))

# Los MISMOS escenarios de area que el banco de solver con tools, para comparar
# manzana con manzana: venta, multiproducto, ficha, FAQ, envio, objecion,
# pregunta abierta, desconfianza, cierre.
CASOS = [
    ("venta simple", "quiero el mouse mas barato con stock"),
    ("venta multiproducto",
     "quiero 2 mouse y 2 teclados los mas baratos con envio a Cordoba capital"),
    ("ficha mixta",
     "que precio tienen 2 teclados y 2 mouse los mas baratos? y decime "
     "procedencia, garantia y materiales"),
    ("FAQ pago/factura", "hacen factura A? se puede en cuotas?"),
    ("envio", "llegan a Salta capital? cuanto sale?"),
    ("objecion precio",
     "me parece caro el mouse mas barato, no tenes algo mejor?"),
    ("pregunta abierta",
     "el teclado mas barato sirve para escribir todo el dia en la oficina?"),
    ("desconfianza", "son originales los productos? es seguro comprar?"),
    ("cierre", "dale, me lo llevo, como sigo?"),
]


def _money(n):
    try:
        return int(n)
    except (TypeError, ValueError):
        return None


def _linea_producto(p):
    campos = [str(p.get("id") or ""), str(p.get("nombre") or ""),
              str(p.get("categoria") or "")]
    precio = _money(p.get("precio_ars"))
    campos.append(f"${precio}" if precio is not None else "$?")
    campos.append(f"stock {p.get('stock', '?')}")
    origen = str(p.get("origen") or "").strip()
    if origen:
        campos.append(f"origen {origen}")
    gar = str(p.get("garantia_detalle") or p.get("garantia") or "").strip()
    if gar:
        campos.append("garantia " + gar[:50])
    desc = str(p.get("descripcion") or "").strip()
    if desc:
        campos.append(desc[:70])
    return " | ".join(campos)


def _contexto_lleno(productos, faq):
    lineas = ["CATALOGO COMPLETO (id | nombre | categoria | precio | stock | "
              "origen | garantia | descripcion):"]
    for p in productos:
        lineas.append("- " + _linea_producto(p))
    lineas.append("\nFAQ / POLITICAS DE LA TIENDA:")
    for tema, data in (faq or {}).items():
        if not isinstance(data, dict):
            continue
        resp = str(data.get("respuesta") or data.get("texto") or "").strip()
        if resp:
            lineas.append(f"- {tema}: {resp[:220]}")
    return "\n".join(lineas)


_SYSTEM = (
    "Sos el vendedor por WhatsApp de Verifika Tech, tienda argentina de "
    "tecnologia, 100% online, entrega solo por envio. Voseo, calido, directo, "
    "vendedor de verdad. Tu meta es VENDER y responder TODO lo que el cliente "
    "pregunta, con tu propia voz.\n\n"
    "REGLA: los datos duros (precios, stock, nombres de producto, origen, "
    "garantia, materiales, politica de pago o envio) SOLO pueden salir del "
    "CONTEXTO de abajo. Si un dato no esta en el contexto, no lo inventes: "
    "decilo con honestidad. No prometas dias exactos de entrega ni retiro en "
    "local. Cerra siempre invitando a avanzar con la compra. Contesta en texto "
    "natural de WhatsApp, sin markdown pesado.")


def _gemini(contexto, mensaje):
    from openai import OpenAI
    key = os.environ.get("GEMINI_API_KEY")
    c = OpenAI(api_key=key,
               base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    prompt = (_SYSTEM + "\n\n" + contexto + "\n\nMensaje del cliente:\n"
              + mensaje + "\n\nRedacta la respuesta.")
    r = c.chat.completions.create(
        model=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5, max_tokens=700,
        extra_body={"reasoning_effort": "none"})
    return (r.choices[0].message.content or "").strip()


_RE_PRECIO = re.compile(r"\$\s?([\d][\d.]{2,})")


def _precios_inventados(texto, precios_reales):
    """Numeros con signo $ en la respuesta que NO son un precio real del
    catalogo. Sonda barata de alucinacion de plata (no cuenta totales sumados,
    que legitimamente no estan en el catalogo)."""
    fuera = []
    for m in _RE_PRECIO.findall(texto or ""):
        val = _money(m.replace(".", ""))
        if val is None or val < 1000:
            continue
        if val not in precios_reales:
            fuera.append(val)
    return fuera


def main():
    info = install()
    from app.storage.firestore_client import get_all_products, get_all_faq
    productos = get_all_products(tienda_id=TIENDA)
    faq = get_all_faq(tienda_id=TIENDA)
    precios_reales = {_money(p.get("precio_ars")) for p in productos
                      if _money(p.get("precio_ars")) is not None}
    contexto = _contexto_lleno(productos, faq)
    print(f"[solver-sin-tools] {len(productos)} productos, {len(faq)} FAQ. "
          f"Contexto ~{len(contexto)//4} tokens. Gemini responde SOLO, sin "
          "tools ni guardas.\n" + "=" * 72)
    for i, (nombre, mensaje) in enumerate(CASOS, 1):
        if i > 1:
            time.sleep(_PACE_SEG)
        resp = None
        for intento in range(3):
            try:
                resp = _gemini(contexto, mensaje)
                break
            except Exception as e:
                if "429" in str(e) and intento < 2:
                    time.sleep(30 * (intento + 1))
                    continue
                print(f"\n### [{i}] {nombre}\nERROR: {str(e)[:160]}")
                break
        if resp is None:
            continue
        inventados = _precios_inventados(resp, precios_reales)
        flag = f"  [PRECIO FUERA DE CATALOGO: {inventados}]" if inventados else ""
        print(f"\n### [{i}] {nombre}{flag}")
        print(f"Cliente: {mensaje}")
        print(f"Gemini:  {resp}")
    print("\n" + "=" * 72)


if __name__ == "__main__":
    main()
