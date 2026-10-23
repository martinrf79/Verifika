"""EL ESTADO DE LA CHARLA — uno solo, lo escribe el codigo (19-oct-2026).

Es lo unico que pasa de un turno al siguiente, ademas del historial. Vive en el documento de la charla, en el campo
`estado_charla`, y tiene estas partes:

  mostrados   lo que el cliente leyo, en orden, con id, nombre y precio. Las referencias salen de aca.
  borrador    lo que dijo el cliente: renglones, lista por rubro, criterios, total, pago, cliente y cierre. Es la verdad
              de todo lo que la charla construye, FICHA 71: `borrador.py`.
  pedido      lo resuelto del borrador, re-derivado en cada turno: id, nombre, cantidad y destino. No se escribe a mano.
  busqueda    la ultima busqueda: rubro, condiciones en palabras y orden.
  abiertas    lo que el vendedor pregunto y el cliente no contesto: [{"texto", "cita", "espera"}]. Es la R de la
              libreta: la respuesta del turno siguiente se ata a la pregunta que la pidio. "espera" dice que respuesta
              sirve —{"tipo": "equipo", "producto", "con", "opciones"}, o {"tipo": "color", "cual" o "si_no",
              "opciones", "hace"}— y `ejecutor.atar_esperas` la controla. El nombre pedido no se guarda: se deriva.
"""
from app.core.calculadora import _money as _plata

VACIO = {"mostrados": [], "pedido": [], "busqueda": {}, "abiertas": [], "borrador": {}}
TOPE_MOSTRADOS = 30


def leer(conv: dict) -> dict:
    guardado = (conv or {}).get("estado_charla") or {}
    out = {k: guardado.get(k, type(v)()) for k, v in VACIO.items()}
    if not guardado.get("borrador") and guardado.get("pedido"):
        out["borrador"] = _de_antes(guardado)
    return out


def _de_antes(g: dict) -> dict:
    """UNA CHARLA EMPEZADA ANTES DEL BORRADOR no pierde su pedido: cada articulo pasa a un renglon dicho y confirmado."""
    renglones = [{"L": f"L-{i}", "que": a.get("nombre") or "", "cantidad": a.get("cantidad") or 1, "color": "",
                  "destino": a.get("destino") or "", "condicion": "", "cita": "", "confirmado": True}
                 for i, a in enumerate(g["pedido"], 1)]
    return {"renglones": renglones, "lista": g.get("por_rubro") or {}, "pago": g.get("reparto") or [],
            "cliente": g.get("cliente") or {}, "siguiente": len(renglones) + 1,
            "cierre": {"huella": g.get("cerrado") or "", "nombre_para": "", "lead": ""}}


def mostrar(estado: dict, filas: list) -> None:
    """Suma al final lo que el cliente acaba de leer. Si ya estaba, pasa al final: es lo mas reciente."""
    ids = {str(f["id"]) for f in filas}
    viejos = [m for m in estado["mostrados"] if str(m["id"]) not in ids]
    nuevos = [{"id": str(f["id"]), "nombre": f.get("nombre") or "", "precio": _plata(f.get("precio_ars"))}
              for f in filas]
    estado["mostrados"] = (viejos + nuevos)[-TOPE_MOSTRADOS:]
