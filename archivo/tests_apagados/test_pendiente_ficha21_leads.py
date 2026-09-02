"""
VERIFICA UN ITEM DE `PENDIENTE.md` QUE SOSPECHO ESTA VIEJO — Martin, 26-ago-2026.

EL RECLAMO TEXTUAL, todavia escrito en `PENDIENTE.md` bajo la FICHA 21: "LA
FICHA 21 CERRO LA MITAD DE LA COSTURA Y DEJO NOMBRADA LA OTRA... `leads.
_RE_CIERRE_YA_PREGUNTADO` lo lee en `_cerrar` -que corre DESPUES de esa
puerta- y da por hecho que el MODELO ya pregunto el cierre, asi que no pega
la suya... `_cerrar` tendria que recibir el texto del modelo, no el
estampado."

LO QUE ENCONTRE LEYENDO `app/core/leads.py` HOY. `_RE_CIERRE_YA_PREGUNTADO`
esta declarado en la linea 51 y no aparece referenciado en ningun otro lugar
del archivo ni del repo: es codigo muerto. Y el parametro `respuesta_solver`
de `procesar_mensaje_para_lead` -que es el texto que le llega, estampado o
no- no se lee en ningun punto de la funcion: la decision de si preguntar el
cierre corre entera sobre `interpretacion`, `presupuesto_nuevo` y
`pregunta_cierre_hecha`, nunca sobre un regex contra el texto.

Si eso es asi, el defecto que el PENDIENTE describe YA NO SE REPRODUCE por
ese camino: no porque alguien lo haya arreglado a proposito con ese nombre,
sino porque una refactorizacion posterior le saco al costado la lectura de
texto que lo causaba. Este test no da por buena esa lectura por grep: la
prueba corriendo la funcion real con el texto estampado exacto que
`guia_pedido.mensaje_presupuesto_sellado` emite, y compara contra el mismo
turno con una respuesta neutra. Si el resultado es identico, el reclamo del
PENDIENTE esta resuelto y hay que sacarle la marca ahi. Si CAMBIA, el
reclamo sigue vivo y hay que arreglarlo antes de tocar nada mas.

CORRE OFFLINE: sin modelo, sin clave, sin red. Reusa el arnes de
`test_cierre.py` (`_correr_cierre`), sin Firestore real via monkeypatch.
"""
import asyncio

import pytest

from tests.test_cierre import _correr_cierre

# EL TEXTO EXACTO QUE ESTAMPA EL CODIGO, verbatim de
# `app/core/guia_pedido.py::mensaje_presupuesto_sellado` (linea 520) y de
# `_ESTAMPADAS` en `tests/test_ficha21_texto_del_modelo.py`. Si esa cadena
# cambia de redaccion, este test hay que releerlo para no quedar midiendo el
# vacio.
_TEXTO_ESTAMPADO_CIERRE = (
    "¿Lo dejamos confirmado? Decime la forma de pago: "
    "transferencia (10% de descuento) o Mercado Pago.")


def test_el_texto_estampado_no_apaga_la_pregunta_suave_de_cierre(monkeypatch):
    """Caso tres de `procesar_mensaje_para_lead`: presupuesto nuevo, intencion
    de pregunta especifica, sin decision de compra confirmada todavia. Tiene
    que devolver accion=pregunta_cierre pase lo que pase en `respuesta_solver`.
    """
    kwargs = dict(mensaje="y hacen envios a Cordoba?",
                  intencion="pregunta_especifica", confianza=0.6,
                  presupuesto="Total: $49.000", presupuesto_nuevo=True,
                  modo="lead")

    neutro = _correr_cierre(monkeypatch, **kwargs, respuesta_solver="Genial.")
    estampado = _correr_cierre(monkeypatch, **kwargs,
                               respuesta_solver=_TEXTO_ESTAMPADO_CIERRE)

    assert neutro.get("accion") == "pregunta_cierre", (
        f"el caso base ya no dispara la pregunta suave: {neutro}. Este test "
        f"no prueba nada si esto no pasa primero.")
    assert estampado.get("accion") == neutro.get("accion"), (
        f"EL RECLAMO DE PENDIENTE.md SIGUE VIVO: con el texto estampado la "
        f"accion fue {estampado.get('accion')!r} contra {neutro.get('accion')!r} "
        f"del caso neutro. `_cerrar` esta leyendo el texto del CODIGO como si "
        f"fuera del modelo. Hay que pasarle `texto_del_modelo`, no `texto`.")


def test_respuesta_solver_no_se_lee_en_la_funcion():
    """CANDADO ESTATICO, offline, sin ejecutar nada: si en el futuro alguien
    vuelve a leer `respuesta_solver` dentro de `procesar_mensaje_para_lead`
    para decidir el cierre, este test tiene que revisarse a mano -puede ser
    una lectura nueva y legitima, o puede ser el mismo acoplamiento
    reapareciendo con otro nombre, que es exactamente el patron que
    `ARQUITECTURA.md` ya documento para la etapa de salida."""
    import ast
    from pathlib import Path

    fuente = (Path(__file__).resolve().parent.parent / "app" / "core"
              / "leads.py").read_text(encoding="utf-8")
    arbol = ast.parse(fuente)
    funcion = next((n for n in ast.walk(arbol)
                    if isinstance(n, ast.AsyncFunctionDef)
                    and n.name == "procesar_mensaje_para_lead"), None)
    assert funcion is not None, "procesar_mensaje_para_lead ya no existe con ese nombre"
    usos = [n for n in ast.walk(funcion)
            if isinstance(n, ast.Name) and n.id == "respuesta_solver"]
    # Un solo uso esperado: el parametro en la firma de la funcion (ast.arg,
    # no ast.Name, asi que no cuenta aca). Cero ast.Name es lo que hoy hay.
    assert len(usos) == 0, (
        f"respuesta_solver aparece referenciado {len(usos)} veces adentro de "
        f"procesar_mensaje_para_lead. Si es una lectura nueva, revisar que no "
        f"reintroduzca el acoplamiento de la FICHA 21: decidir el cierre por "
        f"el texto ESTAMPADO en vez de por la interpretacion del modelo.")
