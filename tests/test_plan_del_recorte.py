"""
EL PLAN DEL RECORTE, ESCRITO COMO TESTS QUE HOY NO PASAN.

Directiva de Martin (21-ago-2026): **cada paso, hueco y fuga que haya que
resolver se escribe como un test que hoy no pasa, y la actividad de cada etapa
es ponerlos en verde.** Ninguna actividad queda a medias.

Este archivo es el plan. No hay una version en prosa que pueda envejecer al
lado: el COMO y el orden estan en `PLAN_RECORTE.md`, el POR QUE en
`DECISIONES.md`, los numeros de partida en `PASO0_CENSO.md`, y **lo que falta
es el numero de `PLAN:` al final de la bateria.**

TODOS CORREN OFFLINE. Sin modelo, sin clave, sin red. El plan entero se ve en
la corrida gratis de `pytest`, en segundos.

CADA MOTIVO TRAE DOS NUMEROS: HOY y OBJETIVO. Un paso sin numeros es una
intencion —"hay que simplificar la salida"— y no se puede verificar ni saber
cuando esta hecho. `test_a_medias.py` lo exige.

COMO SE CIERRA UNO. Se hace el trabajo, el test pasa, y `strict=True` lo pone
ROJO por pasar: eso obliga a sacar la marca en el mismo commit y a bajar el
techo de `plan_techo.json`. **No se puede cerrar en silencio ni quedar marcado
para siempre.**

Y COMO SE CAMBIA UN UMBRAL, que es la unica puerta por la que este metodo se
puede corromper: **en su propio commit, ANTES del trabajo que lo va a hacer
pasar, con las cuentas escritas.** Si el umbral se mueve en el mismo commit que
lo hace pasar, no hay forma de distinguir un requisito que cambio de una vara
que se aflojo. Paso una vez, el 21-ago, con el peso del esquema, y esta anotado
en el motivo de ese test.
"""
import re
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))


# ── PASO 1 — EL TURNO SE ACHICA ─────────────────────────────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: la etapa de salida se recorta a los candados que impiden una mentira "
    "falsificable o cumplen una obligacion. HOY el grafo declara 18 nodos de "
    "salida y 9 no intervienen en 54 turnos. OBJETIVO 4 o menos: la plata, el "
    "dato atado, la obligacion y la higiene. Se cortan JUNTOS, no de a uno: "
    "estan acoplados y cortarlos de a uno ya rompio dos veces."))
def test_la_salida_tiene_cuatro_nodos_o_menos():
    from app.verifika import grafo as G
    salida = [n for n in G.NODOS if n.etapa == "salida"]
    assert len(salida) <= 4, (
        f"la etapa de salida tiene {len(salida)} nodos: "
        + ", ".join(n.id for n in salida))


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: las seis reposiciones se juntan en UNA funcion `completar` con orden "
    "de dependencia explicito. HOY son 6 funciones sueltas en hub_venta que "
    "reescriben lo que el modelo declaro, y ninguna sabe de las otras. "
    "OBJETIVO 1. La mas grande, `_cuenta_con_lo_declarado`, no se borra: sube a "
    "la etapa de resolucion, que es donde corresponde."))
def test_la_reposicion_es_una_sola_funcion():
    from app.core import hub_venta as H
    seis = ("_busqueda_de_lo_declarado", "_condicion_faltante_aplicada",
            "_cuenta_con_lo_declarado", "_reparto_de_pago_declarado",
            "_supuesto_de_pago", "_bloques_a_uno")
    vivas = [n for n in seis if hasattr(H, n)]
    assert len(vivas) <= 1, f"siguen vivas {len(vivas)} reposiciones: {vivas}"


def test_el_grafo_registra_en_las_seis_etapas():
    """CERRADO el 21-ago-2026 — FICHA 01. La marca se saco porque paso.

    ERA: registraban 17 de 32 nodos, todos de `salida`, porque el unico que
    llamaba a `registrar()` era `G.paso` y `G.paso` envuelve transformaciones de
    TEXTO. Las otras cinco etapas estaban declaradas y no se observaban, asi que
    la reposicion hubo que medirla a mano el 18-ago desde un script.

    ES: 32 de 32, medido por `banco_pruebas/peso_del_censo.py`, que dejo de
    imprimir el aviso de nodos ciegos. Los que no comparan texto declaran su
    criterio de 'intervino' en el sitio de la llamada -`G.veredicto`- o lo sacan
    comparando el estado serializado -`G.paso_datos`-, que es la misma regla de
    `G.paso` un piso mas arriba.

    LO QUE LO HACE CONFIABLE: `cuenta_repuesta` da 44%, el MISMO numero que
    `peso_reposicion.py` habia medido a mano envolviendo la funcion desde
    afuera. Dos instrumentos independientes sobre las mismas 15 charlas.

    ESTE TEST NO SE BORRA: es el candado de que no se vuelva a quedar ciego."""
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.verifika import grafo as G
    from banco_pruebas.casete import CASETES, reproducir_charla

    vistas = set()
    orig = G.registrar
    declarado = {n.id: n.etapa for n in G.NODOS}

    def espia(nodo_id, intervino, detalle=""):
        if nodo_id in declarado:
            vistas.add(declarado[nodo_id])
        return orig(nodo_id, intervino, detalle)

    G.registrar = espia
    try:
        uno = sorted(p for p in CASETES.glob("*.json")
                     if not p.name.startswith("_"))[:1]
        assert uno, "no hay casetes grabados: este test no puede medir nada"
        for p in uno:
            reproducir_charla(p)
    finally:
        G.registrar = orig

    assert vistas == set(G.ETAPAS), (
        f"solo registran las etapas {sorted(vistas)}; "
        f"faltan {sorted(set(G.ETAPAS) - vistas)}")


# ── PASO 2 — EL MODELO DEJA DE ELEGIR ────────────────────────────────

def test_el_modelo_ve_una_sola_herramienta():
    """CERRADO el 23-ago-2026 — FICHA 06. La marca se saco porque paso.

    ERA: el modelo veia NUEVE herramientas y elegia. En el 57% de los turnos
    declaraba una cosa y buscaba otra, y toda la maquinaria del reconciliador y
    de las reposiciones existia para tapar esa distancia.

    ES: ve UNA, `registrar_pedido`, con las cuatro familias informativas
    adentro. Las otras ocho NO se borraron -no se saca capacidad-: siguen en
    `_MOLDES` y en `_CUERPOS`, se validan igual, y las llama el CODIGO desde
    `hub_venta._derivar_las_busquedas`, que las deriva de lo declarado. Lo que
    se saco es la ELECCION, no la herramienta.

    ESTE TEST NO SE BORRA: es el candado de que no vuelva a crecer la lista.
    Sumarle una herramienta visible al modelo lo pone rojo en el mismo push."""
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.core import herramientas as H
    esq = H.esquemas("verifika_prod")
    assert len(esq) <= 1, f"el modelo todavia ve {len(esq)} herramientas"


def test_el_esquema_pesa_menos_de_seis_kilobytes():
    """CERRADO el 23-ago-2026 — FICHA 06. La marca se saco porque paso.

    ERA: 25.230 bytes en nueve herramientas, y el 78% eran descripciones en
    prosa metidas adentro del esquema, no los enums.

    ES: 5.891 bytes, `registrar_pedido` solo, ya con las cuatro familias
    nuevas. Un 77% menos, y viaja en CADA llamada del decisor.

    DE DONDE SALIERON LOS 19.339 BYTES. El enum de 129 TEMAS (2.299) salio
    entero: el modelo nombra el tema con las palabras del cliente y lo certifica
    `certificar_tema` contra las 785 señas de la fuente, que es la regla cero
    aplicada a un tema en vez de a un producto. La guia que le explicaba al
    modelo que cubre cada tema (3.843) salio con el: sin enum no hay nada que
    elegir. El resto son las ocho herramientas que el modelo dejo de ver.

    LO QUE NO SALIO, y es a proposito: los enum de `categoria` y de `campo`
    siguen, mudados a los campos de este molde. No estaban por peso: son la
    atadura que impide nombrar un rubro que no vendemos o un campo que la ficha
    no tiene.

    EL UMBRAL SE MOVIO DE 4.000 A 6.000 EL 21-AGO, en su propio commit y ANTES
    del trabajo: el 4.000 asumia que el molde se quedaba en 3.046 bytes, y eso
    era imposible -no puede cargar cuatro familias mas y no pesar mas-."""
    import json
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.core import herramientas as H
    peso = sum(len(json.dumps(e, ensure_ascii=False))
               for e in H.esquemas("verifika_prod"))
    assert peso <= 6000, f"el esquema pesa {peso} bytes"


# ── PASO 3 — EL CONTRATO DEL TURNO ──────────────────────────────────

def test_se_abre_un_punto_por_cada_familia_respondible():
    """CERRADO el 21-ago-2026 — FICHA 02. La marca se saco porque paso.

    ERA: `puntos()` abria SEIS tipos —item, condicion, destino, duda, pago,
    precio— y los seis salian de los campos de `registrar_pedido`, o sea que el
    sistema solo sabia abrir puntos sobre la parte transaccional. Si el cliente
    preguntaba cuantos Hz tiene un monitor no se abria NINGUN punto, asi que la
    cobertura era ciega justo en las preguntas informativas.

    ES: diez familias. Se suman ATRIBUTO, STOCK, COMPATIBILIDAD y POLITICA.

    LO QUE ESTE TEST TODAVIA NO PRUEBA, y esta medido: el molde
    `registrar_pedido` NO tiene esos campos, asi que en las 15 charlas grabadas
    las cuatro familias nuevas no se abren —190 puntos y 24 sin contestar, los
    MISMOS que antes del cambio—. La funcion sabe abrirlas; la declaracion
    todavia no las trae. Eso es la unidad siguiente, y hasta que este hecha
    **el 13% de puntos sin contestar sigue siendo un PISO y no el numero
    real.**"""
    from app.core import indice_turno as IT
    declarado = {
        "items": [{"que": "monitor", "cantidad": 1}],
        "atributos": [{"de": "monitor", "campo": "hz"}],
        "stock": ["monitor"],
        "compatibilidad": [{"que": "monitor", "para": "notebook"}],
        "temas": ["garantia"],
    }
    tipos = {p["tipo"] for p in IT.puntos(declarado)}
    faltan = {"atributo", "stock", "compatibilidad", "politica"} - tipos
    assert not faltan, f"no se abre punto para: {sorted(faltan)}"


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: cada punto termina el turno con UN estado terminal: RESUELTO, "
    "AMBIGUO que obliga a repreguntar, NO SE SABE, o CONFLICTO. HOY `indice_"
    "turno` solo marca ok/FALTA y el resultado se escribe en una linea de log. "
    "OBJETIVO que exista `estado_terminal` y que el turno no pueda salir con un "
    "punto sin estado. Es la diferencia entre observar y ser puerta, y es lo "
    "que mata la omision: hoy 1 de cada 5 turnos se manda con algo sin "
    "contestar y `punto_omitido` intervino 0 veces en 54 turnos."))
def test_el_punto_tiene_estado_terminal():
    from app.core import indice_turno as IT
    assert hasattr(IT, "estado_terminal"), (
        "no existe `indice_turno.estado_terminal`")
    validos = {"RESUELTO", "AMBIGUO", "NO_SE_SABE", "CONFLICTO"}
    assert set(getattr(IT, "ESTADOS_TERMINALES", ())) == validos


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: la COBERTURA pasa de log a puerta. HOY `indice_turno` calcula que "
    "puntos quedaron sin contestar y el numero se tira en el log del turno: 22% "
    "de los turnos cierran con al menos uno. OBJETIVO una funcion que devuelva "
    "si el turno puede salir, y su gemela PROCEDENCIA —todo dato del texto "
    "viene de un punto resuelto—. Las dos juntas reemplazan a los 17 candados y "
    "las dos se comprueban SIN saber cual era la respuesta correcta."))
def test_la_cobertura_es_una_puerta_y_no_un_log():
    from app.core import indice_turno as IT
    assert hasattr(IT, "puede_salir"), (
        "no existe `indice_turno.puede_salir(puntos)`: la cobertura sigue "
        "siendo una metrica que se escribe en el log")


# ── EL MOTOR — QUE NO TENGA UNA TIENDA ADENTRO ─────────────────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: el motor no puede contener el id de ninguna tienda. HOY `app/` "
    "menciona un tienda_id concreto 21 veces, casi todas como valor por defecto "
    "de `os.getenv`, y dos como RUTA cableada a los archivos de esa tienda. "
    "OBJETIVO cero. Es la fuga barata; la cara es la politica de negocio en "
    "Python, que tiene su propio paso."))
def test_app_no_menciona_el_id_de_ninguna_tienda():
    app = _RAIZ / "app"
    culpables = []
    for p in sorted(app.rglob("*.py")):
        for i, linea in enumerate(
                p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if "verifika_prod" in linea:
                culpables.append(f"{p.relative_to(_RAIZ)}:{i}")
    assert not culpables, (
        f"{len(culpables)} menciones de una tienda concreta dentro de app/:\n  "
        + "\n  ".join(culpables[:25]))


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: los prompts salen del codigo a la fuente. HOY `_INSTRUCCION_UNO`, "
    "`_INSTRUCCION_DOS` y `sistema()` viven en hub_venta.py. OBJETIVO que la "
    "PERSONA de la tienda —quien sos, como hablas— sea configuracion, y que en "
    "el codigo quede solo el nucleo de venta, que es igual para todas. Estaba "
    "como decision pendiente de Martin; el 19-ago dejo de ser opcional, porque "
    "un prompt en el codigo es una tienda adentro del motor."))
def test_los_prompts_no_viven_en_el_codigo():
    hub = (_RAIZ / "app" / "core" / "hub_venta.py").read_text(encoding="utf-8")
    clavados = re.findall(r"^_(?:INSTRUCCION|SISTEMA)\w*\s*=", hub, re.M)
    assert not clavados, f"siguen en el codigo: {clavados}"


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: LA TIENDA CERO, el semaforo del motor. HOY no existe. OBJETIVO una "
    "segunda tienda de OTRO RUBRO adentro del repo —deliberadamente lejos de "
    "tecnologia, para que no comparta ninguna intuicion— con su catalogo, su "
    "FAQ, sus tarifas y sus datos de cobro. Se hace PRIMERO, aunque falle: lo "
    "que se rompa al servirla es la lista de fugas REAL, medida y no supuesta. "
    "Sin esto, 'adaptable a otro ecommerce' es una promesa de venta que nadie "
    "puede verificar."))
def test_existe_una_segunda_tienda_de_otro_rubro():
    clientes = _RAIZ / "data" / "clientes"
    tiendas = [d for d in clientes.iterdir() if d.is_dir()] if clientes.exists() else []
    assert len(tiendas) >= 2, (
        f"hay {len(tiendas)} tienda(s) en data/clientes: "
        + ", ".join(d.name for d in tiendas))
