"""LA AGENDA — lo que devuelve el interprete: una pregunta por cada cosa que pide el cliente (20-oct-2026).

Reemplaza a las diecinueve casillas de la ficha 10. El modelo ya no llena un formulario: corta el mensaje en
preguntas, en el orden del cliente, y a cada una le pone UNA accion de un menu cerrado con sus datos. Asi cada pedazo
del mensaje tiene su lugar, y el codigo puede controlar que ninguno quede sin respuesta.

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
              'en palabras del cliente —marca, color, tope de precio, "que no sea X"—; "entre_lo_mostrado" true si elige '
              'entre lo mostrado. Las exclusiones de la libreta van en cada busqueda. Otro orden para lo '
              'pedido —"todo lo mejor"—: rubro "lo pedido".',
    "producto": 'un modelo concreto. "producto" es lo que dijo el cliente, o el numero de la libreta si lo senala: "M-2". '
                'Si lo que senala puede ser varios, la lista: ["M-1", "M-2"], y el codigo pregunta. "quiere_saber": precio, '
                'stock o el dato que pide; "color" si lo dijo; "afirma" lo que da por cierto del producto.',
    "envio": '"destino" a cotizar, con las palabras del cliente.',
    "cuenta": 'pide sumar o presupuesto. "tope" si pone un monto; "si_pasa" lo que saca si el total lo pasa; '
              '"reparto" [{"medio", "porcentaje"}] si dice como paga —sin medio, "sin decir"—.',
    "politica": 'una regla de la tienda: "tema" de la lista; "afirma" lo que da por cierto de ella.',
    "compatibilidad": 'si un producto anda con algo: "producto", "con"; "falta_modelo" true si es un equipo suyo sin '
                      'modelo —"mi notebook"—.',
    "comprar": 'lo que decide llevar, o la lista con cantidades y destinos para el presupuesto. Solo el cambio de este '
               'mensaje: "agrega" [{"producto", "cantidad", "color", "destino"}] —un modelo, un "M-2", un rubro o "los '
               'otros", que sin cantidad es lo que queda de la lista—; "saca" ["L-1"]; "cambia" [{"es": "L-1", y producto, '
               'cantidad, color o destino}]; "confirma" ["L-2"] si dice que si a lo que falta confirmar; "acepta" ["L-2"] '
               'si acepta lo SUPUESTO; "total" si dice cuantos son; "reemplaza" true si rehace el pedido y '
               '"agrega" es como queda; "reparto" como en cuenta.',
    "explicar": 'saber general de tecnologia, no de la tienda: "pregunta".',
    "otro": '"que": saludo, dato —lo que dice de si mismo, que va en "cliente"—, corrige —lo que retiro en el mismo '
            'mensaje—, humano, fuera_de_tema o catalogo.',
}

# Lo que cada accion necesita para que el codigo la pueda cumplir.
OBLIGATORIO = {"buscar": "rubro", "producto": "producto", "envio": "destino", "politica": "tema",
               "compatibilidad": "producto", "explicar": "pregunta", "otro": "que"}

_REF = re.compile(r"^[MLR]-\d+$")

# Palabras que no piden nada: si quedan sin citar no falta nada.
_VACIAS = set("a al algo con de del el en es esta este la las lo los me mi o para pero por que se si su te tu un una "
              "uno unos unas y ya ah eh bueno che hola buenas gracias porfa favor dale ok".split())


def palabras(t: str) -> list:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return re.findall(r"[a-z0-9]+", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def preguntas(agenda) -> list:
    p = agenda.get("preguntas") if isinstance(agenda, dict) else agenda
    return [x for x in p or [] if isinstance(x, dict)]


def sin_citar(mensaje: str, agenda) -> list:
    """Los pedazos del mensaje que ninguna pregunta cita."""
    citadas = {w for p in preguntas(agenda) for w in palabras(p.get("cita"))}
    sueltos, tira = [], []
    for w in palabras(mensaje) + [""]:
        if w and w not in citadas:
            tira.append(w)
            continue
        if any(x not in _VACIAS for x in tira):
            sueltos.append(" ".join(tira))
        tira = []
    return sueltos


def referencias(p: dict) -> list:
    """Los numeros de la libreta que nombra una pregunta, en cualquiera de sus datos."""
    out = []

    def mirar(v):
        if isinstance(v, str) and _REF.match(v.strip()):
            out.append(v.strip())
        elif isinstance(v, list):
            [mirar(x) for x in v]
        elif isinstance(v, dict):
            [mirar(x) for x in v.values()]
    mirar({k: v for k, v in p.items() if k not in ("cita", "n")})
    return out


def faltas(mensaje: str, agenda, numeros: set) -> list:
    """Lo que el codigo no podria cumplir, en palabras para devolverselo al modelo una vez."""
    out = [f'Este pedazo del mensaje no esta en ninguna pregunta: "{s}".' for s in sin_citar(mensaje, agenda)]
    ns = {p.get("n") for p in preguntas(agenda)}
    for p in preguntas(agenda):
        acc, n = p.get("accion"), p.get("n")
        if acc not in ACCIONES:
            out.append(f"La pregunta {n} tiene la accion \"{acc}\", que no esta en el menu.")
            continue
        if acc in OBLIGATORIO and p.get(OBLIGATORIO[acc]) in (None, "", []):
            out.append(f"La pregunta {n} es {acc} y no tiene \"{OBLIGATORIO[acc]}\".")
        out += [f"La pregunta {n} senala {r}, que no esta en la libreta." for r in referencias(p) if r not in numeros]
        si = p.get("si")
        if isinstance(si, dict) and si.get("de") not in ns:
            out.append(f"La pregunta {n} depende de la pregunta {si.get('de')}, que no existe.")
    if not preguntas(agenda) and palabras(mensaje):
        out.append("No hay ninguna pregunta.")
    return out
