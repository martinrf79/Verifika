"""Arma, sin modelo, lo que ve el interprete en un turno: la charla previa real, la libreta, la tabla y la agenda a mano.
Los turnos anteriores corren con la agenda a mano, como en traduccion58, asi la memoria es la correcta."""
import asyncio
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
os.chdir(REPO)

from banco_pruebas import clon_produccion as C  # noqa: E402

C.preparar_entorno()
C.instalar()
from app.core import llm_reintento  # noqa: E402

PUERTA, MODELO = llm_reintento._cliente, llm_reintento._modelo
from banco_pruebas import cableado58 as R  # noqa: E402
from banco_pruebas.agendas58 import AGENDAS, EXPLICAR  # noqa: E402
from banco_pruebas.traduccion58 import _explicacion  # noqa: E402

IT = R.instalar()
llm_reintento._cliente = PUERTA
ELEGIR_MANO = IT.elegir
CHARLAS = {c["id"]: c for c in R.charlas()}


def contexto(cid: str, k: int, uid: str = "ent") -> dict:
    """Corre la charla hasta el turno k con agendas a mano y captura lo que el interprete recibiria en k."""
    from app.core.flujo import interprete as I
    ch, ags = CHARLAS[cid], AGENDAS[cid]
    C.reiniciar_cliente(uid)
    previos = []
    capt = {}
    for i, t in enumerate(ch["turnos"][:k + 1]):
        async def _mano(*a, _i=i, **kw):
            if _i == k:
                capt["args"] = a
            return ags[_i]

        async def _expl(pregunta, *a, _i=i, **kw):
            return _explicacion(ags[_i], EXPLICAR)
        IT.interpretar, IT.explicar, IT.elegir = _mano, _expl, ELEGIR_MANO
        resp = "\n".join(asyncio.run(C.turno(uid, t["texto"])))
        if i < k:
            previos.append((t["texto"], resp))
    mensaje, historial, estado, tienda = capt["args"][:4]
    msgs = I.mensajes(mensaje, historial, estado, tienda)
    return {"id": cid, "k": k, "texto": ch["turnos"][k]["texto"], "previos": previos, "consigna": msgs[0]["content"],
            "entrada": msgs[1]["content"], "estado": estado, "historial": historial, "mano": ags[k],
            "casillas": ch["turnos"][k]["casillas"]}


def llamar(msgs: list, json_=False) -> tuple:
    import time
    cli = PUERTA()
    kw = {"response_format": {"type": "json_object"}} if json_ else {}
    for intento in range(6):
        try:
            t0 = time.time()
            r = cli.chat.completions.create(model=MODELO(), messages=msgs, temperature=0, **kw)
            if asyncio.iscoroutine(r):
                r = asyncio.run(r)
            u = r.usage
            return r.choices[0].message.content or "", {"entrada": u.prompt_tokens, "salida": u.completion_tokens,
                                                         "seg": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            print("reintento", intento, type(e).__name__, str(e)[:120], flush=True)
            time.sleep(10 * (intento + 1))
    raise RuntimeError("el modelo no contesto")
