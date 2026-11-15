"""EL NEXO DE DESTINO: DEL CAMPO DESTINO DEL ENGRANAJE 0 A LA TARIFA DE LA TIENDA, SIN MODELO (15-nov-2026).

Orden de Martin del 14-nov. El primero de los cinco nexos. Sin modelo y sin gasto: usa lo grabado.
  Entrada: el campo destino que escribio cada modelo en la v2 del engranaje 0, `engranaje0_corridas.jsonl`, sobre los 70
  mensajes nuevos de `nuevas70.py`.
  El nexo: el codigo de produccion tal cual, `fuente._cotizar`, que clasifica el lugar y pone la tarifa, sobre el
  Firestore simulado con la config real de la tienda.

LA VARA, escrita antes de correr, por geografia: la zona de cada ciudad, y en el interior su provincia, que es lo que
decide el monto. Por cada destino que el cliente dijo:
  bien       el campo del modelo llega a la zona y la provincia correctas.
  sin dato   el codigo no lo reconoce: corresponde pedir la provincia, no es error.
  mal        llega a otra zona u otra provincia: es el error que no se puede permitir, porque cobra otro envio.
  perdido    ninguna linea del modelo trae ese destino en su campo.

    python3 banco_pruebas/nexo_destino.py
"""
import collections
import json
import logging
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI), AQUI]

VARA = {
    "Mendoza": ("interior", "mendoza"), "Salta": ("interior", "salta"), "Caba": ("caba", None),
    "Rosario": ("interior", "santa fe"), "Neuquen": ("interior", "neuquen"),
    "Bahia Blanca": ("interior", "buenos aires"), "Tucuman": ("interior", "tucuman"),
    "Cordoba": ("interior", "cordoba"), "San Luis": ("interior", "san luis"), "Parana": ("interior", "entre rios"),
    "Santa Fe": ("interior", "santa fe"), "Posadas": ("interior", "misiones"),
    "Corrientes": ("interior", "corrientes"), "Jujuy": ("interior", "jujuy"),
    "Mar del Plata": ("interior", "buenos aires"), "Tandil": ("interior", "buenos aires"),
    "Ushuaia": ("interior", "tierra del fuego"), "Rio Cuarto": ("interior", "cordoba"),
    "Villa Maria": ("interior", "cordoba"), "San Francisco": ("interior", "cordoba"),
    "Resistencia": ("interior", "chaco"), "Comodoro": ("interior", "chubut"), "Lanus": ("gba", None),
    "Pilar": ("gba", None), "San Rafael": ("interior", "mendoza"),
    "Santiago del Estero": ("interior", "santiago del estero"), "La Rioja": ("interior", "la rioja"),
    "Catamarca": ("interior", "catamarca"), "Cipolletti": ("interior", "rio negro"),
}


def instalar():
    from banco_pruebas import camino_fijo as F
    F.instalar()
    import structlog
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))


def veredicto(r, ciudad):
    if not r:
        return "sin dato"
    zona, prov = VARA[ciudad]
    import engranaje0 as E
    if r.get("zona") != zona:
        return "mal"
    if prov and E.n(prov) not in E.n(r.get("provincia")):
        return "mal"
    return "bien"


def main():
    instalar()
    import engranaje0 as E
    from app.core.fuente import _cotizar
    from nuevas70 import CASOS
    filas = {(r["modelo"], r["id"]): r for r in map(json.loads, open(E.SALIDA)) if r["v"] == "v2"}
    print("\nEL NEXO DE DESTINO · el campo destino de la v2 grabada, por el cotizador de produccion")
    for m in ("gemini", "haiku", "deepseek"):
        cuenta, detalle = collections.Counter(), []
        for cid, _, cosas in CASOS:
            ls = ((filas.get((m, cid)) or {}).get("salida") or {}).get("lineas") or []
            for d in (x for c in cosas for x in c.get("d") or []):
                campos = [str(l.get("destino") or "") for l in ls if E.n(d) in E.n(l.get("destino"))]
                if not campos:
                    cuenta["perdido"] += 1
                    detalle.append((cid, d, "perdido", None, None))
                    continue
                campo = min(campos, key=len)
                r = _cotizar(campo)
                v = veredicto(r, d)
                cuenta[v] += 1
                if v != "bien":
                    detalle.append((cid, d, v, campo, {k: r.get(k) for k in ("zona", "provincia", "monto")} if r else {}))
        total = sum(cuenta.values())
        print(f"\n  {m}: bien {cuenta['bien']} de {total} · sin dato {cuenta['sin dato']} · mal {cuenta['mal']} · "
              f"perdido {cuenta['perdido']}")
        for cid, d, v, campo, r in detalle:
            print(f"    {cid} {d}: {v} · campo del modelo '{campo}' -> {r}")


if __name__ == "__main__":
    main()
