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
