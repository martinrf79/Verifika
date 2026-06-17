"""
RENDER_CODIGO — el bloque numerico lo PEGA el codigo, no lo transcribe el Solver.

El Provider calcula bien, pero hoy el Solver TRANSCRIBE el numero con sus
palabras: el contrato le dice "copia TAL CUAL" y el modelo redacta alrededor. El
dato se ensucia en la ultima milla. Lo unico que hay del lado del codigo es
correctivo y por sospecha: la compuerta reemplaza la respuesta entera si detecta
que el Solver rompio la cifra, y PISO_PRESUPUESTO caza el presupuesto fabricado.

Esta pieza lo da vuelta: el bloque numerico verificado (la presentacion de la
calculadora, con su proof) se ESTAMPA por codigo en la respuesta. El Solver
escribe la venta y deja un marcador donde van los numeros; el codigo lo
reemplaza por el bloque verificado. Si el modelo ignora el marcador (modelo
barato o de prueba), el codigo igual garantiza el dato: saca el presupuesto que
el Solver haya escrito a mano y estampa el verificado en su lugar.

Asi el numero llega LIMPIO pase lo que pase con el modelo, que es la condicion
para poder poner un Solver economico sin perder robustez.

Funcion PURA: no toca el LLM ni la red. Detras del flag RENDER_CODIGO
(default off). Se alimenta de estado_pedido.presentacion (o de la verdad del
turno). Nadie la consume todavia: primero verde, despues se enchufa.
"""
import re

# Marcador que el Solver deja donde van los numeros. El prompt le pide ponerlo;
# el codigo lo reemplaza por el bloque verificado. Si no lo pone, el codigo
# estampa igual (camino de respaldo).
MARCADOR = "{{PRESUPUESTO}}"


def instruccion_marcador() -> str:
    """La linea que va al prompt del Solver para que deje el marcador en vez de
    escribir los numeros. Un solo lugar de verdad para el sentinel."""
    return (f"Cuando tengas que mostrar un presupuesto, un total o el detalle de "
            f"precios, NO escribas los numeros vos: escribi {MARCADOR} en la "
            f"linea donde deberian ir y el sistema pega el bloque verificado. "
            f"Redacta la venta alrededor con naturalidad.")


def _es_linea_presupuesto(linea: str) -> bool:
    """True si la linea es parte de un presupuesto (item con precio, total,
    subtotal, encabezado 'Presupuesto:'). Asi se saca lo que el Solver haya
    armado a mano para estampar el verificado en su lugar."""
    s = linea.strip()
    if not s:
        return False
    # Item en vineta con un monto: "- 2x Mouse: $76.000", "* Envio: $3.000".
    if re.match(r"^[-*•]", s) and "$" in s:
        return True
    # Linea de total o subtotal con un numero.
    if re.match(r"(?i)^(sub\s*)?total\b", s) and re.search(r"\d", s):
        return True
    # Encabezado de presupuesto solo.
    if re.match(r"(?i)^presupuesto\s*:?\s*$", s):
        return True
    return False


def _estampar_sin_marcador(respuesta: str, bloque: str) -> str:
    """El Solver no dejo marcador: saca el presupuesto que haya escrito a mano y
    pone el bloque verificado en su lugar (o al final si no escribio ninguno)."""
    lineas = respuesta.splitlines()
    salida: list[str] = []
    insertado = False
    for ln in lineas:
        if _es_linea_presupuesto(ln):
            if not insertado:
                salida.append(bloque)
                insertado = True
            # las lineas de presupuesto del Solver se descartan
            continue
        salida.append(ln)
    if not insertado:
        # No escribio presupuesto: el bloque va al final del cuerpo.
        cuerpo = "\n".join(salida).rstrip()
        return (cuerpo + "\n\n" + bloque) if cuerpo else bloque
    return "\n".join(salida)


def _normalizar(texto: str) -> str:
    """Colapsa corridas de lineas en blanco y recorta los bordes."""
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def renderizar(respuesta: str, presentacion: str, *,
               marcador: str = MARCADOR) -> str:
    """Estampa el bloque numerico verificado en la respuesta del Solver.

    Args:
        respuesta: lo que escribio el Solver (prosa de venta, con o sin marcador
            y con o sin numeros propios).
        presentacion: el bloque verificado de la calculadora (items + total), tal
            cual sale de estado_pedido.presentacion o de la verdad del turno.

    Returns:
        La respuesta con el bloque verificado pegado: por el marcador si esta,
        o sacando el presupuesto que el Solver haya escrito a mano. Si no hay
        bloque verificado, devuelve la respuesta sin tocar (pero limpia un
        marcador colgado).
    """
    resp = respuesta or ""
    bloque = (presentacion or "").strip()

    if not bloque:
        # Sin verdad que estampar: no inventamos. Solo sacamos un marcador
        # colgado para que el cliente no vea el sentinel.
        return _normalizar(resp.replace(marcador, ""))

    if marcador in resp:
        # Camino limpio: el Solver dejo el lugar, el codigo pone el bloque.
        out = resp.replace(marcador, bloque, 1).replace(marcador, "")
        return _normalizar(out)

    # Respaldo: el modelo ignoro el marcador. El codigo garantiza el dato igual.
    return _normalizar(_estampar_sin_marcador(resp, bloque))
