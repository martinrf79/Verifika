"""LA PLANTILLA DE VENTA — el esquema, el mapa y cada caso por el ejecutor, sin modelo (25-oct-2026, FICHA 80).

  1. el mapa: cada clase con su caso, y las 58, las J y las K clasificadas en alguna.
  2. los casos: frases, variaciones, acciones del menu, y ninguna frase copiada de la vara.
  3. lo que devuelve cada motor del modelo: la etiqueta, de la lista de respuestas, y la traduccion alcanzan para que
     el codigo arme la agenda del caso sin mirar nada mas.
  4. el llenado con la fuente de verifika_prod: cada caso validado por el ejecutor. Los que fallan por un defecto del
     codigo van como xfail estricto, uno por defecto.
"""
import json
import os
import re

import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)


@pytest.fixture(scope="module")
def P():
    from banco_pruebas.plantilla_venta import casos, mapa
    return {"casos": casos, "mapa": mapa}


@pytest.fixture(scope="module")
def llenado():
    from banco_pruebas.plantilla_venta import llenar
    llenar.entorno()
    return {c["id"]: c for c in llenar.llenar("verifika_prod")["casos"]}


# ══ 1. EL MAPA ═══════════════════════════════════════════════════════════════

def test_cada_clase_tiene_su_caso_y_cada_caso_su_clase(P):
    clases = {c["id"] for c in P["mapa"].CLASES}
    de_casos = [c["clase"] for c in P["casos"].CASOS]
    ids = [c["id"] for c in P["casos"].CASOS]
    assert len(set(ids)) == len(ids), "hay ids de caso repetidos"
    assert set(de_casos) <= clases, sorted(set(de_casos) - clases)
    sin = sorted(clases - set(de_casos))
    assert not sin, f"{len(sin)} de {len(clases)} clases sin caso: {sin}"


def test_las_58_las_j_y_las_k_estan_clasificadas(P):
    vara = json.load(open(os.path.join(REPO, "banco_pruebas", "vara_58.json"), encoding="utf-8"))
    origen = {o[3:] for c in P["mapa"].CLASES for o in c["origen"] if o.startswith("58:")}
    charlas = [c["id"] for c in vara["charlas"]]
    sin = [c for c in charlas if c not in origen]
    assert not sin, f"{len(sin)} de {len(charlas)} charlas de la vara sin clase: {sin}"


def test_cada_clase_tiene_etapa_y_un_origen_conocido(P):
    M = P["mapa"]
    for c in M.CLASES:
        assert c["etapa"] in M.ETAPAS, c["id"]
        assert c["origen"], c["id"]
        assert all(o.split(":")[0] in M.FUENTES or o == "nuevo" for o in c["origen"]), c["id"]


def test_las_situaciones_existen_en_la_base_de_conocimiento(P):
    base = json.load(open(os.path.join(REPO, "data", "clientes", "verifika_prod", "base_conocimiento.json"),
                          encoding="utf-8"))
    ids = {c["id"] for c in base["categorias"]}
    malas = [(c["id"], s) for c in P["mapa"].CLASES for s in c["situaciones"] if s not in ids]
    assert not malas, malas


# ══ 2. LOS CASOS ═════════════════════════════════════════════════════════════

def test_cada_caso_tiene_tres_frases_con_su_variacion(P):
    letras = set(P["mapa"].VARIACIONES)
    pocas = [c["id"] for c in P["casos"].CASOS if len(c["frases"]) < 3]
    malas = [(c["id"], v) for c in P["casos"].CASOS for _, v, _ in c["frases"] if not v or set(v) - letras]
    total = sum(len(c["frases"]) for c in P["casos"].CASOS)
    assert not pocas, f"{len(pocas)} casos con menos de tres frases: {pocas}"
    assert not malas, malas
    assert total >= 450, f"{total} frases"


def test_cada_agenda_usa_solo_el_menu(P):
    from app.core.flujo.agenda import ACCIONES
    malas = []
    for c in P["casos"].CASOS:
        for p in c["agenda"] + [p for a in c["antes"] for p in a]:
            if p.get("accion") not in ACCIONES:
                malas.append((c["id"], p.get("accion")))
    assert not malas, malas


def test_la_herramienta_de_la_clase_esta_en_su_agenda(P):
    """Si la clase tiene herramienta, su caso la usa: el caso es la etiqueta de esa clase. La respuesta corta a una
    pregunta del bot no: la ata el codigo a lo que esa pregunta dejo dicho que hace."""
    malas = []
    for c in P["casos"].CASOS:
        h = P["mapa"].POR_ID[c["clase"]]["herramienta"]
        if not h.startswith("falta:") and not c["responde"] and h not in {p["accion"] for p in c["agenda"]}:
            malas.append((c["id"], h))
    assert not malas, malas


# ══ 3. LO QUE DEVUELVE CADA MOTOR DEL MODELO ═════════════════════════════════

def test_la_lista_de_respuestas_es_la_de_respuestas_py(P):
    """La etiqueta usa la misma lista que mide `banco_pruebas/respuestas.py`: se lee de su fuente, sin importarlo."""
    import ast
    arbol = ast.parse(open(os.path.join(REPO, "banco_pruebas", "respuestas.py"), encoding="utf-8").read())
    corta = next(n.value for n in arbol.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CORTA")
    assert tuple(k.value for k in corta.keys) == P["casos"].RESPUESTAS


def test_la_etiqueta_y_la_traduccion_alcanzan_para_armar_la_agenda(P):
    """Lo que el codigo necesita: con la etiqueta de cada parte y su traduccion, la agenda del caso sale igual. Las
    clases sin herramienta y las respuestas cortas, que ata el codigo, quedan aparte y se cuentan."""
    C, M = P["casos"], P["mapa"]
    validas = set(C.RESPUESTAS)
    malas, armadas, aparte = [], 0, 0
    for c in C.CASOS:
        h = M.POR_ID[c["clase"]]["herramienta"]
        e = C.etiquetas(c, c["agenda"], h)
        assert all(r in validas or r.startswith("falta:") for x in e for r in x["respuestas"]), c["id"]
        if h.startswith("falta:") or c["etiqueta"]:
            aparte += 1
            continue
        armadas += 1
        if C.a_agenda(C.traducciones(c["agenda"]), e) != c["agenda"]:
            malas.append(c["id"])
    assert not malas, f"de {armadas} agendas no salen {malas}"
    assert armadas >= 130, f"{armadas} agendas armadas, {aparte} aparte"


def _palabras(t: str) -> set:
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower())
    return set(re.findall(r"[a-z0-9]+", "".join(ch for ch in t if unicodedata.category(ch) != "Mn")))


def test_ninguna_frase_copia_la_vara(llenado):
    """La vara mide: una frase de la plantilla que repite un turno de las 58 la contamina."""
    vara = json.load(open(os.path.join(REPO, "banco_pruebas", "vara_58.json"), encoding="utf-8"))
    turnos = [_palabras(t["texto"]) for c in vara["charlas"] for t in c["turnos"]]
    copias = []
    frases = [(c["id"], f["texto"]) for c in llenado.values() for f in c.get("frases") or []]
    for cid, f in frases:
        w = _palabras(f)
        if len(w) < 4:
            continue  # "el primero", "si", "gracias": las respuestas cortas son de todas las charlas
        if any(len(w & t) / len(w | t) >= 0.75 for t in turnos):
            copias.append((cid, f))
    assert not copias, f"{len(copias)} de {len(frases)} frases copian la vara: {copias[:5]}"


# ══ 4. EL LLENADO CON LA FUENTE, POR EL EJECUTOR ═════════════════════════════

# Cada caso que falla por un defecto del codigo, con el defecto. Se arregla en el codigo, no en el caso.
DEFECTOS = {
    "DU12a": "A MEDIAS: 'sirve para trabajo y estudio' dice que no tiene el dato y cita la ficha que lo dice: "
             "el uso recomendado no es un dato que el ejecutor lea",
    "DU16a": "A MEDIAS: 'de donde es' dice que no tiene el dato y el catalogo trae el origen",
    "DU26a": "A MEDIAS: un precio que dice que le dijeron sale como 'No tengo el dato de sale ...': el precio "
             "afirmado no se compara con el precio",
    "AR17a": "A MEDIAS: 'son dos en total' con un renglon deja la respuesta vacia: el total dicho no se pregunta",
    "CE03a": "PLAN: un medio que la tienda no toma entra al total sin aviso, 'cripto (100%)': el medio se valida "
             "contra la FAQ de formas de pago, SIGUE 3",
}


def test_cada_caso_que_aplica_entra(llenado):
    aplican = [c for c in llenado.values() if c["motivo"] != "la clase no aplica a la tienda"]
    afuera = [(c["id"], c["motivo"]) for c in aplican if not c["entra"] and c["id"] not in DEFECTOS]
    entran = sum(c["entra"] for c in aplican)
    assert not afuera, f"entran {entran} de {len(aplican)}; afuera sin defecto anotado: {afuera}"


@pytest.mark.parametrize("cid", [pytest.param(c, marks=pytest.mark.xfail(strict=True, reason=r))
                                 for c, r in sorted(DEFECTOS.items())])
def test_los_defectos_del_codigo(llenado, cid):
    assert llenado[cid]["entra"], llenado[cid]["motivo"]


def test_cada_caso_llenado_trae_lo_de_los_dos_motores(llenado):
    """El indice de los motores: cada caso que entra, con sus frases llenadas, la libreta, la traduccion y la etiqueta."""
    faltan = [c["id"] for c in llenado.values() if c["entra"]
              and not (c["frases"] and c["libreta"] and c["traduccion"] and c["etiqueta"])]
    assert not faltan, faltan
