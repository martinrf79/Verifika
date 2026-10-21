"""LA MEDICION LIMPIA — los ejemplos de las consignas de la prueba no pueden usar las palabras de los turnos que se miden.
V1 a V3 traian algunas: "menos de 10 mil", "el K120 negro", "la Kingston Fury", "70 por ciento", "con envio". Aca se
cambian por otras de la misma clase, y `fugas()` controla que no quede ninguna secuencia de tres palabras de un turno
medido, en ninguna de sus formas."""
import re

import comandos as Cm
import fichas as F
import pistas as P

PASO1_CAMBIOS = [
    ('"G203", "el K120 negro", "la Kingston Fury"', '"MX Master", "el G915 blanco", "la HyperX Cloud"'),
    ('"mouse", "auriculares", "una placa de video"', '"parlante", "unos cascos", "una notebook"'),
    ('"10 mil", "70 por ciento", "dos"', '"20 mil", "40 por ciento", "tres"'),
    ('"el de Rosario"', '"el de Salta"'),
    ('una marca, un color, "inalambrico", "menos de 10 mil", "que no sea X",\n  "el mas potente", "que aguante tal cosa"',
     'una marca, un color, "con bluetooth", "hasta 50 mil", "que no sea X",\n  "el mas liviano", "que entre en tal cosa"'),
]
CONSIGNA_CAMBIOS = [
    ('sumar: el total, "cuanto sale todo", "con envio", un presupuesto.',
     'sumar: el total, "cuanto da en total", el precio sumando el envio, un presupuesto.'),
    ('"si no hay", "si anda", "si sale menos de"', '"si no hay", "si anda", "si es asi"'),
]
FICHAS_CAMBIOS = [
    ('"cuanto sale el K120", "y ese es inalambrico?", "el G305 tiene garantia?"',
     '"cuanto sale el MX Master", "y ese tiene bluetooth?", "el MX Keys tiene garantia?"'),
    ('ELEGIR ENTRE DOS POR UN DATO, "dame el que sea inalambrico"', 'ELEGIR ENTRE DOS POR UN DATO, "de esos dos, el que tenga RGB"'),
    ('"que aguante mi fuente de 550 W"', '"que entre en mi gabinete"'),
    ('"ya no importa la\n   marca"', '"olvidate del\n   color"'),
    ('"Otras opciones", "alguno\n   mas", "y alguno mecanico" piden ver mas', '"Mostrame mas", "hay\n   otros?", "y alguno con luces?" piden ver mas'),
    ('"cuanto es", "cuanto sale todo", un presupuesto, "cuanto me sale con envio"',
     '"cuanto da en total", un presupuesto, el precio sumando el envio'),
    ('"El G203 con envio": PRODUCTO, ENVIO y CUENTA', '"El MX Keys puesto en mi casa": PRODUCTO, ENVIO y CUENTA'),
    ('"tienen 50 off"', '"me dijeron que hay 20 de descuento"'),
    ('"mandame", "anotame", "llevo dos"', '"enviamelo", "anotame", "me llevo tres"'),
    ('"Si no le sirve, que otra hay"', '"Si no anda, que otro tenes"'),
    ('"con envio" sin lugar', 'el envio sin lugar'),
]


def _aplicar(texto, cambios):
    for a, b in cambios:
        if a not in texto:
            raise ValueError(f"no esta: {a[:60]}")
        texto = texto.replace(a, b)
    return texto


def instalar():
    P.PASO1 = _aplicar(P.PASO1, PASO1_CAMBIOS)
    Cm.CONSIGNA = _aplicar(Cm.CONSIGNA, CONSIGNA_CAMBIOS)
    F.FICHAS = _aplicar(F.FICHAS, FICHAS_CAMBIOS)


def fugas(textos_prompt: dict) -> list:
    """Cada secuencia de tres palabras de un turno medido, en cualquiera de sus formas, que aparece en un prompt."""
    from banco_pruebas import cableado58 as R
    from banco_pruebas.traduccion58 import _protegidas, formas_de, plano
    prot = _protegidas()
    out = []
    for ch in R.charlas():
        for k, t in enumerate(ch["turnos"]):
            if (ch["id"], k) not in P.TURNOS:
                continue
            for forma, v in formas_de(ch["id"], k, t["texto"], prot).items():
                ws = plano(v).split()
                for nombre, txt in textos_prompt.items():
                    pt = " " + " ".join(plano(txt).split()) + " "
                    for i in range(len(ws) - 2):
                        tri = " ".join(ws[i:i + 3])
                        if f" {tri} " in pt:
                            out.append((nombre, ch["id"], k, forma, tri))
    return out
