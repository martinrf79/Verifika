"""EL PEDIDO — lo que el cliente pidio, como estado que maneja el codigo (1-oct-2026).

POR QUE EXISTE. Un pedido como el del 70/30 —seis articulos, tres destinos y
un teclado que no estaba en la lista— se resolvia en un solo turno, y cuando
el interprete entendia mal, el error salia directo en el presupuesto. Ahora,
si el codigo ve que lo repartido no cierra con lo pedido, no calcula: guarda
el pedido y le pregunta al cliente si entendio bien. Con el si, calcula.

LO QUE SE GUARDA SON LAS PIEZAS, la misma estructura validada que corre el
codigo. Confirmar es volver a correr exactamente eso: el modelo no lo
reescribe, asi que lo que el cliente aprobo es lo que se cuenta. Vive en
`pedido_pendiente` de la conversacion; `{}` lo borra.

Se confirma UNA vez por pedido: si el cliente corrige, se cuenta con la
correccion y no se vuelve a preguntar. Asi no hay vuelta en circulo.
"""
import copy

# Lo que un pedido guardado reemplaza al confirmarse: lo demas del mensaje
# —una politica, una pregunta suelta— se contesta igual.
DEL_PEDIDO = ("buscar", "cuenta", "producto", "comprar", "envio")


def guardar(piezas: list, avisos: dict) -> dict:
    """El pedido a confirmar: las piezas tal como el codigo las iba a correr,
    antes de cualquier reemplazo, y lo que no cerro."""
    return {"piezas": copy.deepcopy([p for p in piezas if p.get("tipo") in DEL_PEDIDO]),
            "avisos": copy.deepcopy(avisos or {})}


def pendiente(pedido) -> dict:
    """El pedido guardado si hay uno esperando el si del cliente; si no, {}."""
    return pedido if isinstance(pedido, dict) and pedido.get("piezas") else {}


def retomar(pedido: dict, piezas_del_turno: list) -> list:
    """Las piezas guardadas, y del mensaje nuevo solo lo que no es del pedido.
    Los numeros del mensaje nuevo se corren para que no choquen con los
    guardados en depende_de."""
    otras = [dict(p, n=int(p.get("n") or 0) + 100,
                  depende_de=[int(d) + 100 for d in p.get("depende_de") or []])
             for p in piezas_del_turno if p.get("tipo") not in DEL_PEDIDO]
    return copy.deepcopy(pedido["piezas"]) + otras


def resumen(piezas: list) -> dict:
    """Lo que el bot entendio, para que el redactor lo diga sin plata: que va
    a cada destino, las condiciones y el reparto."""
    destinos = []
    for p in piezas:
        if p.get("tipo") != "cuenta":
            continue
        items = [f"{int(i.get('cantidad') or 1)} {i.get('producto')}" for i in p.get("items") or []
                 if isinstance(i, dict)]
        destinos.append({"destino": (p.get("destinos") or [p.get("texto") or ""])[0], "lleva": items})
    condiciones = list(dict.fromkeys(
        f"{c.get('campo')} {c.get('operador')} {c.get('valor')}" for p in piezas if p.get("tipo") == "buscar"
        for c in p.get("condiciones") or [] if isinstance(c, dict)))
    reparto = next((p.get("reparto_pago") for p in piezas if p.get("reparto_pago")), None)
    out = {"por_destino": destinos}
    if condiciones:
        out["condiciones"] = condiciones
    if reparto:
        out["reparto_sobre_el_total"] = [f"{r.get('porcentaje')}%" for r in reparto if isinstance(r, dict)]
    return out
