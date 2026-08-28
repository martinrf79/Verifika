"""
EL CANDADO DEL CENSO — FICHA 12.

QUE CIERRA. El grafo declaraba sus etapas y `registrar()` dejaba la marca del
TURNO, que `abrir_turno` pisa en el siguiente. Al terminar una charla no quedaba
nada que contar, asi que para saber cuantas veces corrio e intervino cada
engranaje sobre las quince charlas habia que envolver `grafo.registrar` DESDE
AFUERA, con un espia a mano en `banco_pruebas/peso_del_censo.py`.

POR QUE ESO NO ALCANZABA, y no es prolijidad. Un instrumento que necesita que
alguien le ponga un espia encima mide **lo que el espia envuelve**. El dia que
una pieza deje su marca por otro camino, el espia no se entera: el censo cuenta
cero, y un cero es indistinguible de 'no corrio'. Es exactamente la forma del
agujero que dejo pasar los nodos ciegos la primera vez.

QUE AFIRMA ESTE TEST, y son tres cosas que un verde por vacio no puede dar:

  1. SOBRE CUANTOS NODOS MIDIO. Un censo que corre y no mide nada pasa igual y
     no dice nada. Aca el numero esta escrito y tiene que coincidir.
  2. QUE LAS SEIS ETAPAS DEJARON MARCA, y que ningun nodo declarado quedo ciego.
  3. QUE NADIE ENVUELVE NADA. Ni este test ni el instrumento le ponen un espia a
     `registrar`: se lee `G.censo()`, que es lo que el grafo conto solo.

CUANTO CUESTA: un casete, poco mas de un segundo. Los quince estan en
`banco_pruebas/peso_del_censo.py`, que es donde se mira el censo entero.
"""
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

# LOS DOS NUMEROS, ESCRITOS. No se deducen: se miden y se anotan, y el dia que
# cambien la bateria se pone roja y obliga a mirar por que.
#
#   22  los HUERFANOS: las piezas de adentro de las puertas. FICHA 35: sale
#       aduana (ya no es _pieza de higiene). 23 - 1 = 22. Se cuentan a
#       proposito: son engranajes reales del turno y un censo que los tira
#       a una lista de nombres miente.
_DECLARADOS = 14
# EL 22 SON las piezas de adentro de salida y de la cuenta del resolver, mas
# camino_al_cobro. El nodo declarado es la PUERTA; las piezas registran una
# por una.
_HUERFANOS = 22


def _censar_un_casete():
    """Corre UN casete por el camino vivo y devuelve lo que el grafo conto.

    No envuelve nada, y eso es el punto de la ficha: si esta funcion tuviera que
    ponerle un espia a `registrar` para medir, el censo seguiria sin ser del
    grafo."""
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.verifika import grafo as G
    from banco_pruebas.casete import CASETES, reproducir_charla

    uno = sorted(p for p in CASETES.glob("*.json")
                 if not p.name.startswith("_"))[:1]
    assert uno, "no hay casetes grabados: este test no puede medir nada"
    G.censo_reiniciar()
    reproducir_charla(uno[0])
    return G, G.censo()


def test_el_censo_dice_sobre_cuantos_nodos_midio():
    """EL ANTI-VACIO. Un censo verde que midio cero nodos es el `|| true` del
    29-jul con otra ropa: verde cinco dias sin correr nada."""
    G, c = _censar_un_casete()

    assert c["turnos"] > 0, (
        "el censo no conto un solo turno: `abrir_turno` no le esta dando el "
        "denominador y todos los porcentajes serian sobre cero")

    assert c["declarados_medidos"] == len(G.NODOS) == _DECLARADOS, (
        f"midio {c['declarados_medidos']} de los {len(G.NODOS)} nodos "
        f"declarados, y estaban escritos {_DECLARADOS}")

    assert c["huerfanos_medidos"] == _HUERFANOS, (
        f"midio {c['huerfanos_medidos']} huerfanos y estaban escritos "
        f"{_HUERFANOS}. Si una pieza nueva empezo a registrar sin nodo "
        "declarado, o si una dejo de hacerlo, el numero se cambia A MANO y el "
        "commit dice cual y por que.")

    assert c["nodos_medidos"] == _DECLARADOS + _HUERFANOS, (
        f"midio {c['nodos_medidos']} nodos y la cuenta escrita es "
        f"{_DECLARADOS} declarados + {_HUERFANOS} huerfanos")

    # FICHA 40. El 22 de arriba es el techo y se queda clavado. Esto clava
    # los NOMBRES: la union de piezas es exactamente el conjunto de huerfanos
    # que el censo midio. No se deriva el 22 de piezas.
    huerfanos = {f["nodo"] for f in c["filas"]
                 if f["corrio"] and not f["declarado"]}
    nombradas = {p for n in G.NODOS for p in n.piezas}
    assert huerfanos == nombradas, (
        f"huerfanos del censo {sorted(huerfanos)} vs piezas nombradas "
        f"{sorted(nombradas)}")


def test_las_seis_etapas_dejan_marca_y_ninguna_queda_ciega():
    """La FICHA 01 cablo las seis a `registrar()`. Esto es el candado de que
    ninguna se vuelva a quedar sin ojo, leido del censo del grafo y no de un
    espia puesto desde afuera."""
    G, c = _censar_un_casete()

    assert c["etapas_medidas"] == sorted(G.ETAPAS), (
        f"solo dejaron marca las etapas {c['etapas_medidas']}; faltan "
        f"{sorted(set(G.ETAPAS) - set(c['etapas_medidas']))}")

    assert not c["ciegos"], (
        f"{len(c['ciegos'])} nodos declarados no dejaron una sola marca: "
        f"{c['ciegos']}. El grafo NO LOS VE.")


def test_ningun_nodo_marca_mas_veces_que_turnos_hubo():
    """UNA MARCA POR NODO Y POR TURNO. Si un nodo marcara dos veces, el censo
    contaria de mas y TODOS los porcentajes quedarian mal EN SILENCIO, que es
    peor que no medir: un numero que miente se usa para decidir."""
    _, c = _censar_un_casete()
    assert not c["marcan_de_mas"], (
        f"estos nodos marcaron mas veces que los {c['turnos']} turnos del "
        f"casete: {c['marcan_de_mas']}")


def test_el_instrumento_no_envuelve_nada():
    """LA CONDICION DE TERMINADO DE LA FICHA 12, escrita como candado.

    `peso_del_censo.py` no puede volver a medir poniendole un espia a
    `grafo.registrar`. Si alguien lo reintroduce, el censo vuelve a medir lo que
    el espia envuelve en vez de lo que el turno hace, y este test lo frena en el
    mismo push."""
    fuente = (_RAIZ / "banco_pruebas" / "peso_del_censo.py").read_text(
        encoding="utf-8")
    espias = re.findall(r"^\s*G\.(registrar|anotar)\s*=", fuente, re.M)
    assert not espias, (
        f"el instrumento le vuelve a poner un espia a: {espias}. El censo se "
        "lee de `G.censo()`, que es lo que el grafo conto solo.")
    assert "G.censo()" in fuente, (
        "`peso_del_censo.py` no lee el censo del grafo: si no lo lee de ahi, "
        "lo esta sacando de otro lado y este candado no dice nada")


def test_las_piezas_nombradas_coinciden_con_las_marcas_del_codigo():
    """FICHA 40. El campo piezas no puede mentir: ni nombrar una que no
    corre, ni correr una que no esta nombrada. El orden es el de la fuente.
    El 22 lo clava el censo; esto clava los nombres."""
    from app.verifika import grafo as G

    tests = Path(__file__).resolve().parent
    if str(tests) not in sys.path:
        sys.path.insert(0, str(tests))
    from test_plan_de_la_simplificacion import _sitios_de_piezas

    declarados = {n.id for n in G.NODOS}
    sitios = _sitios_de_piezas(declarados)
    declaradas = {n.piezas for n in G.NODOS if n.piezas}
    halladas = set(sitios.values())
    assert halladas == declaradas, (
        "el campo piezas no coincide con las marcas del codigo.\n"
        f"sitios: {sitios}\n"
        "nodos: "
        + "; ".join(f"{n.id}={n.piezas}" for n in G.NODOS if n.piezas))
