"""
INDICE — el vocabulario UNICO del sistema.

QUE ES. Una sola lista de nombres compartida entre lo que el INTERPRETE puede
declarar y lo que la FUENTE sabe contestar. Cada nombre es una CELDA, y cada
celda trae con que se responde. Nada mas.

POR QUE NACE, medido el 30-jul sobre las 66 charlas grabadas, 282 turnos:

  - El interprete solo podia nombrar las 93 categorias de base_conocimiento.
  - La fuente contesta ademas 50 temas de FAQ, de los cuales **23 NO estaban en
    ese enum**: cuotas, envios, garantia_como_usar, devoluciones,
    marcas_originales, mayoristas y 17 mas.
  - O sea que ante "puedo pagar en cuotas?" el interprete NO TENIA COMO DECIRLO.
    Su schema se lo prohibia. El unico que ruteaba era un regex de palabras
    clave sobre el mensaje crudo.
  - Medido: en 107 de 282 turnos el tema de FAQ lo aportaba ESE regex, no el
    interprete. En 85 pasaba lo mismo con el criterio.

Esa es la causa de los 116 regex repartidos en app/core, y la razon por la que
no se pueden borrar por disciplina: no estaban de mas, estaban TAPANDO un
vocabulario que al interprete le faltaba. Dos listas de nombres para el mismo
eje -93 categorias y 50 temas, con 27 en comun- y el regex haciendo de puente.

Este modulo elimina el puente juntando las dos listas en una. Con el vocabulario
unificado, el interprete puede DECLARAR lo que antes solo el regex adivinaba, y
el regex se queda sin trabajo.

TRES TIPOS DE CELDA, y la distincion no es decorativa:
  - dato    : la respuesta esta escrita en la fuente. La estampa el codigo.
  - calculo : la respuesta es una funcion determinista de la fuente (total,
              envio, reparto). La celda guarda la calculadora, no el valor.
  - criterio: NO hay respuesta guardada ni la va a haber ("me conviene?", "le
              sirve a mi hija?"). La celda guarda el material y el modelo
              redacta. Si se forzara una respuesta enlatada aca, el bot deja de
              vender y suena a maquina.

REGLA DE ESTE ARCHIVO: los resolutores reciben la CELDA y la FUENTE, nunca el
mensaje crudo del cliente. Sin mensaje no hay sobre que correr un regex, asi que
el segundo interprete no puede volver a nacer aca por descuido.
"""
from app.logger import get_logger

log = get_logger(__name__)

# Grupos que se contestan con PROSA. Si el interprete declara una celda de estas
# y el turno no la contesta, el cliente se queda sin respuesta a algo que
# pregunto. Son las que entran como slot REQUERIDO del schema del solver.
GRUPOS_PROSA = {"politica_faq", "objeciones", "comparacion_compatibilidad",
                "asesoramiento", "postventa", "seguridad", "casos_borde",
                "identidad_dato"}

_VOCAB_CACHE: dict = {}

# GEMELOS — la misma pregunta con dos nombres.
#
# El vocabulario junta dos listas que crecieron por separado, asi que hay
# preguntas que quedaron con nombre en las dos: el interprete declara una y la
# respuesta concreta esta guardada bajo la otra. Caso medido: ante "se puede
# pagar en cuotas sin interes?" el interprete declara `cuotas_financiacion`, que
# solo tiene el criterio vago "depende de tu tarjeta", mientras la cantidad REAL
# de cuotas vive en el tema de FAQ `cuotas`. En la corrida viva de 291 turnos eso
# explica los 24 en que el indice quedaba sin material.
#
# Se LINKEAN, no se fusionan: la celda suma el texto del gemelo y no se pierde
# ninguno de los dos. Fusionar borraria una de las dos respuestas.
#
# CADA PAR DE ACA SE VERIFICO LEYENDO LOS DOS TEXTOS, uno por uno. NO se armo por
# solape de palabras: ese metodo proponia cuatro pares que son preguntas
# DISTINTAS, y unirlos habria borrado una respuesta del bot sin que ningun test
# se pusiera en rojo. Quedan anotados abajo para que no se vuelvan a proponer.
#
# RECHAZADOS, y por que:
#   marcas_originales / marcas          -> "son originales?" no es "que marca me
#                                          conviene". Son dos respuestas.
#   stock_disponibilidad / urgencia_honesta -> "hay stock?" no es como transmitir
#                                          urgencia sin mentir. No se tocan.
#   formas_contacto / producto_no_vendido   -> no tienen nada que ver; el solape
#                                          de palabras fue casualidad.
GEMELOS = {
    "cuotas_financiacion": "cuotas",
    "cambios_devoluciones": "devoluciones",
    "mayorista_cantidad": "mayoristas",
    "producto_defectuoso": "defectuoso",
    "asesoramiento_metodo": "asesoramiento",
    "desconfianza_online": "confianza_seguridad",
    "envio_zonas": "envios",
    "teclado": "teclado_mecanico_membrana",
}


def _faq_dict(tienda_id):
    from app.storage.firestore_client import get_all_faq
    return get_all_faq(tienda_id=tienda_id) or {}


def vocabulario(tienda_id=None) -> list[str]:
    """LA lista de nombres del sistema: las categorias de base_conocimiento mas
    los temas de FAQ que no figuran entre ellas. Es el enum de `categorias` del
    interprete y la clave de este indice: una sola lista, no dos."""
    if tienda_id in _VOCAB_CACHE:
        return list(_VOCAB_CACHE[tienda_id])
    from app.core.guia_venta_prosa import categorias_conocimiento
    nombres = list(categorias_conocimiento())
    try:
        for t in _faq_dict(tienda_id):
            if t not in nombres:
                nombres.append(str(t))
    except Exception as e:
        # Sin FAQ el sistema sigue con las categorias: no se cae un turno por
        # esto. Y NO se cachea el resultado incompleto -si la primera consulta
        # cae antes de que Firestore este disponible, cachear dejaria al
        # interprete mudo sobre los 23 temas por el resto del proceso.
        log.warning("indice_vocabulario_sin_faq", error=str(e)[:120])
        return nombres
    _VOCAB_CACHE[tienda_id] = nombres
    return list(nombres)


def celda(nombre: str, tienda_id=None) -> dict | None:
    """Que sabe contestar la fuente sobre este nombre. None si no sabe nada, que
    es un resultado valido: el turno lo responde honesto sin inventar.

    Un nombre puede traer las DOS cosas -la politica escrita y el criterio de
    venta-; los 27 que estan en las dos listas son justamente esos. Se devuelven
    ambas y el solver usa la que le sirve, igual que hoy."""
    cid = str(nombre or "").strip()
    if not cid:
        return None
    from app.core.guia_venta_prosa import meta_categoria, texto_de
    from app.core.curadas import estampar_valores
    texto_faq, texto_faq_crudo, faq_tema = "", "", ""
    try:
        faq = _faq_dict(tienda_id)
        # el nombre propio, y si no tiene politica escrita, la de su GEMELO: la
        # misma pregunta guardada con el otro nombre.
        gem = GEMELOS.get(cid, "")
        d = faq.get(cid) or faq.get(gem, {}) or {}
        crudo = str(d.get("respuesta_curada") or d.get("respuesta") or "").strip()
        if crudo:
            faq_tema = cid if faq.get(cid) else gem
            # CRUDO = con los huecos {{concepto}} intactos. Es lo que ve el
            # SOLVER: asi redacta la politica en su voz pero el NUMERO no lo
            # escribe el, lo estampa el codigo desde la fuente al renderizar.
            # Mismo mecanismo que los precios, que el modelo tampoco escribe.
            texto_faq_crudo = crudo
            texto_faq = estampar_valores(crudo, d) or crudo
    except Exception as e:
        log.warning("indice_celda_faq_error", nombre=cid, error=str(e)[:120])
    texto_criterio = texto_de(cid) or ""
    if not texto_faq and not texto_criterio:
        return None
    meta = meta_categoria(cid)
    # los temas que vienen SOLO de la FAQ no estan en base_conocimiento, asi que
    # no tienen grupo. Son politica de la tienda por definicion.
    grupo = meta.get("grupo") or ("politica_faq" if texto_faq else "")
    return {"nombre": cid,
            "tipo": "dato" if texto_faq else "criterio",
            "grupo": grupo,
            "faq_tema": faq_tema,
            "texto_faq": texto_faq,
            "texto_faq_crudo": texto_faq_crudo,
            "texto_criterio": texto_criterio}


def celdas(nombres, tienda_id=None) -> list[dict]:
    """Las celdas de los nombres que declaro el interprete, sin repetir y en el
    orden en que las declaro."""
    out, vistos = [], set()
    for n in (nombres or []):
        cid = str(n or "").strip()
        if not cid or cid in vistos:
            continue
        vistos.add(cid)
        c = celda(cid, tienda_id)
        if c:
            out.append(c)
    return out


def obligatorias(celdas_turno, tope: int = 5) -> list[str]:
    """Las celdas que el turno DEBE contestar: las de prosa con material. Son los
    slots requeridos del schema del solver, asi que saltearlas es imposible a
    nivel API, no algo que se mida despues."""
    return [c["nombre"] for c in (celdas_turno or [])
            if c.get("grupo") in GRUPOS_PROSA][:tope]


def menu(celdas_turno, campo: str) -> str:
    """El material de las celdas para el prompt, una linea por celda con su id
    entre corchetes. `campo` es texto_faq o texto_criterio."""
    return "\n".join(f"  [{c['nombre']}] {c[campo]}"
                     for c in (celdas_turno or []) if c.get(campo))
