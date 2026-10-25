"""EL MOTOR DE RESPUESTAS — el dato lo escribe el codigo, el vendedor agrega el gancho, 25-oct-2026, FICHA 80.

La respuesta de un caso se arma en dos partes, y ninguna la escribe el modelo:

  el dato    lo que devolvio el ejecutor, en palabras de `app/core/flujo/redaccion.py`. Es el camino vivo: el motor no
             tiene otra redaccion de los datos, asi un precio o un plazo sale igual aca y en WhatsApp.
  el gancho  lo que agrega un vendedor despues del dato para que la venta siga: reservar, preguntar el uso, ofrecer lo
             parecido. Sale del caso, por el veredicto, o del gancho de su herramienta. No lleva numeros ni nombres de
             producto: el dato ya los dijo. Las estrategias son las de INSPIRED y las movidas de la base de conocimiento.

Si el codigo ya pregunta algo, no va gancho: una sola pregunta por mensaje.
"""
import re

from app.core.flujo import catalogo as K
from app.core.flujo import redaccion
from app.core.flujo.interprete import NUNCA_PIDE

# Lo que salio del ejecutor, en una palabra: de esto depende el gancho.
VEREDICTOS = ("ok", "no_hay", "no_existe", "no_vende", "sin_dato", "sin_politica", "pregunta", "nada")

GANCHOS = {
    "producto": {"ok": "¿Te lo reservo?", "no_hay": "Si querés, te muestro otro parecido que sí tengo.",
                 "no_existe": "¿Querés que te muestre lo que tengo parecido?",
                 "sin_dato": "Si me contás para qué lo necesitás, te digo si te sirve."},
    "buscar": {"ok": "¿Para qué lo vas a usar? Así te digo cuál te conviene.",
               "no_hay": "Con eso justo no tengo; ¿qué es lo que más te importa?",
               "no_vende": "Eso no lo vendemos. Si me contás para qué lo querés, te busco algo que sí tengamos."},
    "comprar": {"ok": "¿Sumamos algo más o lo dejamos así?"},
    "cuenta": {"ok": "Si está bien así, decime tu nombre y te lo reservo."},
    "politica": {"ok": "¿Qué producto estás mirando?", "sin_politica": "Eso no lo tengo escrito; te paso con alguien "
                                                                    "del equipo si querés."},
    "envio": {"ok": "¿Qué producto querés que te mande?"},
    "compatibilidad": {"ok": "¿Te lo reservo?"},
    "explicar": {"ok": "Si querés, te muestro opciones."},
    "otro": {},
}


CON_PEDIDO = {"politica": "¿Seguimos con tu pedido?", "envio": "¿Seguimos con tu pedido?",
              "explicar": "¿Seguimos con tu pedido?", "producto": "¿Lo sumo al pedido?"}


def veredicto(t) -> str:
    """El veredicto del turno, de los hechos del ejecutor."""
    if t.preguntas:
        return "pregunta"
    tipos = [h["tipo"] for h in t.hechos]
    for v in ("no_existe", "no_vende", "sin_politica"):
        if v in tipos:
            return v
    for h in t.hechos:
        if h["tipo"] == "producto" and not K.con_stock(h["producto"]):
            return "no_hay"
        if h["tipo"] == "producto" and (h.get("dato") or {}).get("campo") and not h["dato"].get("valor"):
            return "sin_dato"
        if h["tipo"] == "lista" and (h["vacio_por"] or not h["filas"]):
            return "no_hay"
    return "ok" if tipos else "nada"


# El hecho que manda en el gancho: lo ultimo que cambio para el cliente. Con la cuenta a la vista, el gancho es el de
# cerrar, aunque el caso haya empezado por una busqueda.
MANDA = (("cuenta", "cuenta"), ("pedido", "comprar"), ("lista", "buscar"), ("producto", "producto"),
         ("compat", "compatibilidad"), ("envio", "envio"), ("politica", "politica"), ("explicar", "explicar"))


def gancho(caso: dict, herramienta: str, v: str, t=None, dato: str = "") -> str:
    """El gancho del caso por su veredicto; si no tiene, el del hecho que manda. Nada si el codigo ya pregunta o si
    el dato ya termina en pregunta, como la FAQ curada: una sola pregunta por mensaje."""
    if v == "pregunta" or dato.rstrip().endswith("?"):
        return ""
    if caso["gancho"].get(v):
        return caso["gancho"][v]
    tipos = [h["tipo"] for h in t.hechos] if t else []
    de = next((h for tipo, h in MANDA if tipo in tipos), herramienta.split(":")[0])
    if t and t.estado["pedido"] and de in CON_PEDIDO and v == "ok":
        # CON EL PEDIDO ARMADO no se le pregunta que esta mirando: se vuelve al pedido.
        return CON_PEDIDO[de]
    return GANCHOS.get(de, {}).get(v, "")


def gancho_valido(texto: str) -> bool:
    """Un gancho no da datos ni pide lo que el bot nunca pide."""
    return not re.search(r"\d", texto) and not NUNCA_PIDE.search(K.n(texto))


def responder(caso: dict, herramienta: str, t) -> dict:
    v = veredicto(t)
    dato = redaccion.texto(t.hechos, t.preguntas, False)
    g = gancho(caso, herramienta, v, t, dato)
    return {"veredicto": v, "dato": dato, "gancho": g, "texto": "\n\n".join(x for x in (dato, g) if x)}
