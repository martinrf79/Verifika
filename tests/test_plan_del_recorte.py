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

def test_la_salida_tiene_cuatro_nodos_o_menos():
    """CERRADO el 24-ago-2026 — FICHA 10. La marca se saco porque paso.

    ERA: 18 nodos de salida en fila, cada uno con su `G.paso` en
    `procesar_venta`. SON: cuatro puertas en `app/core/salida.py` —la
    procedencia, la plata, la obligacion y la higiene—, una por pregunta que
    hay que contestarle al mensaje.

    NO SE BORRO NI UNA COMPROBACION, y eso es deliberado. La regla del plan
    dejaba borrar lo que no impide una mentira falsificable, pero las nueve
    que no intervienen sobre el corpus no estan muertas: el corpus no tenia un
    CBU falso ni un "sos un bot". Borrarlas para que un numero baje seria
    cambiar defensa contra la alucinacion por prolijidad, o sea lo contrario
    de la prioridad uno. Lo que se corto son las DIECISIETE COSTURAS: los dos
    errores de plata de agosto no vivian adentro de una pieza, vivian entre
    dos, y el orden que las separaba estaba repartido en el hub en vez de
    escrito en un solo lugar.

    Y el veredicto por engranaje no se pierde: cada pieza sigue pasando por
    `G.paso` adentro de su puerta, asi que se sigue midiendo cual toco el
    mensaje, comparando el texto y no preguntandole a la pieza."""
    from app.verifika import grafo as G
    salida = [n for n in G.NODOS if n.etapa == "salida"]
    assert len(salida) <= 4, (
        f"la etapa de salida tiene {len(salida)} nodos: "
        + ", ".join(n.id for n in salida))


def test_la_reposicion_es_una_sola_funcion():
    """CERRADO el 24-ago-2026 — FICHA 11. La marca se saco porque paso.

    ERA: seis funciones sueltas en `hub_venta`, cada una con su `G.paso_datos`
    en `procesar_venta`, y ninguna sabia de las otras. ES: una puerta,
    `reposicion.completar`, con el orden de dependencia escrito en el docstring
    del modulo en vez de repartido en cinco comentarios del hub.

    NO SE BORRO NI UNA REPOSICION, igual que la FICHA 10 no borro una sola
    comprobacion de salida: las seis corren adentro, cada una con su
    `G.paso_datos`, asi que el veredicto por engranaje sale con el mismo
    detalle y `peso_reposicion.py` ve lo mismo que veia. Lo que se corto son
    las CINCO COSTURAS.

    Y LA CONDICION DE LA MEMORIA BAJO CON ELLAS. La de la FICHA 04 -la memoria
    se abre si el reconciliador reclamo la cuenta o si el turno no certifico
    nada- vivia en `procesar_venta`, a nueve lineas de la unica pieza que la
    usa. Esa distancia es la forma exacta del defecto del total perdido.

    LO QUE EL BARRIDO VIO APENAS SE JUNTARON, y no lo podia ver antes: la
    cuenta cotizando ids que la busqueda de la MISMA puerta acababa de traer.
    Con seis nodos el barrido le daba a cada uno el mismo estado sin tocar, o
    sea que medía la cuenta sobre un turno donde la busqueda no habia pasado.
    En el turno vivo pasa siempre."""
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


# CERRADO POR LA FICHA 08 (24-ago-2026). `estado_terminal` existe y `cobertura`
# le pone la casilla `estado` a TODOS los puntos. La casilla puede salir vacia
# —eso es la omision— pero ya no puede faltar, que es lo que la puerta de la
# ficha 09 necesita para distinguir al turno que pregunto bien del que se
# olvido algo. Los doce casos de cada final estan en `test_estado_terminal.py`.
def test_el_punto_tiene_estado_terminal():
    from app.core import indice_turno as IT
    assert hasattr(IT, "estado_terminal"), (
        "no existe `indice_turno.estado_terminal`")
    # LOS CUATRO DE LA FICHA 08 DICEN COMO TERMINO ALGO QUE EL CLIENTE PIDIO.
    # Los dos ultimos son de la FICHA 15 y son de otra familia: como termino lo
    # que el BOT tenia que proponer. El vocabulario sigue cerrado; lo que crecio
    # es lo que el indice mide.
    validos = {"RESUELTO", "AMBIGUO", "NO_SE_SABE", "CONFLICTO",
               "OFRECIDO", "NO_CORRESPONDE"}
    assert set(getattr(IT, "ESTADOS_TERMINALES", ())) == validos


# CERRADO POR LA FICHA 09 (24-ago-2026). `puede_salir(puntos)` existe y decide
# el turno: frena lo que puede PROBAR —el punto quedo sin estado terminal Y el
# codigo tenia con que contestarlo—, y el actuador repone el renglon con
# material sellado. Medido sobre las 15 charlas grabadas: las omisiones bajaron
# de 38 a 28 y los puntos RESUELTOS subieron de 178 a 188, sin mover el piso.
# Los casos estan en `test_puerta_cobertura.py`.
#
# LA GEMELA PROCEDENCIA —que todo dato del texto venga de un punto resuelto—
# NO la cierra esta ficha. Hoy vive con otro nombre y en otro modulo:
# `atadura_prosa`, que ata cada afirmacion a su fuente y poda la que no tiene
# respaldo. Juntarla con el indice, para que la fuente sea el PUNTO y no el
# producto, es otra unidad de trabajo y esta anotada en `PENDIENTE.md`.
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


# ── LO QUE LA FICHA 11 DEJO ABIERTO ────────────────────────────────────
#
# LOS CINCO DE ABAJO NO SON PASOS NUEVOS. Estaban abiertos desde el 24-ago y
# contados en PROSA, en `arquitectura/LO_QUE_QUEDO_ABIERTO_DE_LA_11.md`, que es
# el unico formato que este repo ya sabe que envejece: ningun contador los veia,
# asi que el techo del plan decia 3 cuando faltaban 8. El techo subio a 8 en su
# propio commit, con la cuenta escrita, ANTES de este archivo.
#
# El relato entero de cada uno sigue en la ficha. Aca va lo unico que una
# maquina puede verificar: el numero de HOY, el numero OBJETIVO, y el assert.


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: la cuenta sube a la etapa de resolucion, como pide DECISIONES.md #8. "
    "HOY la cuenta se arma DESPUES del reconciliador: sobre el primer casete el "
    "reconciliador deja su marca en la posicion 5 del turno y `cuenta_repuesta` "
    "en la 8, adentro de la puerta de reposicion, y `cuenta_repuesta` interviene "
    "en 19 de 54 turnos. OBJETIVO que la cuenta quede ANTES del reconciliador. "
    "NO SE HACE MUDANDOLA Y VIENDO QUE PASA: la condicion que la gobierna "
    "-`falta_la_cuenta`- la emite el reconciliador, asi que subirla sola la deja "
    "armandose sin saber si el cliente pidio precio, que es EXACTAMENTE el "
    "defecto que curo la FICHA 04 el 21-ago. Cierra cuando el reclamo tipado "
    "salga de algo que corra antes, o cuando el reconciliador suba con ella."))
def test_la_cuenta_se_arma_antes_del_reconciliador():
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.verifika import grafo as G
    from banco_pruebas.casete import CASETES, reproducir_charla

    orden = []
    orig = G.registrar

    def espia(nodo_id, intervino, detalle=""):
        orden.append(nodo_id)
        return orig(nodo_id, intervino, detalle)

    G.registrar = espia
    try:
        uno = sorted(p for p in CASETES.glob("*.json")
                     if not p.name.startswith("_"))[:1]
        assert uno, "no hay casetes grabados: este test no puede medir nada"
        reproducir_charla(uno[0])
    finally:
        G.registrar = orig

    assert "reconciliador" in orden and "cuenta_repuesta" in orden, (
        f"el turno no ejercita los dos engranajes que este paso compara: "
        f"{sorted(set(orden))}")
    assert orden.index("cuenta_repuesta") < orden.index("reconciliador"), (
        f"la cuenta se arma en la posicion {orden.index('cuenta_repuesta')} y "
        f"el reconciliador en la {orden.index('reconciliador')}: la cuenta "
        "sigue corriendo despues de quien emite su condicion")


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: `_bloque_hallazgo` sale de `hub_venta` y la ida y vuelta se termina. "
    "HOY son 2 cruces vivos: `hub_venta.py:51` importa `_RE_HAY_CUENTA` y "
    "`_norm_renglon` de `salida.py` por la cabecera, y `salida.py:70` importa "
    "`hub_venta` PEREZOSO para poder llamar a `_bloque_hallazgo`, que es el "
    "unico que le queda despues de que la FICHA 11 se llevara los otros dos. "
    "OBJETIVO cero cruces: ni `_bloque_hallazgo` en el hub, ni un import "
    "perezoso de hub en la salida. LO QUE FALTA ES UNA DECISION, NO UNA "
    "MUDANZA: los dos patrones son de `salida.py`, asi que llevar la funcion a "
    "`reposicion` no saca la ida y vuelta, la da vuelta. Primero se decide de "
    "quien son `_RE_HAY_CUENTA` y `_norm_renglon`, despues se muda."))
def test_el_bloque_hallazgo_no_vive_en_el_hub():
    hub = (_RAIZ / "app" / "core" / "hub_venta.py").read_text(encoding="utf-8")
    sal = (_RAIZ / "app" / "core" / "salida.py").read_text(encoding="utf-8")
    cruces = []
    if re.search(r"^def _bloque_hallazgo\b", hub, re.M):
        cruces.append("hub_venta define _bloque_hallazgo")
    for i, linea in enumerate(sal.splitlines(), 1):
        if re.search(r"\bimport\s+hub_venta\b", linea):
            cruces.append(f"salida.py:{i} importa hub_venta")
    assert not cruces, f"quedan {len(cruces)} cruces: {cruces}"


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: el corpus ejercita las comprobaciones que hoy no despierta ninguna "
    "charla. HOY 9 engranajes corren en los 54 turnos de las 15 charlas "
    "grabadas y NO intervienen en ninguno -`aduana`, `honestidad_bot`, "
    "`sin_cobro_inventado`, `sin_json`, `sin_negar_lo_traido`, "
    "`hallazgo_repuesto`, `busqueda_repuesta`, `condicion_repuesta` y "
    "`cierre`-, y los 26 guiones numerados 26 a 38 que se escribieron para "
    "despertarlos tienen 0 casetes grabados. OBJETIVO que los 13 numeros esten "
    "grabados, para que la evidencia de que una guardia sobra deje de ser 'el "
    "corpus no la toca' y pase a ser 'la toca y no hace falta'. NO SE BORRA "
    "NINGUNA ANTES: el corpus de hoy no tiene un CBU falso ni un 'sos un bot', "
    "asi que hoy los 9 ceros prueban que la charla no los ejercita, no que "
    "sobren. GRABAR ESOS CASETES ES LO UNICO DE ESTE PASO QUE NECESITA LA "
    "CLAVE PAGA y por eso no se hace de paso en otra sesion."))
def test_los_guiones_que_despiertan_las_guardias_estan_grabados():
    guiones = _RAIZ / "banco_pruebas" / "guiones"
    casetes = _RAIZ / "banco_pruebas" / "casetes"
    _RANGO = re.compile(r"^(2[6-9]|3[0-8])_")
    pedidos = sorted(p.stem for p in guiones.glob("*.txt")
                     if _RANGO.match(p.name))
    assert pedidos, "no hay guiones 26 a 38: este test no puede medir nada"
    grabados = {p.stem for p in casetes.glob("*.json")}
    faltan = [g for g in pedidos if g not in grabados]
    assert not faltan, (
        f"{len(faltan)} de {len(pedidos)} guiones del rango 26-38 no tienen "
        f"casete grabado: {faltan[:8]}")


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: existe UN numero de VENTA. HOY el piso de las 15 charlas guarda 8 "
    "varas -piso, puntos, total, charlas, llamadas_max, llamadas_total, "
    "largo_max, largo_promedio- y las 8 son defensivas: miden que no se caiga, "
    "que no invente, que no se alargue. Cero miden si vende. OBJETIVO al menos "
    "una vara `venta_*` en `banco_pruebas/casetes/_piso.json`, medida sobre las "
    "mismas 15 charlas y con el mismo mecanismo de piso que las otras 8. "
    "ESTE PASO SE ESCRIBE AUNQUE TODAVIA NO SEPAMOS QUE SE MIDE, y es el unico "
    "de los cinco que toca la prioridad uno: un sistema que solo mide lo que no "
    "debe hacer termina siendo un bot que no hace nada mal y no vende. QUE "
    "cuenta como venta -avance, cierre, donde se cae el cliente- es una "
    "decision de Martin; el prefijo es solo donde aterriza."))
def test_el_piso_guarda_algun_numero_de_venta():
    import json
    piso = json.loads((_RAIZ / "banco_pruebas" / "casetes" / "_piso.json")
                      .read_text(encoding="utf-8"))
    varas = [k for k in piso if not k.startswith("_")]
    assert varas, "el piso no tiene ninguna vara: este test no mide nada"
    de_venta = [k for k in varas if k.startswith("venta_")]
    assert de_venta, (
        f"las {len(varas)} varas del piso son defensivas y ninguna mide venta: "
        + ", ".join(sorted(varas)))


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: el piso de la puerta guarda el crudo y no la razon. HOY "
    "`banco_pruebas/puerta_piso.json` guarda 6 varas como PORCENTAJE -items, "
    "destinos, reparto_pago, restricciones, pide_precio, contradicciones- y 0 "
    "de las 6 guardan su numerador y su denominador por separado. OBJETIVO las "
    "6 con `<vara>_n` y `<vara>_de`, asi el rojo dice CUAL de los dos se movio. "
    "POR QUE NO ES COSMETICA: el 22-ago se puso rojo con `reparto_pago: 11.1% "
    "-> 9.1%` y no entendia menos, sacaba el MISMO 1 turno; lo que cambio fue "
    "el denominador, porque el modelo declaro reparto en 11 turnos en vez de 9. "
    "Una razon contra un corpus mutable mide dos cosas a la vez y no puede "
    "decir cual se movio, que es la misma enfermedad que la FICHA 03 curo en el "
    "otro piso."))
def test_el_piso_de_la_puerta_guarda_crudo_y_no_razon():
    import json
    piso = json.loads((_RAIZ / "banco_pruebas" / "puerta_piso.json")
                      .read_text(encoding="utf-8"))
    varas = [k for k in piso if not k.startswith("_")]
    assert varas, "el piso de la puerta no tiene varas: este test no mide nada"
    sin_crudo = [v for v in varas
                 if f"{v}_n" not in piso or f"{v}_de" not in piso]
    assert not sin_crudo, (
        f"{len(sin_crudo)} de {len(varas)} varas guardan una razon sin su "
        f"numerador y su denominador: {sin_crudo}")
