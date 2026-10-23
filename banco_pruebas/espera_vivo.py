"""LA ESPERA DE CADA PREGUNTA, CON EL MODELO DE PRODUCCION — las charlas de `tests/test_espera.py`, dichas como cliente
(23-oct-2026).

El test las corre con la agenda escrita a mano; aca el interprete es el modelo real, por el camino vivo entero. Mide si
el modelo deja la respuesta corta donde el codigo la puede atar. Cada turno dice lo que el cliente tiene que leer y lo
que no. Lo ya preguntado sale de `libro_paga.recordar` sin gasto.
    python3 banco_pruebas/espera_vivo.py [--ver]      con la gratis; la paga, con la marca de Martin y su tope en dolares
"""
import asyncio
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path.insert(0, REPO)
os.chdir(REPO)
if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"

from banco_pruebas import clon_produccion as C  # noqa: E402
from banco_pruebas import libro_paga  # noqa: E402
C.preparar_entorno()
C.instalar()

# El tope de esta corrida, ademas del diario: lo que Martin dio para ella.
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.35"))


def tiene(*xs):
    return lambda t: all(x.lower() in t.lower() for x in xs)


def no_tiene(*xs):
    return lambda t: not any(x.lower() in t.lower() for x in xs)


def pregunta(t):
    return "?" in t


TABLET = ("el teclado Logitech K380 anda con mi tablet?",
          [tiene("android", "ipad"), pregunta, no_tiene("pregunta cual", "no elijas")])
CHARLAS = {
    "ipad": [("el teclado Logitech K380 anda con mi iPad?", [tiene("anda con"), no_tiene("qué modelo")])],
    "ram": [("la Kingston Fury Beast DDR4 16GB le sirve a mi pc de escritorio?",
             [pregunta, no_tiene("anda con una pc")])],
    "tablet_samsung": [TABLET, ("la ultima de Samsung", [tiene("android", "anda con"), no_tiene("tengo:", "presupuesto")])],
    "tablet_es_android": [TABLET, ("es android", [tiene("android", "anda con"), no_tiene("tengo:", "presupuesto")])],
    "tablet_ps5": [TABLET, ("no, es una PS5", [tiene("no es tu tablet"), pregunta,
                                               no_tiene("anda con un celular", "presupuesto")])],
    "tablet_otro_tema": [TABLET, ("dejá, mostrame mouses para mac", [tiene("mouse"), no_tiene("anda con un")])],
}


def main() -> None:
    ver = "--ver" in sys.argv
    desde = libro_paga.gastado(libro_paga._hoy())
    bien = 0
    for nombre, turnos in CHARLAS.items():
        gasto = libro_paga.gastado(libro_paga._hoy()) - desde
        if gasto >= TOPE:
            print(f"TOPE de la corrida: {gasto:.3f} de {TOPE} dolares, paro antes de {nombre}")
            break
        uid = f"espera_vivo_{nombre}"
        C.reiniciar_cliente(uid)
        malas = []
        for i, (texto, controles) in enumerate(turnos):
            r = "\n".join(asyncio.run(C.turno(uid, texto)))
            m = [f"turno {i + 1}, control {j + 1}" for j, ok in enumerate(controles) if not ok(r)]
            malas += m
            if ver or m:
                print(f"--- {nombre} CLIENTE: {texto}\n{r}\n    MAL: {m}")
        bien += not malas
        print(f"{nombre}: {'bien' if not malas else 'MAL'}", flush=True)
    gasto = libro_paga.gastado(libro_paga._hoy()) - desde
    print(f"\nESPERA EN VIVO: {bien} de {len(CHARLAS)} charlas bien, {gasto:.3f} dolares")


if __name__ == "__main__":
    main()
