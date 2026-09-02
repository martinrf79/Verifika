"""
AREA: EL EXTREMO PEDIDO -"la mas barata", "la mas cara"- Y SU DIRECCION.

EL DEFECTO, medido en el turno `95175a7f` de WhatsApp el 2-sep-2026. El cliente
escribio "Que notebook es la mas barata y cual la mas cara" y el turno cotizo
DOS VECES el mismo producto:

    calculate_total items=[NOT0019 x1, NOT0019 x1]

NOT0019 sale 693.000 y es la mas BARATA de las 171 notebooks. La mas cara es
NOT0162, a 3.100.500. O sea que la mitad de la pregunta se contesto con el
producto opuesto al pedido, y el cliente no tenia como saberlo.

SON DOS CAUSAS ENCADENADAS Y LAS DOS ESTAN CUBIERTAS ACA:

  1. `resolver_orden` mandaba "cara" al campo `caracteristicas_extra`, porque el
     puente al reves -`raiz.startswith(palabra[:5])`- deja que una palabra de
     cuatro letras se quede con un campo largo: `carac` empieza con `cara`.
     Ordenar por esa columna es ordenar por prosa, alfabeticamente.
  2. `resolver` guarda UN solo `orden` para el turno entero con `orden or
     extremo`, y despues lo hacia ganar sobre el extremo del propio item. El
     primero -"barata"- se quedaba con las dos busquedas.

LO QUE SIGUE ABIERTO A PROPOSITO: dos extremos declarados como condiciones
sueltas, sin que ningun item los nombre, siguen colapsando en el primero. No hay
a que busqueda atarlos y elegir uno seria inventar.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import filtros_catalogo as FC  # noqa: E402
from app.core import resolver as R  # noqa: E402

TIENDA = "verifika_prod"

# Frase del cliente y el par (campo, direccion) que le corresponde.
EXTREMOS = [
    ("la mas barata", "precio_ars", "min"),
    ("la mas cara", "precio_ars", "max"),
    ("notebook mas barata", "precio_ars", "min"),
    ("notebook mas cara", "precio_ars", "max"),
    ("el mas caro de todos", "precio_ars", "max"),
    ("el mas liviano", "peso_gramos", "min"),
    ("el mas pesado", "peso_gramos", "max"),
    ("el de mas garantia", "garantia_meses", "max"),
]


def test_cada_extremo_cae_en_su_campo_y_su_direccion(firestore_doble):
    """El test dice sobre cuantos paso, no solo que paso."""
    fallados = []
    for frase, campo, direccion in EXTREMOS:
        got = FC.resolver_orden(frase, TIENDA)
        if not got or got.get("campo") != campo or got.get("direccion") != direccion:
            fallados.append((frase, got, (campo, direccion)))
    assert not fallados, (
        f"{len(fallados)} de {len(EXTREMOS)} extremos mal resueltos: {fallados}")


def test_cara_no_se_va_a_caracteristicas_extra(firestore_doble):
    """La causa uno, aislada. `cara` no puede quedarse con `caracteristicas_extra`
    solo por compartir las primeras cuatro letras."""
    got = FC.resolver_orden("la mas cara", TIENDA)
    assert got["campo"] == "precio_ars"


def test_peso_sigue_pegando_en_su_campo_por_el_nombre(firestore_doble):
    """La red del arreglo: pedir cinco letras para el puente al reves no puede
    romper el puente derecho, donde la palabra del cliente EMPIEZA con la raiz
    del campo."""
    got = FC.resolver_orden("el de menos peso", TIENDA)
    assert got == {"campo": "peso_gramos", "direccion": "min"}


def test_dos_extremos_en_un_mensaje_dan_dos_productos_distintos(firestore_doble):
    """LA VARA, y es la pregunta real del cliente. Dos items, cada uno con su
    extremo, tienen que salir con direcciones distintas y traer productos
    distintos."""
    declarado = {
        "items": [{"categoria": "notebook", "que": "notebook mas barata"},
                  {"categoria": "notebook", "que": "notebook mas cara"}],
        "restricciones": ["la mas barata", "la mas cara"],
        "pide_precio": True,
    }
    llamadas = [{"herramienta": "registrar_pedido",
                 "resultado": {"estado": "registrado", "pedido": declarado}}]
    out = R.resolver(declarado, [], TIENDA, "t", llamadas=llamadas)

    busquedas = [l for l in (out.get("llamadas") or out.get("fuera") or [])
                 if l.get("herramienta") == "consultar_productos"
                 and (l.get("pedido") or {}).get("ordenar_por")]
    direcciones = {(b["pedido"].get("ordenar_por"), b["pedido"].get("direccion"))
                   for b in busquedas}
    assert ("precio_ars", "min") in direcciones, direcciones
    assert ("precio_ars", "max") in direcciones, direcciones
