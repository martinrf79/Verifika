"""
LA PRIORIDAD UNO, ESCRITA COMO TEST: el bot no alucina aunque el modelo mienta.

QUE ES. Las mismas charlas de los guiones, corridas ENTERAS por el camino vivo
-`app.main._process_and_reply_whatsapp`, el que atiende el webhook- con el
modelo reemplazado por codigo. El doble no escribe bien a proposito: cada turno
inyecta UNA de las mentiras que este sistema ya sufrio en real -un peso que
nadie calculo, un CBU que no es el de la casa, una spec inventada, el volcado
del JSON, markdown que WhatsApp no renderiza-. Ver `banco_pruebas/modelo_sintetico.py`.

POR QUE ESTA VARA Y NO UN PUNTAJE. Los 15 casetes reales puntuan de 0 a 100 y
ese numero mezcla dos cosas: si el modelo tuvo un buen dia y si el codigo hizo
su trabajo. Cuando el numero baja hay que averiguar cual de las dos fue, y eso
costo dias. Aca no hay numero: hay afirmaciones duras que ninguna respuesta
correcta viola, y el modelo es codigo, asi que un rojo solo puede ser del
codigo. Se reproduce siempre igual y no depende de ningun proveedor.

EL AGUJERO QUE VIENE A TAPAR, con su fecha. El 17-ago el gate de las charlas
quedo trabado en 491 contra 493 sin una sola regresion real: los casetes se
habian grabado con la arquitectura de cuatro rondas y penalizaban a la de dos
por no consumir una llamada que ya no hace. Regrabar necesitaba clave: la paga
esta cerrada hasta que se mueva la aguja y la gratis se quedo sin cuota a mitad
de la tanda. Un instrumento que depende de un proveedor se traba justo cuando
mas se lo necesita. Este no.

LO QUE NO MIDE, dicho adelante: si la frase vende, si el tono esta bien, o si
el modelo real mejoro. Eso lo siguen midiendo los 15 casetes reales, el
explorador y la prueba en vivo por WhatsApp. Esto mide el CODIGO, que es donde
vivieron todos los defectos de estas semanas.
"""
import asyncio
import re
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import modelo_sintetico as MS  # noqa: E402

GUIONES = _RAIZ / "banco_pruebas" / "guiones"

# Las charlas que se corren. Son las mismas que tienen casete real, para que
# las dos varas hablen de las mismas conversaciones y se puedan comparar.
_CON_CASETE = sorted(
    p.stem for p in (_RAIZ / "banco_pruebas" / "casetes").glob("*.json")
    if not p.name.startswith("_") and (GUIONES / f"{p.stem}.txt").exists())


def _charla(nombre: str) -> tuple:
    """Una charla entera por el camino vivo, con el modelo sintetico."""
    from banco_pruebas import clon_produccion as clon
    from banco_pruebas.puntaje import leer_guion

    turnos = leer_guion((GUIONES / f"{nombre}.txt").read_text(encoding="utf-8"))
    clon.instalar()
    user = f"sintetico_{nombre}"
    clon.reiniciar_cliente(user)

    async def _correr():
        fuera = []
        for t in turnos:
            fuera.append("\n".join(await clon.turno(user, t["mensaje"])))
        return fuera

    with MS.sin_modelo():
        return turnos, asyncio.run(_correr())


# ── LAS AFIRMACIONES ────────────────────────────────────────────────────────
# EL TITULO HUERFANO: LA MARCA SE SACO EL 21-ago (FICHA 04), Y CONVIENE SER
# EXACTO SOBRE QUE SE CERRO Y QUE NO.
#
# ERA: en el turno 8 de `80_charla_real_12ago` quedaba un titulo que prometia
# una lista y abajo, en vez de la lista, la linea "Sin cambios en la cuenta.
# Total final: $X". Se salvaba de las CUATRO implementaciones de la regla
# porque las cuatro preguntan si hay ALGO abajo, no si abajo esta lo que el
# titulo anuncio.
#
# LO QUE SE CERRO: el TRIGGER. Ese turno ya no produce esa linea, porque la
# cuenta ahora se arma de verdad —el cliente pidio agregar un teclado y la
# cuenta cambia, asi que no hay nada que podar por "sin cambios"—. El caso
# pasa y `strict=True` obligo a sacar la marca.
#
# LO QUE NO SE CERRO, Y NO HAY QUE CREER QUE SI: las cuatro implementaciones
# siguen siendo cuatro y siguen preguntando lo mismo. Una reparacion todavia
# puede apagar a otra sin que nadie lo note; lo que cambio es que este corpus
# ya no tiene el caso que lo mostraba. **Fusionarlas en UNA que compare el
# titulo contra lo que sigue sigue pendiente**, y entra en el paso 3 del
# recorte, que es el que borra tres de las cuatro.
_CASOS = list(_CON_CASETE)


@pytest.mark.skipif(not _CON_CASETE, reason="no hay guiones")
@pytest.mark.parametrize("nombre", _CASOS)
def test_ninguna_mentira_del_modelo_llega_al_cliente(nombre, firestore_doble):
    """LA VARA, y es la prioridad uno entera en un assert.

    El doble miente en CADA turno, con una mentira distinta por vez. Ninguna
    puede salir. No se juzga el estilo ni el largo: se juzga que lo que el
    codigo no puede respaldar, no se manda."""
    from app.core import herramientas as H

    _turnos, respuestas = _charla(nombre)
    sucios = []
    for i, texto in enumerate(respuestas):
        t = texto or ""
        cual = MS.mentira_del_turno(i)

        # 1. EL COBRO. Un CBU o un titular que no son los de la tienda.
        if "2850590940090418135201" in t.replace(" ", ""):
            sucios.append(f"turno {i + 1} [{cual}]: salio un CBU inventado")

        # 2. EL VOLCADO CRUDO. El JSON de una herramienta no es un mensaje.
        if '{"estado"' in t or '"productos":' in t:
            sucios.append(f"turno {i + 1} [{cual}]: salio el JSON crudo")

        # 3. MARKDOWN. WhatsApp no lo renderiza: sale el asterisco pelado.
        if "**" in t or re.search(r"^\s*\|.*\|\s*$", t, re.MULTILINE):
            sucios.append(f"turno {i + 1} [{cual}]: salio markdown")

        # 4. EL ID INTERNO. Es sintaxis nuestra y no le dice nada al cliente.
        if re.search(r"\b(?:id|sku)\s*[:=]?\s*[A-Z]{2,5}\d{2,}", t, re.I):
            sucios.append(f"turno {i + 1} [{cual}]: salio un id interno")

        # 5. EL TITULO QUE PROMETE UNA LISTA Y NO MUESTRA NINGUNA.
        for m in re.finditer(r"(?im)^(.*modelos que te sirven:)\s*$", t):
            resto = t[m.end():].strip()
            if not resto or not resto.startswith(("-", "•", "1")):
                sucios.append(f"turno {i + 1} [{cual}]: titulo sin lista abajo")

        assert t.strip(), f"turno {i + 1}: el cliente no recibio NADA"

    assert not sucios, ("MENTIRAS QUE LLEGARON AL CLIENTE:\n  "
                        + "\n  ".join(sucios))
    # El nombre queda usado aunque el assert de arriba pase: si un dia alguien
    # borra el import, esto se rompe y no queda un test que no prueba nada.
    assert H is not None


@pytest.mark.skipif(not _CON_CASETE, reason="no hay guiones")
@pytest.mark.parametrize("nombre", _CON_CASETE)
def test_ningun_peso_sin_respaldo(nombre, firestore_doble):
    """LA REGLA DEL SISTEMA, sola y aparte porque es la que toca la plata.

    Todo monto que salga tiene que haberlo calculado el codigo. El doble
    escribe $99.999 en uno de cada ocho turnos y ese numero no lo trajo ninguna
    herramienta: si aparece en el mensaje, la regla de plata se rompio."""
    _turnos, respuestas = _charla(nombre)
    coladas = [f"turno {i + 1}" for i, t in enumerate(respuestas)
               if "99.999" in (t or "") or "99999" in (t or "")]
    assert not coladas, (
        "EL PESO INVENTADO LLEGO AL CLIENTE en " + ", ".join(coladas))


@pytest.mark.skipif(not _CON_CASETE, reason="no hay guiones")
def test_el_descuento_afirmado_tampoco_llega(firestore_doble):
    """EL DESCUENTO AFIRMADO, cerrado el 17-ago en la atadura.

    El doble afirma un 25% que ninguna politica de la casa respalda. Nacio
    como `xfail` estricto porque salia al cliente; lo cierra
    `atadura_prosa._sin_descuento_sin_respaldo`, contrastando el porcentaje
    contra lo que trajeron las herramientas. La marca se saco el mismo dia en
    que el test empezo a pasar, que es para lo que servia el `strict`."""
    coladas = []
    for nombre in _CON_CASETE:
        _t, respuestas = _charla(nombre)
        for i, t in enumerate(respuestas):
            if re.search(r"25\s*%\s*de descuento", t or "", re.I):
                coladas.append(f"{nombre} turno {i + 1}")
    assert not coladas, ("EL DESCUENTO INVENTADO LLEGO AL CLIENTE en "
                         + ", ".join(coladas))


@pytest.mark.skipif(not _CON_CASETE, reason="no hay guiones")
def test_los_invariantes_valen_con_el_modelo_mintiendo(firestore_doble):
    """LOS INVARIANTES, sobre conversaciones que ningun humano escribio.

    Son las propiedades que no saben cual era la respuesta correcta -que la
    cuenta cierre, que lo cobrado sea lo facturado, que nada se diga dos veces,
    que no se fugue nada interno-. Corridas sobre un modelo hostil miden lo que
    el codigo garantiza cuando el de arriba no ayuda, que es el peor caso y el
    unico que importa para la prioridad uno."""
    from app.storage.firestore_client import get_all_products
    from banco_pruebas.invariantes import revisar_charla

    vocabulario = {str(p.get("nombre") or "") for p in
                   get_all_products(tienda_id="verifika_prod") if p.get("nombre")}
    sucias = []
    for nombre in _CON_CASETE:
        _t, respuestas = _charla(nombre)
        for f in revisar_charla(respuestas, vocabulario=vocabulario):
            sucias.append(f"{nombre} turno {f['turno']}: {f['regla']} — "
                          f"{f['detalle']}")
    assert not sucias, ("INVARIANTES VIOLADOS CON EL MODELO MINTIENDO:\n  "
                        + "\n  ".join(sucias))
