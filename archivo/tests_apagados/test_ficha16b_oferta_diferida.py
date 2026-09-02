"""
LA FICHA 16B — CEDER SIGNIFICA DIFERIR, y antes no significaba nada.

POR QUE EXISTE ESTE ARCHIVO. La ficha 16 puso el cuarto freno: si el turno ya
le pregunta algo al cliente, la oferta CEDE. El comentario decia "queda para el
turno siguiente" y eso NO estaba implementado —no habia flag, ni estado, ni
memoria—: `punto_de_oferta` hacia `return None` y el producto se evaporaba. Y el
punto solo se reabria si el turno siguiente volvia a llamar una herramienta de
productos, porque `_productos_certificados` mira las llamadas de ESTE turno y
nada mas.

EL DAÑO MEDIDO ES EL DE LA FICHA 15 ENTRANDO POR LA PUERTA DE AL LADO: el
cliente pregunta algo ambiguo, el bot aclara, y la oferta pendiente se pierde.
Los dos turnos hacen lo correcto y la venta no avanza nunca.

LO QUE SE DEFIENDE ACA SON TRES COSAS:

  1. QUE SE DIFIERA        ceder devuelve el producto pendiente, no vacio.
  2. QUE SE REABRA         el turno siguiente abre el punto desde el estado,
                           SIN NINGUNA llamada a herramientas.
  3. QUE SE APAGUE         con los tres motivos tipados que ya existen, y no
                           con un cuarto inventado: rechazado, ya_en_el_pedido
                           y cerrando. Sin esto la oferta se arrastra para
                           siempre, que es la insistencia que el punto evita.

Y LA VUELTA COMPLETA POR EL CAMINO VIVO, dos turnos con el modelo reemplazado
por una grabacion escrita aca: es la unica forma de probar que el campo se
guarda y se vuelve a leer. Sin ese test los tres de arriba pasan con el estado
muerto, que es exactamente lo que pasaba antes de esta ficha.

CORRE OFFLINE: sin modelo, sin clave, sin red.
"""
import asyncio
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import indice_turno as IT  # noqa: E402

_DECLARADO = {"items": [{"que": "mouse", "cantidad": 1}]}

_CON_DUDA = {"items": [{"que": "mouse", "cantidad": 1}],
             "contradicciones": ["pidio 1 mouse y nombro 2 destinos"]}

_MOUSE = {"herramienta": "buscar_productos",
          "pedido": {"descripcion": "mouse logitech"},
          "resultado": {"estado": "encontrado", "productos": [
              {"id": "MOU-001", "nombre": "Mouse Logitech M170 Negro",
               "precio": "$12.000"}]}}

_AMBIGUA = {"herramienta": "buscar_productos",
            "pedido": {"descripcion": "g pro x"},
            "resultado": {"estado": "ambiguo", "productos": [
                {"id": "AUR-010", "nombre": "Logitech G Pro X"},
                {"id": "AUR-011", "nombre": "Logitech G Pro X 2"}]}}

_CUENTA = {"herramienta": "armar_presupuesto",
           "pedido": {"items": [{"product_id": "MOU-001", "cantidad": 1}]},
           "resultado": {"estado": "ok", "total_ars": 12000, "detalle": [
               {"id": "MOU-001", "nombre": "Mouse Logitech M170 Negro",
                "cantidad": 1}]}}

_PENDIENTE = [{"id": "MOU-001", "nombre": "Mouse Logitech M170 Negro"}]


# ── 1. QUE SE DIFIERA ────────────────────────────────────────────────────────

# (que cede, con que declarado, con que llamadas, con que texto)
LOS_DOS_QUE_CEDEN = [
    ("la herramienta salio ambigua: el turno esta obligado a repreguntar",
     _DECLARADO, [_AMBIGUA], "Tengo dos G Pro X. ¿Cuál de los dos querés?"),
    ("el turno arrastra una contradiccion declarada, o sea que va a preguntar",
     _CON_DUDA, [_MOUSE], "Pediste uno y nombraste dos destinos, ¿cuál va?"),
]


def test_los_dos_que_ceden_devuelven_el_producto_pendiente():
    """LOS DOS `return None` QUE PERDIAN LA OFERTA, uno por uno.

    El punto NO se abre —eso esta bien, el turno tiene que preguntar— pero el
    producto tiene que salir por `diferida` o no llega al turno siguiente."""
    fallan = []
    for nombre, declarado, llamadas, texto in LOS_DOS_QUE_CEDEN:
        idx = IT.cobertura(declarado, texto, "t", llamadas=llamadas)
        if [p for p in idx["puntos"] if p["tipo"] == "oferta"]:
            fallan.append(f"{nombre}: el punto se abrio y tenia que ceder")
        if not idx.get("diferida"):
            fallan.append(f"{nombre}: cedio y no dejo nada diferido")
    print(f"\n  se midieron {len(LOS_DOS_QUE_CEDEN)} formas de ceder")
    assert not fallan, "\n  ".join([""] + fallan)


def test_el_turno_que_si_ofrece_no_difiere_nada():
    """EL OTRO LADO, Y SIN ESTO LA OFERTA SE ARRASTRA PARA SIEMPRE. Cuando el
    punto se abre, la oferta esta VIVA en este turno y su estado lo mide
    `estado_terminal`. Guardarla ademas en el estado seria contarla dos veces y
    volver a proponerla al turno siguiente."""
    idx = IT.cobertura(_DECLARADO, "Te lo cargo al pedido, el Logitech M170.",
                       "t", llamadas=[_MOUSE])
    assert [p for p in idx["puntos"] if p["tipo"] == "oferta"]
    assert idx["diferida"] == [], idx["diferida"]


# ── 2. QUE SE REABRA ─────────────────────────────────────────────────────────

def test_el_turno_siguiente_abre_el_punto_SIN_NINGUNA_HERRAMIENTA():
    """EL ARREGLO, Y EL TEST QUE LA FICHA PIDE. Turno con duda declarada que
    trae producto; turno siguiente SIN llamada a herramientas: el punto se abre
    igual, desde el estado de la conversacion."""
    cedio = IT.cobertura(_CON_DUDA, "Pediste uno y nombraste dos, ¿cuál va?",
                         "t1", llamadas=[_MOUSE])
    assert not [p for p in cedio["puntos"] if p["tipo"] == "oferta"]
    pendiente = cedio["diferida"]
    assert [p["nombre"] for p in pendiente] == ["Mouse Logitech M170 Negro"]

    # EL TURNO SIGUIENTE: el cliente aclaro, el bot no busco nada de nuevo.
    sigue = IT.cobertura({}, "Perfecto, entonces va uno solo a Concordia.",
                         "t2", llamadas=[], diferida=pendiente)
    punto = next((p for p in sigue["puntos"] if p["tipo"] == "oferta"), None)
    assert punto is not None, (
        "el turno siguiente no llamo ninguna herramienta y el punto no se "
        "abrio: la oferta se evaporo igual que antes de la ficha 16B")
    assert punto["termino"] == "Mouse Logitech M170 Negro"
    # Y LA INSTRUCCION LLEGA AL REDACTOR, que es lo que hace que el defecto no
    # se ESCRIBA: sin la linea, el modelo no tiene por que cerrar proponiendo.
    assert "Mouse Logitech M170 Negro" in IT.instruccion(sigue["faltan"])


def test_lo_que_el_turno_certifica_pisa_lo_diferido():
    """LO NUEVO MANDA. Si este turno trajo productos, la charla se movio:
    arrastrar tambien el de dos turnos atras es la insistencia."""
    idx = IT.cobertura(_DECLARADO, "El Logitech M170 tiene 1000 DPI.", "t",
                       llamadas=[_MOUSE],
                       diferida=[{"id": "TEC-001", "nombre": "Teclado Genius "
                                  "KB-110X Blanco"}])
    punto = next(p for p in idx["puntos"] if p["tipo"] == "oferta")
    assert punto["candidatos"] == ["Mouse Logitech M170 Negro"], punto


def test_lo_que_llega_de_firestore_se_sanea_y_no_tumba_el_turno():
    """EL CAMPO VIENE DE AFUERA. Un documento viejo, un campo a medio escribir o
    directamente otra forma no pueden tumbar el turno ni abrir un punto sobre un
    producto sin nombre."""
    for basura in ([None], ["Mouse M170"], [{}], [{"id": "X"}], "no es lista"):
        assert IT.punto_de_oferta([], None, "", None, None, basura)[0] is None, basura
    # Y LOS REPETIDOS NO SE DUPLICAN.
    limpio = IT._limpiar_diferida(_PENDIENTE + _PENDIENTE)
    assert len(limpio) == 1, limpio


# ── 3. QUE SE APAGUE ─────────────────────────────────────────────────────────

# (que lo apaga, con que llamadas, con que memoria, con que descartados,
#  con que texto)
LOS_TRES_QUE_APAGAN = [
    ("ya esta en el pedido", [_CUENTA], None, None, "Total: $12.000",
     "ya_en_el_pedido"),
    ("el cliente lo rechazo", [], None, ["Mouse Logitech M170 Negro"],
     "Dale, lo saco.", "rechazado"),
    ("el turno esta cerrando", [], None, None,
     "¿A nombre de quién lo emito?", "cerrando"),
]


def test_los_tres_motivos_tipados_apagan_la_oferta_diferida():
    """SE APAGA CON LOS TRES QUE YA EXISTEN, Y CON NINGUNO MAS.

    Es la mitad que impide que esto sea un producto que persigue al cliente
    hasta el final de la charla. Los tres se prueban sobre una oferta que viene
    DIFERIDA y sin ninguna herramienta nueva, que es el caso que no existia
    antes de esta ficha."""
    fallan = []
    for nombre, llamadas, memoria, descartados, texto, motivo in LOS_TRES_QUE_APAGAN:
        idx = IT.cobertura({}, texto, "t", llamadas=llamadas, memoria=memoria,
                           descartados=descartados, diferida=_PENDIENTE)
        punto = next((p for p in idx["puntos"] if p["tipo"] == "oferta"), None)
        if punto is None:
            fallan.append(f"{nombre}: el punto no se abrio, no se puede saber "
                          "si se apago o si se perdio otra vez")
        elif punto.get("no_corresponde") != motivo:
            fallan.append(f"{nombre}: el motivo salio "
                          f"{punto.get('no_corresponde')!r} y no {motivo!r}")
        if idx.get("diferida"):
            fallan.append(f"{nombre}: se apago y siguio arrastrando "
                          f"{idx['diferida']}")
    print(f"\n  se midieron {len(LOS_TRES_QUE_APAGAN)} motivos de apagado")
    assert len(LOS_TRES_QUE_APAGAN) == len(IT.MOTIVOS_NO_CORRESPONDE)
    assert not fallan, "\n  ".join([""] + fallan)


# ── LA VUELTA COMPLETA: DOS TURNOS POR EL CAMINO VIVO ────────────────────────

def _casete_de_dos_turnos():
    """La grabacion escrita a mano, con el modelo diciendo exactamente lo que
    hace falta para el caso: turno 1 declara una contradiccion y busca un
    producto; turno 2 NO LLAMA NINGUNA HERRAMIENTA."""
    from banco_pruebas.casete import Casete
    registrar = {"content": "", "tool_calls": [{"name": "registrar_pedido",
                 "arguments": json.dumps(
                     {"items": [{"categoria": "teclado",
                                 "que": "teclado mas barato"}],
                      "contradicciones": ["pidio uno y nombro dos destinos"],
                      "pide_precio": True})}]}
    return Casete("ficha16b_diferida", [
        {"mensaje": "quiero el teclado mas barato, va a Rosario y a Cordoba",
         "llamadas": [
             {"etapa": "herramientas", "salida": json.dumps(registrar)},
             {"etapa": "herramientas", "salida": json.dumps(registrar)},
             {"etapa": "redaccion", "salida": json.dumps(
                 {"content": "El Genius KB-110X sale $12.000. Nombraste dos "
                             "destinos y pediste uno, ¿a cuál va?",
                  "tool_calls": []})}]},
        {"mensaje": "va uno solo, a Rosario",
         "llamadas": [
             {"etapa": "herramientas", "salida": json.dumps(
                 {"content": "Perfecto, uno solo a Rosario.",
                  "tool_calls": []})},
             {"etapa": "redaccion", "salida": json.dumps(
                 {"content": "Perfecto, uno solo a Rosario.",
                  "tool_calls": []})}]},
    ])


def test_la_oferta_diferida_sobrevive_el_turno_por_el_camino_vivo(firestore_doble):
    """LA UNICA PRUEBA DE QUE EL ESTADO EXISTE DE VERDAD.

    Los tests de arriba le pasan `diferida` a mano y pasarian igual con el campo
    muerto —que es lo que estuvo pasando con el comentario "queda para el turno
    siguiente"—. Aca los dos turnos entran por el webhook real, con el modelo
    reemplazado por la grabacion de arriba, y se lee el documento de la
    conversacion en el medio: si `hub_venta` no guarda el campo o no lo vuelve a
    leer, este test se pone rojo y los otros cinco no."""
    from banco_pruebas import clon_produccion as clon, observador
    from banco_pruebas import vara_de_venta as vara
    from banco_pruebas.casete import reproducir
    from app.storage.firestore_client import get_conversation

    casete = _casete_de_dos_turnos()
    user = "ficha16b_diferida"
    clon.reiniciar_cliente(user)
    visto = {}

    async def _charla():
        for i, t in enumerate(casete.turnos):
            casete.abrir_turno(t["mensaje"])
            with observador.turno() as obs:
                await clon.turno(user, t["mensaje"])
            visto[i] = {
                "guardado": ((get_conversation(user, tienda_id=clon.TIENDA)
                              or {}).get("oferta_diferida") or []),
                "estados": [m for e in obs.eventos
                            if e.get("event") == "indice_turno"
                            for m in (e.get("estados") or [])
                            if str(m).startswith("oferta:")],
            }

    # `_escuchando` engancha el clon Y prende el observador, en ese orden: al
    # reves, `app.main` reconfigura structlog y la captura de eventos queda
    # muda. Adentro de la bateria structlog esta callado a proposito.
    with vara._escuchando(), reproducir(casete):
        asyncio.run(_charla())

    # TURNO 1: cedio —tenia una contradiccion declarada— y guardo lo pendiente.
    assert visto[0]["estados"] == [], (
        "el turno 1 tenia una duda declarada: la oferta tenia que ceder, y "
        f"salio con estado {visto[0]['estados']}")
    assert visto[0]["guardado"], (
        "el turno 1 cedio la oferta y no guardo nada: es el defecto exacto de "
        "la ficha 16B, el comentario decia 'queda para el turno siguiente' y "
        "no habia ni flag, ni estado, ni memoria")

    # TURNO 2: no llamo NINGUNA herramienta y el punto se abrio igual.
    assert visto[1]["estados"], (
        "el turno 2 no llamo ninguna herramienta y el punto de oferta no se "
        "abrio: la oferta pendiente se evaporo en la transicion, que es "
        "justamente lo que este campo existe para que no pase")
