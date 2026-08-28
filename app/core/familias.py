"""UNA PREGUNTA, ESTAS FAMILIAS.

Una pregunta mezcla varias. Eso es lo normal, no un caso raro.
Pedido, precio, garantia y si le sirve a la notebook pueden ir
en la misma frase. El sistema tiene que nombrar cada una, con
el mismo nombre en todos lados.

Esto NO es el interprete de veinte campos. Ese se borro el 1-ago
porque entendia peor. Esto es el catalogo de lo que una pregunta
PUEDE abrir, para que la maquinaria deje de hablar idiomas distintos.

De donde sale cada familia:

  declaracion  lo declara registrar_pedido en la llamada uno
  memoria      ya estaba en el estado de la charla
  cierre       lo detecta el codigo de cierre, no el molde

La oferta no esta aca: la abre el codigo, no el cliente.
"""

# Lo que el molde ya nombra, en el orden de una venta. Los nombres
# son EXACTOS los de registrar_pedido. Sin apodo. El orden del molde
# es otro; el candado compara el conjunto, no la fila.
DECLARACION = (
    "items",
    "stock",
    "atributos",
    "compatibilidad",
    "restricciones",
    "destinos",
    "pide_precio",
    "reparto_pago",
    "temas",
    "contradicciones",
)

MEMORIA = "memoria"
CIERRE = "cierre"

MAS_ALLA = (MEMORIA, CIERRE)
FAMILIAS = DECLARACION + MAS_ALLA

# La abre el codigo. No se suma al catalogo de la pregunta.
NO_ES_PREGUNTA = ("oferta",)


# Piezas de memoria. Los nombres SON las claves de construir_estado.
# Una pregunta puede reabrirlas. Las dos de contexto no: viajan de
# fondo y no se contestan como si el cliente las hubiera preguntado.
MEMORIA_PIEZAS = (
    "productos_vistos",
    "carrito",
    "descartados",
    "presupuesto",
    "localidad_envio",
    "localidades_envio",
    "provincia_envio",
    "grupos_envio",
    "criterio",
    "producto_anotado",
    "preferencias",
)

MEMORIA_CONTEXTO = (
    "resumen_charla",
    "datos_cliente",
)


# Los veinte campos del interprete muerto, en el orden de su schema.
# Cada uno cae en una familia viva o en None: murio con el interprete
# y no se reactiva. El motivo de los None esta en MURIO_CON_EL_INTERPRETE.
DEL_VIEJO = {
    "respondiendo_a": MEMORIA,
    "productos_consultados": "items",
    "producto_resuelto": "items",
    "candidatos": None,
    "ofrecer_opciones": None,
    "intencion": CIERRE,
    "estado_conversacion": None,
    "criterio": "restricciones",
    "orden": "restricciones",
    "pedido": "items",
    "solicitud_nueva": "items",
    "categorias": "temas",
    "temas_politica": "temas",
    "specs_preguntadas": "atributos",
    "plataformas_cliente": "compatibilidad",
    "tope_presupuesto": "restricciones",
    "exclusiones": "restricciones",
    "uso_previsto": "restricciones",
    "pago_reparto": "reparto_pago",
    "confianza": None,
}

MURIO_CON_EL_INTERPRETE = {
    "candidatos": "interno de identidad: el certificador decide sobre items",
    "ofrecer_opciones": "el bot pregunta; no es una familia que abra el cliente",
    "estado_conversacion": "embudo del interprete; el estado vivo es construir_estado",
    "confianza": "score del interprete, no del cliente",
}


def abiertas(declarado: dict | None, *, memoria: bool = False,
             cierre: bool = False) -> tuple[str, ...]:
    """Familias que esta pregunta abre. Mezclar varias es lo normal.

    memoria y cierre se pasan desde afuera. Detectarlos es la etapa
    siguiente, no este catalogo: un turno 2 no abre memoria solo por
    existir historial.
    """
    d = declarado or {}
    fuera = []
    for campo in DECLARACION:
        val = d.get(campo)
        if campo == "pide_precio":
            if val:
                fuera.append(campo)
            continue
        if val:
            fuera.append(campo)
    if memoria:
        fuera.append(MEMORIA)
    if cierre:
        fuera.append(CIERRE)
    return tuple(fuera)
