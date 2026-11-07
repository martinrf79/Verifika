"""LO QUE DIJO EL BOT NO ES FUENTE — auditoria de las 12 capas del 6-nov, hallazgo 1, FICHA 87 causa 3.

Hasta hoy el texto del bot en los turnos anteriores entraba como fuente del verificador y como "visto" del candado de
productos: un dato inventado una vez pasaba los controles en los turnos siguientes. El Pandora "compatible con PS5" en
b8bb001ee8 t1 a t3. La fuente pasa a ser lo que devolvieron las herramientas, en este turno y en los anteriores, lo que
dijo el cliente, la memoria del codigo y las reglas.

Cuatro casos, con el modelo falso del banco y sin modelo de verdad:
  dato        un monto que solo dijo el bot vuelve a decirse: se marca y no sale.
  dato bueno  un monto que dio una herramienta en un turno anterior se puede repetir sin volver a buscar.
  producto    un producto que solo nombro el bot no entra al presupuesto sin buscarlo.
  producto    el mismo producto, devuelto por el buscador en un turno anterior, entra.
"""
import asyncio
import re

import pytest

from banco_pruebas import clon_produccion as C
from banco_pruebas.agente_replay import Grabado

G305 = "Mouse Logitech G305 Lightspeed Negro"


@pytest.fixture(scope="module")
def A():
    C.instalar()
    from app.core import llm_reintento
    from app.core.flujo import agente
    antes = llm_reintento._cliente, agente._parecidos
    falso = Grabado()
    llm_reintento._cliente = lambda: falso
    agente._parecidos = lambda consulta, tipo, tienda_id: []
    agente._falso = falso
    yield agente
    llm_reintento._cliente, agente._parecidos = antes


def _turno(A, historial, mensaje, pasos, respuesta, memoria=None):
    A._falso.turno({"pasos": [{"herramienta": h, "pide": p} for h, p in pasos], "respuesta": respuesta})
    memoria = memoria or A.memoria_de({})
    return asyncio.run(A.responder(mensaje, historial, memoria, "u_fuente", "telegram", C.TIENDA, "t")), memoria


def test_un_monto_que_solo_dijo_el_bot_no_vale_como_fuente(A):
    historial = [{"role": "user", "content": "cuanto sale el envio a Posadas"},
                 {"role": "assistant", "content": "El envio a Posadas sale $99.999."}]
    # Desde el 7-nov el modelo escribe un saludo y una pregunta, y un numero ahi no sale, FICHA 90: se le devuelve una vez, y
    # si lo repite, ese campo se saca.
    dicho = {"saludo": "Perfecto, el envio a Posadas era $99.999.", "bloques": [], "pregunta": "¿Algo mas?"}
    r, _ = _turno(A, historial, "ok gracias", [], dicho)
    assert A.datos_en_libre(dicho, C.TIENDA)
    assert "99.999" not in r["respuesta"] and "99999" not in r["respuesta"]


def test_un_monto_que_dio_una_herramienta_antes_sigue_valiendo(A):
    memoria = A.memoria_de({})
    r1, memoria = _turno(A, [], "cuanto sale el envio a Posadas", [("buscar", {"consulta": "envio a Posadas"})],
                         "Te cuento el envio.", memoria)
    monto = re.search(r"\$\s?\d[\d.]*\d", r1["pasos"][0]["devuelve"]).group(0)
    historial = [{"role": "user", "content": "cuanto sale el envio a Posadas"},
                 {"role": "assistant", "content": r1["respuesta"]}]
    r2, _ = _turno(A, historial, "ok gracias", [], f"Perfecto, el envio a Posadas sale {monto}. ¿Algo mas?", memoria)
    assert not [h for h in r2["hallazgos"] if h[0] == "dato"], r2["hallazgos"]


def test_un_producto_que_solo_nombro_el_bot_no_entra_sin_buscarlo(A):
    historial = [{"role": "user", "content": "quiero un mouse inalambrico"},
                 {"role": "assistant", "content": f"Te recomiendo el {G305}."}]
    r, _ = _turno(A, historial, "dale, ese a Rosario",
                  [("pedido", {"agrega": [{"producto": G305, "destino": "Rosario", "cita": "dale, ese a Rosario"}]})],
                  "Listo.\n[[PEDIDO]]")
    paso = next(p for p in r["pasos"] if p["herramienta"] == "pedido")
    assert "Primero busca" in paso["devuelve"] and not paso["al_cliente"]


def test_el_mismo_producto_devuelto_por_el_buscador_antes_entra(A):
    memoria = A.memoria_de({})
    consulta = "SELECT nombre, precio, stock FROM productos WHERE nombre LIKE '%G305%'"
    r1, memoria = _turno(A, [], "quiero un mouse inalambrico", [("buscar", {"consulta": consulta})],
                         f"Te recomiendo el {G305}.", memoria)
    historial = [{"role": "user", "content": "quiero un mouse inalambrico"},
                 {"role": "assistant", "content": r1["respuesta"]}]
    r2, _ = _turno(A, historial, "dale, ese a Rosario",
                   [("pedido", {"agrega": [{"producto": G305, "destino": "Rosario", "cita": "dale, ese a Rosario"}]})],
                   "Listo.\n[[PEDIDO]]", memoria)
    paso = next(p for p in r2["pasos"] if p["herramienta"] == "pedido")
    assert "Total" in paso["al_cliente"], paso["devuelve"]
