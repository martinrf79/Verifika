"""
AREA: LAS TRES QUE SE VIERON EN LAS CHARLAS REALES DEL 3 Y 4 DE SEPTIEMBRE.

Los tres defectos de esta vara salieron del puente de produccion, issue 31, y
los tres se reprodujeron offline antes de escribirse. No son hipotesis: cada
uno tiene el turno, la hora y el renglon de log que lo prueba.

Nacen con marca PLAN: y strict=True. El que implementa no reescribe la vara.
Cuando el caso pasa, `strict` obliga a sacar la marca en ese mismo commit.

UNA VARA DE D13 SE CAMBIO A PROPOSITO, en su propio commit y ANTES del arreglo.
La primera version llamaba `con_saludo_inicial` con tres argumentos y pedia que
no reventara: eso no mide el requisito, mide UNA de las dos formas de arreglarlo
—agregarle un parametro a la funcion— y se la habria podido poner en verde con
un parametro de adorno. Lo que hay que medir es que la obligacion SALGA y que
las tres sean independientes, y eso es lo que miden las dos de ahora. La vara
quedo mas dura, no mas blanda.

Y NO SE MIDE POR EL LOG, aunque el defecto se haya visto ahi. La bateria filtra
structlog en CRITICAL para no imprimir dos megas de JSON por corrida, asi que un
warning no llega a ningun capturador y un test que lo buscara daria verde
siempre, que es la peor clase de test que existe. Se mide por comportamiento:
la linea tiene que estar en el texto, y con la primera guarda reventada a mano
la de abajo tiene que salir igual.

Relato completo en arquitectura/FICHA_49_la_obligacion_muda.md.
Los numeros de desconexion, D13 D14 y D15, viven en
arquitectura/MAPA_CABLEADO.md y en ningun otro lado.
"""
import re
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import guardas_salida as gs  # noqa: E402
from app.core import tabla as TB  # noqa: E402
from app.core import turno as T  # noqa: E402

TIENDA = "verifika_prod"
NEGOCIO = "Verifika Tech"


# ── D13 — LA OBLIGACION DE DECIR QUE ES UN BOT NO SALE NUNCA ────────────────

def test_el_primer_mensaje_lleva_la_linea_de_que_es_automatico():
    """D13, CERRADA el 7-sep. Hasta el arreglo esto era rojo: `turno.py` le
    pasaba a `con_saludo_inicial` un tercer argumento que la funcion no tiene,
    el bloque entero de obligaciones se cortaba con TypeError y el cliente
    recibia un mensaje sin el aviso de que habla con algo automatico. Medido
    en produccion el 3-sep 17:37:17 UTC, turno tg_524215785."""
    mesa = {"bloque": "", "puntos": []}
    salida = T._obligaciones(
        "hola, que venden?", mesa, NEGOCIO, True,
        "hola, que venden?", "", TIENDA, "t-d13")
    assert gs.linea_saludo(NEGOCIO) in salida, (
        "el primer mensaje salio sin la linea obligatoria de que es un "
        f"asistente automatico: {salida!r}")


def test_una_obligacion_que_se_cae_no_apaga_a_las_otras(monkeypatch):
    """D13, la otra mitad, CERRADA el 7-sep. Las tres obligaciones iban dentro
    de un solo try: la primera que fallaba apagaba a las de abajo y afuera
    quedaba un warning sin nombre. Esa forma se comio la misma obligacion dos
    veces seguidas, el 3-sep la honestidad y el 6-sep el saludo. Ahora cada
    una se cae sola."""
    def _revienta(*a, **k):
        raise RuntimeError("guarda rota a proposito")

    monkeypatch.setattr(gs, "asegurar_honestidad_bot", _revienta)
    mesa = {"bloque": "", "puntos": []}
    salida = T._obligaciones("hola, que venden?", mesa, NEGOCIO, True,
                             "hola, que venden?", "", TIENDA, "t-d13c")
    assert gs.linea_saludo(NEGOCIO) in salida, (
        "una guarda rota se llevo puesta a la de abajo: "
        f"{salida!r}")


# ── D14 — UN UNIVERSAL SOBRE EL CATALOGO SIN HERRAMIENTA QUE LO MIRE ────────

_UNIVERSALES = (
    "Actualmente, no contamos con ningun producto que disponga de mas de 5 "
    "variantes o tipos diferentes en nuestro catalogo.",
    "No tenemos ningun producto de origen estadounidense en todo el catalogo.",
)


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: D14. Una fila SIN MATERIAL no puede afirmar nada sobre el catalogo "
    "entero. HOY sale tal cual y encima se contradice dos renglones despues "
    "con la pregunta del codigo, que dice que no tiene el dato. Medido en "
    "produccion el 3-sep 17:38:51 UTC, turno tg_524215788: "
    "busquedas_derivadas con hechas=[] y el cliente leyo 'no contamos con "
    "ningun producto que disponga de mas de 5 variantes'. La guarda vieja "
    "-hub_venta_afirmo_sobre_el_catalogo- se apago con el hub el 3-sep y no "
    "la reemplazo nadie. OBJETIVO 0 de 2. Relato en "
    "arquitectura/FICHA_49_la_obligacion_muda.md."))
@pytest.mark.parametrize("texto_del_modelo", _UNIVERSALES)
def test_un_universal_sobre_el_catalogo_no_sale_de_una_fila_sin_material(
        texto_del_modelo):
    mesa = {"bloque": "", "puntos": [
        {"id": "temas:1", "estado": "sin_material",
         "pregunto": "la politica de que producto tienen en mas de 5 tipos"}]}
    respuesta = {"apertura": "",
                 "puntos": [{"id": "temas:1", "texto": texto_del_modelo}],
                 "pregunta_final": ""}
    salida = TB.armar(respuesta, mesa, "t-d14", {})
    assert texto_del_modelo not in salida, (
        "una casilla sin material afirmo sobre el catalogo entero y salio "
        f"al cliente: {salida!r}")


# ── D15 — LA PREGUNTA DEL CODIGO LLAMA POLITICA A UNA PREGUNTA DEL CLIENTE ──

# La frase del cliente, y la parte que NO puede viajar pegada adentro de la
# pregunta que escribe el codigo.
_PEGADAS = (
    ("la politica de que producto tienen en mas de 5 tipos",
     "que producto tienen en mas de 5 tipos"),
    ("la politica de cuantos productos tenes en catalogo",
     "cuantos productos tenes en catalogo"),
)

_INTERROGATIVA = re.compile(
    r"(?i)\bla politica de (?:que|cual|cuales|cuanto|cuantos|cuanta|"
    r"cuantas|como|donde|cuando)\b")


@pytest.mark.parametrize("pregunto,clausula", _PEGADAS)
def test_la_pregunta_del_codigo_no_llama_politica_a_una_pregunta_del_cliente(
        pregunto, clausula):
    """D15, CERRADA el 7-sep. El molde generico pegaba el renglon crudo y
    salia 'Sobre la politica de que producto tienen en mas de 5 tipos no tengo
    el dato confirmado', que le atribuye a la casa una politica que el cliente
    nunca nombro. Medido el 3-sep 17:38:51 UTC, turno tg_524215788."""
    fila = {"id": "temas:1", "estado": "sin_material", "pregunto": pregunto}
    escrita = TB._pregunta_del_codigo(fila)
    assert not _INTERROGATIVA.search(escrita), (
        "el codigo llamo politica a una pregunta del cliente: "
        f"{escrita!r}")
    assert clausula not in escrita, (
        "la frase del cliente viajo pegada adentro de la pregunta que "
        f"escribe el codigo: {escrita!r}")


def test_una_politica_de_verdad_sigue_saliendo_con_su_nombre():
    """LA CONTRACARA, y esta nace VERDE: arreglar D15 no puede volver mudo el
    caso legitimo. Cuando el punto SI es una politica de la casa, decir su
    nombre es lo correcto y no se toca."""
    fila = {"id": "temas:1", "estado": "sin_material",
            "pregunto": "la politica de garantia"}
    escrita = TB._pregunta_del_codigo(fila)
    assert "garantia" in escrita
    assert escrita.strip().endswith("?")
