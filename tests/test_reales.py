"""LAS CHARLAS REALES, REPETIDAS — cada una con la agenda exacta que escribio el modelo en produccion (19-oct-2026).

Los casos los junta `python3 banco_pruebas/produccion.py --juntar --desde 1d`: uno por charla, en
`banco_pruebas/reales/`. Cada turno se repite por el flujo vivo, con el catalogo real y sin modelo: la agenda es la
que devolvio el modelo ese dia. Asi un cambio de codigo se mide contra lo que pasa de verdad, no solo contra las 58.

Lo que se controla:
  - en ningun turno el codigo revienta: la respuesta no es la de una agenda que no se pudo cumplir;
  - lo que se le marco a mano al caso cuando se encontro un defecto: `debe` y `no_debe` por turno, con el motivo en
    `defecto`. Un defecto del codigo se marca asi y queda como test para siempre.

Su limite: si cambia lo que ve el modelo, la agenda guardada ya no es la que escribiria hoy. El caso sigue sirviendo
para el codigo; un defecto de traduccion se mide aparte, contra las agendas a mano.
"""
import asyncio
import glob
import json
import os

import pytest

from banco_pruebas import cableado58 as CB
from banco_pruebas import clon_produccion as C

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASOS = sorted(glob.glob(os.path.join(RAIZ, "banco_pruebas", "reales", "*.json")))
REVENTO = "No te entendí bien. ¿Me lo decís de otra forma?"


def _repetir(caso: dict) -> list:
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    interprete = CB.instalar()
    cola = [t["agenda"] for t in caso["turnos"]]

    async def _interpretar(*a, **k):
        return cola.pop(0)

    async def _explicar(*a, **k):
        return ""
    real = interprete.interpretar, interprete.explicar
    interprete.interpretar, interprete.explicar = _interpretar, _explicar
    try:
        uid = "real_" + caso["id"]
        C.reiniciar_cliente(uid)
        return ["\n".join(asyncio.run(C.turno(uid, t["mensaje"]))) for t in caso["turnos"]]
    finally:
        interprete.interpretar, interprete.explicar = real
        llm_reintento._cliente = puerta


@pytest.mark.parametrize("ruta", CASOS, ids=[os.path.basename(r)[:-5] for r in CASOS])
def test_la_charla_real_se_repite_sin_defectos(ruta):
    caso = json.load(open(ruta, encoding="utf-8"))
    respuestas = _repetir(caso)
    marcas, cambiaron = 0, 0
    for i, (t, r) in enumerate(zip(caso["turnos"], respuestas), 1):
        assert REVENTO not in r, f"T{i}: el codigo no pudo cumplir la agenda\n{t['agenda']}"
        for x in t.get("debe") or []:
            marcas += 1
            assert x in r, f"T{i} debe decir {x!r}. {caso.get('defecto', '')}\n{r}"
        for x in t.get("no_debe") or []:
            marcas += 1
            assert x not in r, f"T{i} no debe decir {x!r}. {caso.get('defecto', '')}\n{r}"
        cambiaron += r.strip() != (t.get("respondio") or "").strip()
    print(f"\nREAL {caso['id']}: {len(respuestas)} turnos, {marcas} marcas bien, "
          f"{cambiaron} respuestas distintas de las de produccion")


def test_hay_charlas_reales():
    assert CASOS, "banco_pruebas/reales/ esta vacio: se llena con produccion.py --juntar"
    print(f"\nREALES: {len(CASOS)} charlas")


def test_juntar_corta_en_el_reset_y_toma_el_mensaje_entero():
    from banco_pruebas.produccion import casos
    ag = json.dumps({"preguntas": [{"n": 1, "cita": "x", "accion": "otro", "que": "saludo"}]})
    largo = "hola " * 100

    def turno(t, hora, msg, con_agenda=True):
        evs = [{"event": "message_received", "trace_id": t, "user_id": "549", "msg_preview": msg[:400],
                "_t": f"2026-10-19T10:00:0{hora}Z"}]
        return evs + ([{"event": "interprete_ok", "trace_id": t, "agenda": ag}] if con_agenda else [])
    eventos = turno("a", 1, largo) + turno("b", 2, "verifika2026", False) + turno("c", 3, "otra")
    dialogos = {"549": [("user", largo), ("assistant", "hola!"), ("user", "otra"), ("assistant", "ok")]}
    hechos = casos(eventos, dialogos)
    assert [len(c["turnos"]) for c in hechos] == [1, 1]
    assert hechos[0]["turnos"][0]["mensaje"] == largo and hechos[0]["turnos"][0]["respondio"] == "hola!"
    assert "549" not in json.dumps(hechos)
