"""
BANCO DE INTERPRETACION MULTI-TURNO — la charla encadenada, no el mensaje suelto.

Pedido de Martin (10-jul): medir la interpretacion en charlas de 3-4 turnos,
porque en un turno solo la respuesta no es representativa. Cada charla es una
secuencia de turnos del cliente con la respuesta del bot GUIONADA (fija y
coherente con el catalogo), asi el contexto crece igual que en produccion y lo
unico que varia es la lectura del interprete vivo en CADA turno.

Chequeos PARCIALES por turno (solo lo que importa), mismo estilo que
banco_interpretacion.py. Proveedor por env: INTERPRETER_PROVIDER=deepseek /
openai / gemini (con su clave). Piso 0.8.

Uso:  INTERPRETER_PROVIDER=deepseek python3 banco_pruebas/banco_interpretacion_multiturno.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas.sim_firestore import install
from banco_pruebas.banco_interpretacion import (
    _es, _no_es, _producto_contiene, _pedido_es, _criterio_barato, _VISTOS)

PISO = 0.8

_OFERTA = ("Tengo el Mouse Genius DX-110 Negro a $8.500, el Mouse Genius "
           "DX-110 Blanco a $8.500 y el Mouse Logitech M170 Negro a $12.000. "
           "¿Cuál te gusta?")


def _sin_pedido(i):
    return not (i.get("pedido") or [])


# Cada charla: (descripcion, [turnos]). Turno = (mensaje_cliente,
# respuesta_guionada_del_bot, estado_anterior, [(nombre_chequeo, fn)]).
# Los chequeos van sobre la lectura de ESE turno, con toda la historia previa.
CHARLAS = [
    ("decision que cambia lejos: la señora elige el blanco",
     [("hola, tenes mouse?", _OFERTA, "saludo",
       [("no es compra", _no_es("intencion", "decision_compra"))]),
      ("dame 2 del dx-110 negro",
       "Perfecto, 2x Mouse Genius DX-110 Negro: $17.000 en total. ¿Confirmamos?",
       "explorando",
       [("pedido 2 negros", _pedido_es(("dx-110 negro", 2)))]),
      ("espera que le pregunto a mi señora",
       "Dale, tomate tu tiempo y avisame.",
       "esperando_confirmacion",
       [("no es compra", _no_es("intencion", "decision_compra"))]),
      ("dice que mejor el blanco, pero uno solo",
       "Anotado: 1x Mouse Genius DX-110 Blanco, $8.500. ¿Confirmamos?",
       "esperando_confirmacion",
       [("pedido 1 blanco", _pedido_es(("dx-110 blanco", 1)))])]),

    ("referencia al 'primero que te dije' contra el historial",
     [("cuanto sale el logitech m170?",
       "El Mouse Logitech M170 Negro sale $12.000. ¿Te interesa?",
       "explorando",
       [("resuelve m170", _producto_contiene("m170"))]),
      ("y el genius negro?",
       "El Mouse Genius DX-110 Negro sale $8.500.",
       "explorando",
       [("resuelve dx-110 negro", _producto_contiene("dx-110 negro"))]),
      ("no, sabes que? el primero que te pregunte nomas, dame ese",
       "Perfecto, 1x Mouse Logitech M170 Negro: $12.000. ¿Confirmamos?",
       "explorando",
       [("vuelve al m170", _producto_contiene("m170"))])]),

    ("ironia, condicion y cierre real",
     [("che se me rompio el mouse, necesito algo ya",
       _OFERTA, "saludo",
       [("no es compra", _no_es("intencion", "decision_compra"))]),
      ("jaja si, seguro me llega hoy magicamente no?",
       "Hoy no te miento, pero despachamos en 24hs y llega en 2 a 4 dias "
       "habiles.",
       "explorando",
       [("ironia no es compra", _no_es("intencion", "decision_compra"))]),
      ("bueno va, si me llega esta semana lo llevo. llega o no?",
       "A la mayoria de las ciudades llega dentro de la semana, si.",
       "explorando",
       [("condicionada no es compra", _no_es("intencion", "decision_compra"))]),
      ("dale entonces, metele con el genius negro",
       "¡Genial! 1x Mouse Genius DX-110 Negro: $8.500. Te paso el pago.",
       "explorando",
       [("ahora SI es compra", _es("intencion", "decision_compra")),
        ("producto negro", _producto_contiene("negro"))])]),

    ("cantidades que van y vienen",
     [("dame 3 del dx110 negro",
       "Perfecto, 3x Mouse Genius DX-110 Negro: $25.500. ¿Confirmamos?",
       "explorando",
       [("pedido 3 negros", _pedido_es(("dx-110 negro", 3)))]),
      ("mejor hace 2 negros y 1 blanco",
       "Queda: 2x DX-110 Negro + 1x DX-110 Blanco = $25.500. ¿Confirmamos?",
       "esperando_confirmacion",
       [("pedido 2+1", _pedido_es(("dx-110 negro", 2),
                                  ("dx-110 blanco", 1)))]),
      ("uh no, el blanco sacalo y sumale otro negro",
       "Listo: 3x Mouse Genius DX-110 Negro = $25.500. ¿Confirmamos?",
       "esperando_confirmacion",
       [("pedido vuelve a 3 negros", _pedido_es(("dx-110 negro", 3)))])]),

    ("criterio abreviado y mudanza a mitad de charla",
     [("necesito 2 mouse para la oficina, lo mas eco que tengas",
       "Los más económicos con stock son los DX-110 a $8.500. 2x DX-110 "
       "Negro: $17.000. ¿A dónde te los mando?",
       "saludo",
       [("lee criterio barato", _criterio_barato)]),
      ("van para Rosario",
       "Envío a Rosario: $6.500. Total con envío: $23.500. ¿Confirmamos?",
       "explorando",
       [("aporta dato, no compra", _no_es("intencion", "decision_compra"))]),
      ("pera, al final me mude, mandalos a cordoba capital",
       "Sin problema: envío a Córdoba capital $6.000. Total $23.000. "
       "¿Confirmamos?",
       "esperando_confirmacion",
       [("cambio de destino no es compra",
         _no_es("intencion", "decision_compra")),
        ("no inventa pedido nuevo",
         lambda i: not (i.get("pedido") or []) or
         _pedido_es(("dx-110", 2))(i))]),
      ("listo, confirmame eso",
       "¡Confirmado! Te paso el pago.",
       "esperando_confirmacion",
       [("es compra", _es("intencion", "decision_compra"))])]),

    ("despedida que parece compra, y el si llega despues",
     [("cuanto salen 2 del blanco con envio a rosario?",
       "2x Mouse Genius DX-110 Blanco: $17.000 + envío $6.500 = $23.500.",
       "explorando",
       [("no es compra", _no_es("intencion", "decision_compra"))]),
      ("buenisimo, lo hablo con mi socio y te aviso, gracias!",
       "Dale, quedo atento. ¡Gracias a vos!",
       "esperando_confirmacion",
       [("despedida NO es compra", _no_es("intencion", "decision_compra"))]),
      ("me dijo que si asi que dale, mandalos",
       "¡Genial! Confirmo 2x DX-110 Blanco a Rosario.",
       "esperando_confirmacion",
       [("ahora es compra", _es("intencion", "decision_compra"))])]),
]


async def correr(verbose: bool = True) -> float:
    install()
    from app.core.interpretador import interpretar_mensaje

    ok_total, checks_total = 0, 0
    fallas = []
    for c_idx, (desc, turnos) in enumerate(CHARLAS, 1):
        hist: list[dict] = []
        for t_idx, (msg, bot_resp, estado_ant, checks) in enumerate(turnos, 1):
            interp = await interpretar_mensaje(
                msg, hist, f"multi{c_idx:02d}t{t_idx}",
                estado_anterior=estado_ant, productos_vistos=_VISTOS)
            for nombre, chk in checks:
                checks_total += 1
                if chk(interp if isinstance(interp, dict) else {}):
                    ok_total += 1
                else:
                    fallas.append((c_idx, t_idx, desc, nombre, {
                        "intencion": interp.get("intencion"),
                        "producto": interp.get("producto_resuelto"),
                        "pedido": interp.get("pedido"),
                        "criterio": interp.get("criterio"),
                        "confianza": interp.get("confianza")}))
            hist += [{"role": "user", "content": msg},
                     {"role": "assistant", "content": bot_resp}]
        if verbose:
            print(f"[{c_idx}] {desc}: "
                  f"{'OK' if not any(f[0] == c_idx for f in fallas) else 'FALLA'}")

    score = ok_total / checks_total if checks_total else 0.0
    if verbose:
        prov = os.getenv("INTERPRETER_PROVIDER", "(default)")
        print(f"\nProveedor: {prov} — {ok_total}/{checks_total} chequeos "
              f"= {score:.0%} (piso {PISO:.0%})")
        for c, t, desc, nombre, leido in fallas:
            print(f"  FALLA charla {c} turno {t} [{desc}] -> {nombre}")
            print(f"        leido: {leido}")
    return score


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(correr()) >= PISO else 1)
