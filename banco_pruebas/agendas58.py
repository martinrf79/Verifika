"""LAS 58 Y LAS K COMO AGENDAS, A MANO — lo que tiene que devolver el interprete en cada turno (20-oct-2026).

Es la vara del intérprete nuevo, en el formato de `app/core/flujo/agenda.py`: una pregunta por cada cosa que pide el
cliente, con una accion del menu. Lo que el cliente senala de la charla va con el numero de la libreta que ve en ese
turno —M lo mostrado, P el pedido—, como la arma `interprete.libreta` sobre el estado real del banco.

Sin citas: la cita la controla `agenda.faltas` sobre lo que devuelve el modelo, y aca no hace falta.

Sirve dos veces:
  1. Sin modelo, para medir si lo que recibe el modelo alcanza: `tests/test_agenda.py`, la suficiencia.
  2. Con el modelo, al final, para compararlo pregunta por pregunta.
"""


def _p(accion, si=None, **datos):
    p = {"accion": accion, **{k: v for k, v in datos.items() if v not in (None, "", [], False)}}
    if si:
        p["si"] = {"de": si[0], "da": si[1]}
    return p


def bu(rubro, *condiciones, orden="nada", cantidad=1, entre=False, si=None):
    return _p("buscar", si, rubro=rubro, cantidad=cantidad, orden=orden, condiciones=list(condiciones),
              entre_lo_mostrado=entre)


def pr(producto, quiere_saber="precio", color=None, afirma=None, si=None):
    return _p("producto", si, producto=producto, quiere_saber=quiere_saber, color=color, afirma=afirma)


def a(producto, cantidad=1, color=None, destino=None):
    return {k: v for k, v in {"producto": producto, "cantidad": cantidad, "color": color, "destino": destino}.items()
            if v is not None}


def com(*agrega, saca=None, cambia=None, reparto=None, si=None):
    return _p("comprar", si, agrega=list(agrega), saca=saca, cambia=cambia, reparto=reparto)


def cu(tope=None, si_pasa=None, reparto=None):
    return _p("cuenta", tope=tope, si_pasa=si_pasa, reparto=reparto)


def po(tema, afirma=None):
    return _p("politica", tema=tema, afirma=afirma)


def en(destino):
    return _p("envio", destino=destino)


def co(producto, con, falta_modelo=False):
    return _p("compatibilidad", producto=producto, con=con, falta_modelo=falta_modelo)


def ex(pregunta):
    return _p("explicar", pregunta=pregunta)


def otro(que):
    return _p("otro", que=que)


def ag(*preguntas, cliente=None) -> dict:
    out = {"preguntas": [{"n": i, **p} for i, p in enumerate(preguntas, 1)]}
    if cliente:
        out["cliente"] = cliente
    return out


def pago(*pares):
    return [{"medio": m, "porcentaje": n} for m, n in pares]


SETENTA_TREINTA = pago(("transferencia", 70), ("Mercado Pago", 30))
SIN_CHINAS = "menos partes chinas posibles"

AGENDAS = {
    "C01": [ag(pr("G305", "stock"))],
    "C02": [ag(bu("parlante"))],
    "C03": [ag(pr("G502 Hero", "dpi"))],
    "C04": [ag(pr("K120", afirma="inalambrico"))],
    "C05": [ag(bu("notebook", "16 GB de RAM"))],
    "C06": [ag(bu("mouse", "inalambrico", "preferentemente Logitech"))],
    "C07": [ag(bu("mouse", "que no sea Genius"))],
    "C08": [ag(bu("tablet", "lo menos china posible"))],
    "C09": [ag(bu("monitor", orden="mas barato"))],
    "C10": [ag(en("Posadas"))],
    "C11": [ag(po("factura"))],
    "C12": [ag(po("promociones", afirma="50 por ciento off en todo"))],
    "C13": [ag(otro("dato"), po("mayoristas"), cliente={"es": "revendedor"})],
    "C14": [ag(ex("que conviene, DDR4 o DDR5?"))],
    "C15": [ag(com(a("G305", 2, "negro")))],
    "C16": [ag(com(a("K120", 1, "negro")), cu(reparto=SETENTA_TREINTA))],
    "C17": [ag(pr("G305"), bu("teclado", "mecanico"))],
    "C18": [ag(bu("auriculares", "JBL"), en("Cordoba"))],
    "C19": [ag(pr("G203", "stock"), po("factura"))],
    "C20": [ag(com(a("K120", 2, "negro"), a("G203", 1, "negro")))],
    "C21": [ag(com(a("G305", 1, "negro"), a("K120", 1, "negro"))),
            ag(cu(reparto=SETENTA_TREINTA))],
    "C22": [ag(pr("G305", "sirve para jugar"))],
    "C23": [ag(com(a("G305", 1, "blanco"), a("K120")))],
    "C24": [ag(bu("teclado", orden="mas barato"), bu("mouse", orden="mas barato"))],
    "C25": [ag(com(a("G305", 2, "negro"), a("K120", 3, "blanco")), cu())],
    "C26": [ag(com(a("G203", destino="Rosario"), a("G203", destino="Mendoza")), en("Rosario"), en("Mendoza"))],
    "C27": [ag(bu("mouse", "Logitech")),
            ag(bu("mouse", orden="mas barato", entre=True))],
    "C28": [ag(pr("G502 Hero", "stock", "negro"), pr("G305", si=(1, "no")))],
    "C29": [ag(co("G305", "Mac"), com(a("G305"), si=(1, "si")))],
    "C30": [ag(otro("dato"), co("Kingston Fury Beast DDR4 16GB", "placa DDR5"),
               bu("memoria ram", "DDR5", si=(2, "no")), cliente={"equipo": "PC de escritorio con placa DDR5"})],
    "C31": [ag(com(a("MX Master 3S", 1, "negro"), a("G305", 2, "negro")), cu(tope=300000, si_pasa="MX Master 3S"))],
    "C32": [ag(pr("G305", "inalambrico"), pr("G203", "inalambrico"))],
    "C33": [ag(otro("corrige"), bu("teclado", "Logitech"))],
    "C34": [ag(pr("G203"), en("Rosario")),
            ag(en("Cordoba"))],
    "C35": [ag(bu("mouse", "gamer", "Logitech")),
            ag(bu("mouse", "gamer", "que no sea Logitech"))],
    "C36": [ag(co("G305", "Mac"))],
    "C37": [ag(otro("dato"), co("memoria ram", "notebook", True), cliente={"equipo": "notebook"})],
    "C38": [ag(pr("Kingston Fury Beast DDR4 16GB")),
            ag(co("M1", "pc", True))],
    "C39": [ag(pr("G203", "inalambrico", afirma="inalambrico"))],
    "C40": [ag(po("costo_envio", afirma="envio gratis a todo el pais"))],
    "C41": [ag(otro("dato"), po("descuento_transferencia"), cliente={"es": "jubilado"})],
    "C42": [ag(bu("notebook", "64 GB de RAM", "menos de 200 mil"))],
    "C43": [ag(pr("K120")),
            ag(pr("M1", "inalambrico"))],
    "C44": [ag(pr("G305"), pr("G203")),
            ag(pr("M2", "stock"))],
    "C45": [ag(bu("mouse", "Logitech", "con cable")),
            ag(bu("mouse", "Logitech", "con cable", "blanco"))],
    "C46": [ag(bu("teclado", "que no sea Redragon")),
            ag(bu("teclado", "mecanico", "que no sea Redragon"))],
    "C47": [ag(otro("dato"), cliente={"localidad": "Posadas, Misiones"}),
            ag(pr("G203", color="negro"), en("Posadas"), cu())],
    "C48": [ag(com(a("G305", 1, "negro"))),
            ag(com(cambia=[{"es": "P1", "destino": "Rosario"}]), cu())],
    "C49": [ag(pr("K120", color="negro")),
            ag(bu("auriculares", "JBL")),
            ag(bu("webcam")),
            ag(pr("M1", "stock"))],
    "C50": [ag(pr("G203"), pr("G305")),
            ag(com(a(["M1", "M2"]))),
            ag(com(a("M1")))],
    "C51": [ag(pr("G305", color="negro"), com(a("G305", 1, "negro", "Cordoba")))],
    "C52": [ag(bu("mouse", "Logitech"), bu("teclado", "Logitech"), bu("auriculares", "JBL")),
            ag(pr([f"M{i}" for i in range(1, 13)]))],
    "C53": [ag(pr("G502 Hero")),
            ag(pr("M1", "stock", "negro"), com(a("M1", 1, "blanco"), si=(1, "no")))],
    "C54": [ag(otro("dato"), bu("placa de video", "que aguante una fuente de 550 watts", orden="mas potente"),
               cliente={"equipo": "fuente de 550 watts"})],
    "C55": [ag(pr("G305", color="negro"), pr("G203", color="negro")),
            ag(pr("G305")),
            ag(otro("corrige"), com(a("M1")))],
    "C56": [ag(po("promociones", afirma="50 off"), pr("K120", "si sale menos de 10 mil", "negro"),
               com(a("K120", 2, "negro"), si=(2, "si")))],
    "C57": [ag(otro("fuera_de_tema"))],
    "C58": [ag(otro("saludo"), pr("G305", "garantia"))],
    "K03": [ag(bu("auriculares", orden="mas barato", cantidad=2), bu("mouse", orden="mas barato", cantidad=2),
               com(a("auriculares", 2, destino="Cordoba capital"), a("mouse", 2, destino="Cordoba capital")), cu())],
    "K06": [ag(bu("teclado", orden="mas barato", cantidad=2), bu("mouse", orden="mas barato", cantidad=2),
               com(a("teclado", destino="Cordoba"), a("mouse", destino="Cordoba"),
                   a("teclado", destino="Rio Tercero"), a("mouse", destino="Rio Tercero")),
               cu(reparto=pago(("transferencia", 100))))],
    "K07": [ag(otro("saludo"), bu("mouse", orden="mas barato", cantidad=2), bu("teclado", orden="mas barato", cantidad=2),
               bu("auriculares", orden="mas barato", cantidad=2),
               com(a("mouse", destino="Rosario"), a("teclado", destino="Rosario"), a("teclado", destino="Concordia"),
                   a("auriculares", destino="Concordia"), a("los otros", 2, destino="Rio Cuarto")),
               cu(), po("formas_pago")),
            ag(cu(reparto=pago(("transferencia", 50), ("Mercado Pago", 50))))],
    "K20": [ag(bu("auriculares", SIN_CHINAS, cantidad=2), bu("mouse", SIN_CHINAS, cantidad=2),
               bu("memoria ram", SIN_CHINAS, cantidad=2),
               com(a("auriculares", destino="Cordoba capital"), a("mouse", destino="Cordoba capital"),
                   a("teclado", destino="Concordia"), a("mouse", destino="Concordia"),
                   a("los otros", 2, destino="Posadas")),
               cu(reparto=SETENTA_TREINTA)),
            ag(com(a("auriculares", destino="Cordoba capital"), a("mouse", destino="Cordoba capital"),
                   a("memoria ram", destino="Concordia"), a("mouse", destino="Concordia"),
                   a("los otros", 2, destino="Posadas")),
               cu(reparto=SETENTA_TREINTA))],
}
