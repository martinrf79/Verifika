"""LA MEMORIA LARGA VIVE EN EL CODIGO — 6-nov-2026, orden de Martin, FICHA 89 hallazgo 6.

El historial que lee el modelo es una ventana, `HISTORY_LIMIT` turnos. Hasta el 6-nov, todo lo que el codigo controla
con "lo que dijo el cliente" —el medio de pago, el color, el destino, la cita de un comando— salia de esa ventana: un
dato dicho antes del corte dejaba de valer sin aviso, y el modelo tampoco lo veia. Medido el 6-nov con la gratis: con
20 turnos o mas, el modelo ya no recordaba el nombre ni la ciudad dichos en el primero.

Ahora lo que dijo el cliente se guarda entero en la memoria del agente, `memoria_agente["dicho"]`, hasta
`MEMORIA_TURNOS` mensajes. El codigo lo usa siempre, y al modelo le llega lo que quedo fuera de la ventana, solo las
lineas del cliente. Una charla mas corta que la ventana lee exactamente lo mismo que antes: la vara no cambia.

Se corre por el webhook entero del clon con un modelo falso, como `tests/test_agente.py`.
"""
import asyncio
import json
import time

import pytest

from banco_pruebas import agente_replay as R
from banco_pruebas import clon_produccion as C

M220 = "Mouse Logitech M220 Silent Negro"
PRIMERO = "hola, soy Rocio Benitez, el envio va a Gualeguaychu y pago todo por transferencia"
RELLENO = [g["mensaje"] for gs in R._charlas().values() for g in gs]


@pytest.fixture(scope="module")
def falso():
    f, _ = R.instalar()
    f.leidos = []
    crear = f._crear

    def _anota(**k):
        f.leidos.append(k.get("messages") or [])
        return crear(**k)
    f.chat.completions.create = _anota
    return f


def charla(falso, uid: str, mensajes: list, ultimo: dict = None) -> list:
    """Cada mensaje del cliente con una respuesta corta del modelo; el ultimo, con lo que diga `ultimo`."""
    C.reiniciar_cliente(uid)
    out = []
    for i, m in enumerate(mensajes):
        falso.turno(ultimo if ultimo and i == len(mensajes) - 1 else {"respuesta": "Dale, te sigo."})
        out.append("\n".join(asyncio.run(C.turno(uid, m))))
    return out


def guardada(uid: str) -> dict:
    from app.storage import firestore_client as fc
    return fc.get_conversation(uid, tienda_id=C.TIENDA) or {}


def test_lo_dicho_antes_de_la_ventana_sigue_valiendo(falso):
    """El medio dicho en el primer mensaje, 30 turnos despues: el presupuesto lo usa, con su descuento, y el modelo lo
    lee. Antes quedaba "a definir" y el bot volvia a preguntar con que paga."""
    from app.config import get_settings
    n = 3 * get_settings().HISTORY_LIMIT
    ultimo = {"pasos": [{"herramienta": "buscar", "pide": {"consulta": "SELECT nombre, precio, stock FROM productos WHERE nombre LIKE '%M220%' AND stock > 0"}},
                        {"herramienta": "presupuesto", "pide": {
        "renglones": [{"producto": M220, "cantidad": 1, "destino": "Gualeguaychu"}], "pago": "100 transferencia",
        "anotar": True}}], "respuesta": "Listo.\n[[PRESUPUESTO]]"}
    textos = charla(falso, "memoria_larga_1", [PRIMERO] + RELLENO[:n - 2] + ["dale, el m220 entonces"], ultimo)
    assert "transferencia" in textos[-1].lower() and "a definir" not in textos[-1].lower(), textos[-1]
    leido = json.dumps(falso.leidos[-1], ensure_ascii=False).lower()
    assert "gualeguaychu" in leido and "rocio" in leido
    dicho = guardada("memoria_larga_1")["memoria_agente"]["dicho"]
    assert dicho[0] == PRIMERO and len(dicho) == n


def test_una_charla_corta_lee_lo_mismo_que_antes(falso):
    """Dentro de la ventana no se suma nada a lo que lee el modelo: la vara grabada sigue valiendo sin regrabar."""
    charla(falso, "memoria_larga_2", [PRIMERO, "y cuanto sale el m220?"])
    assert "ANTES DE LA CHARLA" not in json.dumps(falso.leidos[-1], ensure_ascii=False)


def test_cuantos_turnos_entran_sin_conflicto_ni_latencia(falso):
    """LA MEDICION, sin modelo: por largo de charla, el documento guardado, lo que lee el modelo y el tiempo del codigo
    en el ultimo turno. El peor caso: cada mensaje del cliente de 400 caracteres, el mas largo de las charlas grabadas.
    Firestore corta en 1 MiB por documento; se exige quedar debajo de un cuarto."""
    from app.config import get_settings
    tope, filas = get_settings().MEMORIA_TURNOS, []
    largo = ("necesito que me confirmes el envio a gualeguaychu y el medio de pago " * 6)[:400]
    for n in (10, 40, tope, tope + 20):
        uid = f"memoria_larga_n{n}"
        charla(falso, uid, [PRIMERO] + [f"{largo} {i}" for i in range(n - 1)])
        t0 = time.time()
        falso.turno({"respuesta": "Dale."})
        asyncio.run(C.turno(uid, "y entonces?"))
        seg = time.time() - t0
        doc = guardada(uid)
        bytes_doc = len(json.dumps({k: v for k, v in doc.items() if k != "updated_at"}, ensure_ascii=False, default=str))
        leido = sum(len(str(m.get("content") or "")) for m in falso.leidos[-1])
        filas.append((n, len(doc["memoria_agente"]["dicho"]), bytes_doc, leido, round(seg, 2)))
    print("\nMEMORIA LARGA, peor caso: turnos, mensajes guardados, bytes del documento, caracteres que lee el modelo, "
          "segundos del codigo")
    for f in filas:
        print("  ", *f)
    assert all(d <= tope for _, d, *_ in filas) and filas[-1][1] == tope
    assert all(b < 1024 * 1024 // 4 for _, _, b, *_ in filas)
    assert filas[-1][4] < 2 * max(filas[0][4], 0.5), "el tiempo del codigo crece con la charla"
