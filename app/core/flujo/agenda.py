"""LA AGENDA — lo que cumple el ejecutor: una pregunta por cada cosa que pide el cliente (20-oct-2026).

Desde el 22-oct no la escribe el modelo: el modelo llena la ficha nativa y `ficha.a_agenda` la lleva a esta forma, FICHA
76. Cada pregunta tiene UNA accion de un menu cerrado con sus datos; las agendas a mano de `banco_pruebas/agendas58.py`
son la vara del ejecutor.

  {"preguntas": [{"n": 1, "cita": "las palabras literales", "accion": "buscar", ...los datos de la accion,
                  "si": {"de": 2, "da": "si"|"no"}, "responde": "R-1"}],
   "cliente": {"es", "nombre", "localidad", "equipo"}}

Lo que el modelo senala de la charla lo senala con el numero de la libreta —M-2 lo mostrado, L-1 un renglon del borrador, R-1 la
repregunta abierta—, que arma el codigo en `interprete.libreta`. Asi no reescribe nombres ni reconstruye la charla.
"""
import re
import unicodedata

ACCIONES = {
    "buscar": 'productos sin modelo concreto, uno por rubro. "rubro" de la lista; "cantidad"; "orden": "mas barato" '
              '—economico, "de acuerdo a la crisis"—, "mas caro" —lo mejor—, "mas <dato>" o "nada"; "condiciones" '
              'en palabras del cliente —marca, color, precio unitario, "que no sea X"—; "entre_lo_mostrado" true si elige '
              'entre lo mostrado. Las exclusiones de la libreta van en cada busqueda. Con pedido en la '
              'libreta, otro orden para todo: rubro "el pedido".',
    "producto": 'un modelo concreto. "producto" es lo que dijo el cliente, o el numero de la libreta si lo senala: "M-2". '
                'Si lo que senala puede ser varios, la lista: ["M-1", "M-2"], y el codigo pregunta. "quiere_saber": precio, '
                'stock o el dato que pide; "color" si lo dijo; "afirma" lo que da por cierto del producto.',
    "envio": '"destino" a cotizar, con las palabras del cliente.',
    "cuenta": 'pide sumar o presupuesto. "tope": un monto, del total si son varios; "si_pasa" lo que saca si el total lo pasa; '
              '"reparto" [{"medio", "porcentaje"}] si dice como paga —sin medio, "sin decir"—.',
    "politica": 'una regla de la tienda: "tema" de la lista; "afirma" lo que da por cierto de ella.',
    "compatibilidad": 'si un producto anda con algo: "producto", "con"; "falta_modelo" true si es un equipo suyo sin '
                      'modelo, "mi notebook".',
    "comprar": 'lo que decide llevar, o la lista con cantidades y destinos. Solo el cambio de este '
               'mensaje: "agrega" [{"producto", "cantidad", "color", "destino"}] —un modelo, un "M-2", un rubro o "los '
               'otros", que sin cantidad es lo que queda de la lista—; "saca" ["L-1"]; "cambia" [{"es": "L-1", y producto, '
               'cantidad, color o destino}]; "confirma" ["L-2"] si dice que si a lo que falta confirmar; "acepta" ["L-2"] '
               'si acepta lo SUPUESTO; "total" si dice cuantos son; "reemplaza" true si rehace el pedido y '
               '"agrega" es como queda; "reparto" como en cuenta.',
    "explicar": 'saber general de tecnologia, no de la tienda: "pregunta".',
    "otro": '"que": saludo, dato —lo que dice de si mismo, que va en "cliente"—, corrige —lo que retiro '
            'en el mensaje—, humano, fuera_de_tema o catalogo.',
}

# Lo que cada accion necesita para que el codigo la pueda cumplir.
OBLIGATORIO = {"buscar": "rubro", "producto": "producto", "envio": "destino", "politica": "tema",
               "compatibilidad": "producto", "explicar": "pregunta", "otro": "que"}

_REF = re.compile(r"^[MLR]-\d+$")

# Palabras que no piden nada: una cita hecha solo de estas, y de las que afirman, es un si.
_VACIAS = set("a al algo con de del el en es esta este la las lo los me mi o para pero por que se si su te tu un una "
              "uno unos unas y ya ah eh bueno che hola buenas gracias porfa favor dale ok".split())


def palabras(t: str) -> list:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return re.findall(r"[a-z0-9]+", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def preguntas(agenda) -> list:
    p = agenda.get("preguntas") if isinstance(agenda, dict) else agenda
    return [x for x in p or [] if isinstance(x, dict)]
