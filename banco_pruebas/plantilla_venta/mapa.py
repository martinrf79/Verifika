"""EL MAPA — las clases de pregunta de una tienda online, ampliadas desde las 58, 25-oct-2026, FICHA 80.

Las 58 de la FICHA 58 clasifican por gramatica: verbo, fuerza, dueno, enlace y memoria, sobre una tienda de tecnologia.
Para cualquier tienda faltaban las clases que las 58 no tenian porque Verifika no las vio: la postventa, el regateo,
la confianza, los ganchos de la venta y el que no compra. Cada clase dice de donde salio, en `origen`:

  58:C01      una de las 58, o J o K, de `vara_58.json`. Las 58 se clasifican aca, no se copian: son la vara.
  verifika:x  una situacion de `data/clientes/<tienda>/base_conocimiento.json`.
  bitext:x    una intencion de Bitext, Customer Service Tagged Training Dataset, 27 intenciones en 10 categorias,
              licencia CDLA-Sharing-1.0. Casi toda postventa y cuenta.
  gorgias:x   las seis intenciones de preventa del estudio de Gorgias de mayo de 2026, citado por Macha: availability,
              details, usage, promotion, warranty, wholesale. De segunda mano: no se leyo el estudio.
  pqa:x       Amazon product QA, McAuley y Yang: la pregunta de si o no contra la abierta; AmazonQA, la que la ficha no
              contesta.
  eqa:x       la taxonomia EQA de Yang y Alonso, SIGIR eCom 2024. Solo se confirmo su clase instruction.
  craigslist:x  los actos de la negociacion de CraigslistBargain, He y otros, 2018.
  inspired:x  las estrategias del vendedor de INSPIRED, Hayati y otros, 2020.
  wos         Wizard of Shopping, ACL 2025: la necesidad se achica por atributos, una condicion por turno.
  nuevo       la escribio esta ficha.

`herramienta` es la accion del menu de `app/core/flujo/agenda.py` que la cumple. "falta:x" dice que el ejecutor no
tiene con que cumplirla: el caso queda escrito y su validacion lo cuenta aparte, no se inventa una accion.
`universal` es False cuando la clase depende de lo que vende la tienda: la variante de talle no aplica a Verifika.
"""

ETAPAS = {
    "apertura": "el primer mensaje: saluda, pregunta directo o dice algo de si",
    "descubrir": "la necesidad: para que, para quien, cuanto quiere gastar, una cosa por vez",
    "mostrar": "opciones con precio, filtradas u ordenadas como lo pide",
    "dudas": "lo que pregunta antes de decidir: del producto, de la tienda, del envio, del pago, y las objeciones",
    "decidir": "elige, cambia de idea, pone una condicion o contesta lo que pregunto el vendedor",
    "armar": "el pedido: cantidades, variantes, destinos, cambios, el total y el tope",
    "cerrar": "el medio de pago, el reparto, el nombre y el link",
    "no_compra": "lo piensa, se va o se enoja: el lead se guarda sin presionar",
    "postventa": "despues de comprar: seguimiento, cambios, factura, reclamo. Queda para despues",
    "fuera": "lo que no es de la tienda: otro tema, manipulacion, cuenta de usuario",
    "union": "como se unen dos partes de un mensaje: si no hay, si da si, si pasa, y ademas, ah no",
}

# Como varia una misma pregunta, de las marcas de Bitext llevadas al rioplatense de WhatsApp.
VARIACIONES = {
    "B": "basica, afirmativa: 'busco un mouse'",
    "I": "interrogativa: '¿tenes mouse?'",
    "C": "coordinada, con contexto antes: 'tengo una notebook vieja, ¿que le sirve?'",
    "N": "con negacion: 'no quiero nada caro'",
    "P": "cortes: 'buenas, ¿me podrias decir...?'",
    "Q": "coloquial, voseo y jerga: 'che, ¿tenes algo piola?'",
    "K": "palabras sueltas: 'precio g305'",
    "E": "abreviada: 'q', 'xq', 'tmb', 'x favor'",
    "Z": "con errores de tipeo, sin tildes ni signos",
    "D": "indirecta, por otro: 'mi hermano quiere saber si...'",
    "Y": "mezcla de idioma: 'tienen delivery', 'el setup'",
    "W": "enojada u ofensiva",
    "R": "con ruido de charla: risas, saludo, gracias en el medio",
}

FUENTES = {
    "58": "FICHA 58, archivo/fichas_cerradas/FICHA_58_la_traduccion_en_gramatica.md, y banco_pruebas/vara_58.json",
    "verifika": "data/clientes/verifika_prod/base_conocimiento.json, las situaciones con su criterio y su movida",
    "bitext": "github.com/bitext/customer-support-llm-chatbot-training-dataset, README: categorias, intenciones y "
              "marcas de variacion del lenguaje. Los datos estan en Hugging Face, fuera de la red de la sesion",
    "gorgias": "getmacha.com/blog/ai-answer-pre-purchase-product-questions, que resume el estudio de Gorgias",
    "pqa": "cseweb.ucsd.edu/~jmcauley/datasets/amazon/qa y arxiv 1908.04364, AmazonQA",
    "eqa": "Yang y Alonso, A Bespoke Question Intent Taxonomy for E-commerce, SIGIR eCom 2024",
    "craigslist": "github.com/stanfordnlp/cocoa, craigslistbargain: actos de la negociacion",
    "inspired": "github.com/sweetpeach/Inspired: estrategias del vendedor en la recomendacion",
    "wos": "Wizard of Shopping, ACL 2025, aclanthology 2025.acl-long.641",
}


def _c(id_, etapa, nombre, herramienta, situaciones=(), origen=(), universal=True):
    return {"id": id_, "etapa": etapa, "nombre": nombre, "herramienta": herramienta,
            "situaciones": list(situaciones), "origen": list(origen), "universal": universal}


CLASES = [
    # ── APERTURA ─────────────────────────────────────────────────────────────
    _c("AP01", "apertura", "saluda y nada mas", "otro", ["saludo_apertura"], ["verifika:saludo_apertura"]),
    _c("AP02", "apertura", "saluda y pregunta directo por un producto", "producto", ["saludo_apertura"],
       ["58:C58", "gorgias:availability"]),
    _c("AP03", "apertura", "que vende la tienda, el catalogo", "otro", [], ["58:K19"]),
    _c("AP04", "apertura", "dice algo de si: de donde es, quien es", "otro", [], ["58:C47", "58:C13"]),
    _c("AP05", "apertura", "como se compra en la tienda", "politica", [], ["eqa:instruction", "nuevo"]),

    # ── DESCUBRIR LA NECESIDAD ───────────────────────────────────────────────
    _c("DE01", "descubrir", "necesita algo para un uso, sin decir el rubro", "buscar", ["asesoramiento_metodo"],
       ["58:J06", "gorgias:usage", "wos"]),
    _c("DE02", "descubrir", "es para regalar o para otro, sin saber que", "falta:asesorar", ["regalo"],
       ["verifika:regalo", "inspired:experience_inquiry"]),
    _c("DE03", "descubrir", "tiene un presupuesto para un rubro", "buscar", ["presupuesto_minimo", "calidad_precio"],
       ["verifika:presupuesto_minimo", "wos"]),
    _c("DE04", "descubrir", "le alcanza la plata para varias cosas", "cuenta", ["continuacion_presupuesto"],
       ["58:K15"]),
    _c("DE05", "descubrir", "nombra el rubro con jerga o describiendolo", "buscar", ["cliente_desprolijo"],
       ["58:J01", "58:J02", "58:J03", "58:J04", "58:J05", "58:J07", "58:J08", "58:J09"]),
    _c("DE06", "descubrir", "pide un rubro que la tienda no vende", "buscar", ["producto_no_vendido"],
       ["58:K12", "verifika:producto_no_vendido"]),
    _c("DE07", "descubrir", "nombra un modelo que la tienda no tiene", "producto", ["producto_ajeno_modelo"],
       ["verifika:producto_ajeno_modelo"]),
    _c("DE08", "descubrir", "pide algo tan vago que no hay rubro", "falta:asesorar", ["asesoramiento_metodo"],
       ["verifika:asesoramiento_metodo", "nuevo"]),
    _c("DE09", "descubrir", "saber general antes de elegir", "explicar", [], ["58:C14"]),
    _c("DE10", "descubrir", "gama: entrada, media o alta", "buscar", ["gama_entrada_media_alta"],
       ["verifika:gama_entrada_media_alta"]),

    # ── MOSTRAR Y RECOMENDAR ─────────────────────────────────────────────────
    _c("MO01", "mostrar", "que tiene de un rubro", "buscar", [], ["58:C02", "gorgias:availability"]),
    _c("MO02", "mostrar", "exige una condicion", "buscar", [], ["58:C05", "wos"]),
    _c("MO03", "mostrar", "prefiere una marca o algo, sin exigirlo", "buscar", ["marcas"], ["58:C06"]),
    _c("MO04", "mostrar", "rechaza una marca o algo", "buscar", [], ["58:C07"]),
    _c("MO05", "mostrar", "lo menos posible de algo", "buscar", [], ["58:C08", "58:K02"]),
    _c("MO06", "mostrar", "el mas barato o el mejor", "buscar", ["calidad_precio"], ["58:C09", "58:J01"]),
    _c("MO07", "mostrar", "ordena por un dato: el mas liviano, el mas grande", "buscar", [], ["58:K04"]),
    _c("MO08", "mostrar", "los n mas baratos", "buscar", [], ["58:K05"]),
    _c("MO09", "mostrar", "de toda la tienda: lo mas caro o lo mas barato", "buscar", [], ["58:K18", "58:K01"]),
    _c("MO10", "mostrar", "ordena o filtra solo entre lo que ya le mostraron", "buscar", [], ["58:C27"]),
    _c("MO11", "mostrar", "quiere ver otras opciones", "buscar", ["consulta_algo_mas"],
       ["verifika:consulta_algo_mas"]),
    _c("MO12", "mostrar", "cambia la busqueda anterior: y en blanco", "buscar", [], ["58:C45"]),
    _c("MO13", "mostrar", "otro rubro con la condicion que dijo antes", "buscar", [], ["58:C46", "58:K17"]),
    _c("MO14", "mostrar", "saca una condicion que habia puesto", "buscar", [], ["58:C35"]),
    _c("MO15", "mostrar", "pide condiciones que juntas no existen", "buscar", [], ["58:C42"]),
    _c("MO16", "mostrar", "cual me recomendas, entre lo mostrado", "falta:recomendar", ["indecision"],
       ["verifika:indecision", "inspired:personal_opinion"]),
    _c("MO17", "mostrar", "pide fotos", "falta:fotos", ["pedido_de_fotos"], ["verifika:pedido_de_fotos"]),
    _c("MO18", "mostrar", "pide una variante de talle o medida", "producto", [], ["nuevo"], universal=False),

    # ── DUDAS Y OBJECIONES ───────────────────────────────────────────────────
    _c("DU01", "dudas", "si hay stock de un producto", "producto", [], ["58:C01", "gorgias:availability", "pqa:si_no"]),
    _c("DU02", "dudas", "el precio de un producto", "producto", [], ["pqa:abierta"]),
    _c("DU03", "dudas", "un dato de la ficha", "producto", [], ["gorgias:details", "pqa:abierta"]),
    _c("DU04", "dudas", "un dato que la ficha no trae", "producto", [], ["58:C03", "pqa:sin_respuesta"]),
    _c("DU05", "dudas", "si viene en una variante: color", "producto", ["ambiguedad_variante"], ["gorgias:details"]),
    _c("DU06", "dudas", "si hay tantos", "producto", ["reposicion_stock"], ["gorgias:availability"]),
    _c("DU07", "dudas", "da por cierto algo falso del producto", "producto", [], ["58:C04", "58:C39"]),
    _c("DU08", "dudas", "compara dos productos", "producto", ["comparar_dos_productos"],
       ["verifika:comparar_dos_productos"]),
    _c("DU09", "dudas", "si un producto anda con lo suyo", "compatibilidad", ["compatibilidad"],
       ["58:C36", "gorgias:usage"]),
    _c("DU10", "dudas", "que le sirve de un rubro para lo suyo", "compatibilidad", ["compatibilidad"], ["58:C37"]),
    _c("DU11", "dudas", "si le sirve, sin decir el modelo de lo suyo", "compatibilidad", ["compatibilidad"],
       ["58:C38"]),
    _c("DU12", "dudas", "si sirve para un uso", "producto", [], ["58:C22", "gorgias:usage"]),
    _c("DU13", "dudas", "si es original", "politica", ["desconfianza_online"], ["verifika:desconfianza_online"]),
    _c("DU14", "dudas", "la garantia", "politica", ["garantia"], ["gorgias:warranty"]),
    _c("DU15", "dudas", "que trae la caja", "producto", [], ["gorgias:details"]),
    _c("DU16", "dudas", "de donde es", "producto", [], ["58:C08", "gorgias:details"]),
    _c("DU17", "dudas", "si es bueno, si dura: una opinion", "falta:opinar", ["durabilidad"],
       ["verifika:durabilidad", "pqa:abierta"]),
    _c("DU18", "dudas", "cuando entra lo que no hay", "politica", ["reposicion_stock"], ["verifika:reposicion_stock"]),
    _c("DU19", "dudas", "la factura o el IVA", "politica", ["factura", "precios_iva"], ["58:C11", "bitext:check_invoice"]),
    _c("DU20", "dudas", "da por cierto algo falso de la tienda", "politica", ["promociones"], ["58:C12", "58:C40"]),
    _c("DU21", "dudas", "dice quien es para pedir un permiso", "politica", ["promociones"], ["58:C41"]),
    _c("DU22", "dudas", "precio mayorista", "politica", ["mayorista_cantidad"], ["58:C13", "gorgias:wholesale"]),
    _c("DU23", "dudas", "desconfia de comprar online", "politica", ["desconfianza_online", "prueba_social_confianza"],
       ["verifika:desconfianza_online"]),
    _c("DU24", "dudas", "le parece caro", "buscar", ["objecion_precio"],
       ["verifika:objecion_precio", "craigslist:disagree"]),
    _c("DU25", "dudas", "pide un descuento", "politica", ["pedir_descuento"],
       ["58:K13", "verifika:pedir_descuento", "craigslist:counter_price", "gorgias:promotion"]),
    _c("DU26", "dudas", "dice un precio que le dijeron", "producto", ["precio_afirmado_falso"],
       ["verifika:precio_afirmado_falso", "craigslist:insist"]),
    _c("DU27", "dudas", "en otro lado esta mas barato", "politica", ["objecion_precio"],
       ["58:K13", "craigslist:counter_price"]),
    _c("DU28", "dudas", "las cuotas", "politica", ["cuotas_financiacion"], ["gorgias:promotion"]),
    _c("DU29", "dudas", "cuanto sale el envio a un lugar", "envio", ["costo_envio"], ["58:C10", "bitext:delivery_options"]),
    _c("DU30", "dudas", "cuanto tarda en llegar", "politica", ["plazo_envio"], ["bitext:delivery_period"]),
    _c("DU31", "dudas", "a donde envian, y al exterior", "politica", ["envio_zonas", "envio_exterior"],
       ["bitext:delivery_options"]),
    _c("DU32", "dudas", "si se puede retirar", "politica", ["retiro_local", "ubicacion"], ["bitext:delivery_options"]),
    _c("DU33", "dudas", "si llega urgente", "politica", ["envio_urgente", "urgencia_honesta"],
       ["verifika:envio_urgente"]),
    _c("DU34", "dudas", "los medios de pago", "politica", ["formas_pago"], ["bitext:check_payment_methods"]),
    _c("DU35", "dudas", "el descuento por transferencia", "politica", ["descuento_transferencia"], ["gorgias:promotion"]),
    _c("DU36", "dudas", "pagar al recibir", "politica", ["pago_contra_entrega"], ["verifika:pago_contra_entrega"]),
    _c("DU37", "dudas", "y si no le gusta: cambios y devoluciones", "politica", ["cambios_devoluciones"],
       ["bitext:check_refund_policy"]),
    _c("DU38", "dudas", "y si viene fallado", "politica", ["producto_defectuoso"], ["58:J10"]),
    _c("DU39", "dudas", "si venden usados", "politica", ["usados"], ["verifika:usados"]),
    _c("DU40", "dudas", "envoltorio de regalo", "politica", ["envoltorio_regalo"], ["verifika:envoltorio_regalo"]),
    _c("DU41", "dudas", "donde estan y que horario tienen", "politica", ["ubicacion", "horarios"],
       ["verifika:ubicacion"]),
    _c("DU42", "dudas", "un servicio que la tienda no tiene escrito", "politica", [], ["nuevo"]),
    _c("DU43", "dudas", "pagar en dolares u otra moneda", "politica", ["monedas_aceptadas"],
       ["verifika:monedas_aceptadas"]),
    _c("DU44", "dudas", "como lo embalan", "politica", ["embalaje_envio"], ["verifika:embalaje_envio"]),

    # ── DECIDIR ──────────────────────────────────────────────────────────────
    _c("DC01", "decidir", "se lleva un producto", "comprar", ["cierre_venta"], ["58:C15", "bitext:place_order"]),
    _c("DC02", "decidir", "se lleva con cantidad y variante", "comprar", ["cierre_venta"], ["58:C15"]),
    _c("DC03", "decidir", "se corrige en el mismo mensaje", "comprar", ["cambio_de_producto"], ["58:C33"]),
    _c("DC04", "decidir", "mejor el otro", "comprar", ["cambio_de_producto"], ["58:C44", "58:C55"]),
    _c("DC05", "decidir", "elige de lo mostrado por la posicion: el segundo", "comprar", [], ["58:C43"]),
    _c("DC06", "decidir", "elige de lo mostrado por un dato: el inalambrico", "comprar", [], ["58:C32"]),
    _c("DC07", "decidir", "contesta cual, a la repregunta del vendedor", "comprar", [], ["58:C50"]),
    _c("DC08", "decidir", "contesta que si a lo sumo", "comprar", ["preguntas_confirmacion"],
       ["verifika:preguntas_confirmacion"]),
    _c("DC09", "decidir", "contesta la variante que le pregunto el vendedor", "comprar", ["ambiguedad_variante"],
       ["verifika:ambiguedad_variante"]),
    _c("DC10", "decidir", "esa variante no, la otra", "comprar", ["negacion_variante"], ["verifika:negacion_variante"]),
    _c("DC11", "decidir", "elegi vos", "falta:recomendar", ["indecision"], ["verifika:indecision"]),
    _c("DC12", "decidir", "lo quiere reservar", "politica", ["reservas"], ["verifika:reservas"]),
    _c("DC13", "decidir", "lo lleva si cumple un precio", "comprar", [], ["58:C56"]),

    # ── ARMAR EL PEDIDO ──────────────────────────────────────────────────────
    _c("AR01", "armar", "suma varios productos", "comprar", ["edicion_pedido"], ["58:C20", "58:C21"]),
    _c("AR02", "armar", "cantidad distinta por producto", "comprar", [], ["58:C25"]),
    _c("AR03", "armar", "una condicion para un solo producto", "comprar", [], ["58:C23"]),
    _c("AR04", "armar", "una condicion para todos", "buscar", [], ["58:C24"]),
    _c("AR05", "armar", "cada cosa a un destino", "comprar", ["multidestino"],
       ["58:C26", "58:K06", "58:K07", "58:K09", "58:K20", "58:K02"]),
    _c("AR06", "armar", "suma por rubro, sin modelo", "comprar", [], ["58:K03"]),
    _c("AR07", "armar", "cambia la variante de un renglon", "comprar", ["edicion_pedido"], ["verifika:edicion_pedido"]),
    _c("AR08", "armar", "cambia la cantidad de un renglon", "comprar", ["edicion_pedido"], ["58:K11"]),
    _c("AR09", "armar", "cambia el destino que dijo antes", "comprar", ["cambio_direccion"], ["58:C34"]),
    _c("AR10", "armar", "saca algo del pedido", "comprar", ["edicion_pedido"], ["58:K16"]),
    _c("AR11", "armar", "rehace el pedido entero", "comprar", ["edicion_pedido"], ["58:K16"]),
    _c("AR12", "armar", "otro orden para todo lo pedido", "buscar", [], ["nuevo"]),
    _c("AR13", "armar", "cuanto es el total", "cuenta", [], ["58:C48"]),
    _c("AR14", "armar", "el total con envio", "cuenta", [], ["58:C48", "58:K03"]),
    _c("AR15", "armar", "si pasa de un monto, que saque algo", "cuenta", [], ["58:C31"]),
    _c("AR16", "armar", "un tope, sin decir que sacar", "cuenta", [], ["58:K15"]),
    _c("AR17", "armar", "dice cuantos son en total", "comprar", [], ["58:K08"]),
    _c("AR18", "armar", "nombra a medias algo de mucho antes", "producto", ["retomar_memoria"],
       ["58:C49", "58:K10", "verifika:retomar_memoria"]),
    _c("AR19", "armar", "un ese que puede ser varios", "producto", [], ["58:C52"]),
    _c("AR20", "armar", "algo del pedido con una condicion de antes", "comprar", [], ["58:C53"]),
    _c("AR21", "armar", "lo suyo con una condicion y un orden", "compatibilidad", [], ["58:C54"]),
    _c("AR22", "armar", "muchas unidades: precio por cantidad", "politica", ["mayorista_cantidad"], ["58:K13"]),

    # ── CERRAR ───────────────────────────────────────────────────────────────
    _c("CE01", "cerrar", "dice con que paga", "cuenta", ["formas_pago"], ["58:K06"]),
    _c("CE02", "cerrar", "reparte el pago en dos medios", "cuenta", ["split_pago"], ["58:C16", "58:C21"]),
    _c("CE03", "cerrar", "un medio que la tienda no toma", "falta:validar_medio", ["formas_pago"], ["nuevo"]),
    _c("CE04", "cerrar", "da el nombre", "otro", ["lead_captura"], ["58:K21"]),
    _c("CE05", "cerrar", "da el nombre y como paga", "cuenta", ["lead_captura"], ["58:K21"]),
    _c("CE06", "cerrar", "dale, cerralo", "comprar", ["cierre_venta"], ["verifika:cierre_venta"]),
    _c("CE07", "cerrar", "acepta lo que el vendedor supuso", "comprar", ["preguntas_confirmacion"], ["nuevo"]),
    _c("CE08", "cerrar", "ya pago y manda el comprobante", "politica", ["comprobante_no_verificado",
       "verificacion_pagos"], ["verifika:comprobante_no_verificado"]),

    # ── NO COMPRA TODAVIA ────────────────────────────────────────────────────
    _c("NC01", "no_compra", "lo piensa", "otro", ["postergacion"], ["verifika:postergacion", "craigslist:quit"]),
    _c("NC02", "no_compra", "agradece y se va", "otro", ["despedida_cordial"], ["verifika:despedida_cordial"]),
    _c("NC03", "no_compra", "pide hablar con una persona", "otro", ["contacto_humano"],
       ["bitext:contact_human_agent", "verifika:contacto_humano"]),
    _c("NC04", "no_compra", "se queja o se enoja", "otro", ["queja_enojo"], ["bitext:complaint", "verifika:queja_enojo"]),
    _c("NC05", "no_compra", "no le interesa", "otro", ["despedida_cordial"], ["craigslist:reject"]),

    # ── POSTVENTA ────────────────────────────────────────────────────────────
    _c("PV01", "postventa", "donde esta mi pedido", "politica", ["seguimiento_pedido", "estado_pedido"],
       ["bitext:track_order"]),
    _c("PV02", "postventa", "cancelar el pedido", "politica", ["cancelacion_pedido"], ["bitext:cancel_order"]),
    _c("PV03", "postventa", "cambiar la direccion de un pedido hecho", "politica", ["cambio_direccion"],
       ["bitext:change_shipping_address"]),
    _c("PV04", "postventa", "la devolucion de la plata", "politica", ["cambios_devoluciones"],
       ["bitext:get_refund", "bitext:track_refund"]),
    _c("PV05", "postventa", "le llego fallado", "politica", ["producto_defectuoso", "proceso_cambio"],
       ["verifika:producto_defectuoso"]),
    _c("PV06", "postventa", "no lo sabe configurar", "politica", ["soporte_configuracion"],
       ["verifika:soporte_configuracion"]),
    _c("PV07", "postventa", "quiere dejar una opinion", "falta:resena", [], ["bitext:review"]),
    _c("PV08", "postventa", "pide la factura de lo que compro", "politica", ["factura"], ["bitext:get_invoice"]),

    # ── FUERA DE LA TIENDA ───────────────────────────────────────────────────
    _c("FU01", "fuera", "otro tema", "otro", ["fuera_de_tema"], ["58:C57"]),
    _c("FU02", "fuera", "charla con una pregunta en el medio", "producto", ["cliente_desprolijo"], ["58:C58"]),
    _c("FU03", "fuera", "le cambia el rol al bot", "otro", ["jailbreak_rol"], ["58:K14", "verifika:jailbreak_rol"]),
    _c("FU04", "fuera", "dice ser el dueno o alguien de la tienda", "otro", ["autoridad_falsa"],
       ["verifika:autoridad_falsa"]),
    _c("FU05", "fuera", "cuenta de usuario y contrasena", "otro", [], ["bitext:create_account", "bitext:recover_password"]),
    _c("FU06", "fuera", "las redes de la tienda", "politica", [], ["bitext:newsletter_subscription"]),

    # ── LAS UNIONES ──────────────────────────────────────────────────────────
    _c("UN01", "union", "y ademas: dos consultas distintas", "producto", ["varias_preguntas"],
       ["58:C17", "58:C18", "58:C19", "58:C22"]),
    _c("UN02", "union", "si no hay, el otro", "producto", [], ["58:C28"]),
    _c("UN03", "union", "si da si, lo lleva", "compatibilidad", [], ["58:C29"]),
    _c("UN04", "union", "si no le sirve, que otra hay", "compatibilidad", [], ["58:C30"]),
    _c("UN05", "union", "ah no, mejor otra cosa", "buscar", ["cambio_de_producto"], ["58:C33"]),
    _c("UN06", "union", "uno de lo pedido a otra pieza del mismo mensaje", "producto", [], ["58:C51"]),
    _c("UN07", "union", "dato falso y compra con condicion", "politica", [], ["58:C56"]),
]

# Las 58, las J y las K: todas estan en alguna clase. Lo controla `tests/test_plantilla_venta.py`.
POR_ID = {c["id"]: c for c in CLASES}
