"""EL LIBRO DE LA PAGA — cada llamada del banco con la clave paga, anotada, y un tope por dia (2-oct-2026).

POR QUE EXISTE. El 1-oct una sesion corrio cinco tandas con la paga, cada una
por debajo del tope por proceso, y el credito prepago se agoto: Google cobro
unos cinco dolares y las corridas guardadas sumaban 1,58. Nadie lo vio hasta
que produccion, que usa la misma clave, se quedo sin modelo. El 28 y 29-sep
habian sido diez dolares desde otra sesion. Un tope por corrida no frena diez
corridas; la estimacion de la sesion no ve las sondas sueltas.

QUE HACE. `clon_produccion` envuelve el cliente del modelo cuando el banco usa
la paga: cada llamada se anota aca, en `libro_paga.jsonl`, con fecha, modelo,
tokens y dolares, venga de la herramienta que venga. Y antes de cada llamada
se mira lo gastado HOY por todas las corridas juntas: si llego al tope, la
llamada no sale. El tope es por dia y para todas las sesiones.

LO QUE NO VE: las llamadas que no pasan por el clon y lo que cobra Google de
mas por su cuenta. La verdad es la consola de facturacion; esto es el piso.

  python3 -m banco_pruebas.libro_paga            lo gastado hoy y en el mes
"""
import datetime
import json
import os
from pathlib import Path

LIBRO = Path(__file__).resolve().parent / "libro_paga.jsonl"
# Un dolar por dia entre todas las corridas. Subirlo es una orden de Martin,
# en su propio commit, como cualquier umbral.
TOPE_DIARIO = 1.00


class TopeDiario(Exception):
    pass


def _hoy() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def gastado(desde: str) -> float:
    if not LIBRO.exists():
        return 0.0
    total = 0.0
    for x in open(LIBRO, encoding="utf-8"):
        r = json.loads(x)
        if r.get("dia", "") >= desde:
            total += float(r.get("dolares") or 0)
    return total


def hoy() -> float:
    return gastado(_hoy())


def mes() -> float:
    return gastado(_hoy()[:8] + "01")


def puede() -> None:
    """Lanza TopeDiario si hoy ya se llego al tope."""
    g = hoy()
    if g >= TOPE_DIARIO:
        raise TopeDiario(f"la paga ya gasto {g:.2f} dolares hoy y el tope diario es {TOPE_DIARIO:.2f}: "
                         "sigue manana o con la orden de Martin")


def anotar(modelo: str, entrada: int, salida: int) -> float:
    from banco_pruebas import costo
    d = costo.dolares(int(entrada or 0), int(salida or 0), modelo)
    with open(LIBRO, "a", encoding="utf-8") as f:
        f.write(json.dumps({"dia": _hoy(), "hora": datetime.datetime.utcnow().strftime("%H:%M:%S"),
                            "modelo": modelo, "entrada": int(entrada or 0), "salida": int(salida or 0),
                            "dolares": round(d, 5), "proceso": os.getpid()}) + "\n")
    return d


def envolver(cliente):
    """El cliente del modelo con cada llamada mirada y anotada."""
    if cliente is None or getattr(cliente, "_libro", False):
        return cliente
    crear = cliente.chat.completions.create

    def create(*a, **k):
        puede()
        r = crear(*a, **k)
        u = getattr(r, "usage", None)
        anotar(k.get("model") or "gemini-3.1-flash-lite", getattr(u, "prompt_tokens", 0) if u else 0,
               getattr(u, "completion_tokens", 0) if u else 0)
        return r
    cliente.chat.completions.create = create
    cliente._libro = True
    return cliente


def main() -> int:
    print(f"PAGA · hoy {hoy():.2f} dolares de {TOPE_DIARIO:.2f} · este mes {mes():.2f} · {LIBRO.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
