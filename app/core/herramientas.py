"""
HERRAMIENTAS — lo UNICO que el modelo puede pedirle al codigo.

Reemplaza al interprete y al solver de fragmentos. Antes el modelo tenia que
traducir el mensaje a una taxonomia nuestra de veinte campos -intencion,
producto_resuelto, categorias, specs_preguntadas, criterio, destinos- y despues
componer la respuesta como fragmentos atados a enums. Dos andamios de LLM
alrededor de las funciones deterministas que son lo que de verdad sabe.

Aca no hay taxonomia. El modelo decide QUE BUSCAR y el codigo se lo trae. El
cuerpo de cada herramienta es una funcion que YA existia y estaba probada: el
certificador de identidad, la FAQ curada, la tabla de tarifas, la calculadora,
la tabla de compatibilidad. No se reescribio la logica, se le puso un molde
adelante.

LO QUE SIGUE ATADO, y es lo unico que hace falta atar:
  - la IDENTIDAD la decide `certificar_producto`, nunca el modelo (regla cero).
    Sus tres veredictos viajan tal cual: encontrado, ambiguo, no_encontrado.
    Con `ambiguo` el modelo esta obligado a preguntar; no puede elegir.
  - los enums de `categoria` y `tema` salen de la fuente viva, no de una lista
    escrita a mano: el modelo no puede nombrar una categoria que no vendemos ni
    un tema de politica que no existe.
  - la PLATA la calcula `armar_presupuesto` y vuelve como bloque ya renderizado,
    renglon por renglon. El modelo lo pega, no lo recompone.

Los moldes son Pydantic y el esquema que ve el modelo se GENERA de ellos: una
sola definicion. Si un molde cambia, el esquema cambia solo.
"""
import json
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

from app.logger import get_logger

log = get_logger(__name__)


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


# ── LOS MOLDES ───────────────────────────────────────────────────────────────
# Pydantic manda: valida y coacciona lo que el modelo devuelve. Un argumento
# fuera de molde no llega a la funcion, se descarta con su motivo.

class Filtro(BaseModel):
    """Una condicion estructurada sobre un campo real del catalogo."""
    campo: str = Field(
        description="El campo exacto de la lista. No inventes nombres.")
    operador: Literal["contiene", "no_contiene", "igual", "mayor",
                      "menor"] = Field(
        description="'contiene' para texto -color contiene blanco-. "
                    "'no_contiene' para lo que el cliente NO quiere -pais_"
                    "fabricacion no_contiene china, marca no_contiene "
                    "logitech-. 'igual' para un valor exacto. 'mayor' y "
                    "'menor' SOLO para campos numericos, e incluyen el borde: "
                    "menor 500 es hasta 500, y precio_ars menor 100000 es el "
                    "presupuesto maximo.")
    valor: str = Field(
        description="Lo que tiene que valer. Para numeros mandalo pelado: 500, "
                    "no '500 gramos'.")


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
                          "marca, que no se fabrique en un pais, que salga "
                          "menos de tanto-. No lo resuelvas leyendo las "
                          "descripciones: pedilo aca y el codigo filtra sobre "
                          "los 880.")
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
    operacion: Literal["contar", "mas_barato", "mas_caro", "valores",
                       "donde_se_cumple"] = Field(
        description="'contar' cuantos hay. 'mas_barato' y 'mas_caro' el de "
                    "todo el catalogo. 'valores' que valores distintos existen "
                    "de un campo, por ejemplo que marcas manejamos. "
                    "'donde_se_cumple' en que categorias SI se cumple del todo "
                    "lo que el cliente pide evitar.")
    campo: str | None = Field(
        None, description="Solo para 'valores': de que campo querés la lista.")
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
    medio: Literal["transferencia", "mercado pago"] = Field(
        description="Con que paga esta parte.")
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


class TomarPedido(BaseModel):
    """Se llama SOLO cuando el cliente decide comprar o pide los datos para
    pagar. Dispara la captura del pedido y la entrega del cobro."""
    motivo: Literal["decide_comprar", "pide_datos_de_pago"] = Field(
        description="Que hizo el cliente exactamente.")


class ItemDeclarado(BaseModel):
    que: str = Field(description="Que pidio, tal cual: 'auriculares', "
                                 "'la asus tuf f15', 'memoria ram'.")
    cantidad: int = Field(1, description="Cuantas unidades de eso.")
    # EL DESTINO VA PEGADO AL ITEM, no en una lista suelta al costado. Hasta el
    # 5-ago `destinos` viajaba aparte, sin ninguna atadura con los items, asi
    # que "un mouse a Cordoba y el otro a Concordia" NO SE PODIA DECLARAR: el
    # reconciliador veia "2 mouse" y "Cordoba, Concordia" sin saber cual iba a
    # donde, y por lo tanto un reparto mal hecho no lo podia detectar. Es la
    # familia mas grande de las preguntas de prueba.
    destino: str | None = Field(
        None, description="A donde va ESTE item, si el pedido se reparte entre "
                          "varios lugares. Si todo va a un solo lado, dejalo "
                          "vacio y usá `destinos`.")


class RegistrarPedido(BaseModel):
    """DECLARA lo que entendiste del mensaje ANTES de buscar. Llamala SIEMPRE
    que el cliente pida productos, precios, un presupuesto o un envio, junto
    con las demas herramientas y en la misma tanda. No busca nada: deja
    asentado que entendiste, y el sistema compara eso contra lo que pediste. Si
    lo que declaras y lo que buscas no coinciden, te lo va a devolver."""
    items: list[ItemDeclarado] = Field(
        description="Un renglon por cada cosa que el cliente quiere COTIZAR o "
                    "ver. Solo lo que pidio de verdad; si nombro algo al pasar "
                    "y no queda claro que lo quiera, no lo pongas aca: ponelo "
                    "en contradicciones.")
    restricciones: list[str] | None = Field(
        None, description="Condiciones que puso el cliente, tal cual las dijo: "
                          "['sin partes chinas'], ['hasta 100 mil'], ['que sea "
                          "inalambrico']. Vacio si no puso ninguna.")
    destinos: list[str] | None = Field(
        None, description="Todas las localidades de envio que nombro.")
    pide_precio: bool = Field(
        False, description="True si espera un numero: precio, total, cuanto "
                           "sale, presupuesto.")
    contradicciones: list[str] | None = Field(
        None, description="Lo que NO cierra en el mensaje y no podes resolver "
                          "vos sin elegir por el cliente: cantidades que no dan, "
                          "un producto nombrado en el envio que no esta en el "
                          "pedido, dos cosas incompatibles. Escribi cada una "
                          "como la duda concreta que le harias al cliente. Si "
                          "todo cierra, vacio.")


_MOLDES = {
    "registrar_pedido": RegistrarPedido,
    "buscar_productos": BuscarProductos,
    "consultar_catalogo": ConsultarCatalogo,
    "ficha_producto": FichaProducto,
    "consultar_temas": ConsultarTemas,
    "cotizar_envio": CotizarEnvio,
    "armar_presupuesto": ArmarPresupuesto,
    "ver_compatibilidad": VerCompatibilidad,
    "tomar_pedido": TomarPedido,
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


def _guia_de_temas(faq: dict, temas: list[str]) -> str:
    """QUE CUBRE CADA TEMA, en las palabras del cliente.

    Hasta el 3-ago el enum eran nombres pelados y el modelo tenia que adivinar
    la frontera entre `envios`, `envio_exterior`, `costo_envio` y `plazo_envio`.
    Elegir mal ahi no es un matiz: el bot afirma una politica que no es la que
    pregunto el cliente, que es la peor forma de alucinar porque suena bien y
    viene de la fuente.

    Esto lo cubria antes un ruteo determinista por keywords (`query_faq`), que
    murio con el camino atado. Las keywords SIGUEN en `faq.json` y los
    disparadores en `base_conocimiento.json`, escritos como los dice el cliente;
    ahora se los pasamos al modelo, que es quien elige. No es codigo nuevo: es
    usar el dato que ya estaba y nadie leia.

    La seña de cada tema sale de la fuente que lo define: keywords si es de la
    FAQ, disparadores si es de la base de conocimiento.

    SE ACLARAN LOS DE POLITICA, que es donde el error esta MEDIDO. Elegir mal
    entre `envios`, `envio_exterior`, `costo_envio` y `plazo_envio` hace que el
    bot afirme una politica que no es la que preguntaron. Los temas de criterio
    -`mouse`, `queja_enojo`, `objecion_precio`- no tienen esa frontera, nunca
    tuvieron guia y no hizo falta: el nombre alcanza. Describirlos igual costaba
    once mil caracteres de esquema, mas que las dos herramientas que esto
    reemplazo juntas, para repetir lo que el enum ya dice.

    Y SOLO SE NOMBRA AL QUE LLEVA SEÑA. El enum ya lista los ciento
    veintinueve; repetirlos aca abajo era pagarlos dos veces por llamada.
    """
    from app.core.guia_venta_prosa import disparadores_de
    partes = []
    for tema in temas:
        if tema not in faq:
            continue
        propias = set(_norm(tema).replace("_", " ").split())
        # Una seña que solo repite el nombre del tema no desempata nada.
        señas = [k for k in ((faq.get(tema, {}).get("keywords") or [])
                             + disparadores_de(tema))
                 if k and not set(_norm(k).split()) <= propias]
        if señas:
            partes.append(f"{tema} ({', '.join(dict.fromkeys(señas[:3]))})")
    return ("Los temas exactos de la lista, UNO POR CADA COSA que pregunto el "
            "cliente: si pregunto si hacen envio al exterior, cuanto tarda y "
            "cuanto sale, van los tres temas, no uno. Elegi SIEMPRE el mas "
            "especifico que cubra cada pregunta: si pregunta por el exterior es "
            "envio_exterior y no envios, si pregunta cuanto tarda es plazo_envio "
            "y no costo_envio. Que cubren los que se pisan: " + "; ".join(partes))


def temas_consultables(tienda_id: str) -> list[str]:
    """EL ENUM UNICO de temas: la FAQ y la base de conocimiento en UNA lista.

    Hasta el 4-ago eran dos enums en dos herramientas -`consultar_politica` con
    los cincuenta temas de la FAQ y `consultar_criterio` con los ciento seis de
    la base-, y VEINTISIETE nombres estaban en las dos. Para esos veintisiete el
    modelo tenia que adivinar cual de las dos mitades de la casa guardaba la
    respuesta, y cada mitad devolvia solo la suya: `descuento_transferencia` por
    politica trae el diez por ciento real, y por criterio trae una prosa sin un
    solo digito que literalmente dice que el numero lo trae la otra. Medido con
    el modelo vivo el 4-ago: ante "esta caro, me haces precio si llevo dos? y
    con transferencia cuanto queda" pidio el criterio, o sea la mitad que NO
    puede tener el porcentaje.

    Eso no era un error del modelo: era pedirle que aprendiera nuestro
    archivero. Un tema es un tema; de que archivo sale es asunto del codigo."""
    from app.storage.firestore_client import get_all_faq
    from app.core.guia_venta_prosa import temas as temas_criterio
    faq = get_all_faq(tienda_id=tienda_id) or {}
    # Los temas de criterio incluyen los que solo tienen MOVIDA -queja,
    # despedida, postergacion-: sin ellos en el enum el modelo no puede pedir
    # lo unico que la fuente escribio para esas situaciones.
    return sorted(set(faq.keys()) | set(temas_criterio()))


def _atar_filtros(prop: dict, tienda_id: str) -> None:
    """El enum de `campo` SALE DEL CATALOGO VIVO, igual que `categoria` y que
    `temas`. Sin esto el modelo inventa nombres de campo -`peso`, `garantia`,
    `medidas`- que la fuente no tiene, y el filtro no filtra nada en silencio.

    Se le dice ademas cuales son numericos: es el unico dato que no se puede
    deducir del nombre y sin el pide `mayor` sobre `color`."""
    from app.core.filtros_catalogo import campos_filtrables
    registro = campos_filtrables(tienda_id)
    if not registro:
        return
    items = prop.get("items")
    if not isinstance(items, dict):
        return
    campo = (items.get("properties") or {}).get("campo")
    if not isinstance(campo, dict):
        return
    campo["enum"] = list(registro)
    numericos = [c for c, t in registro.items() if t == "numero"]
    if numericos:
        campo["description"] = (
            "El campo exacto de la lista. Numericos, los unicos que aceptan "
            "mayor y menor: " + ", ".join(numericos) + ". El resto es texto y "
            "va con contiene.")


def esquemas(tienda_id: str) -> list[dict]:
    """Los esquemas de las herramientas, en formato function calling, con los
    ENUMS de la fuente viva inyectados. Es la unica atadura que queda del lado
    del modelo: no puede pedir una categoria que no vendemos ni un tema que no
    existe."""
    from app.storage.firestore_client import get_categories, get_all_faq
    cats = [str(c) for c in (get_categories(tienda_id=tienda_id) or [])]
    faq = get_all_faq(tienda_id=tienda_id) or {}
    temas = temas_consultables(tienda_id)
    fuera = []
    for nombre, modelo in _MOLDES.items():
        esq = _esquema_de(modelo)
        props = esq.get("properties") or {}
        if nombre == "buscar_productos" and cats and "categoria" in props:
            props["categoria"]["enum"] = cats
        if nombre == "buscar_productos" and "filtros" in props:
            _atar_filtros(props["filtros"], tienda_id)
        if nombre == "buscar_productos" and "ordenar_por" in props:
            # MISMA ATADURA que los campos de condicion, y por el mismo motivo:
            # el enum sale de la fuente viva. `fuente_producto.ordenar_por` y
            # `atributos_ordenables` estaban escritos desde el interprete que
            # murio el 1-ago y ninguna herramienta los exponia, asi que "el mas
            # liviano" no tenia como llegar al codigo con el dato cargado.
            from app.core.filtros_catalogo import campos_filtrables
            reg = campos_filtrables(tienda_id)
            if reg:
                props["ordenar_por"]["enum"] = list(reg)
        if nombre == "consultar_catalogo" and "filtros" in props:
            _atar_filtros(props["filtros"], tienda_id)
        if nombre == "consultar_catalogo":
            # MISMA ATADURA que buscar_productos: los campos y las categorias
            # salen de la fuente viva, asi que el agregado no puede contar sobre
            # una columna ni un rubro que no existe.
            if cats and "categoria" in props:
                props["categoria"]["enum"] = cats
            from app.core.filtros_catalogo import campos_filtrables
            reg = campos_filtrables(tienda_id)
            if reg and "campo" in props:
                props["campo"]["enum"] = list(reg)
        if nombre == "consultar_temas" and temas and "temas" in props:
            props["temas"]["items"] = {"type": "string", "enum": temas}
            props["temas"]["description"] = _guia_de_temas(faq, temas)
        fuera.append({"type": "function", "function": {
            "name": nombre,
            "description": (modelo.__doc__ or "").strip(),
            "parameters": esq}})
    return fuera


def validar(nombre: str, args: dict):
    """Coaccion Pydantic de los argumentos que devolvio el modelo. Devuelve el
    objeto validado, o None con el motivo logueado: un argumento fuera de molde
    no entra a una funcion que toca plata."""
    modelo = _MOLDES.get(nombre)
    if modelo is None:
        return None
    try:
        return modelo(**(args if isinstance(args, dict) else {}))
    except Exception as e:
        log.warning("herramienta_args_invalidos", herramienta=nombre,
                    error=str(e)[:160])
        return None


# ── FICHA: lo que el modelo ve de un producto ────────────────────────────────
# LOS CAMPOS QUE EL MODELO VE DE CADA PRODUCTO. Tienen que llamarse EXACTAMENTE
# como en la fuente: el `if prod.get(k)` de `_ficha` descarta en silencio un
# nombre que no existe, asi que un campo mal escrito no se nota nunca.
#
# 3-ago-2026: habia tres nombres INVENTADOS que no traian nada -"garantia",
# "medidas" y "caracteristicas"-. En la fuente se llaman garantia_meses,
# dimensiones y caracteristicas_extra. Se corrigieron y se sumaron color y
# peso_gramos, que existian en el catalogo y no llegaban estructurados: su
# contenido viajaba suelto adentro de la prosa de `descripcion`, o sea el modelo
# no podia compararlos entre productos.
#
# NO entran a proposito: `tags` son terminos de busqueda internos, no info para
# el cliente; y `descripcion_rica` es identica a `descripcion` -medido, mismos
# 161 caracteres-, asi que solo duplicaria tokens.
_CAMPOS_FICHA = ("id", "nombre", "categoria", "marca", "modelo", "precio_ars",
                 "stock", "origen", "material", "color", "peso_gramos",
                 "dimensiones", "garantia_meses", "garantia_detalle",
                 "contenido_caja", "uso_recomendado", "caracteristicas_extra",
                 "descripcion", "specs")


def _money(n) -> str:
    try:
        return f"${int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return ""


def _ficha(prod: dict, tienda_id: str | None = None) -> dict:
    """El producto tal como lo ve el modelo. Sale entero de la fuente: precio,
    stock y specs no se resumen ni se redondean.

    El precio viaja YA ESCRITO ademas de como numero. Sin eso el modelo lo
    redacta a su manera -"8500 ARS", "6500 pesos", medido en la primera corrida
    viva- y ademas de quedar feo se escapa de la regla de plata, que busca el
    signo. Se le da escrito y se le pide que lo copie."""
    if not isinstance(prod, dict):
        return {}
    out = {k: prod[k] for k in _CAMPOS_FICHA
           if prod.get(k) not in (None, "", [], {})}
    if isinstance(prod.get("precio_ars"), (int, float)):
        out["precio"] = _money(prod["precio_ars"])
    try:
        from app.core.compatibilidad import compat_de, etiqueta_plataforma
        c = compat_de(prod, tienda_id) or {}
        sirve = [etiqueta_plataforma(p, tienda_id)
                 for p in (c.get("plataformas") or [])]
        if sirve:
            out["sirve_para"] = sirve
    except Exception as e:
        log.warning("ficha_compat_error", error=str(e)[:120])
    return out


def _categorias_donde_se_cumple(filtros: list, tienda_id: str,
                                salvo: str | None = None) -> list[str]:
    """EL AGREGADO. En que categorias del catalogo SI se cumplen del todo las
    condiciones que el cliente puso.

    Por que existe (4-ago-2026). "Tenes algo sin China?" es una pregunta sobre
    los 880, no una busqueda: no la resuelve traer seis productos ni mandarle el
    catalogo al modelo. La calcula el codigo, exacta, en milisegundos y sin un
    solo token. La respuesta real es 86 con stock, y el bot en produccion
    contesto que no tenia ninguno. Nunca se lo habiamos pedido al codigo, asi
    que el modelo relleno el hueco inventando un universal.

    5-ago: corre sobre las CONDICIONES generales, no sobre el viejo `excluir`.
    """
    from app.storage.firestore_client import get_all_products
    from app.core import filtros_catalogo as FC
    if not filtros:
        return []
    n = len(filtros)
    cats: dict[str, int] = {}
    for p in (get_all_products(tienda_id=tienda_id) or []):
        if (p.get("stock") or 0) <= 0:
            continue
        if FC.cuantos_cumple(p, filtros, tienda_id) < n:
            continue
        cat = str(p.get("categoria") or "").strip()
        if cat and _norm(cat) != _norm(salvo):
            cats[cat] = cats.get(cat, 0) + 1
    # Solo las que tienen surtido de verdad: ofrecer un rubro con un producto
    # suelto no es una alternativa comercial, es un consuelo.
    return sorted(c for c, n_ in cats.items() if n_ >= 3)


# ── LOS CUERPOS ──────────────────────────────────────────────────────────────
def cuantos_pedidos(a: BuscarProductos) -> int:
    return max(1, min(int(a.cuantos or 3), 6))


def buscar_productos(a: BuscarProductos, tienda_id: str) -> dict:
    """Identidad y catalogo. El veredicto lo da el CODIGO, siempre."""
    from app.storage.firestore_client import get_all_products
    from app.core.pedido_helpers import certificar_producto
    from app.core.guia_compra import categoria_no_vendida

    catalogo = get_all_products(tienda_id=tienda_id) or []
    pedido_txt = a.descripcion or a.categoria or ""

    # CERTIFICADOR DE RUBRO: lo que no vendemos lo dice el codigo desde
    # no_vendidas.json, no el modelo. El "no" honesto no puede depender de que
    # al modelo se le ocurra decirlo.
    try:
        cnv = categoria_no_vendida(pedido_txt, tienda_id)
    except Exception:
        cnv = None
    if cnv:
        pedida, alt = cnv
        alternativas = []
        if alt:
            from app.core.guia_pedido import opciones_por_categoria
            alternativas = [_ficha(p, tienda_id)
                            for p in opciones_por_categoria(alt, tienda_id, k=3)]
        return {"estado": "no_vendemos", "pedido": pedida,
                "rubro_real": "tecnologia e informatica",
                "alternativa": alt or None, "productos": alternativas}

    prods: list[dict] = []
    if a.descripcion:
        veredicto, hits = certificar_producto(a.descripcion, catalogo)
        if veredicto == "ambiguous":
            vistos, opciones = set(), []
            for p in hits:
                clave = (_norm(p.get("marca")), _norm(p.get("modelo")))
                if clave in vistos:
                    continue
                vistos.add(clave)
                opciones.append(_ficha(p, tienda_id))
            return {"estado": "ambiguo", "productos": opciones[:6],
                    "instruccion": "Hay varios modelos distintos. Preguntale "
                                   "cual quiere. No elijas vos."}
        if veredicto == "exists":
            prods = hits
        elif not a.categoria:
            # NO ENCONTRADO NO ES "NO VENDEMOS ESO". Si la descripcion nombra
            # una categoria que SI tenemos -"memoria ram de 16gb", y las
            # nuestras son de 8- se devuelven las reales de esa categoria. Sin
            # esto el modelo generaliza el no: medido el 1-ago, ante "tenes
            # memoria ram de 16gb" contesto "no estamos vendiendo modulos de
            # RAM sueltos", con el catalogo lleno de memorias.
            alternativas = []
            try:
                from app.core.guia_pedido import (categorias_nombradas,
                                                  opciones_por_categoria)
                for cat in (categorias_nombradas(a.descripcion, tienda_id)
                            or [])[:1]:
                    alternativas = [_ficha(p, tienda_id) for p in
                                    opciones_por_categoria(cat, tienda_id, k=3)]
            except Exception as e:
                log.warning("buscar_alternativas_error", error=str(e)[:120])
            if alternativas:
                return {"estado": "no_encontrado", "buscado": a.descripcion,
                        "hay_en_la_categoria": alternativas,
                        "instruccion": "Ese exacto no lo tenemos, pero la "
                                       "categoria SI la vendemos. Decile que "
                                       "eso puntual no, y mostrale estas que si "
                                       "tenemos. NO digas que no vendemos el "
                                       "rubro."}
            # LA SALIDA MUDA ERA EL GENERADOR DE MURO. Este era el unico de los
            # estados de salida que volvia SIN instruccion, sin cuantos habia y
            # sin alternativa: el modelo recibia "no_encontrado" pelado y de ahi
            # generalizaba al catalogo entero. Medido el 5-ago con "un regalo
            # para mi viejo que labura en el campo": estado no_encontrado,
            # instruccion False, nada mas.
            #
            # No se inventa un candidato: se le da al modelo con QUE preguntar.
            from app.storage.firestore_client import get_categories
            return {"estado": "no_encontrado", "buscado": a.descripcion,
                    "categorias_que_vendemos": [
                        str(c) for c in (get_categories(tienda_id=tienda_id)
                                         or [])],
                    "instruccion": "No se pudo identificar un producto con eso. "
                                   "NO digas que no tenemos nada ni afirmes "
                                   "nada sobre el catalogo entero: lo que pasa "
                                   "es que la descripcion no alcanza para "
                                   "elegir. Preguntale lo minimo que te falta "
                                   "para poder buscar, o proponele un rubro de "
                                   "`categorias_que_vendemos` que le pueda "
                                   "servir y confirmá con él antes de seguir."}

    if not prods:
        cat = _norm(a.categoria)
        prods = [p for p in catalogo if _norm(p.get("categoria")) == cat]

    prods = [p for p in prods
             if isinstance(p.get("precio_ars"), (int, float))
             and (p.get("stock") or 0) > 0]
    # Sin nada de entrada el veredicto es no_encontrado y se corta aca. Si se
    # siguiera, un tope de presupuesto sobre una lista vacia devolvia
    # "nada_dentro_del_presupuesto" SIN alternativas, que le hace decir al
    # modelo que es cuestion de plata cuando en realidad no tenemos el rubro.
    if not prods:
        return {"estado": "no_encontrado", "buscado": pedido_txt}
    # ── UNA SOLA PUERTA: condiciones, degradacion, orden ────────────────
    # Antes habia TRES bloques aca -excluir, tope_precio y filtros-, cada uno
    # con su propio estado de salida y su propia instruccion escrita a mano.
    # Cuatro contratos distintos que el modelo tenia que aprender por separado,
    # y cada arreglo habia que hacerlo cuatro veces. Ahora es uno.
    from app.core import filtros_catalogo as FC
    filtrado = None
    empatados = 0
    if a.filtros:
        filtrado = FC.aplicar(prods, a.filtros, tienda_id)
        if filtrado["descartados"]:
            log.warning("filtros_descartados", trace=[
                d["motivo"] for d in filtrado["descartados"]][:3])
        if not filtrado["productos"]:
            # NINGUNA HERRAMIENTA DEVUELVE VACIO (Martin, 2-ago). Un conjunto
            # de condiciones que no deja nada casi nunca significa que no
            # tenemos el producto: significa que ESA condicion no se cumple.
            #
            # EL CASO QUE LO PARIO: "las menos partes chinas posibles" sobre un
            # catalogo donde los 46 auriculares, los 52 mouse y las 96 memorias
            # se fabrican en China. Cero chino no existe; MENOS chino si, y es
            # lo que el cliente pidio. "Lo que menos X tenga" no es un filtro,
            # es un RANKING: presupone que todo tiene algo y pide el minimo.
            # Filtrar da cero y de ahi nace el muro; ordenar siempre devuelve un
            # primero y nunca puede producirlo.
            #
            # 5-AGO, LO QUE SE AGREGA: el EMPATE se dice. Medido, 19 mouse
            # estaban igual de lejos y el codigo devolvia tres arbitrarios como
            # si fueran "los menos chinos". Ahora vuelve `empatados` y el
            # criterio de desempate, para que el modelo pueda ser honesto en
            # vez de inventar un orden que la fuente no tiene.
            cercanos, empatados, faltan = FC.rankear_por_cercania(
                prods, a.filtros, tienda_id)
            fichas = []
            for p in cercanos[:max(3, cuantos_pedidos(a))]:
                f = _ficha(p, tienda_id)
                f["no_cumple"] = FC.incumplidos(p, a.filtros, tienda_id)
                fichas.append(f)
            return {"estado": "ninguno_cumple_del_todo",
                    "condiciones": filtrado["aplicados"],
                    "condiciones_no_aplicadas": filtrado["descartados"] or None,
                    "categoria": a.categoria,
                    "productos": fichas,
                    "empatados_igual_de_cerca": empatados,
                    "desempate": "entre los que estan igual de cerca, primero "
                                 "el mas barato",
                    "cuantas_condiciones_incumple_el_mejor": faltan,
                    "donde_si_se_cumple": _categorias_donde_se_cumple(
                        a.filtros, tienda_id, a.categoria),
                    "instruccion": "NINGUNO cumple todas las condiciones, pero "
                                   "estos son los que MENOS se alejan, en "
                                   "orden: arranca por ellos, no por un no. No "
                                   "digas que no tenemos el producto: tenemos "
                                   "estos, que es lo mas parecido. "
                                   "Decile cual condicion es la que no se "
                                   "cumple, esta en `no_cumple` de cada uno. Si "
                                   "`empatados_igual_de_cerca` es mayor que los "
                                   "que ves, decilo: estan TODOS igual de "
                                   "lejos y no hay uno mejor, se te muestran "
                                   "los mas baratos de ese grupo. No inventes "
                                   "un orden que la ficha no respalda. "
                                   "PROHIBIDO afirmar nada sobre el catalogo "
                                   "entero: viste unos pocos productos, no los "
                                   "880. Si `donde_si_se_cumple` trae algo, "
                                   "ofrecelo como el rubro donde la condicion "
                                   "SI se cumple del todo. Despues preguntale "
                                   "si con eso avanza."}
        prods = filtrado["productos"]

    # EL ORDEN. Por el campo que pidio el cliente si pidio un extremo; si no,
    # por lo que MAS SE PARECE a lo que describio. El precio dejo de ser el
    # unico criterio que existia: medido el 5-ago, "notebook para diseño
    # grafico" devolvia las 3 mas baratas de 171 porque la descripcion se
    # descartaba entera.
    orden_usado = ""
    if a.ordenar_por and _norm(a.ordenar_por) in FC.campos_filtrables(tienda_id):
        prods = FC.ordenar(prods, _norm(a.ordenar_por), a.direccion, tienda_id)
        orden_usado = f"{_norm(a.ordenar_por)} {a.direccion}"
    elif a.descripcion:
        # El peso por rareza se calcula sobre los CANDIDATOS de esta consulta,
        # no sobre el catalogo entero: dentro de una categoria, la palabra del
        # rubro no separa nada y la que el cliente agrego es la que elige.
        raras = FC.pesos_por_rareza(prods, a.descripcion)
        puntuados = [(FC.relevancia(p, a.descripcion, raras), p["precio_ars"], p)
                     for p in prods]
        if any(s > 0 for s, _, _ in puntuados):
            puntuados.sort(key=lambda t: (-t[0], t[1]))
            prods = [p for _, _, p in puntuados]
            orden_usado = "lo que mas se parece a lo que pidio"
    if not orden_usado:
        prods = sorted(prods, key=lambda p: p["precio_ars"])
        orden_usado = "precio, del mas barato al mas caro"

    if not prods:
        return {"estado": "no_encontrado", "buscado": pedido_txt}
    cuantos = cuantos_pedidos(a)
    salida = {"estado": "encontrado", "hay_en_total": len(prods),
              "ordenados_por": orden_usado,
              "productos": [_ficha(p, tienda_id) for p in prods[:cuantos]]}
    if filtrado:
        # QUE SE FILTRO Y QUE NO, dicho. Sin esto el modelo no puede saber que
        # una condicion se cayo -campo inexistente, operador imposible- y
        # presenta como filtrada una lista que no lo esta.
        salida["condiciones_aplicadas"] = filtrado["aplicados"]
        if filtrado["descartados"]:
            salida["condiciones_no_aplicadas"] = filtrado["descartados"]
            salida["instruccion"] = (
                "OJO: esas condiciones NO se pudieron aplicar. No digas que "
                "los productos las cumplen. Si hace falta, preguntale.")
        if filtrado["sin_dato"]:
            salida["sin_dato_en_la_ficha"] = filtrado["sin_dato"]
    return salida


def consultar_catalogo(a: ConsultarCatalogo, tienda_id: str) -> dict:
    """EL AGREGADO SOBRE LOS 880. La clase de pregunta que el modelo no podia
    ni formular, y por eso la inventaba.

    Medido el 4-ago en produccion: ante "las menos partes chinas posibles" el
    bot contesto "no tengo productos que no sean fabricados en China". Es FALSO
    -91 de los 880 no tienen China, los 72 de almacenamiento externo y los 19
    procesadores- y no habia forma de que lo supiera: `buscar_productos` le
    trae seis productos de UNA categoria, nunca el universo. El unico modo de
    llenar ese hueco era inventarlo.

    ESCALA A CUALQUIER CATALOGO, y es lo que la hace viable: contar sobre 5.000
    productos cuesta lo mismo que sobre 880 y NO gasta un solo token, porque lo
    resuelve el codigo y al modelo le vuelve un numero. La alternativa -mandarle
    el catalogo al modelo- se cae con el tamaño; esta no.

    No trae logica nueva: reusa el registro de campos y las condiciones de
    `filtros_catalogo`, las MISMAS que usa `buscar_productos`. Una sola forma de
    decir una condicion en todo el sistema.
    """
    from app.storage.firestore_client import get_all_products
    from app.core import filtros_catalogo as FC

    todos = get_all_products(tienda_id=tienda_id) or []
    prods = [p for p in todos if (p.get("stock") or 0) > 0]
    if a.categoria:
        cat = _norm(a.categoria)
        prods = [p for p in prods if _norm(p.get("categoria")) == cat]
    descartadas = []
    if a.filtros:
        res = FC.aplicar(prods, a.filtros, tienda_id)
        prods = res["productos"]
        descartadas = res["descartados"]

    total = len(prods)
    if a.operacion == "contar":
        out = {"estado": "ok", "cuantos": total,
               "de_un_total_de": len(todos), "categoria": a.categoria}
        if descartadas:
            # Una condicion que no se pudo aplicar cambia el numero. Si no se
            # dice, el modelo presenta como filtrada una cuenta que no lo esta.
            out["condiciones_no_aplicadas"] = descartadas
            out["instruccion"] = ("Esa condicion NO se pudo aplicar, asi que "
                                  "el numero NO la tiene en cuenta. No lo "
                                  "presentes como si la cumpliera.")
        return out

    if a.operacion in ("mas_barato", "mas_caro"):
        conp = [p for p in prods if isinstance(p.get("precio_ars"), (int, float))]
        if not conp:
            return {"estado": "sin_resultados", "cuantos": 0}
        p = (min if a.operacion == "mas_barato" else max)(
            conp, key=lambda x: x["precio_ars"])
        return {"estado": "ok", "cuantos": total,
                "producto": _ficha(p, tienda_id)}

    if a.operacion == "valores":
        campo = _norm(a.campo)
        if campo not in FC.campos_filtrables(tienda_id):
            return {"estado": "campo_desconocido", "campo": a.campo}
        vistos: dict[str, int] = {}
        for p in prods:
            v = FC._valor_crudo(p, campo)
            if v in (None, "", [], {}):
                continue
            vistos[str(v)] = vistos.get(str(v), 0) + 1
        orden = sorted(vistos.items(), key=lambda t: -t[1])
        return {"estado": "ok", "campo": campo, "cuantos_distintos": len(orden),
                "valores": [{"valor": v, "productos": n} for v, n in orden[:25]]}

    # donde_se_cumple: en que categorias la condicion se cumple DEL TODO. Se
    # descarta la categoria ya consultada -no se le ofrece al cliente el mismo
    # rubro del que se le acaba de decir que no cumple- y los rubros con menos
    # de tres, que no son una alternativa comercial sino un consuelo.
    cats: dict[str, int] = {}
    for p in prods:
        c = str(p.get("categoria") or "").strip()
        if c and _norm(c) != _norm(a.categoria):
            cats[c] = cats.get(c, 0) + 1
    return {"estado": "ok", "cuantos": total,
            "categorias": sorted(c for c, n in cats.items() if n >= 3),
            "instruccion": "Estas son las categorias donde la condicion SI se "
                           "cumple del todo. Si la lista viene vacia, decilo "
                           "acotado a lo que consultaste; NUNCA generalices a "
                           "todo el catalogo."}


def ficha_producto(a: FichaProducto, tienda_id: str) -> dict:
    from app.storage.firestore_client import get_product_by_id
    p = get_product_by_id(str(a.product_id).upper(), tienda_id=tienda_id)
    if not p:
        return {"estado": "no_encontrado", "product_id": a.product_id}
    return {"estado": "encontrado", "producto": _ficha(p, tienda_id)}


def _politica_de(tema: str, tienda_id: str) -> dict:
    """La politica de la tienda con sus numeros REALES ya puestos. El texto es
    el que escribio Martin; los huecos los rellena el codigo desde los valores
    estructurados del mismo tema."""
    from app.storage.firestore_client import get_all_faq
    from app.core.curadas import estampar_valores
    data = (get_all_faq(tienda_id=tienda_id) or {}).get(tema)
    if not data:
        return {}
    texto = str(data.get("respuesta_curada") or "").strip()
    estampada = estampar_valores(texto, data) if texto else None
    politica = estampada or str(data.get("respuesta") or "")
    if not politica.strip():
        return {}
    return {"politica": politica, "valores": data.get("valores") or []}


def _criterio_de(tema: str) -> dict:
    """El criterio y la movida que la fuente tiene escritos para ESE tema:
      - `criterio`: desde donde razonar. Para que sirve, que conviene segun el
        uso, como se comparan.
      - `objetivo` / `movida` / `escape`: como se conduce esa situacion de
        venta. Que se busca, como se arma el mensaje, y cuando NO se usa.

    SOLO match exacto, a proposito. `consultar_guia_venta` tambien matchea
    aproximado, y sobre el enum unido eso trae criterio de OTRO tema: medido el
    4-ago, `especificaciones` caia en `verificacion_pagos`, `fabricacion` en
    `ubicacion` y `formas_contacto` en `formas_pago`. Un criterio del tema
    equivocado es peor que ninguno, porque suena fundado."""
    from app.core.guia_venta_prosa import consultar_guia_venta
    r = consultar_guia_venta(tema) or {}
    if r.get("id") != tema:
        return {}
    fuera = {k: r[k] for k in ("objetivo", "movida", "escape") if r.get(k)}
    if r.get("texto"):
        fuera["criterio"] = r["texto"]
    return fuera


def consultar_temas(a: ConsultarTemas, tienda_id: str) -> dict:
    """LO QUE LA CASA TIENE ESCRITO SOBRE CADA TEMA, entero y de una.

    Reemplaza a `consultar_politica` y `consultar_criterio`, que eran dos
    puertas al mismo cuarto: veintisiete temas estaban en los dos enums y cada
    herramienta devolvia solo su mitad, asi que el modelo elegia un area y
    contestaba con la mitad que le habia tocado. Aca el tema es uno y vuelve
    completo: la politica con sus numeros y el criterio con la movida, lo que
    exista de cada uno.

    Recibe VARIOS temas porque las preguntas vienen de a varias. Con un tema por
    llamada el modelo pedia uno solo y contestaba una de las tres cosas que le
    preguntaron: medido el 4-ago con "hacen envios al exterior? cuanto tarda a
    uruguay y cuanto sale", pidio `envio_exterior` y nada mas."""
    pedidos = list(dict.fromkeys(
        str(t).strip() for t in (a.temas or []) if str(t).strip()))
    if not pedidos:
        return {"estado": "sin_tema"}
    # El tope existe para que un modelo desbocado no vuelque media fuente en el
    # contexto, pero CORTAR EN SILENCIO es peor que el problema que evita: es la
    # misma leccion que dejo `_ejecutar_en_paralelo` el 1-ago. Si se corta, se dice.
    if len(pedidos) > 6:
        log.warning("consultar_temas_recortado", pidio=len(pedidos),
                    descartados=pedidos[6:])
    fuera = []
    for tema in pedidos[:6]:
        datos = {**_politica_de(tema, tienda_id), **_criterio_de(tema)}
        if datos:
            fuera.append({"tema": tema, "estado": "encontrado", **datos})
        else:
            fuera.append({"tema": tema, "estado": "no_encontrado",
                          "instruccion": "No hay nada escrito sobre eso. "
                                         "Razona desde la ficha del producto o "
                                         "decilo honesto; no lo completes de "
                                         "memoria."})
    return {"estado": "ok", "temas": fuera}


def cotizar_envio(a: CotizarEnvio, tienda_id: str) -> dict:
    from app.core import calculadora as T
    r = T.cotizar_envio(localidad=a.localidad)
    r.pop("mensaje_para_llm", None)
    # Todas las herramientas contestan con `estado`: la regla 3 del prompt se
    # apoya en eso, y sin el la traza mostraba `cotizar_envio -> None`, que no
    # dice si cotizo o si el destino no se entendio.
    r["estado"] = "ok" if r.get("ok") else "no_se_pudo"
    for clave in ("monto", "costo", "costo_ars"):
        if isinstance(r.get(clave), (int, float)):
            r["costo"] = _money(r[clave])
            break
    return r


def armar_presupuesto(a: ArmarPresupuesto, tienda_id: str) -> dict:
    """LA CUENTA. Cotiza cada destino y suma, y devuelve el presupuesto ya
    escrito renglon por renglon.

    Corre las cotizaciones y el total en el MISMO hilo a proposito: la
    calculadora lee las localidades cotizadas del turno por contextvar, y una
    escritura hecha en otro hilo no vuelve al que suma.
    """
    from app.core import calculadora as T
    items = [{"product_id": str(i.product_id).upper(), "cantidad": max(1, i.cantidad)}
             for i in (a.items or [])]
    if not items:
        return {"estado": "sin_items"}

    destinos = [d for d in (a.destinos or []) if str(d or "").strip()]
    # Un destino por item si el modelo lo repartio y no declaro la lista aparte.
    if not destinos:
        destinos = list(dict.fromkeys(
            [str(i.destino).strip() for i in a.items if i.destino]))
    envios = []
    for d in destinos:
        try:
            envios.append(T.cotizar_envio(localidad=d))
        except Exception as e:
            log.warning("presupuesto_envio_error", destino=d, error=str(e)[:120])

    extras = [{"faq_tema": "costo_envio", "concepto": "envio"}] if destinos else []
    pago = [{"medio": p.medio, "porcentaje": float(p.porcentaje)}
            for p in (a.pago or [])]
    r = T.calculate_total(items=items, items_extra=extras,
                          destinos=max(1, len(destinos)), pago=pago or None)
    if not r.get("ok"):
        return {"estado": "no_se_pudo", "motivo": r.get("mensaje_para_llm")}

    # EL REPARTO POR DESTINO. Solo sale si CIERRA contra los items: el modelo a
    # veces resuelve mal "el resto" y reparte mas unidades de las que hay.
    reparto = ""
    # CON UN SOLO DESTINO SE NOMBRA IGUAL. El bloque decia "Envio: $7.500" a
    # secas: el cliente daba la ciudad y la cuenta no se la confirmaba nunca,
    # asi que no tenia como saber si el numero era del destino que pidio. Con
    # varios destinos ya se nombraban; con uno, no. Medido el 5-ago, Serie 1.
    if len(destinos) == 1:
        reparto = f"Envio a {destinos[0]}."
    if len(destinos) > 1:
        por_destino: dict = {}
        for i in a.items:
            if i.destino:
                por_destino.setdefault(str(i.destino).strip(), []).append(i)
        repartidas = sum(max(1, i.cantidad) for i in a.items if i.destino)
        totales = sum(max(1, i.cantidad) for i in a.items)
        if por_destino and repartidas == totales:
            from app.storage.firestore_client import get_product_by_id
            lineas = []
            for dest, its in por_destino.items():
                nombres = []
                for i in its:
                    p = get_product_by_id(str(i.product_id).upper(),
                                          tienda_id=tienda_id) or {}
                    nombres.append(f"{max(1, i.cantidad)}x "
                                   f"{p.get('nombre', i.product_id)}")
                lineas.append(f"- A {dest}: " + ", ".join(nombres))
            reparto = "Reparto de los envios:\n" + "\n".join(lineas)
        else:
            log.warning("presupuesto_reparto_no_cierra",
                        repartidas=repartidas, totales=totales)

    bloque = r.get("presentacion") or ""
    if reparto:
        bloque = bloque + "\n\n" + reparto
    return {"estado": "ok", "bloque": bloque,
            "total_ars": r.get("total_final_ars") or r.get("total_ars"),
            "envios": [{"localidad": e.get("localidad") or e.get("zona"),
                        "costo": e.get("costo")} for e in envios],
            "detalle": r.get("detalle") or [],
            "proof": r.get("proof") or {}}


def ver_compatibilidad(a: VerCompatibilidad, tienda_id: str) -> dict:
    from app.storage.firestore_client import get_product_by_id
    from app.core.compatibilidad import (evaluar, plataformas_del_mensaje,
                                         etiqueta_plataforma)
    p = get_product_by_id(str(a.product_id).upper(), tienda_id=tienda_id)
    if not p:
        return {"estado": "no_encontrado", "product_id": a.product_id}

    # PRODUCTO CONTRA PRODUCTO. `compatibilidad.evaluar_par` cruza `requiere`
    # contra `provee` en las dos direcciones y estaba escrita, probada y SIN
    # NINGUNA PUERTA que la expusiera: la unica forma era contra plataforma
    # generica, asi que "tengo la Lenovo IdeaPad 3, que memoria le sirve" no
    # tenia como resolverse aunque las aristas estuvieran cargadas -`requiere`
    # en 388 de 482 filas, `provee` en 111-. Cazado el 5-ago por el banco.
    if a.contra_product_id:
        from app.core.compatibilidad import evaluar_par
        otro = get_product_by_id(str(a.contra_product_id).upper(),
                                 tienda_id=tienda_id)
        if not otro:
            return {"estado": "no_encontrado",
                    "product_id": a.contra_product_id}
        veredicto, motivo = evaluar_par(p, otro, tienda_id)
        return {"estado": "ok", "producto": p.get("nombre"),
                "contra": otro.get("nombre"),
                "compatibilidad": [{"equipo": otro.get("nombre"),
                                    "veredicto": veredicto, "motivo": motivo}],
                "instruccion": ("Si el veredicto es sin_dato, decile honesto "
                                "que no lo podes confirmar con la ficha. No "
                                "supongas que sirve porque son de la misma "
                                "categoria.")}

    plats = plataformas_del_mensaje(a.equipo or "", tienda_id)
    if not plats:
        return {"estado": "equipo_desconocido", "equipo": a.equipo,
                "producto": _ficha(p, tienda_id)}
    veredictos = []
    for pl in plats[:3]:
        # `evaluar` devuelve una TUPLA (veredicto, motivo), no un dict. Acá se
        # la leía como dict y la herramienta reventaba con AttributeError en
        # TODAS sus llamadas: el hub atrapaba la excepción, devolvía
        # {estado: error} y el modelo contestaba sin el dato de compatibilidad.
        # Se veía como que el bot "no supo", nunca como una herramienta rota,
        # porque ningún test tocaba las herramientas. Cazado el 5-ago por el
        # banco de candidatos; la prueba de humo de las nueve puertas queda en
        # `tests/test_puertas_humo.py` para que no pueda repetirse.
        veredicto, motivo = evaluar(p, pl, tienda_id)
        veredictos.append({"equipo": etiqueta_plataforma(pl, tienda_id),
                           "veredicto": veredicto, "motivo": motivo})
    return {"estado": "ok", "producto": p.get("nombre"),
            "compatibilidad": veredictos}


def tomar_pedido(a: TomarPedido, tienda_id: str) -> dict:
    """MARCA la decision para que el cierre corra, y cuando el cliente pide los
    datos para pagar los TRAE de la config de la tienda.

    Lo segundo nacio del peor error medido en el camino nuevo, charla viva del
    2-ago: el cliente pidio los datos para transferir sin presupuesto sobre la
    mesa, el cierre no los entrego -pide un total o un lead activo- y el modelo
    llenó el hueco INVENTANDO un CBU, un alias y un banco. Una plata a una
    cuenta que no existe. La leccion es la misma de siempre: si el dato no se le
    entrega, se lo inventa. Ahora se lo entrega la herramienta."""
    out = {"estado": "registrado", "motivo": a.motivo}
    if a.motivo != "pide_datos_de_pago":
        return out
    try:
        from app.core.pago import datos_transferencia
        d = datos_transferencia(tienda_id) or {}
        if d.get("cbu") or d.get("alias"):
            out["datos_de_pago"] = {
                "titular": d.get("titular_cuenta"), "banco": d.get("banco"),
                "cbu": d.get("cbu"), "alias": d.get("alias")}
            out["instruccion"] = ("Pasale ESTOS datos tal cual, sin cambiar un "
                                  "digito. No inventes ni completes ninguno.")
    except Exception as e:
        log.warning("tomar_pedido_cobro_error", error=str(e)[:120])
    return out


def registrar_pedido(a: RegistrarPedido, tienda_id: str) -> dict:
    """No busca nada: devuelve lo declarado para que el RECONCILIADOR lo compare
    contra lo que el plan efectivamente pidio. Es la unica herramienta que no
    toca la fuente, y existe porque hasta hoy no habia en el sistema NINGUNA
    estructura con lo que el cliente pidio, asi que nada podia compararla."""
    return {"estado": "registrado", "pedido": a.model_dump()}


_CUERPOS = {
    "registrar_pedido": registrar_pedido,
    "buscar_productos": buscar_productos,
    "consultar_catalogo": consultar_catalogo,
    "ficha_producto": ficha_producto,
    "consultar_temas": consultar_temas,
    "cotizar_envio": cotizar_envio,
    "armar_presupuesto": armar_presupuesto,
    "ver_compatibilidad": ver_compatibilidad,
    "tomar_pedido": tomar_pedido,
}


def ejecutar(nombre: str, args: dict, tienda_id: str) -> dict:
    """Corre UNA herramienta. Nunca levanta: un fallo vuelve como estado, para
    que el modelo lo cuente honesto en vez de que se caiga el turno."""
    cuerpo = _CUERPOS.get(nombre)
    if cuerpo is None:
        return {"estado": "herramienta_desconocida", "nombre": nombre}
    validado = validar(nombre, args)
    if validado is None:
        return {"estado": "pedido_mal_formado", "nombre": nombre}
    try:
        return cuerpo(validado, tienda_id)
    except Exception as e:
        log.warning("herramienta_error", herramienta=nombre,
                    error=f"{type(e).__name__}: {str(e)[:160]}")
        return {"estado": "error", "nombre": nombre}


# ── LA PLATA QUE QUEDO RESPALDADA ────────────────────────────────────────────
# Unidades que hacen que un numero NO sea plata. Sin esta lista, "1600 DPI",
# "3200 MHz" o "12 meses" se leerian como montos y la regla podaria una spec
# REAL: es el mismo error que en el camino viejo borraba respuestas en silencio.
_UNIDADES = (r"(?:dpi|hz|mhz|ghz|rpm|ms|mah|w|watts?|gb|tb|mb|kb|nits?|px|"
             r"pulgadas?|cm|mm|km|kg|gr|g|meses|mes|d[ií]as?|a[nñ]os|horas?|"
             r"unidades?|cuotas?|ohm|bits?)")

# PLATA en el texto. La primera version solo miraba el signo peso, y en la
# primera corrida viva el modelo escribio "8500 ARS" y "6500 pesos": plata que
# la regla no veia, o sea que una cifra inventada sin signo salia derecho al
# cliente. Cuatro formas, en orden: con signo, con la palabra, con separador de
# miles, y el numero pelado de cuatro a siete digitos que no lleve unidad
# detras ni sea un año.
_RE_PLATA = re.compile(
    r"\$\s?(\d[\d.]*)"
    r"|\b(\d[\d.]*)\s*(?:pesos|ars)\b"
    r"|\b(\d{1,3}(?:\.\d{3})+)\b"
    r"|\b(?!19\d\d\b|20\d\d\b)(\d{4,7})\b(?!\s*" + _UNIDADES + r")",
    re.IGNORECASE)


def _montos_del_texto(texto: str) -> list[int]:
    """Los montos que el texto escribe, sea como sea que los escriba."""
    fuera = []
    for m in _RE_PLATA.finditer(str(texto or "")):
        crudo = next((g for g in m.groups() if g), "")
        try:
            fuera.append(int(crudo.replace(".", "")))
        except ValueError:
            continue
    return fuera


def montos_respaldados(resultados: list[dict]) -> set[int]:
    """Todos los montos que las herramientas trajeron este turno. Es contra
    esto que se mide la prosa: un peso que no este aca no lo puso el codigo."""
    ok: set[int] = set()

    def _sumar(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)) and v >= 100:
            ok.add(int(v))
        elif isinstance(v, str):
            ok.update(_montos_del_texto(v))
        elif isinstance(v, dict):
            for x in v.values():
                _sumar(x)
        elif isinstance(v, list):
            for x in v:
                _sumar(x)

    for r in resultados or []:
        _sumar(r)
    return ok


def plata_inventada(texto: str, respaldados: set[int]) -> list[int]:
    """Los montos del texto que ninguna herramienta trajo. UNA regla, en vez de
    los once verificadores que se borraron: si el codigo no lo calculo, no sale.
    """
    return [n for n in _montos_del_texto(texto)
            if n >= 100 and n not in respaldados]


def contexto_json(llamadas: list[dict]) -> str:
    """El JSON que se le inyecta al modelo para redactar. Un bloque por
    herramienta con su nombre: un dict plano pisaria las claves entre
    herramientas y el no_encontrado de una taparia el resultado de otra."""
    return json.dumps(llamadas, ensure_ascii=False, default=str)[:14000]
