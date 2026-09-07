"""
AREA: LAS TRES QUE SE VIERON EN LAS CHARLAS REALES DEL 3 Y 4 DE SEPTIEMBRE.

Los tres defectos de esta vara salieron del puente de produccion, issue 31, y
los tres se reprodujeron offline antes de escribirse. No son hipotesis: cada
uno tiene el turno, la hora y el renglon de log que lo prueba.

Nacen con marca PLAN: y strict=True. El que implementa no reescribe la vara.
Cuando el caso pasa, `strict` obliga a sacar la marca en ese mismo commit.

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

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: D13. El primer mensaje de cada charla tiene que llevar la linea "
    "obligatoria de que es un asistente automatico. HOY no la lleva: "
    "turno.py:984 llama con_saludo_inicial con TRES argumentos y "
    "guardas_salida.py:136 la define con DOS, asi que el bloque entero de "
    "obligaciones se corta con TypeError y el except lo deja en un warning. "
    "Medido en produccion el 3-sep 17:37:17 UTC, turno tg_524215785: sale "
    "turno_guarda_error con "
    "'con_saludo_inicial() takes 2 positional arguments but 3 were given' y "
    "el cliente recibio un mensaje que arranca con el saludo del modelo, sin "
    "el aviso. OBJETIVO: la linea esta. Relato en "
    "arquitectura/FICHA_49_la_obligacion_muda.md."))
def test_el_primer_mensaje_lleva_la_linea_de_que_es_automatico():
    mesa = {"bloque": "", "puntos": []}
    salida = T._obligaciones(
        "hola, que venden?", mesa, NEGOCIO, True,
        "hola, que venden?", "", TIENDA, "t-d13")
    assert gs.linea_saludo(NEGOCIO) in salida, (
        "el primer mensaje salio sin la linea obligatoria de que es un "
        f"asistente automatico: {salida!r}")


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: D13. Ninguna obligacion del turno puede caerse en silencio. HOY "
    "el bloque de guardas es un solo try: si la primera falla, las de abajo "
    "no corren y afuera no se nota. OBJETIVO: llamar a las obligaciones no "
    "levanta TypeError. Relato en "
    "arquitectura/FICHA_49_la_obligacion_muda.md."))
def test_las_obligaciones_no_se_caen_por_una_firma_que_no_coincide():
    # No se atrapa la excepcion a proposito: si la firma vuelve a no
    # coincidir, este test tiene que verlo, no taparlo como lo tapa el vivo.
    texto = gs.asegurar_honestidad_bot("hola", "Hola, te paso los precios.",
                                       NEGOCIO)
    gs.con_saludo_inicial(texto, NEGOCIO, TIENDA)


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


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: D15. El codigo no redacta, pero lo poco que escribe no puede "
    "mentir sobre lo que el cliente pregunto. HOY el molde generico de "
    "tabla._pregunta_del_codigo pega el renglon crudo de la fila y sale "
    "'Sobre la politica de que producto tienen en mas de 5 tipos no tengo el "
    "dato confirmado', que llama politica de la casa a una pregunta del "
    "cliente sobre el catalogo. Medido en produccion el 3-sep 17:38:51 UTC, "
    "turno tg_524215788, y leido tal cual en la charla del puente. OBJETIVO "
    "0 de 2. Relato en arquitectura/FICHA_49_la_obligacion_muda.md."))
@pytest.mark.parametrize("pregunto,clausula", _PEGADAS)
def test_la_pregunta_del_codigo_no_llama_politica_a_una_pregunta_del_cliente(
        pregunto, clausula):
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
