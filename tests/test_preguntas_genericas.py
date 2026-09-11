"""CANDADO DE LA CASILLA — un tipo de pregunta, una respuesta generica.

La lista de tipos vive en `banco_pruebas/preguntas.py` y ahora cada uno
declara COMO suena su respuesta. Este candado cuida las tres cosas que
hacen que esa lista sirva para algo:

  1. Ni un tipo sin casilla, ni una casilla sin tipo. Si alguien agrega
     una clase difícil y no escribe como se contesta, el test lo frena.
  2. Cero digitos adentro del molde. Un numero escrito ahi seria un dato
     sin fuente: la plata la arma la calculadora y la spec sale de la
     ficha. El molde tiene huecos, no cifras.
  3. Cada tipo sigue apuntando a familias vivas de `app/core/familias.py`.
     Dos taxonomias que se despegan es el telefono descompuesto que el
     proyecto ya pago tres veces.

Y dice sobre CUANTOS casos paso, no solo que paso.
"""
import re

from app.core import familias
from banco_pruebas import preguntas as P

_DIGITO = re.compile(r"\d")


def test_cada_clase_tiene_su_respuesta_generica():
    clases = [c[0] for c in P.CLASES]
    faltan = [c for c in clases if c not in P.RESPUESTA_GENERICA]
    sobran = [c for c in P.RESPUESTA_GENERICA if c not in clases]
    assert not faltan, f"clases sin respuesta generica: {faltan}"
    assert not sobran, f"respuestas sin clase: {sobran}"
    assert len(P.RESPUESTA_GENERICA) == len(clases) == 20, (
        f"{len(clases)} clases, {len(P.RESPUESTA_GENERICA)} respuestas")


def test_el_molde_no_trae_un_solo_digito():
    con_numero = [c for c, t in P.RESPUESTA_GENERICA.items() if _DIGITO.search(t)]
    assert not con_numero, f"numero sin fuente en el molde: {con_numero}"


def test_toda_respuesta_tiene_hueco_y_ninguno_queda_a_medias():
    sin_hueco = []
    for clase in P.RESPUESTA_GENERICA:
        if not P.huecos(clase):
            sin_hueco.append(clase)
    assert not sin_hueco, f"molde sin ningun hueco de dato: {sin_hueco}"
    # Los dos delimitadores tienen que cerrar: un hueco a medias se sirve roto.
    # Son DOS desde el 11-sep: llaves dobles para los tres que llena el codigo,
    # menor y mayor para los que escribe el modelo con la palabra de la ficha.
    for clase, texto in P.RESPUESTA_GENERICA.items():
        assert texto.count("{{") == texto.count("}}"), f"llave abierta en {clase}"
        assert texto.count("<") == texto.count(">"), f"signo abierto en {clase}"
        assert texto.count("{{") + texto.count("<") == len(P.huecos(clase)), (
            f"hueco mal cerrado en {clase}")


def test_cada_clase_cae_en_familias_vivas():
    vivas = set(familias.FAMILIAS)
    revisadas = 0
    for clase, campos in P.CLASE_A_CAMPOS.items():
        assert clase in P.RESPUESTA_GENERICA, f"{clase} sin casilla"
        for campo in campos:
            assert campo in vivas, f"{clase} apunta a una familia muerta: {campo}"
            revisadas += 1
    assert revisadas >= 20, f"solo {revisadas} pares clase-familia revisados"
