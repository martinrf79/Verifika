"""
LOS CINCO QUE DEJO LA SONDA DEL 25-AGO — en tests, no en prosa.

De donde salen: `banco_pruebas/casetes_sonda_25ago/DEFECTOS.md`, que es lo
unico que sobrevivio de esa grabacion. Los numeros de turno de alla no se
pueden reproducir aca —los casetes se perdieron—, asi que cada paso se mide
contra el CODIGO DE HOY y no contra el texto de aquel dia. Es mejor vara: el
turno 76 t1 es una anecdota, y "el punto de oferta se abre igual cuando el
turno dejo una pregunta propia sin contestar" es una propiedad que se verifica
sola y que la regrabacion no puede volver falsa por casualidad.

NACIERON LOS CINCO CON MARCA `PLAN:` y `strict=True`, que es lo que hace que no
se puedan cerrar en silencio: el dia que alguien los arregla, el test se pone
rojo si no le saca la marca. Asi se cerraron los dos primeros.

QUEDAN TRES MARCADOS. Los dos primeros —el cuarto freno y el detector
estricto— los cerro la FICHA 16 el 25-ago y sus marcas ya no estan; siguen aca
como candado, porque el dia que alguien afloje el detector se ponen rojos.

EL ORDEN NO ERA LIBRE, y por eso esos dos iban primero: mientras el detector
contara como OFRECIDO cuatro frases que no ofrecen nada, cualquier numero sobre
oferta estaba sucio, y regrabar antes de arreglarlo era pagar la grabacion dos
veces. Los tres que quedan —(c), (d) y (e)— ya se pueden medir limpio.
"""
import pytest

from app.core import indice_turno as IT
from app.core import salida as SAL


# ── (a) EL CUARTO FRENO: la oferta cede ante una pregunta propia ─────────────

# CERRADO POR LA FICHA 16, 25-ago. El cuarto freno existe y vive en
# `punto_de_oferta`: la marca `PLAN:` se fue y el test queda como candado.
def test_la_oferta_cede_ante_una_pregunta_propia():
    llamadas = [{"herramienta": "ficha_producto",
                 "resultado": {"estado": "encontrado",
                               "producto": {"id": "M1",
                                            "nombre": "Mouse Logitech G203",
                                            "categoria": "mouse"}}}]
    # LA OFERTA NOMBRA EL PRODUCTO, y desde el detector estricto tiene que
    # hacerlo para SER una oferta. Este texto decia "te lo cargo": con el
    # pronombre pelado ya no ofrece nada, asi que el turno no estaria ofreciendo
    # encima de su pregunta y el caso dejaria de ser el caso. Se corrige el
    # PLANTEO, no la vara: el assert y el motivo son los mismos.
    texto = ("Cual de las dos versiones tenes, la Core i5 o la Ryzen 7? "
             "Te cargo el Mouse Logitech G203 al pedido y te paso el total.")
    p, _ = IT.punto_de_oferta(llamadas, None, texto, None)
    assert not p or p.get("no_corresponde"), (
        "el turno dejo una pregunta propia sin contestar y la oferta se abrio "
        f"igual, sin motivo: {p}")


# ── (b) EL DETECTOR DE OFERTA ES LAXO ────────────────────────────────────────

# Las cuatro familias que la sonda encontro contadas como OFRECIDO sin serlo.
# Las cuatro entran por el MISMO agujero: `_RE_PRONOMBRE` deja que un "lo" o un
# "la" pelado haga de producto, asi que basta un verbo de accion y un pronombre
# para que la oracion cuente, sin nombrar nada.
NO_SON_OFERTAS = {
    "71 t3 cortesia de cierre generica": "Cualquier duda la coordinamos por aca.",
    "73 t3 mencion de descuento": "El descuento te lo puedo cotizar aparte.",
    "80 t8 pedido de confirmacion": "Me confirmas y lo reservo.",
    "76 t2 sin nombrar producto": "Dale, te lo preparo enseguida.",
}


# CERRADO POR LA FICHA 16, 25-ago. `_RE_PRONOMBRE` ya no existe: la oracion
# NOMBRA el producto o no cuenta. La marca `PLAN:` se fue y el test queda.
def test_ofrecido_exige_nombrar_el_producto():
    punto = {"tipo": "oferta", "candidatos": ["Mouse Logitech G203"]}
    colados = [k for k, frase in NO_SON_OFERTAS.items()
               if IT._ofrecio_el_paso(punto, frase)]
    real = "Te cargo el Mouse Logitech G203 al pedido y te paso el total."
    assert IT._ofrecio_el_paso(punto, real), (
        "se perdio el ofrecimiento REAL: arreglar el detector matando los "
        "verdaderos no es arreglarlo")
    assert not colados, (
        f"{len(colados)} de {len(NO_SON_OFERTAS)} frases que no ofrecen nada "
        f"cuentan como OFRECIDO: {colados}")


# ── (c) UN UNIVERSAL SOBRE EL CATALOGO, SIN HERRAMIENTA QUE LO RESPALDE ──────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: un universal sobre el catalogo no puede salir si NINGUNA herramienta "
    "miro el catalogo. HOY `_sin_afirmar_sobre_el_catalogo` cubre dos casos "
    "—hay evidencia de que el universal es falso, o la busqueda fallo— y "
    "arranca con `if not cumplen and not busqueda_fallida: return texto`. El "
    "tercer caso, el turno que afirma sobre los 880 SIN HABER LLAMADO A NADA, "
    "sale por ese return sin que la guardia lo mire: medido, 1 de 1 universal "
    "plantado con `llamadas=[]` llega intacto al cliente. La sonda lo vio en "
    "46 t4 y 62 t2. OBJETIVO 0: sin herramienta no hay universal, por la misma "
    "razon que ya vale para la busqueda fallida —no hace falta saber cual es la "
    "respuesta correcta para saber que esa esta mal—. Es alucinacion, o sea "
    "prioridad uno del objetivo, no estilo."))
def test_no_hay_universal_sin_herramienta_que_lo_respalde():
    texto = "Todos nuestros productos tienen garantia de 12 meses."
    salida = SAL._sin_afirmar_sobre_el_catalogo(texto, [], "t1")
    assert "todos nuestros productos" not in salida.lower(), (
        "el universal salio entero al cliente sin que ninguna herramienta "
        f"hubiera mirado el catalogo: {salida!r}")


# ── (d) LA NOTA INTERNA QUE LE LLEGA AL CLIENTE ──────────────────────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: la nota interna no sale al cliente. HOY `sin_narracion_interna` "
    "EXISTE y CORRE en todos los turnos: el censo lo dio 0/54 y eso se leyo "
    "como nodo muerto, pero no esta muerto, esta CIEGO. `_RE_NARRACION` es un "
    "vocabulario cerrado de ocho formas y las ocho nombran la MAQUINA —'el "
    "sistema me', 'la herramienta', 'en mi base de datos'—. Hablar del cliente "
    "en tercera persona es otra familia y no esta: medido, 'el cliente pide' "
    "pasa intacto, y hasta 'Nota interna: el cliente pide confirmacion' pasa "
    "intacto. 0 de 3 formas de esta familia cazadas. La sonda lo vio en 80 t6. "
    "OBJETIVO 3 de 3: la guardia suma la familia de la TERCERA PERSONA sobre el "
    "cliente, que es una forma, no una redaccion perseguida una por una."))
def test_la_nota_interna_no_le_llega_al_cliente():
    casos = ["Perfecto. el cliente pide dos mouse y un teclado, se los cotizo.",
             "Dale, el cliente pide el presupuesto con envio.",
             "Nota interna: el cliente pide confirmacion."]
    colados = [c for c in casos
               if "el cliente pide" in SAL._sin_narracion_interna(c, "t1")]
    assert not colados, (
        f"{len(colados)} de {len(casos)} notas internas le llegan al cliente "
        f"tal cual: {colados}")


# ── (e) LA PROMESA DE UN DATO QUE DESPUES NO SE DA ───────────────────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: si el turno anuncia un dato, el dato va abajo o el anuncio se va. "
    "HOY `_sin_anuncio_vacio` cubre UNA sola familia, la de la cuenta: "
    "`_RE_ANUNCIO` pide que la linea diga presupuesto, cotizacion, detalle o "
    "total. Un anuncio de PRECIO, de PLAZO o de STOCK no lo mira nadie: medido, "
    "3 de 3 promesas de esas familias salen enteras sin nada abajo. La sonda lo "
    "vio en 79 t1, y `camino_al_cobro` bajo de 9/15 a 7/15 en esa corrida. "
    "OBJETIVO 0 de 3, con la misma valvula que ya tiene la familia de la "
    "cuenta: si podar se lleva el mensaje entero no se poda, porque un turno "
    "mudo es peor que un turno feo."))
def test_no_se_promete_un_dato_que_no_se_da():
    casos = ["Te paso el precio del Mouse Logitech G203:",
             "Ahora te confirmo el plazo de entrega:",
             "Te averiguo el stock y te aviso."]
    colados = [c for c in casos if SAL._sin_anuncio_vacio(c, "t1") == c]
    assert not colados, (
        f"{len(colados)} de {len(casos)} anuncios de un dato salen sin el dato "
        f"abajo: {colados}")
