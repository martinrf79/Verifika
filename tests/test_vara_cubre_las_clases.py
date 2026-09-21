"""EL CANDADO DE LA COBERTURA — que la vara mida las 52 clases, no seis
mensajes.

POR QUE EXISTE (21-sep-2026). La vara tenia SEIS mensajes y el diseno de la
FICHA 57 cubre 52 clases. **Optimizar contra seis mensajes es optimizar contra
seis mensajes:** el numero sube, el sistema no mejora, y no hay forma de
notarlo. Es el paso 0 de la FICHA 57 y va antes de cualquier edicion.

QUE ATA Y QUE NO. Ata la COBERTURA, no el puntaje: que cada clase de la FICHA
56 tenga al menos un mensaje que la ejercite, o este declarada como imposible
de medir en un turno. No dice si el modelo acierta -eso lo dice produccion-.

LAS CUATRO QUE NO SE PUEDEN. A11, B8, E5 y G5 necesitan memoria entre turnos.
Una vara de UN turno no las puede tocar, y fingir que si seria peor que no
medirlas. Estan declaradas en la vara con el motivo.
"""
import json
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARA = os.path.join(RAIZ, "banco_pruebas", "vara_interpretacion.json")
FICHA = os.path.join(RAIZ, "arquitectura", "FICHA_56_el_idioma_del_cliente.md")


def _vara() -> dict:
    return json.load(open(VARA, encoding="utf-8"))


def _clases_de_la_ficha() -> set:
    """LAS CLASES SALEN DE LA FICHA, NO DE UNA LISTA ESCRITA ACA. Si alguien
    agrega una clase y no agrega un mensaje, este test se pone rojo solo. Una
    lista copiada seria la segunda descripcion de lo mismo, que es lo que el
    bloque 0 de CLAUDE.md prohibe."""
    texto = open(FICHA, encoding="utf-8").read()
    return set(re.findall(r"^\*\*([A-G]\d+) · ", texto, re.M))


def _clases_cubiertas(v: dict) -> set:
    """Lo que la vara ejercita: las casillas y lo que cada mensaje declara
    cubrir en su `_cubre`, porque una casilla puede medir una clase mientras
    el mensaje ejercita tres."""
    fuera = set()
    for m in v["mensajes"]:
        for c in m["casillas"]:
            if c.get("clase"):
                fuera.add(c["clase"])
        fuera |= set(re.findall(r"\b([A-G]\d+)\b", m.get("_cubre", "")))
        fuera |= set(re.findall(r"\b([A-G]\d+)\b", m.get("dificultad", "")))
    return fuera


def test_la_ficha_declara_las_clases_que_dice_declarar():
    """Si esto falla, el formato de la ficha cambio y el candado quedo ciego."""
    clases = _clases_de_la_ficha()
    assert len(clases) >= 50, (
        f"la ficha 56 declara {len(clases)} clases y tendrian que ser 52; "
        "cambio el formato y este candado dejo de leerla")


def test_cada_clase_tiene_un_mensaje_o_esta_declarada_imposible():
    v = _vara()
    imposibles = set(v["_clases_que_NO_se_pueden_medir_en_un_turno"]) - {
        "_por_que"}
    faltan = _clases_de_la_ficha() - _clases_cubiertas(v) - imposibles
    assert not faltan, (
        f"clases de la FICHA 56 que ninguna casilla ejercita y que tampoco "
        f"estan declaradas imposibles: {sorted(faltan)}")


def test_las_imposibles_dicen_POR_QUE():
    """Una clase sin medir y sin motivo es una clase olvidada. Con motivo es
    una decision."""
    v = _vara()
    d = v["_clases_que_NO_se_pueden_medir_en_un_turno"]
    for clase, motivo in d.items():
        assert len(str(motivo)) > 30, f"{clase} no dice por que no se mide"


def test_la_deuda_dice_QUE_FALTA_CONSTRUIR():
    """Una casilla `sin_mecanismo` en cero y muda es ruido. Con el motivo
    escrito ES la especificacion de lo que la FICHA 57 tiene que construir, y
    es el mismo recurso con el que `envio_va` se convirtio en el campo `va`."""
    v = _vara()
    sin = [(m["id"], c) for m in v["mensajes"] for c in m["casillas"]
           if c["tipo"] == "sin_mecanismo"]
    assert sin, "la vara dejo de declarar deuda: ¿se construyo todo?"
    for mid, c in sin:
        assert len(str(c.get("_por_que", ""))) > 40, (
            f"{mid}/{c['n']} no dice que falta construir")


def test_el_NUCLEO_del_piso_no_se_toca():
    """LOS SEIS PRIMEROS SON EL PISO MEDIDO, 31 de 31 en 8 de 9 corridas. Si
    entran mensajes nuevos al nucleo, el piso deja de tener con que
    compararse y se pierde la unica referencia que hay."""
    v = _vara()
    nucleo = [m for m in v["mensajes"] if m.get("nucleo")]
    assert [m["id"] for m in nucleo] == ["M1", "M2", "M3", "M4", "M5", "M6"]
    puntuables = sum(1 for m in nucleo for c in m["casillas"]
                     if c["tipo"] != "sin_mecanismo")
    assert puntuables == 31, (
        f"el nucleo tiene {puntuables} casillas puntuables y el piso se midio "
        "sobre 31: el numero dejo de ser comparable")
