"""CADA PUNTO TERMINA EN UN ESTADO, Y SE PUEDE NOMBRAR (FICHA 08).

Lo que este archivo defiende es una distincion, no una funcion: hasta ahora
"no atendido" queria decir cuatro cosas a la vez —el bot se lo olvido, el bot
pregunto, no habia con que contestarlo, el cliente se contradijo— y tres de
esas cuatro no son un defecto. Un turno que pregunta bien y un turno que se
olvida algo se veian IGUAL en el log.

LA PRUEBA QUE IMPORTA ES LA SEXTA, y es la que hace que esto no sea un
colador: una pregunta de cortesia al final del mensaje —"¿te lo despacho
hoy?"— NO puede dejar en AMBIGUO al punto que el bot se olvido. Si eso pasara,
esta casilla convertiria toda omision en un final feliz, que es exactamente el
verde falso contra el que existe `indice_turno`.

CORRE OFFLINE: sin modelo, sin clave, sin red.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import indice_turno as IT  # noqa: E402


def _busqueda(descripcion, resultado):
    return {"herramienta": "buscar_productos",
            "pedido": {"descripcion": descripcion}, "resultado": resultado}


# (que se declaro, que texto salio, que herramientas hubo, en que termina)
CASOS = [
    ("RESUELTO: el punto llego al texto",
     {"items": [{"que": "mouse logitech", "cantidad": 2}]},
     "Te paso 2 Mouse Logitech M170 Negro a $12.000 cada uno.",
     [], "item:1", "RESUELTO"),

    ("OMISION: habia con que contestarlo y no salio dicho",
     {"items": [{"que": "mouse logitech", "cantidad": 2}]},
     "Perfecto, ya lo anoto y seguimos.",
     [_busqueda("mouse logitech", {"estado": "encontrado", "productos": [
         {"nombre": "Mouse Logitech M170 Negro"}]})],
     "item:1", ""),

    ("AMBIGUO: la busqueda volvio ambigua, hay que preguntar cual",
     {"items": [{"que": "g pro x", "cantidad": 1}]},
     "Dale, lo vemos.",
     [_busqueda("g pro x", {"estado": "ambiguo", "productos": [
         {"nombre": "Logitech G Pro X"}, {"nombre": "Logitech G Pro X 2"}]})],
     "item:1", "AMBIGUO"),

    ("NO_SE_SABE: la casa no lo vende y la fuente lo dice",
     {"items": [{"que": "iphone", "cantidad": 1}]},
     "Dale, lo vemos.",
     [_busqueda("iphone", {"estado": "no_vendemos", "productos": []})],
     "item:1", "NO_SE_SABE"),

    ("AMBIGUO: el texto repregunta POR ESE punto",
     {"stock": ["notebook asus"]},
     "De la Notebook Asus, ¿cual de las dos versiones te interesa?",
     [], "stock:1", "AMBIGUO"),

    ("OMISION: una pregunta de cortesia NO salva al punto olvidado",
     {"items": [{"que": "monitor samsung", "cantidad": 1}]},
     "Listo, ya lo anoto. ¿Te lo despacho hoy?",
     [_busqueda("monitor samsung", {"estado": "encontrado", "productos": [
         {"nombre": "Monitor Samsung 24"}]})],
     "item:1", ""),

    ("NO_SE_SABE: el bot dice honestamente que no tiene el dato",
     {"atributos": [{"de": "monitor samsung", "campo": "hz"}]},
     "Del Monitor Samsung no tengo ese dato en la ficha.",
     [], "atributo:1", "NO_SE_SABE"),

    ("CONFLICTO: el cliente se contradijo y el turno no pregunto",
     {"contradicciones": ["pediste 3 teclados pero nombraste 2 destinos"]},
     "Te confirmo los 3 teclados.",
     [], "duda:1", "CONFLICTO"),

    ("AMBIGUO: la misma contradiccion, pero preguntada",
     {"contradicciones": ["pediste 3 teclados pero nombraste 2 destinos"]},
     "Me quedan 3 teclados y 2 destinos, ¿como los reparto?",
     [], "duda:1", "AMBIGUO"),

    ("NO_SE_SABE: la fuente no tiene escrito ESE tema",
     {"temas": ["envio_exterior"]},
     "Contame la localidad y seguimos.",
     [{"herramienta": "consultar_temas", "pedido": {"temas": ["envio_exterior"]},
       "resultado": {"estado": "ok", "temas": [
           {"tema": "envio_exterior", "estado": "no_encontrado"}]}}],
     "politica:1", "NO_SE_SABE"),

    ("RESUELTO: el precio se contesta con el Total",
     {"items": [{"que": "teclado", "cantidad": 1}], "pide_precio": True},
     "Teclado Redragon.\nTotal: $24.000",
     [], "precio:1", "RESUELTO"),

    ("RESUELTO: la politica llego al texto",
     {"temas": ["garantia"]},
     "La garantia es de 6 meses por fabrica.",
     [], "politica:1", "RESUELTO"),

    ("RESUELTO: el destino en Envio a, fuera de la cuenta",
     {"destinos": ["Rosario"]},
     "Sin cambios en la cuenta. Total: $104.500\n\nEnvío a Rosario.",
     [], "destino:1", "RESUELTO"),
]


def test_cada_caso_termina_donde_tiene_que_terminar():
    """LOS TRECE CASOS, uno por uno, con su id y su final."""
    assert len(CASOS) == 13, f"se declararon 13 casos y hay {len(CASOS)}"
    fallan = []
    for nombre, declarado, texto, llamadas, id_punto, esperado in CASOS:
        idx = IT.cobertura(declarado, texto, "test", llamadas=llamadas)
        punto = next((p for p in idx["puntos"] if p["id"] == id_punto), None)
        if punto is None:
            fallan.append(f"{nombre}: no se abrio el punto {id_punto}")
            continue
        if punto["estado"] != esperado:
            fallan.append(
                f"{nombre}: {id_punto} termino en "
                f"'{punto['estado'] or 'SIN_ESTADO'}' y tenia que terminar en "
                f"'{esperado or 'SIN_ESTADO'}'")
    assert not fallan, "\n  ".join([""] + fallan)


def test_los_seis_estados_y_nada_mas():
    """El vocabulario es cerrado. Uno nuevo obliga a decidirlo, no a aparecer.

    ERAN CUATRO Y SON SEIS DESDE LA FICHA 15, y el requisito cambio de verdad:
    los cuatro primeros dicen como termino algo que el CLIENTE pidio, y no hay
    ninguno que sirva para lo que el BOT tiene que proponer. Una oferta no se
    "resuelve", no se "sabe" y no entra en "conflicto": o se hizo, o no
    correspondia hacerla. Meterla a la fuerza en los cuatro viejos hubiera sido
    ensanchar uno de ellos, que es como se afloja una definicion."""
    assert set(IT.ESTADOS_TERMINALES) == {
        "RESUELTO", "AMBIGUO", "NO_SE_SABE", "CONFLICTO",
        "OFRECIDO", "NO_CORRESPONDE"}
    assert len(IT.ESTADOS_TERMINALES) == 6
    # LOS DOS DE LA OFERTA SON SOLO DE LA OFERTA. Si un punto del cliente
    # pudiera terminar OFRECIDO, la omision se escaparia por ahi.
    assert IT.estado_terminal({"tipo": "item", "termino": "mouse"},
                              "Te cargo el mouse al pedido.") == "RESUELTO"


def test_ningun_punto_sale_sin_la_casilla_estado():
    """LA MITAD QUE HABILITA LA PUERTA DE LA FICHA 09. La casilla puede salir
    VACIA —eso es la omision— pero no puede FALTAR: un punto sin la clave es un
    punto que nadie miro, y la puerta no podria distinguirlo de uno que
    termino bien."""
    declarado = {
        "items": [{"que": "monitor samsung", "cantidad": 1},
                  {"que": "teclado", "cantidad": 2}],
        "restricciones": ["que sea inalambrico"],
        "destinos": ["Concordia"],
        "contradicciones": ["pediste 2 teclados y nombraste 3 destinos"],
        "pide_precio": True,
        "reparto_pago": [{"porcentaje": 70}, {"porcentaje": 30}],
        "atributos": [{"de": "monitor samsung", "campo": "hz"}],
        "stock": ["teclado"],
        "compatibilidad": [{"que": "teclado", "para": "notebook"}],
        "temas": ["garantia"],
    }
    idx = IT.cobertura(declarado, "Te confirmo el Monitor Samsung.", "test")
    assert len(idx["puntos"]) >= 11, (
        f"el caso tiene que abrir al menos 11 puntos y abrio "
        f"{len(idx['puntos'])}")
    validos = set(IT.ESTADOS_TERMINALES) | {""}
    sin_casilla = [p["id"] for p in idx["puntos"] if "estado" not in p]
    assert not sin_casilla, f"puntos sin la casilla `estado`: {sin_casilla}"
    raros = [(p["id"], p["estado"]) for p in idx["puntos"]
             if p["estado"] not in validos]
    assert not raros, f"estados fuera del vocabulario: {raros}"


def test_el_estado_no_le_pregunta_nada_al_modelo():
    """Sin llamadas y sin texto, la funcion contesta igual: es determinista y
    offline. Un punto sin nada con que contestarse queda SIN estado, que es
    lo que la puerta frena."""
    punto = {"id": "item:1", "tipo": "item", "termino": "mouse", "texto": "1 mouse"}
    assert IT.estado_terminal(punto, "") == ""
    assert IT.estado_terminal(punto, "Te paso el mouse.") == "RESUELTO"
