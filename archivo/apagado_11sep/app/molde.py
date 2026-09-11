"""
EL MOLDE — lo que el modelo DECLARA en la llamada uno, y el esquema que ve.

Salio de `herramientas.py` el 11-sep-2026, sin cambiar una linea de lo que
hace. Es el primer corte de la etapa 2 del orden: aca estan los moldes de
Pydantic -`RegistrarPedido` y sus hermanos-, la lista `_MOLDES`, y `esquemas()`,
que es donde se inyectan los enums de la fuente viva. Es exactamente lo que se
edita para cambiar las casillas de la interpretacion, y vivia mezclado con las
herramientas de consulta.

`herramientas.py` importa todo esto con sus nombres de siempre: lo que decia
`herramientas.RegistrarPedido` o `herramientas.esquemas` sigue andando igual.
Este archivo no importa nada de `herramientas.py`, a proposito: el molde no
depende de las herramientas, las herramientas dependen del molde.

Los moldes son Pydantic y el esquema que ve el modelo se GENERA de ellos: una
sola definicion. Si un molde cambia, el esquema cambia solo.
"""
import typing
from typing import Literal

from pydantic import BaseModel, Field


# ── LOS MOLDES ───────────────────────────────────────────────────────────────
# Pydantic manda: valida y coacciona lo que el modelo devuelve. Un argumento
# fuera de molde no llega a la funcion, se descarta con su motivo.

class Filtro(BaseModel):
    """Una condicion estructurada sobre un campo real del catalogo."""
    campo: str = Field(
        description="El campo exacto de la lista. No inventes nombres.")
    operador: Literal["contiene", "no_contiene", "igual", "mayor",
                      "menor"] = Field(
        description="'contiene' texto. 'no_contiene' lo que NO quiere. "
                    "'igual' exacto. 'mayor'/'menor' solo numeros e INCLUYEN "
                    "el borde, asi que 'mas de N' se pide como N+1.")
    valor: str = Field(
        description="Numero pelado, en la UNIDAD DEL CAMPO: garantia_meses en "
                    "meses, un año es 12. No '500 gramos'.")


class BuscarProductos(BaseModel):
    """Busca productos en el catalogo real.

    UNA sola forma de acotar y ordenar. Todo lo que el cliente pida sobre un
    atributo va en `filtros`, incluido el presupuesto -precio_ars menor X- y lo
    que NO quiere -no_contiene-. Todo lo que sea "el mas algo" va en
    `ordenar_por`."""
    descripcion: str | None = Field(
        None, description="Como lo nombro el cliente, tal cual: 'la asus tuf "
                          "f15', 'un mouse gamer inalambrico para viajar'. "
                          "Mandala SIEMPRE que el cliente haya descrito lo que "
                          "busca, aunque tambien pases categoria: con esto se "
                          "ordenan los candidatos por lo que mas se le parece.")
    categoria: str | None = Field(
        None, description="Categoria del catalogo, si el cliente pidio un "
                          "rubro y no un modelo puntual.")
    filtros: list[Filtro] | None = Field(
        None, description="CONDICIONES CONCRETAS sobre los campos del "
                          "catalogo. Usalas SIEMPRE que el cliente pida un "
                          "atributo -que sea blanco, que pese menos de 500 "
                          "gramos, que tenga bluetooth, que no sea de una "
                          "marca, que salga menos de tanto-. No lo resuelvas "
                          "leyendo las descripciones: pedilo aca y el codigo "
                          "filtra sobre los 880. EL ORIGEN TAMBIEN ES UN CAMPO: "
                          "'que no sea chino' o 'lo menos chino posible' es "
                          "pais_fabricacion no_contiene china mas pais_marca "
                          "no_contiene china. NUNCA contestes que no sabes de "
                          "donde viene un producto: la fuente lo tiene y estos "
                          "campos te lo dan.")
    ordenar_por: str | None = Field(
        None, description="Campo por el que ordenar cuando el cliente pide un "
                          "extremo: 'el mas barato' es precio_ars con "
                          "direccion min, 'el mas liviano' es peso_gramos con "
                          "min, 'el de mas garantia' es garantia_meses con "
                          "max. Vacio si no pidio ningun extremo: por defecto "
                          "se ordena por lo que mas se parece a lo que pidio.")
    direccion: Literal["min", "max"] = Field(
        "min", description="'min' para el menor -el mas barato, el mas "
                           "liviano-, 'max' para el mayor.")
    cuantos: int = Field(3, description="Cuantas opciones traer, 1 a 6.")


class ConsultarCatalogo(BaseModel):
    """RESPONDE SOBRE EL CATALOGO ENTERO, no sobre unos pocos productos.

    Usala cuando la pregunta es sobre TODO lo que vendemos y no sobre un
    producto puntual: si tenemos algo que cumpla una condicion, cuantos hay,
    cual es el mas barato o el mas caro de todo, que marcas manejamos, en que
    rubros se cumple algo. `buscar_productos` te trae seis productos; esta te
    da el numero exacto sobre los 880.

    ES OBLIGATORIA antes de afirmar cualquier cosa sobre el catalogo entero. Si
    vas a decir "no tenemos nada que...", "todo lo que trabajamos es..." o
    "ninguno de nuestros productos...", primero preguntalo aca. Sin este dato
    NO podes afirmarlo: no lo sabes."""
    operacion: Literal["contar", "mas_barato", "mas_caro", "el_mayor",
                       "el_menor", "valores", "donde_se_cumple"] = Field(
        description="'contar' cuantos hay. 'mas_barato' y 'mas_caro' el de "
                    "todo el catalogo por precio. 'el_mayor' y 'el_menor' el "
                    "extremo de CUALQUIER otro campo: el de mas garantia es "
                    "el_mayor con campo garantia_meses, el mas liviano es "
                    "el_menor con campo peso_gramos. 'valores' que valores "
                    "distintos existen de un campo, por ejemplo que marcas "
                    "manejamos. 'donde_se_cumple' en que categorias SI se "
                    "cumple del todo lo que el cliente pide evitar.")
    campo: str | None = Field(
        None, description="De que campo. Obligatorio para 'valores', "
                          "'el_mayor' y 'el_menor'.")
    categoria: str | None = Field(
        None, description="Acotá a una categoria si la pregunta es de un rubro.")
    filtros: list[Filtro] | None = Field(
        None, description="Condiciones que acotan la cuenta, con la MISMA "
                          "forma que en buscar_productos: 'cuantos mouse "
                          "blancos hay' es contar con color contiene blanco; "
                          "'cuantos no se fabrican en China' es contar con "
                          "pais_fabricacion no_contiene china; 'la notebook "
                          "mas barata con 16GB' es mas_barato con ram "
                          "contiene 16.")
    # 5-AGO: `filtros` ENTRA. Antes no estaba, con el argumento de que costaba
    # 2.500 caracteres de esquema por turno. Medido: sin esto no habia forma de
    # cruzar un agregado con una condicion -"cuantos mouse blancos tenes", "la
    # mas barata con 16GB"-, o sea 38 campos en una puerta y cero en la otra, y
    # el hueco lo llenaba el modelo inventando. El esquema se comparte con
    # buscar_productos, asi que el enum de campos ya estaba pago.


class FichaProducto(BaseModel):
    """Trae la ficha completa de un producto ya identificado, por su id."""
    product_id: str = Field(description="El id exacto del catalogo, ej TEC0019.")


class ConsultarTemas(BaseModel):
    """Trae TODO lo que la casa tiene escrito sobre uno o varios temas. De cada
    tema vuelve lo que exista: la POLITICA oficial ya redactada con sus numeros
    reales, el CRITERIO desde donde razonar -para que sirve cada cosa, que
    conviene segun el uso, como se comparan- y la MOVIDA de esa situacion -que
    se busca, como se arma el mensaje y cuando NO se usa-.

    Pedila para contestar una politica (envios, pagos, garantia, factura), para
    recomendar o comparar, y para conducir una situacion de venta: dice que
    esta caro, pide descuento, desconfia, se queja, apura, posterga, cancela,
    se despide, pide hablar con una persona o afirma un precio que no es el
    nuestro.

    UN TEMA POR CADA COSA QUE PREGUNTO EL CLIENTE. Si pregunto tres cosas van
    los tres temas juntos en esta misma llamada, no uno solo."""
    temas: list[str] = Field(
        description="Los temas exactos de la lista, uno por cada cosa que "
                    "pregunto el cliente.")


class CotizarEnvio(BaseModel):
    """Cotiza el envio a un destino concreto."""
    localidad: str = Field(
        description="Localidad, provincia o codigo postal que dijo el cliente.")


class ItemPedido(BaseModel):
    product_id: str = Field(description="Id del catalogo.")
    cantidad: int = Field(1, description="Unidades de ese producto.")
    destino: str | None = Field(
        None, description="A donde va ESTE item, si el pedido se reparte "
                          "entre varios lugares.")


class PartePago(BaseModel):
    # EL MEDIO PUEDE VENIR VACIO, y es a proposito. Medido en produccion dos
    # dias seguidos: "divide el presupuesto en setenta treinta" NO dice que
    # medio lleva cada parte, y cuando el modelo elegia en silencio elegia
    # DISTINTO cada vez -y como la transferencia tiene descuento, ese silencio
    # le cambiaba al cliente lo que paga-. Ahora puede declarar el reparto sin
    # inventar el medio, y el supuesto lo pone el codigo, declarado en la cuenta.
    medio: Literal["transferencia", "mercado pago", ""] = Field(
        "", description="Con que paga esta parte. Vacio si el cliente no lo "
                        "dijo: NO lo elijas vos.")
    porcentaje: float = Field(description="Que porcentaje del total va por ahi.")


class ArmarPresupuesto(BaseModel):
    """Arma la cuenta completa: productos, envios y reparto de pago. Devuelve
    el presupuesto ya escrito, renglon por renglon."""
    items: list[ItemPedido] = Field(description="Todo lo que el cliente pidio.")
    destinos: list[str] | None = Field(
        None, description="Localidades de envio, una por destino distinto.")
    pago: list[PartePago] | None = Field(
        None, description="Reparto del pago SOLO si el cliente lo dividio "
                          "entre medios, ej 20 por ciento con Mercado Pago y "
                          "el resto por transferencia.")


class VerCompatibilidad(BaseModel):
    """Dice si un producto sirve para lo que tiene el cliente.

    Dos formas, se usa la que corresponda:
      - contra una PLATAFORMA generica, con `equipo`: 'mi notebook', 'la ps5'.
      - contra OTRO PRODUCTO del catalogo, con `contra_product_id`: 'tengo la
        Lenovo IdeaPad 3, que memoria le sirve'. Cruza lo que uno REQUIERE
        contra lo que el otro PROVEE, en las dos direcciones. Es mas preciso:
        compara las fichas de los dos."""
    product_id: str = Field(description="Id del producto en duda.")
    equipo: str | None = Field(
        None, description="Lo que tiene el cliente, tal cual lo dijo: "
                          "'notebook', 'ps5', 'pc de escritorio'.")
    contra_product_id: str | None = Field(
        None, description="Id del OTRO producto, cuando el equipo del cliente "
                          "es algo que nosotros vendemos y ya lo certificaste "
                          "con buscar_productos.")


class ConsultarProductos(BaseModel):
    """Una puerta al catalogo, con proyeccion. lista busca, catalogo agrega,
    ficha trae un id, compatibilidad cruza. Compatibilidad no se apaga: se
    pide por proyeccion, no por otra puerta."""
    proyeccion: Literal["lista", "catalogo", "ficha", "compatibilidad"] = Field(
        "lista",
        description="lista busca, catalogo agrega, ficha trae un id, "
                    "compatibilidad cruza.")
    descripcion: str | None = Field(None)
    categoria: str | None = Field(None)
    filtros: list[Filtro] | None = Field(None)
    ordenar_por: str | None = Field(None)
    direccion: Literal["min", "max"] = Field("min")
    cuantos: int = Field(3)
    operacion: Literal["contar", "mas_barato", "mas_caro", "el_mayor",
                       "el_menor", "valores", "donde_se_cumple"] | None = Field(
        None)
    campo: str | None = Field(None)
    product_id: str | None = Field(None)
    equipo: str | None = Field(None)
    contra_product_id: str | None = Field(None)


class Cotizar(BaseModel):
    """Una puerta a la plata: envio y presupuesto."""
    localidad: str | None = Field(
        None, description="Localidad de envio si solo se cotiza el envio.")
    items: list[ItemPedido] | None = Field(None)
    destinos: list[str] | None = Field(None)
    pago: list[PartePago] | None = Field(None)


class ItemDeclarado(BaseModel):
    que: str = Field(description="Que pidio, tal cual: 'auriculares', "
                                 "'la asus tuf f15', 'memoria ram'.")
    # LA CATEGORIA ES ATADURA, NO PESO (FICHA 06). El enum sale del catalogo
    # vivo, asi que el modelo no puede nombrar un rubro que no vendemos, y con
    # el rubro puesto la busqueda que deriva el codigo acota de una: sin el, un
    # rubro pelado -"auriculares"- vuelve `no_encontrado` porque la descripcion
    # esta pensada para lo que el cliente DESCRIBE, no para un rubro solo.
    categoria: str | None = Field(
        None, description="El rubro, si es uno de la lista. Vacio si no.")
    cantidad: int = Field(1, description="Cuantas unidades de eso.")
    # EL DESTINO VA PEGADO AL ITEM, no en una lista suelta al costado. Hasta el
    # 5-ago `destinos` viajaba aparte, sin ninguna atadura con los items, asi
    # que "un mouse a Cordoba y el otro a Concordia" NO SE PODIA DECLARAR: el
    # reconciliador veia "2 mouse" y "Cordoba, Concordia" sin saber cual iba a
    # donde, y por lo tanto un reparto mal hecho no lo podia detectar. Es la
    # familia mas grande de las preguntas de prueba.
    # ── LA ATADURA FUERTE, PROBADA Y REVERTIDA CON SU NUMERO (9-ago) ────────
    # Se probo cerrarle al modelo la puerta de la lista suelta: esta descripcion
    # pasaba a "ES OBLIGATORIO partir el item en un renglon por destino" y la de
    # `destinos` a "SOLO cuando todo va a un mismo lugar". La idea era buena en
    # el papel -un solo lugar donde declarar el reparto- y midio PEOR:
    #
    #   redaccion 1, la del teclado ....... 92 -> 31, peor caso 88 -> 8
    #   redaccion 5, coloquial ............ 75 -> 69
    #   redaccion 6, la limpia ............ 96 -> 100
    #   `tres_envios_cotizados` ........... fallo 5 de 9, antes 3 de 18
    #   y el MURO volvio a salir en una corrida
    #
    # LA CAUSA, y es la leccion: la lista suelta no era solo un lugar comodo
    # para tirar las ciudades, era tambien una RED. Cuando el mensaje tiene una
    # arista -el teclado que no esta en el pedido- el modelo no logra pegar los
    # tres destinos a los renglones, y sin la lista las ciudades que no pego se
    # PIERDEN enteras: el envio ni siquiera se cotiza. Antes quedaban en la
    # lista y al menos se cobraban los tres envios.
    #
    # Cerrarle una puerta al modelo solo sirve si la que queda le alcanza para
    # todos los casos. Aca no le alcanzaba, y el precio lo pago el mensaje mas
    # dificil. Lo que SI quedo de este intento es la derivacion de `destinos`
    # desde los renglones en `registrar_pedido`, que solo suma y nunca pierde.
    destino: str | None = Field(
        None, description="A donde va ESTE item si el pedido se reparte. Si "
                          "todo va a un lado, vacio y usá `destinos`.")


# EL DOCSTRING DE UN SUBMODELO VIAJA EN EL ESQUEMA, en cada llamada y por
# turno. Lo que explica POR QUE existe el campo va como comentario, que no se
# paga; lo que el modelo necesita para llenarlo va en el docstring, corto.
# Este se lleva la semantica de `ficha_producto`, que dejo de ser visible: lo
# que antes era "traeme la ficha del id tal" ahora es "el cliente pregunto ESTE
# campo de ESTE producto", y la ficha la trae el codigo.
class AtributoDeclarado(BaseModel):
    """Un dato duro que el cliente pregunto de un producto."""
    de: str = Field(description="Que producto, como lo nombro el cliente: "
                                "'el mouse logitech', 'ese'.")
    campo: str = Field(description="Que dato pregunto.")


# Se lleva la semantica de `ver_compatibilidad`: el cruce contra las dos fichas
# lo hace el codigo; aca solo se declaran los dos lados.
class CompatibilidadDeclarada(BaseModel):
    """Si un producto le sirve para lo que tiene o para lo que quiere."""
    que: str = Field(description="El producto en duda, como lo nombro.")
    para: str = Field(description="Contra que: 'mi notebook', 'la ps5', "
                                  "'jugar', 'editar video'.")


class RegistrarPedido(BaseModel):
    """DECLARA TODO lo que entendiste. Es lo UNICO que llamas: no busca nada,
    el codigo deriva de esto que ir a buscar y te lo devuelve para escribir.
    Llamala siempre, salvo que el mensaje no pida ningun dato -un saludo-.

    UN RENGLON POR CADA COSA QUE PREGUNTO, en el campo que corresponda. Lo que
    no declares no se busca, y el cliente se queda sin esa respuesta."""
    # `items` DEJO DE SER OBLIGATORIO (FICHA 06, 23-ago-2026), y lo encontro el
    # turno 3 del casete 77 al regrabar. El cliente pregunta "que trae la caja?"
    # -una pregunta informativa pura, sin nada que cotizar-, el modelo declara
    # SOLO `atributos`, que es exactamente lo correcto, y Pydantic rechaza el
    # molde entero por falta de `items`. El turno se queda sin declaracion, sin
    # puntos, sin derivacion y sin ficha: `pedido_mal_formado` y el cliente sin
    # respuesta.
    #
    # ES LA MISMA FALLA QUE `_sin_nulos` documenta doce lineas mas abajo -la
    # distancia entre lo que el molde PIDE y lo que ACEPTA- y aparecio ahora
    # porque hasta hoy no existia una declaracion legitima sin items: los seis
    # campos viejos eran todos de la parte transaccional. Con las cuatro
    # familias informativas adentro, "no hay nada que cotizar" pasa a ser un
    # estado normal del turno y no un molde roto.
    items: list[ItemDeclarado] = Field(
        default_factory=list,
        description="Un renglon por cada cosa que quiere COTIZAR o ver. Solo "
                    "lo que pidio de verdad; si nombro algo al pasar y no "
                    "queda claro, va en contradicciones.")
    restricciones: list[str] | None = Field(
        None, description="TODA condicion y TODO extremo que puso, tal cual y "
                          "uno por renglon: 'sin partes chinas', 'que sea "
                          "inalambrico', 'el mas barato', 'el de mas "
                          "garantia'. El codigo las traduce a filtros y a un "
                          "orden. El ORIGEN es una condicion mas y la fuente lo "
                          "sabe: nunca digas que no sabes de donde viene algo.")
    destinos: list[str] | None = Field(
        None, description="Todas las localidades de envio que nombro.")
    # LA SEMANTICA DE `armar_presupuesto` VIVE ACA DESDE LA FICHA 06, y la
    # segunda frase la puso un turno perdido al regrabar. El turno 8 de la
    # charla real del 12-ago —"agregá a ese presupuesto que detallaste al
    # último un teclado con envío a Córdoba"— salio SIN Total: el modelo dejo
    # `pide_precio` en falso porque el cliente no pregunto "cuanto sale", y con
    # eso el reconciliador no marca `falta_la_cuenta` y la cuenta no se rehace.
    # Es exactamente el aviso de la ficha: la semantica que llevaban las ocho
    # descripciones es lo que le enseñaba al modelo a declarar bien, y lo
    # primero que hay que mirar si empieza a declarar peor.
    pide_precio: bool = Field(
        False, description="True si espera un numero: precio, total, cuanto "
                           "sale, presupuesto. TAMBIEN si pide agregar, sacar "
                           "o cambiar algo de un presupuesto que ya le diste: "
                           "la cuenta se rehace entera y lleva Total.")
    contradicciones: list[str] | None = Field(
        None, description="Lo que NO cierra y no podes resolver sin elegir por "
                          "el cliente: cantidades que no dan, algo nombrado en "
                          "el envio que no esta en el pedido. Cada una como la "
                          "duda concreta que le harias. Si cierra, vacio.")
    # ── EL CAMPO QUE VOLVIO DEL INTERPRETE VIEJO (Martin, 7-ago-2026) ────────
    #
    # ES EL UNICO QUE VOLVIO, y no es una corazonada: salio de medir los dos
    # interpretes con la misma vara, cinco redacciones por tres corridas.
    #
    #   ENTIENDE el mensaje    interprete viejo 69    el de hoy 91
    #
    # O sea que la decision del 1-ago de matar el interprete NO fue un error: el
    # de hoy entiende mejor y sobre todo es ESTABLE -exactamente 91 en las cinco
    # redacciones, mientras el viejo va de 45 a 82 segun como este escrito el
    # mensaje-. Pero el viejo GANA EN UNA SOLA COSA, y es la que hoy falla
    # SIEMPRE: tenia `pago_reparto` tipado y entendia el reparto 15 de 15.
    #
    # EL AGUJERO QUE ESTO TAPA, medido: `RegistrarPedido` no tenia DONDE poner
    # un reparto de pago. Sus campos eran items, restricciones, destinos,
    # pide_precio y contradicciones, y un reparto no entra en ninguno, asi que
    # el modelo lo tiraba: 15 de 15 corridas sin declararlo. En la charla real
    # del 6-ago eso costo $17.500 la primera vez -la cuenta salio sin reparto- y
    # $9.140 la segunda -el modelo lo puso al reves, con la parte grande en el
    # medio SIN descuento-.
    #
    # POR QUE TIPADO Y NO UNA FRASE. Mientras viajaba como texto libre en
    # `restricciones`, el codigo tenia que leer castellano: la primera version
    # leia "70/30" y se caia con "setenta treinta", que es como lo escribio
    # Martin. Traducir la frase a dos numeros es lo unico que un modelo hace
    # mejor que cualquier regex. Con el campo tipado esa clase de falla no puede
    # existir, y se BORRA codigo en vez de agregar.
    reparto_pago: list[PartePago] | None = Field(
        None, description="Si dividio el pago, el reparto en numeros que suman "
                          "100: 'setenta treinta', '70/30', 'mitad y mitad'. Si "
                          "no dijo el medio de una parte, dejalo vacio.")

    # ── LAS CUATRO FAMILIAS INFORMATIVAS (FICHA 06, 23-ago-2026) ─────────
    #
    # POR QUE ENTRAN. `indice_turno.puntos` sabe abrir punto para atributo,
    # stock, compatibilidad y politica desde la FICHA 02, y no lo abria nunca:
    # los seis campos de arriba son la parte TRANSACCIONAL del pedido y una
    # pregunta informativa no entra en ninguno. O sea que el contrato de
    # cobertura era ciego justo en la mitad de la charla donde mas se alucina,
    # y el 11% de puntos sin contestar era un PISO, no el numero.
    #
    # Y NO SE SUMAN A LOS 25 KB: LOS REEMPLAZAN. Las otras ocho herramientas
    # dejaron de ser visibles el mismo dia. La semantica que llevaban en su
    # descripcion -que resuelve cada una y cuando se usa- es lo que le enseñaba
    # al modelo a declarar bien, asi que se MUDO acá campo por campo en vez de
    # tirarse. Si el modelo empieza a declarar peor, es lo primero que hay que
    # mirar.
    atributos: list[AtributoDeclarado] | None = Field(
        None, description="Cada DATO DURO que pregunto de un producto: cuanto "
                          "pesa, cuantos dpi, que trae la caja, de donde viene. "
                          "Uno por dato, aunque sean del mismo producto.")
    stock: list[str] | None = Field(
        None, description="Cada cosa sobre la que pregunto SI LA TENEMOS, con "
                          "sus palabras: 'celulares samsung', 'una play 5'. "
                          "Declarala TAMBIEN si creés que no la vendemos: es la "
                          "unica forma de mirar el catalogo entero antes de "
                          "decir que no hay. Sin eso no podes afirmarlo.")
    compatibilidad: list[CompatibilidadDeclarada] | None = Field(
        None, description="Cada vez que pregunto si algo LE SIRVE.")
    temas: list[str] | None = Field(
        None, description="UNO POR CADA COSA que pregunto y contesta la casa, "
                          "con LAS PALABRAS DEL CLIENTE: 'envio al exterior', "
                          "'cuanto tarda', 'la garantia', 'factura'. Va tambien "
                          "la SITUACION: esta caro, pide descuento, desconfia, "
                          "se queja, apura, posterga, cancela, se despide, pide "
                          "una persona, afirma otro precio. Si pregunto tres "
                          "van tres. El codigo lo certifica y te trae la "
                          "politica con sus numeros, el criterio y la movida.")


# UNA SOLA LISTA DEL MOLDE. El tipo de un punto ES el campo. Inventar
# `condicion` al lado de `restricciones` es el telefono descompuesto.
# El catalogo COMPLETO de lo que una pregunta puede abrir —estos diez,
# mas memoria y cierre— vive en `app/core/familias.py`.
CAMPOS_PEDIDO = tuple(RegistrarPedido.model_fields.keys())


_MOLDES = {
    "registrar_pedido": RegistrarPedido,
    "consultar_productos": ConsultarProductos,
    "cotizar": Cotizar,
    "consultar_temas": ConsultarTemas,
}


# ── EL ESQUEMA QUE VE EL MODELO, generado del molde ──────────────────────────
def _aplanar(nodo, defs):
    """Pydantic emite `$ref` a `$defs` y `anyOf: [X, null]` para los opcionales.
    Gemini rechaza las dos formas. Se inlinean las referencias y el opcional
    queda como el tipo a secas: la nulabilidad la maneja el que llama, no el
    esquema."""
    if not isinstance(nodo, dict):
        return nodo
    if "$ref" in nodo:
        nombre = nodo["$ref"].rsplit("/", 1)[-1]
        return _aplanar(dict(defs.get(nombre, {})), defs)
    if "anyOf" in nodo:
        ramas = [r for r in nodo["anyOf"]
                 if isinstance(r, dict) and r.get("type") != "null"]
        base = _aplanar(ramas[0], defs) if ramas else {"type": "string"}
        if nodo.get("description"):
            base["description"] = nodo["description"]
        return base
    out = {}
    for k, v in nodo.items():
        if k in ("title", "default", "$defs", "additionalProperties"):
            continue
        if k == "properties":
            out[k] = {pk: _aplanar(pv, defs) for pk, pv in v.items()}
        elif k == "items":
            out[k] = _aplanar(v, defs)
        else:
            out[k] = v
    return out


def _esquema_de(modelo) -> dict:
    bruto = modelo.model_json_schema()
    return _aplanar(bruto, bruto.get("$defs") or {})


# `_atar_filtros` MURIO ACA (FICHA 06, 23-ago-2026). Inyectaba el enum de campos
# en los `filtros` de `buscar_productos` y de `consultar_catalogo`, que eran las
# dos herramientas donde el MODELO escribia una condicion. Ahora las condiciones
# las escribe el codigo -`filtros_catalogo.resolver_exclusion` y su gemela
# `resolver_orden`- con los nombres de campo sacados de la fuente, asi que no
# hay a quien atar: no se puede inventar un campo que no se tipea. La misma
# atadura, para el unico campo que el modelo SI escribe, quedo adentro de
# `esquemas()`, que es su unico uso.
# LAS OCHO QUE EL MODELO YA NO VE (FICHA 06, 23-ago-2026). No se borran: no se
# saca capacidad. Siguen en `_MOLDES` y en `_CUERPOS`, se validan igual y las
# llama el CODIGO desde `hub_venta._derivar_las_busquedas`, que las deriva de lo
# que el modelo declaro. Lo que se saca es la ELECCION: el modelo declara, el
# codigo busca. En el 57% de los turnos declaraba una cosa y buscaba otra, y esa
# distancia era todo lo que el reconciliador tenia para reclamar.
_VISIBLES = ("registrar_pedido",)


def esquemas(tienda_id: str) -> list[dict]:
    """EL MOLDE UNICO que ve el modelo, con los ENUMS de la fuente viva
    inyectados. La atadura que queda es la que impide nombrar una categoria que
    no vendemos o un campo que la ficha no tiene; el tema se nombra libre y lo
    certifica `certificar_temas` contra las señas de la fuente."""
    from app.storage.firestore_client import get_categories
    from app.core.filtros_catalogo import campos_filtrables, SIN_CAMPO
    cats = [str(c) for c in (get_categories(tienda_id=tienda_id) or [])]
    registro = campos_filtrables(tienda_id)
    fuera = []
    for nombre in _VISIBLES:
        modelo = _MOLDES[nombre]
        esq = _esquema_de(modelo)
        props = esq.get("properties") or {}
        items = (props.get("items") or {}).get("items") or {}
        if cats and "categoria" in (items.get("properties") or {}):
            items["properties"]["categoria"]["enum"] = cats
        campo = (((props.get("atributos") or {}).get("items") or {})
                 .get("properties") or {}).get("campo")
        if registro and isinstance(campo, dict):
            # LA ESCAPATORIA ENTRA AL ENUM, igual que en el filtro que murio con
            # `buscar_productos`: un enum cerrado sin salida no previene el
            # invento, lo fabrica, porque obliga a elegir el campo mas parecido
            # cuando ninguno sirve. Ver `filtros_catalogo.SIN_CAMPO`.
            campo["enum"] = list(registro) + [SIN_CAMPO]
            campo["description"] = (
                f"El campo exacto. Si ninguno sirve usa '{SIN_CAMPO}': NO "
                "elijas el mas parecido, sale como si la fuente hubiera "
                "contestado y no contesto.")
        fuera.append({"type": "function", "function": {
            "name": nombre,
            "description": (modelo.__doc__ or "").strip(),
            "parameters": esq}})
    return fuera


def _submodelo(anotacion):
    """El molde que hay ADENTRO de una anotacion, si lo hay. Se busca en
    profundidad porque el campo que rompio el turno del 9-ago se declara
    `list[PartePago] | None`: el submodelo esta a dos niveles, y una sola vuelta
    de `get_args` devuelve `list[PartePago]`, que no es un molde."""
    if isinstance(anotacion, type) and issubclass(anotacion, BaseModel):
        return anotacion
    for hijo in typing.get_args(anotacion) or ():
        hallado = _submodelo(hijo)
        if hallado is not None:
            return hallado
    return None


def _sin_nulos(modelo, datos):
    """EL NULL QUE EL MOLDE PEDIA Y DESPUES RECHAZABA (medido el 9-ago).

    La redaccion coloquial de la pregunta de Martin daba 8 sobre 100, tres
    corridas de tres, y no era la redaccion: `registrar_pedido` volvia
    `pedido_mal_formado` y el turno entero se caia sin cuenta, sin busqueda y
    sin la pregunta por el teclado. El motivo, textual del log:

        reparto_pago.0.medio -- Input should be 'transferencia',
        'mercado pago' or '' [input_value=None]

    El modelo habia hecho EXACTAMENTE lo que la descripcion del campo le pedia
    -"si no dijo con que medio paga cada parte, pone el medio en null"- y el
    tipo, que acepta la cadena vacia pero no el null, lo tiro. Un turno entero
    perdido por la distancia entre lo que el molde PIDE y lo que ACEPTA.

    LA REGLA, y vale para todos los moldes y para siempre: un campo que TIENE
    default no se rompe porque llegue null. Null ahi significa "no lo dije", y
    eso es justo lo que el default resuelve, asi que se saca la clave y el
    default hace su trabajo. Los campos que ya son `X | None` no se tocan: ahi
    el null es un valor legitimo y significa algo.

    Va en la puerta unica -`validar`- y no campo por campo, a proposito: un
    saneo repetido en quince moldes es la misma regla escrita en quince lados,
    que es la falla que este repo ya pago dos veces."""
    if not isinstance(datos, dict):
        return datos
    limpio = {}
    for clave, valor in datos.items():
        campo = getattr(modelo, "model_fields", {}).get(clave)
        if campo is None:
            limpio[clave] = valor
            continue
        # El default es lo que decide. `is_required()` es falso solo cuando el
        # campo tiene uno; si ademas ese default es None, el campo ya acepta
        # null por su cuenta y no hay nada que sanear.
        if valor is None:
            if not campo.is_required() and campo.get_default() is not None:
                continue
            limpio[clave] = None
            continue
        # Y hacia adentro: `reparto_pago` es una lista de PartePago, y el null
        # que rompio el turno vivia en el submodelo, no en el molde de arriba.
        anidado = _submodelo(campo.annotation)
        if anidado is not None:
            if isinstance(valor, list):
                valor = [_sin_nulos(anidado, v) for v in valor]
            else:
                valor = _sin_nulos(anidado, valor)
        limpio[clave] = valor
    return limpio
