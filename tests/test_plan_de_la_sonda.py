"""
LOS CINCO QUE DEJO LA SONDA DEL 25-AGO — en tests, no en prosa.

De donde salen: `banco_pruebas/casetes_sonda_25ago/DEFECTOS.md`, que es lo
unico que sobrevivio de esa grabacion. Los numeros de turno de alla no se
pueden reproducir aca —los casetes se perdieron—, asi que cada paso se mide
contra el CODIGO DE HOY y no contra el texto de aquel dia. Es mejor vara: el
turno 76 t1 es una anecdota, y "el punto de oferta se abre igual cuando el
turno dejo una pregunta propia sin contestar" es una propiedad que se verifica
sola y que la regrabacion no puede volver falsa por casualidad.

LOS CINCO SON `PLAN:`, o sea que TODAVIA NO SE EMPEZARON, y los cinco estan en
rojo a proposito con `strict=True`: el dia que alguien los arregle, el test se
pone rojo si no le saca la marca. No se pueden cerrar en silencio.

EL ORDEN NO ES LIBRE. Los dos primeros —el freno y el detector— ensucian la
medicion de los otros tres: mientras el detector cuente como OFRECIDO cuatro
frases que no ofrecen nada, cualquier numero sobre oferta esta sucio, y
regrabar antes de arreglarlo es pagar la grabacion dos veces.
"""
import pytest

from app.core import indice_turno as IT
from app.core import salida as SAL


# ── (a) EL CUARTO FRENO: la oferta cede ante una pregunta propia ─────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: si el turno ya le pregunta algo al cliente, la oferta CEDE. HOY el "
    "punto de oferta tiene TRES frenos —`ya_en_el_pedido`, `rechazado` y "
    "`cerrando`— y los tres miran otra cosa: los dos primeros miran el pedido y "
    "el tercero es un vocabulario de cierre, no una pregunta. Ninguno mira si "
    "el turno dejo una pregunta PROPIA sin contestar, asi que un texto que "
    "pregunta y ofrece en el mismo mensaje abre el punto sin `no_corresponde`. "
    "Medido: 3 turnos de la sonda ofrecen encima de su propia pregunta —76 t1, "
    "80 t6, 80 t8—. OBJETIVO un cuarto freno: con una pregunta propia abierta "
    "el punto no se abre, igual que con herramienta ambigua, y la oferta queda "
    "para el turno siguiente. Dos preguntas en el mismo mensaje es pedirle al "
    "cliente que administre una agenda."))
def test_la_oferta_cede_ante_una_pregunta_propia():
    llamadas = [{"herramienta": "ficha_producto",
                 "resultado": {"estado": "encontrado",
                               "producto": {"id": "M1",
                                            "nombre": "Mouse Logitech G203",
                                            "categoria": "mouse"}}}]
    texto = ("Cual de las dos versiones tenes, la Core i5 o la Ryzen 7? "
             "Te lo cargo al pedido y te paso el total.")
    p = IT.punto_de_oferta(llamadas, None, texto, None)
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


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: OFRECIDO tiene que exigir que la oracion NOMBRE el producto Y "
    "proponga una accion concreta sobre el —cargarlo, sumarlo, reservarlo, "
    "cotizarlo—. HOY `_ofrecio_el_paso` acepta accion + `_RE_PRONOMBRE`, y un "
    "'lo' o 'la' pelado hace de producto: las CUATRO frases de `NO_SON_OFERTAS` "
    "cuentan hoy como oferta, 4 de 4. Por eso la sonda conto 16 OFRECIDO con al "
    "menos 4 que no lo eran. OBJETIVO 0 de 4, sin perder el ofrecimiento real "
    "—que este test tambien verifica—, porque un detector que se arregla "
    "matando los verdaderos no arregla nada. Va PRIMERO junto con (a): mientras "
    "cuente esto, todo numero sobre oferta esta sucio."))
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
