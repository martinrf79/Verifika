"""
EL PEDIDO COMO OBJETO, Y EL RECONCILIADOR.

POR QUE EXISTE (Martin, 2-ago-2026). El sistema tenia diecinueve controles
-nueve invariantes en el juez, diez funciones `_sin_algo` en el hub- y los
diecinueve miraban la PROSA ya escrita. Cero miraban la DECISION. La prosa es
un espacio infinito: cada error nuevo llega con otras palabras y obliga a un
parche nuevo, para siempre. Eso fue el loop de meses.

La decision, en cambio, es un objeto chico y tipado. Se chequea de forma
general, UNA vez, para todos los casos.

EL CASO QUE LO PARIO, medido el 2-ago sobre un mensaje real:
  "Dame precio de dos auriculares, dos mouse y dos memorias... que lleven las
   menos partes chinas posibles... un auricular y un mouse a Cordoba capital,
   un teclado y un mouse a Concordia, los otros dos a posadas... divide el
   presupuesto en setenta treinta."
El bot cotizo CUATRO categorias sobre un pedido de tres, metio un teclado que
el cliente solo habia nombrado al hablar del envio, borro un auricular para
hacerle lugar, ignoro el filtro de origen que la herramienta ofrece, y ordeno
por el mas caro a partir de "el precio no seria tan importante". Los nueve
invariantes dijeron LIMPIO, porque ninguna de las cuatro fallas es una mentira
sobre el catalogo. Son fallas de DECISION.

COMO FUNCIONA. El modelo declara lo que entendio llamando a `registrar_pedido`
-una herramienta mas, con su esquema- y despues pide las herramientas que le
parecen. El codigo compara las dos cosas:

    lo que dijo que entendio   contra   lo que efectivamente pidió

Cuando no coinciden, el codigo hace UNA de dos cosas y nunca una tercera:
  1. le devuelve al modelo el faltante concreto para la vuelta siguiente, o
  2. si el pedido tiene una CONTRADICCION, obliga a preguntarle al cliente.

Nunca inventa la pieza que falta ni deja pasar. Es el mismo mecanismo del
veredicto `ambiguo` del certificador -que ya funciona hace meses para la
identidad del producto- extendido al pedido entero.

El reconciliador NO sabe de teclados ni de China. Sabe que el cliente nombro
tres categorias y el plan busco cuatro, y que una restriccion declarada no
viaja en ningun argumento. Por eso caza la CLASE y no el caso.
"""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _stems(valor: str) -> list[str]:
    """Mismas raices que usa `herramientas._excluido`, para que lo que el
    reconciliador considera 'presente' sea lo mismo que el filtro considera
    aplicado. Si las dos definiciones divergen, el chequeo miente."""
    return [w[:4] for w in _norm(valor).split() if len(w) >= 4]


# ── EL REPARTO DE PAGO, UNA SOLA DEFINICION ─────────────────────────────────
# La vivian dos modulos con la misma regex escrita dos veces: el reconciliador
# tenia que saber que un reparto NO es una condicion de busqueda, y el hub tenia
# que saber cual reparto puede aplicar solo. Con dos copias, la del hub se
# arreglo el 6-ago y la del reconciliador no, y el turno se comio una ronda
# entera. Es exactamente la leccion del 31-jul con el patron de la poda: una
# regla escrita en dos lugares termina distinta.
_RE_DOS_PORCENTAJES = re.compile(r"\b(\d{1,3})\s*(?:/|-|y|,| )\s*(\d{1,3})\b")
_MEDIOS = ("transferencia", "mercado pago", "mercadopago", "mp", "efectivo",
           "tarjeta", "credito", "debito")

# ── LOS NUMEROS EN LETRAS ───────────────────────────────────────────────────
#
# LA FALLA, y es la que le puso nombre a esta etapa. El 7-ago se arreglo el
# reparto de pago leyendo "70/30" y se deployo. Corrido en vivo con la redaccion
# REAL de Martin -"divide el presupuesto en SETENTA TREINTA"- el mecanismo quedo
# mudo: no aplico el reparto y no declaro el supuesto. El modelo eligio solo, y
# eligio el 70 por Mercado Pago, que es el medio SIN descuento: $9.140 en contra
# del cliente. El arreglo del dia anterior habia funcionado por casualidad,
# porque esa vez el modelo transcribio la frase a digitos.
#
# La leccion no es "faltaba esta tabla": es que una regla que lee CASTELLANO
# depende de como el modelo transcriba, o sea de una loteria. Por eso la salida
# de fondo es el campo TIPADO de abajo, y esta tabla es la red para cuando el
# modelo no lo llena. Solo las decenas: un reparto de pago se dice "setenta
# treinta", nunca "setenta y tres coma cinco".
_DECENAS = {"diez": 10, "veinte": 20, "treinta": 30, "cuarenta": 40,
            "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
            "noventa": 90}
_RE_DOS_EN_LETRAS = re.compile(
    r"\b(" + "|".join(_DECENAS) + r")\b(?:\s+(?:y|por|,|-))?\s+\b("
    + "|".join(_DECENAS) + r")\b")


def _dos_porcentajes(texto: str):
    """Los dos porcentajes de un reparto, vengan en digitos o en letras."""
    m = _RE_DOS_PORCENTAJES.search(texto)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _RE_DOS_EN_LETRAS.search(texto)
    if m:
        return _DECENAS[m.group(1)], _DECENAS[m.group(2)]
    return None


def reparto_declarado(pedido: dict) -> tuple:
    """EL REPARTO DE PAGO, LEIDO DEL CAMPO TIPADO. Devuelve (texto, mayor,
    menor) o ().

    ESTE ES EL CAMINO BUENO, y desde el 7-ago es el primero que se mira.
    `registrar_pedido.reparto_pago` es una lista de {medio, porcentaje} que
    llena el MODELO, que es quien sabe traducir "setenta treinta" a dos numeros.
    El codigo no lee castellano: lee dos enteros.

    Solo devuelve algo cuando el reparto es AMBIGUO en el medio -ninguna parte
    dice con que se paga-, porque ese es el unico caso que el codigo resuelve
    solo, asumiendo y declarando el supuesto. Si el cliente SI dijo el medio, el
    reparto viaja tal cual y no hay nada que asumir.
    """
    partes = [p for p in (pedido or {}).get("reparto_pago") or []
              if isinstance(p, dict)]
    if len(partes) != 2:
        return ()
    try:
        pcts = [float(p.get("porcentaje") or 0) for p in partes]
    except (TypeError, ValueError):
        return ()
    if abs(sum(pcts) - 100) > 1 or min(pcts) <= 0:
        return ()
    if any(_norm(p.get("medio")) for p in partes):
        return ()                      # el cliente dijo el medio: nada que asumir
    a, b = int(max(pcts)), int(min(pcts))
    return (f"reparto {a}/{b}", a, b)


def reparto_ambiguo(restricciones) -> tuple:
    """LA RED, para cuando el modelo no llena el campo tipado. Lee los
    porcentajes de una restriccion escrita en castellano.

    QUEDA COMO SEGUNDA OPCION, no como la primera. Nacio el 7-ago leyendo solo
    digitos, se cayo con "setenta treinta" -que es como lo escribio Martin-, y
    se le agregaron las letras. Esa rueda es exactamente la que el campo tipado
    viene a cortar: mientras el codigo tenga que leer castellano, siempre va a
    haber una forma de decirlo que no contemple. Si `reparto_declarado` empieza
    a acertar siempre, esta funcion se borra.
    """
    for r in (restricciones or []):
        t = _norm(r)
        if any(m in t for m in _MEDIOS):
            # El cliente SI dijo el medio. Cual porcentaje va con cual es
            # interpretacion del texto, y eso no lo hace el codigo: sigue
            # siendo del modelo, y si no lo aplica el reconciliador lo reclama.
            continue
        par = _dos_porcentajes(t)
        if not par:
            continue
        a, b = par
        if a + b != 100 or min(a, b) <= 0:
            continue
        return (str(r), max(a, b), min(a, b))
    return ()


def _cubierto(texto: str, universo: str) -> bool:
    """Una raiz alcanza. Conservador a proposito: preferimos NO acusar un
    faltante falso antes que mandar al modelo a buscar de nuevo al pedo.

    LAS PALABRAS DE MENOS DE CUATRO LETRAS TIENEN SU PROPIO CAMINO, y sin el
    esta funcion mentia de la peor manera posible: `_stems` descarta todo lo
    que tenga menos de cuatro letras, asi que para `ssd` y `ram` devolvia lista
    vacia y esto daba SIEMPRE False. O sea que un rubro de nombre corto no
    podia considerarse atendido NUNCA: el reconciliador lo reclamaba, el modelo
    lo buscaba, lo encontraba, y se lo volvia a reclamar. Un reclamo imposible
    y una ronda quemada por turno, con su latencia y sus tokens, cada vez que
    alguien escribia "ssd" o "ram" — y `ssd` es una categoria entera de la
    tienda.

    Lo encontro el barrido de la decision al subirle los sorteos de 3 a 12: con
    la muestra chica no aparecia. Es la prueba de que un barrido chico esconde.

    Para las cortas se compara la palabra ENTERA contra las palabras del
    universo, no por adentro: con `in` a secas, "ram" daria cubierto dentro de
    "programa" y estariamos cambiando un reclamo imposible por un faltante que
    se traga en silencio, que es peor.
    """
    st = _stems(texto)
    if st:
        return any(s in universo for s in st)
    cortas = [w for w in _norm(texto).split() if w]
    palabras = set(universo.split())
    return any(w in palabras for w in cortas)



# reconciliar e instruccion_de_preguntas salieron en la FICHA 36.
# Snapshot: archivo/reconciliador_20260827.py
