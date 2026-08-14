"""
EL PESO DE LA CADENA — que hace cada pieza que reescribe el mensaje, medido.

POR QUE EXISTE (Martin, 14-ago-2026): *"veo al sistema con montones de
herramientas que tal vez hacen lo mismo, que se pisan"*. Tiene razon y el
sintoma esta medido en el log del 13-ago: en UN turno intervinieron cuatro
piezas en cascada -602 a 339, a 302, a 158, y de vuelta a 212- sin que ninguna
supiera lo que hizo la anterior, y el mensaje termino MAS largo de donde venia.

PERO RECORTAR A OJO ES COMO SE ROMPE LA RESPUESTA, y este repo ya lo pago dos
veces: el tope por caracteres tiro una nota de 55 a 23, y una poda borro la
oracion de otro producto. Antes de sacar una pieza hay que saber QUE hace y
CUANTO se pisa con las demas. Eso es este banco.

QUE MIDE, y son las tres preguntas que decide el recorte:

  CUANTAS VECES INTERVIENE cada pieza sobre el corpus. Una que no interviene
      NUNCA es candidata a borrarse: no esta protegiendo nada.
  CUANTO CAMBIA EL LARGO cada una. La que solo suma caracteres esta peleando
      con la prioridad dos.
  CON QUIEN SE PISA. Dos piezas que intervienen sobre los MISMOS mensajes son
      candidatas a fusionarse, y ese es el numero que Martin viene pidiendo.

LA LISTA DE PIEZAS NO ESTA ESCRITA ACA: sale de `grafo.barribles()`, o sea del
cableado declarado. Una pieza nueva entra a la medicion por existir.

EL CORPUS TAMPOCO SE ESCRIBE: es el mismo que ya usa
`tests/test_grafo_cableado.py` -un turno sano y las once formas en que el
modelo lo ensucia, en los dos regimenes del turno-, generado sobre la cuenta
real que calcula la calculadora con el catalogo real.

ESTO NO RECORTA NADA. Mide para que el recorte se pueda hacer con un numero
adelante y otro atras. Correrlo antes y despues de fusionar dos piezas es la
unica forma de probar que la fusion no se llevo puesto un comportamiento.

CORRE OFFLINE Y GRATIS: cero llamadas al modelo, cero credenciales.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"


def _contexto(con_cuenta: bool = True) -> dict:
    """El turno real sobre el que se mide. Se genera con la calculadora y el
    catalogo de verdad: si mañana cambia el formato de la cuenta, el corpus
    cambia solo y la medicion sigue valiendo."""
    from app.core.contexto_turno import set_current_tienda
    from app.core import estado_venta
    from app.core.calculadora import calculate_total
    from app.storage.firestore_client import get_all_products

    set_current_tienda(TIENDA)
    prods = [p for p in get_all_products(tienda_id=TIENDA)
             if p.get("stock", 0) >= 3 and p.get("precio_ars")]
    prods.sort(key=lambda p: p["precio_ars"])
    dos = [prods[10], prods[len(prods) // 2]]
    estado_venta._envio_localidades.set([])
    estado_venta.set_envio_localidad("Cordoba, provincia de Cordoba")
    r = calculate_total(
        items=[{"product_id": p["id"], "cantidad": c}
               for c, p in zip((1, 2), dos)],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}])
    if not r.get("ok"):
        raise RuntimeError(f"no se pudo armar la cuenta del corpus: {r}")
    bloque = r["presentacion"]
    llamadas = [{"herramienta": "armar_presupuesto", "pedido": {},
                 "resultado": {"estado": "ok", "bloque": bloque,
                               "total_ars": r["total_ars"]}}]
    for p in dos:
        llamadas.append({"herramienta": "buscar_productos",
                         "pedido": {"categoria": p.get("categoria", ""),
                                    "descripcion": p.get("nombre", "")},
                         "resultado": {"estado": "ok", "productos": [p]}})
    if not con_cuenta:
        llamadas = llamadas[1:]
        bloque = ""
    return {"llamadas": llamadas, "bloque": bloque, "tienda_id": TIENDA,
            "trace_id": "peso-cadena", "previo": "", "vistos": dos,
            "negocio": "Verifika", "mensaje": "cuanto sale todo junto?",
            "anterior": "", "vocabulario": {p["nombre"] for p in prods},
            "productos": dos, "declarado": {}, "memoria": [], "hallazgo": ""}


def _corpus(ctx: dict) -> list:
    """Un turno sano y las formas en que el modelo lo ensucia. Es el mismo
    corpus del barrido del cableado, para que los dos midan lo mismo."""
    bloque = ctx["bloque"] or "Total: $100.000"
    nombre = ctx["productos"][0]["nombre"]
    return [
        f"Perfecto, te armo la cuenta.\n\n{bloque}\n\n¿Te lo mando a Cordoba?",
        "Tenemos ese modelo en stock. ¿Querés que te arme el presupuesto?",
        f"**Te paso el detalle:**\n\n{bloque}\n\n*Avisame*",
        '{"herramienta": "buscar_productos", "args": {}}\n'
        f"Encontre esto:\n{bloque}",
        f"El <d MOU0023>{nombre}</d> esta disponible.\n{bloque}",
        f"{bloque}\n\nReparto de los envios:\n\n¿Confirmamos?",
        "Te confirmo que el envio a Cordoba capital sale $7.500.\n"
        "Te confirmo que el envio a Cordoba capital sale $7.500.\n" + bloque,
        f"{bloque}\n\nY te hago un descuento especial de $99.999.",
        f"{bloque}\n\n{bloque}",
        "El sistema me indica que hay varios modelos distintos, "
        f"asi que te paso lo que encontre.\n{bloque}",
        "Te paso el presupuesto por los dos productos:",
        "Hola",
    ]


def medir() -> dict:
    """{nodo: {veces, delta, mensajes}} y los pares que se pisan."""
    from app.verifika import grafo as G

    nodos = G.barribles()
    veces, delta, tocados = {}, {}, {}
    corridas = 0
    for con_cuenta in (True, False):
        ctx = _contexto(con_cuenta)
        for i, texto in enumerate(_corpus(ctx)):
            corridas += 1
            clave = (con_cuenta, i)
            for n in nodos:
                try:
                    salida = n.aplicar(texto, ctx)
                except Exception:  # noqa: BLE001 — lo reporta el otro barrido
                    continue
                if salida is None or salida == texto:
                    continue
                veces[n.id] = veces.get(n.id, 0) + 1
                delta[n.id] = delta.get(n.id, 0) + (len(salida) - len(texto))
                tocados.setdefault(n.id, set()).add(clave)

    # LOS QUE SE PISAN: dos piezas que intervienen sobre los MISMOS mensajes.
    # No prueba que hagan lo mismo -eso lo dice leerlas- pero dice DONDE mirar,
    # que es lo que hoy no existe y por eso el recorte se hacia a ojo.
    pisan = []
    ids = sorted(tocados)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            x, y = ids[a], ids[b]
            comun = tocados[x] & tocados[y]
            if not comun:
                continue
            union = tocados[x] | tocados[y]
            pisan.append({"a": x, "b": y, "juntos": len(comun),
                          "solapamiento": round(100.0 * len(comun) / len(union), 1)})
    pisan.sort(key=lambda p: (-p["solapamiento"], -p["juntos"]))

    return {"nodos": len(nodos), "corridas": corridas,
            "veces": veces, "delta": delta,
            "nunca": sorted(n.id for n in nodos if n.id not in veces),
            "pisan": pisan}


def main() -> int:
    from banco_pruebas.sim_firestore import install
    from app.core.contexto_turno import set_current_tienda
    install()
    set_current_tienda(TIENDA)

    r = medir()
    print("=" * 74)
    print("EL PESO DE LA CADENA — que hace cada pieza que reescribe el mensaje")
    print("=" * 74)
    print(f"  piezas medidas: {r['nodos']}   mensajes del corpus: "
          f"{r['corridas'] // max(1, r['nodos']) if False else r['corridas']}\n")
    print(f"  {'pieza':26} {'interviene':>10} {'caracteres':>12}")
    for nodo, n in sorted(r["veces"].items(), key=lambda x: -x[1]):
        d = r["delta"][nodo]
        print(f"  {nodo:26} {n:>10} {d:>+12}")
    if r["nunca"]:
        print(f"\n  NUNCA INTERVIENEN sobre este corpus, candidatas a mirar de "
              f"cerca:\n    {', '.join(r['nunca'])}")
    print("\n  LAS QUE SE PISAN — intervienen sobre los MISMOS mensajes.")
    print("  No prueba que hagan lo mismo: dice DONDE mirar antes de fusionar.")
    for p in r["pisan"][:12]:
        print(f"    {p['a']:24} + {p['b']:24} {p['juntos']:>3} mensajes  "
              f"{p['solapamiento']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
