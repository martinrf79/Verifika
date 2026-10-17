"""UNA PREGUNTA, ESTAS FAMILIAS. Una pregunta mezcla varias."""

# Lo que el molde ya nombra, en el orden de una venta.
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
    """Familias que esta pregunta abre. Mezclar varias es lo normal. memoria y cierre se pasan desde afuera."""
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
