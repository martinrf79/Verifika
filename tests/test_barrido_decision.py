"""
EL CANDADO DEL BARRIDO DE LA DECISION Y LA REPOSICION.

Lo que barre y por que, en `banco_pruebas/barrido_decision.py`. Aca vive la
vara, y son cuatro cosas: que ningun contrato se rompa, que el barrido cubra
todas sus celdas, que cada nodo se EJERCITE de verdad y no solo se recorra, y
que ningun nodo del turno pueda quedar sin contrato y sin motivo.

EL ULTIMO ES EL QUE IMPORTA MAS ALLA DE HOY. Los quince nodos sin contrato no
aparecieron de golpe: se fueron sumando de a uno, cada uno con su razon del
momento, y como no habia donde mirarlos juntos nadie noto que eran quince. El
candado no deja que vuelva a pasar: un nodo nuevo entra al turno con su
contrato o con el motivo escrito de por que no puede tenerlo.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import barrido_decision as BD  # noqa: E402


def test_ningun_contrato_de_la_mitad_que_decide_se_rompe(firestore_doble):
    """LA VARA. Cada violacion de estas es un defecto que le puede llegar al
    cliente sin que ningun test por ejemplo lo vea: los dos que encontro el dia
    que nacio este barrido —la busqueda repuesta dos veces y el supuesto de
    pago dicho dos veces— vivian en codigo que ya tenia pruebas en verde."""
    r = BD.barrer()
    assert r["casos"] > 0, "el barrido no genero ni un estado de turno"
    assert not r["violaciones"], (
        f"{len(r['violaciones'])} violaciones de contrato:\n  "
        + "\n  ".join(f"{n} [{c}] {contrato}: {detalle}"
                      for n, c, contrato, detalle in r["violaciones"][:15]))


def test_el_barrido_corre_cada_nodo_en_cada_clase_de_estado(firestore_doble):
    """La celda es nodo x clase de estado. Si una queda sin correr, hay una
    combinacion del turno que nadie probo nunca."""
    r = BD.barrer()
    assert r["cobertura"] == 100.0, (
        f"celdas sin cubrir: {r['sin_cubrir'][:10]}")


def test_cada_nodo_hace_algo_al_menos_una_vez(firestore_doble):
    """EL CANDADO CONTRA EL VERDE VACIO, y no es teorico: la primera corrida de
    este barrido daba 100% de celdas con CUATRO de los diez nodos que no
    intervenian nunca. Correr un nodo no es probarlo. Si un nodo deja de
    dispararse, o el generador dejo de producir su caso, o el nodo esta muerto,
    y las dos cosas hay que mirarlas."""
    r = BD.barrer()
    assert not r["nunca_intervino"], (
        f"nodos que el barrido recorre pero no ejercita: "
        f"{r['nunca_intervino']}. O el generador perdio su clase de estado, o "
        f"el nodo ya no se alcanza.")


def test_ningun_nodo_queda_sin_contrato_ni_motivo(firestore_doble):
    """EL CANDADO QUE SOBREVIVE A ESTA SESION. Un nodo sin contrato mecanico
    tiene que declarar POR QUE no lo tiene. Sin esto, un nodo al que nadie le
    escribio el contrato es indistinguible de uno que no puede tenerlo, que es
    como quedaron quince sin que se notara."""
    from app.verifika import grafo as G
    mudos = [nodo for nodo, motivo in G.sin_contrato() if not str(motivo).strip()]
    assert not mudos, (
        f"nodos sin contrato y sin motivo: {mudos}. Escribile los contratos, o "
        f"declara en `sin_contrato` por que no puede tenerlos.")


def test_los_contratos_de_datos_estan_todos_en_uso(firestore_doble):
    """Un contrato declarado que ningun nodo usa es letra muerta: o se le
    asigna a quien corresponde, o se borra."""
    from app.verifika import grafo as G
    usados = {c for n in G.NODOS for c in n.contratos}
    sin_usar = [c for c in G.CONTRATOS_DE_DATOS if c not in usados]
    assert not sin_usar, f"contratos declarados que no usa ningun nodo: {sin_usar}"


def test_los_contratos_frenan_de_verdad(firestore_doble):
    """EL CANDADO DEL CANDADO. Un contrato que nunca se pone rojo no protege
    nada y da la peor sensacion posible: verde tranquilo sobre codigo roto. Se
    le planta una violacion a proposito a cada uno y se exige que la cace.

    Es el mismo metodo con el que se probo la aduana el 11-ago, dopandole una
    reparacion, y no es paranoia: el primer `no_inventa_id` de este mismo
    barrido marcaba como id inventado el `CV550` que era el MODELO de una
    webcam, o sea que cazaba lo que no era. Un contrato hay que probarlo en las
    dos direcciones."""
    from banco_pruebas import barrido_decision as BD
    from app.verifika import grafo as G

    catalogo = BD._ids_del_catalogo()
    base = {"llamadas": [{"herramienta": "buscar_productos", "pedido": {},
                          "resultado": {"estado": "ok",
                                        "productos": [{"id": "MOU0001",
                                                       "nombre": "x"}]}}],
            "declarado": {}, "memoria": [], "estado": {}}
    # LA PUERTA DE LA REPOSICION, que desde la FICHA 11 es un nodo y eran seis.
    # Este caso no prueba la pieza sino los CONTRATOS del nodo, y son los
    # mismos `CONTRATOS_DE_REPOSICION` que declaraba `cuenta_repuesta`.
    nodo = G.POR_ID["reposicion"]

    dopadas = {
        G.NO_INVENTA_ID: base["llamadas"] + [
            {"herramienta": "ficha_producto",
             "pedido": {"product_id": "NOEXISTE999"}, "resultado": {}}],
        G.NO_PIERDE_EVIDENCIA: [],
        G.NO_AGREGA_LO_NO_PEDIDO: base["llamadas"] + [
            {"herramienta": "armar_presupuesto",
             "pedido": {"items": [{"product_id": "TEC0007", "cantidad": 1}]},
             "resultado": {}}],
    }
    for contrato, llamadas in dopadas.items():
        despues = {**base, "llamadas": llamadas}
        cazados = [c for c, _ in BD.violaciones(nodo, base, despues, catalogo)]
        assert contrato in cazados, (
            f"se le planto una violacion de {contrato} y el barrido no la vio")

    # El del reconciliador va aparte: su violacion no es una llamada de mas,
    # es reclamar un item que la evidencia ya cubre.
    antes = {"declarado": {"items": [{"que": "mouse"}]}, "memoria": [],
             "estado": {}, "ya_resuelto": "",
             "llamadas": [{"herramienta": "buscar_productos", "pedido": {},
                           "resultado": {"estado": "ok", "productos": [
                               {"id": "MOU0001",
                                "nombre": "Mouse Logitech Negro"}]}}]}
    despues = {**antes, "rec": {"faltantes":
                                ["El cliente pidio 'mouse' y no lo buscaste."],
                                "sin_buscar": ["mouse"]}}
    cazados = [c for c, _ in BD.violaciones(G.POR_ID["reconciliador"], antes,
                                            despues, catalogo)]
    assert G.NO_RECLAMA_LO_RESUELTO in cazados, (
        "se le planto un reclamo sobre un item ya atendido y no lo vio")

    # Y EL MISMO RECLAMO CON OTRA REDACCION TIENE QUE CAZARSE IGUAL. Este es el
    # test que hace que el contrato no dependa del texto: si mañana alguien
    # reescribe como habla el reconciliador, esto sigue en verde porque mira el
    # campo tipado `sin_buscar`. Sin este caso, el contrato podia dejar de
    # cazar en silencio, que es la unica falla que un candado no puede tener.
    otra = {**antes, "rec": {"faltantes": ["Che, fijate el mouse que te pidio."],
                             "sin_buscar": ["mouse"]}}
    cazados = [c for c, _ in BD.violaciones(G.POR_ID["reconciliador"], antes,
                                            otra, catalogo)]
    assert G.NO_RECLAMA_LO_RESUELTO in cazados, (
        "el contrato dejo de cazar porque cambio la redaccion del reclamo: "
        "esta atado al texto en vez de al campo tipado")
