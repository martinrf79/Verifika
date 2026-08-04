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
    operador: Literal["contiene", "igual", "mayor", "menor"] = Field(
        description="'contiene' para texto -color contiene blanco-. 'igual' "
                    "para un valor exacto. 'mayor' y 'menor' SOLO para campos "
                    "numericos, e incluyen el borde: menor 500 es hasta 500.")
    valor: str = Field(
        description="Lo que tiene que valer. Para numeros mandalo pelado: 500, "
                    "no '500 gramos'.")


class BuscarProductos(BaseModel):
    """Busca productos en el catalogo real."""
    descripcion: str | None = Field(
        None, description="Como lo nombro el cliente, tal cual: 'la asus tuf "
                          "f15', 'un mouse gamer barato'. Vacio si solo pide "
                          "una categoria entera.")
    categoria: str | None = Field(
        None, description="Categoria del catalogo, si el cliente pidio un "
                          "rubro y no un modelo puntual.")
    orden: Literal["barato", "caro"] | None = Field(
        None, description="'barato' si pide lo mas economico, 'caro' si pide "
                          "lo mejor o mas premium.")
    tope_precio: int | None = Field(
        None, description="Presupuesto maximo en pesos, si lo dijo.")
    excluir: list[str] | None = Field(
        None, description="Marcas u origenes que el cliente NO quiere: "
                          "['china'], ['logitech']. Tal cual lo dijo.")
    filtros: list[Filtro] | None = Field(
        None, description="CONDICIONES CONCRETAS sobre los campos del "
                          "catalogo. Usalas SIEMPRE que el cliente pida un "
                          "atributo -que sea blanco, que pese menos de 500 "
                          "gramos, que tenga bluetooth, que sea resistente al "
                          "agua, que tenga dos anios de garantia-. No lo "
                          "resuelvas leyendo las descripciones: pedilo aca y "
                          "el codigo filtra sobre los 880.")
    cuantos: int = Field(3, description="Cuantas opciones traer, 1 a 6.")


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
    """Dice si un producto sirve para el equipo que tiene el cliente."""
    product_id: str = Field(description="Id del producto en duda.")
    equipo: str = Field(
        description="Lo que tiene el cliente, tal cual lo dijo: 'notebook', "
                    "'ps5', 'pc de escritorio'.")


class TomarPedido(BaseModel):
    """Se llama SOLO cuando el cliente decide comprar o pide los datos para
    pagar. Dispara la captura del pedido y la entrega del cobro."""
    motivo: Literal["decide_comprar", "pide_datos_de_pago"] = Field(
        description="Que hizo el cliente exactamente.")


class ItemDeclarado(BaseModel):
    que: str = Field(description="Que pidio, tal cual: 'auriculares', "
                                 "'la asus tuf f15', 'memoria ram'.")
    cantidad: int = Field(1, description="Cuantas unidades de eso.")


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


def _stems(valor: str) -> list[str]:
    """Raices por palabra. 'partes chinas' -> ['chin'], y filtra escriba como
    escriba el cliente. El corte por frase entera no matcheaba nunca."""
    return [w[:4] for w in _norm(valor).split() if len(w) >= 4]


def _grado(prod: dict, excluir: list[str]) -> int:
    """CUANTO incumple, no SI incumple. Sirve para ordenar cuando la exclusion
    vacia el resultado y hay que ofrecer lo que menos la incumple.

    La marca pesa mas que la fabricacion: una marca china fabricada en China
    esta mas lejos del pedido que una suiza fabricada en China. Y un origen que
    nombra alternativas -"Taiwan o China segun linea"- esta mas cerca que uno
    que dice China a secas, porque no siempre es del pais excluido.
    """
    marca, origen = _norm(prod.get("marca")), _norm(prod.get("origen"))
    nombre = _norm(prod.get("nombre"))
    g = 0
    for valor in (excluir or []):
        for s in _stems(valor):
            if s in marca:
                g += 3
            if s in nombre:
                g += 2
            if s in origen:
                g += 2
    if g and ("segun linea" in origen or " o " in origen):
        g -= 1
    return g


def _excluido(prod: dict, excluir: list[str]) -> bool:
    campos = " ".join([_norm(prod.get("marca")), _norm(prod.get("origen")),
                       _norm(prod.get("nombre"))])
    for valor in excluir:
        st = _stems(valor)
        if st and any(s in campos for s in st):
            return True
    return False


# ── LOS CUERPOS ──────────────────────────────────────────────────────────────
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
            return {"estado": "no_encontrado", "buscado": a.descripcion}

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
    if a.excluir:
        filtrados = [p for p in prods if not _excluido(p, a.excluir)]
        # Si la exclusion vacia el resultado se DICE, no se devuelve el mismo
        # listado como si nada: el 1-ago el cliente pidio menos partes chinas y
        # recibio identico presupuesto, sin una palabra de por que.
        if not filtrados:
            # NINGUNA HERRAMIENTA DEVUELVE VACIO (Martin, 2-ago). Antes esto
            # cortaba con "no tenemos nada" y era un MURO: verdad literal que
            # mata la venta. El caso real: "las menos partes chinas posibles"
            # sobre un catalogo donde los 46 auriculares, los 52 mouse y las 96
            # memorias se fabrican en China. Cero chino no existe; MENOS chino
            # si, y es lo que el cliente pidio. La condicion casi nunca es
            # binaria aunque el argumento lo sea, asi que el codigo devuelve
            # los que MENOS la incumplen, ordenados, y le dice al modelo que
            # sea honesto sobre el grado.
            cercanos = sorted(prods, key=lambda p: _grado(p, a.excluir))
            return {"estado": "ninguno_cumple_del_todo",
                    "excluido": a.excluir, "categoria": a.categoria,
                    "lo_que_menos_incumple": [_ficha(p, tienda_id)
                                              for p in cercanos[:3]],
                    "instruccion": "NINGUNO cumple esa condicion del todo, y "
                                   "hay que decirlo derecho, sin adornar. Pero "
                                   "no cierres con un no: mostrale estos, que "
                                   "son los que MENOS la incumplen, y explicale "
                                   "en una linea por que -mira el campo origen-. "
                                   "Despues preguntale si con eso avanza."}
        prods = filtrados
    if a.tope_precio:
        dentro = [p for p in prods if p["precio_ars"] <= a.tope_precio]
        if not dentro:
            baratos = sorted(prods, key=lambda p: p["precio_ars"])[:2]
            return {"estado": "nada_dentro_del_presupuesto",
                    "tope": a.tope_precio,
                    "lo_mas_cercano": [_ficha(p, tienda_id) for p in baratos]}
        prods = dentro

    # LOS FILTROS ESTRUCTURADOS. Van al final a proposito: primero la identidad
    # y el rubro, que los decide el codigo, y recien despues las condiciones
    # sobre los campos. Asi un filtro imposible no puede disfrazar de "no
    # tenemos eso" algo que en realidad si vendemos.
    filtrado = None
    if a.filtros:
        from app.core import filtros_catalogo as FC
        filtrado = FC.aplicar(prods, a.filtros, tienda_id)
        if filtrado["descartados"]:
            log.warning("filtros_descartados", trace=[
                d["motivo"] for d in filtrado["descartados"]][:3])
        if not filtrado["productos"]:
            # MISMA REGLA QUE `excluir` (Martin, 2-ago): ninguna herramienta
            # devuelve vacio. Un filtro que no deja nada casi nunca significa
            # que no tenemos el producto; significa que ESA condicion no se
            # cumple. Se devuelve lo que MAS condiciones cumple y se dice cual
            # falla, para que el modelo no cierre con un no que es mentira.
            cercanos = sorted(
                prods, key=lambda p: -FC.cuantos_cumple(p, a.filtros, tienda_id))
            return {"estado": "ninguno_cumple_del_todo",
                    "filtros_pedidos": filtrado["aplicados"],
                    "filtros_descartados": filtrado["descartados"] or None,
                    "lo_mas_parecido": [
                        {**_ficha(p, tienda_id),
                         "no_cumple": FC.incumplidos(p, a.filtros, tienda_id)}
                        for p in cercanos[:3]],
                    "instruccion": "NINGUNO cumple todas esas condiciones. "
                                   "Decilo derecho y decile CUAL condicion es "
                                   "la que no se cumple -esta en no_cumple de "
                                   "cada uno-. No digas que no tenemos el "
                                   "producto: tenemos estos, que es lo mas "
                                   "parecido. Si dice que la ficha no lo "
                                   "especifica, no afirmes ni que si ni que "
                                   "no. Despues preguntale si con eso avanza."}
        prods = filtrado["productos"]

    prods.sort(key=lambda p: p["precio_ars"], reverse=(a.orden == "caro"))
    if not prods:
        return {"estado": "no_encontrado", "buscado": pedido_txt}
    cuantos = max(1, min(int(a.cuantos or 3), 6))
    salida = {"estado": "encontrado",
              "productos": [_ficha(p, tienda_id) for p in prods[:cuantos]]}
    if filtrado:
        # QUE SE FILTRO Y QUE NO, dicho. Sin esto el modelo no puede saber que
        # una condicion se cayo -campo inexistente, operador imposible- y
        # presenta como filtrada una lista que no lo esta.
        salida["filtros_aplicados"] = filtrado["aplicados"]
        salida["hay_en_total"] = len(prods)
        if filtrado["descartados"]:
            salida["filtros_no_aplicados"] = filtrado["descartados"]
            salida["instruccion"] = (
                "OJO: esas condiciones NO se pudieron aplicar. No digas que "
                "los productos las cumplen. Si hace falta, preguntale.")
        if filtrado["sin_dato"]:
            salida["sin_dato_en_la_ficha"] = filtrado["sin_dato"]
    return salida


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
    plats = plataformas_del_mensaje(a.equipo, tienda_id)
    if not plats:
        return {"estado": "equipo_desconocido", "equipo": a.equipo,
                "producto": _ficha(p, tienda_id)}
    veredictos = []
    for pl in plats[:3]:
        v = evaluar(p, pl, tienda_id)
        veredictos.append({"equipo": etiqueta_plataforma(pl, tienda_id),
                           "veredicto": v.get("veredicto"),
                           "motivo": v.get("motivo")})
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
