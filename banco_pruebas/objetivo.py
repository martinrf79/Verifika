"""
EL OBJETIVO, Y SI LLEGAMOS — el instrumento que faltaba (Martin, 7-ago-2026).

POR QUE EXISTE. Los tres numeros que ya hay miden el APARATO: que la
herramienta devuelva el conjunto correcto, que funcion toca que prueba, que el
turno no se caiga. Ninguno contesta la unica pregunta que importa: **¿el bot
contesta BIEN esta pregunta?**. Sin eso, cada sesion inventa su propio "listo",
mide otra cosa, y el avance no se acumula. Textual de Martin: "se nos acaban las
ideas". Se acaban porque no hay contra que medirlas.

DE DONDE SALE EL DISENO. De tau-bench, el banco de agentes de atencion al
cliente de Sierra, que es publico y esta probado. Su regla es la que copiamos:

  - **ESTADO FINAL**: se compara el estado que quedo, no los pasos que se
    dieron. Cualquier camino que llegue al mismo estado pasa.
  - **COMUNICACION**: ¿aparecen en el mensaje las frases que si o si habia que
    decir?
  - **LA NOTA ES EL PRODUCTO DE LAS DOS.** Un mensaje hermoso con la cuenta mal
    da CERO, y una cuenta perfecta que no dice lo que habia que decir, tambien.
    **No se gana hablando.**

LAS DOS VARAS, y son distintas a proposito:

  `--codigo`  (default, gratis, offline). Se le dan al codigo las llamadas
              IDEALES, las que el modelo tendria que pedir, y se mide QUE
              PRODUCE. Contesta: si el modelo pide bien, ¿el codigo entrega
              bien? Lo que falle aca no lo arregla ningun prompt.
  `--vivo`    (con clave, a mano). Las SEIS REDACCIONES de la misma pregunta
              corren por `_process_and_reply_whatsapp`, el camino del webhook,
              con el modelo de verdad.

POR QUE VARIAS REDACCIONES Y NO UNA. Es la falla que Martin viene senalando hace
semanas: se arregla un caso, cambia una palabra, y se cae. Medido el 7-ago: el
reparto de pago se arreglo leyendo "70/30" y se cayo con "setenta treinta",
que es como lo escribio el. **Una sola redaccion no prueba nada.**

EL HISTORIAL SOBREVIVE LAS SESIONES. Cada corrida con `--anotar` agrega una
fila a `OBJETIVO.md`: fecha, que se cambio, la nota antes y despues. El archivo
es GENERADO, nunca escrito a mano: un documento a mano miente a las dos
sesiones, uno calculado no puede.

USO:
    python3 banco_pruebas/objetivo.py                      # la nota, gratis
    python3 banco_pruebas/objetivo.py --vivo               # con el modelo real
    python3 banco_pruebas/objetivo.py --anotar "que hice"  # deja la fila
"""
import json
import sys
import unicodedata
from datetime import date
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

DOC = _RAIZ / "OBJETIVO.md"
TIENDA = "verifika_prod"


# ── EL OBJETIVO ─────────────────────────────────────────────────────────────
OBJETIVO = ("Que el bot conteste BIEN la pregunta real de Martin: seis "
            "productos en tres rubros, un criterio no binario -las menos "
            "partes chinas posibles-, tres destinos de envio, una "
            "contradiccion a proposito -un teclado que no estaba en el "
            "pedido- y un reparto de pago 70/30.")

# LAS REDACCIONES. La misma pregunta, dicha distinto. La 1 es TEXTUAL la que
# Martin mando por WhatsApp el 6-ago y la 6 la que mando el 9-ago; las del medio
# cambian lo que historicamente rompio: numeros en letras contra digitos, el
# orden de las clausulas, y las palabras del criterio de origen.
VARIANTES = {
    "1_textual_de_martin":
        "Dame precio de dos auriculares, dos mouse y dos memorias. El precio "
        "no seria tan importante. Lo que si que necesito que lleven las menos "
        "partes chinas posibles. Un auricular y un mouse sera envio a Cordoba "
        "capital. Un teclado y un mouse sera envio a Concordia. Los otros dos "
        "articulos seran con envio a posadas. Divide el presupuesto en "
        "setenta treinta, ya que vere en la fase siguiente como seguimos.",
    "2_porcentajes_en_digitos":
        "Necesito precio de 2 auriculares, 2 mouse y 2 memorias ram. Que "
        "tengan la menor cantidad de componentes chinos que puedas. Un "
        "auricular y un mouse van a Cordoba capital, un teclado y un mouse a "
        "Concordia, y los otros dos a Posadas. El presupuesto dividilo 70/30.",
    "3_orden_invertido":
        "Dividime el pago en un 70 y un 30. Mandame un auricular y un mouse a "
        "Cordoba capital, un teclado y un mouse a Concordia y los otros dos "
        "articulos a Posadas. Lo que necesito es el precio de dos auriculares, "
        "dos mouse y dos memorias, y sobre todo que sean lo menos chinos "
        "posible; la plata no es lo principal.",
    "4_criterio_dicho_distinto":
        "Pasame cuanto salen dos auriculares, dos mouse y dos memorias. Me "
        "importa poco el precio, me importa que no sean de fabricacion china, "
        "o lo mas lejos de eso que tengas. Envio: un auricular y un mouse a "
        "Cordoba capital, un teclado y un mouse a Concordia, los otros dos a "
        "Posadas. El presupuesto en dos partes, setenta y treinta.",
    "5_coloquial":
        "hola, necesito cotizar 2 auriculares 2 mouse y 2 memorias. no me "
        "fijo tanto en el precio pero quiero que tengan la menor cantidad de "
        "partes chinas posible. un auricular y un mouse me los mandas a "
        "cordoba capital, un teclado y un mouse a concordia y los otros dos a "
        "posadas. el presupuesto partilo setenta treinta asi despues veo",
    # LA SEXTA, Y ES LA QUE MARTIN MANDO POR WHATSAPP EL 9-AGO A LAS 14:13.
    # Es la misma pregunta con la contradiccion SACADA a proposito: donde antes
    # decia "un teclado y un mouse a Concordia" ahora dice "una memoria y un
    # mouse". Con eso los seis cierran por resta y no queda una sola arista:
    # Cordoba se lleva un auricular y un mouse, Concordia una memoria y un
    # mouse, y a Posadas van el auricular y la memoria que sobran.
    #
    # POR QUE IMPORTA MEDIRLA APARTE. Es el caso limpio: si el bot falla aca no
    # se puede echar la culpa a la ambiguedad del mensaje. Corrida en
    # produccion -trace 57ad6a0d- el modelo la dedujo PERFECTO y el turno salio
    # mal igual, por tres cables del codigo.
    "6_sin_teclado_los_seis_cierran":
        "Dame precio de dos auriculares, dos mouse y dos memorias. El precio "
        "no sería tan importante. Lo que sí que necesito que lleven las menos "
        "partes chinas posibles. Un auricular y un mouse será envío a Córdoba "
        "capital. Una memoria y un mouse será envío a Concordia. Los otros dos "
        "artículos serán con envío a posadas. Divide el presupuesto en setenta "
        "treinta, ya que veré en la fase siguiente cómo seguimos.",
}


def _n(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# ── VARA 1: EL ESTADO FINAL ─────────────────────────────────────────────────
# No se miran los pasos. Se mira que quedo, igual que la comparacion de base de
# datos de tau-bench: cualquier camino que llegue al mismo estado pasa.
def medir_estado(bloque: str, args_cuenta: dict) -> list:
    """(nombre, ok, detalle) por cada cosa que TIENE que estar en la cuenta."""
    b = _n(bloque)
    items = list((args_cuenta or {}).get("items") or [])
    unidades = sum(max(1, int(i.get("cantidad") or 1)) for i in items)
    con_destino = sum(max(1, int(i.get("cantidad") or 1)) for i in items
                      if str(i.get("destino") or "").strip())
    pago = list((args_cuenta or {}).get("pago") or [])
    pcts = sorted((float(p.get("porcentaje") or 0) for p in pago), reverse=True)
    grande = next((p for p in pago
                   if float(p.get("porcentaje") or 0) == (pcts[0] if pcts else 0)),
                  {})
    return [
        ("los_tres_rubros_en_la_cuenta",
         all(x in b for x in ("auricular", "mouse", "memoria")),
         "auriculares, mouse y memorias, los tres con su renglon"),
        ("seis_unidades", unidades == 6, f"pidio 6, la cuenta tiene {unidades}"),
        ("tres_envios_cotizados", "3 envio" in b or "tres envio" in b,
         "los tres destinos cotizados"),
        ("hay_total", "total:" in b, "la cuenta cierra con un total"),
        ("reparto_de_pago_aplicado", len(pago) == 2 and abs(sum(pcts) - 100) < 1,
         f"70/30 en el argumento pago, hoy {pcts or 'nada'}"),
        ("la_parte_grande_por_transferencia",
         bool(pago) and "transferencia" in _n(grande.get("medio")),
         "la parte grande va por el medio CON descuento, que es lo que le "
         "conviene al cliente"),
        ("descuento_en_la_cuenta", "descuento" in b,
         "el descuento por transferencia sale escrito"),
        ("cada_unidad_con_destino", con_destino == unidades and unidades > 0,
         f"{con_destino} de {unidades} unidades con destino"),
    ]


# ── VARA 2: LA COMUNICACION ─────────────────────────────────────────────────
# Lo que SI o SI hay que decirle, y lo que no se puede decir. Cada grupo es un
# O: alcanza con que aparezca una de las alternativas.
DEBE_DECIR = [
    (["china", "chino"], "nombrar el origen: es el unico criterio que el "
                         "cliente dijo que le importaba"),
    (["teclado"], "preguntar por el teclado, que es la contradiccion puesta a "
                  "proposito"),
    (["70", "setenta"], "el reparto que pidio tiene que aparecer"),
]
NO_PUEDE_DECIR = [
    (["todos los productos", "ninguno de los productos", "no tengo ningun",
      "no tengo nada", "todo el catalogo", "no manejo ningun"],
     "afirmar sobre los 880 es falso: hay 86 que cumplen"),
    (["no puedo cumplir"], "el muro: mata la venta y ademas es mentira"),
    (["los mas baratos", "mas economicos"],
     "contestarle con el precio a quien dijo que el precio no importa"),
]


def medir_comunicacion(texto: str, mensaje: str = "") -> list:
    """LO QUE HAY QUE DECIR DEPENDE DE LO QUE EL CLIENTE DIJO.

    "Preguntar por el teclado" es obligatorio solo cuando el cliente nombro un
    teclado. La sexta redaccion -la que Martin mando el 9-ago- lo saco a
    proposito, y exigirle igual esa pregunta seria pedirle al bot que invente
    una duda que nadie planteo. Sin `mensaje` la vara queda como estaba, asi que
    ningun banco viejo cambia de numero por esto.
    """
    t = _n(texto)
    fuera = []
    for alt, por_que in DEBE_DECIR:
        if mensaje and alt[0] == "teclado" and "teclado" not in _n(mensaje):
            continue
        fuera.append((f"dice: {alt[0]}", any(_n(a) in t for a in alt), por_que))
    for alt, por_que in NO_PUEDE_DECIR:
        malas = [a for a in alt if _n(a) in t]
        fuera.append((f"no dice: {alt[0]}", not malas,
                      por_que + (f" -- dijo '{malas[0]}'" if malas else "")))
    return fuera


def nota(estado: list, comunicacion: list) -> dict:
    """LA NOTA ES EL PRODUCTO, no la suma. Regla de tau-bench: una cuenta
    perfecta que no dice lo que habia que decir vale lo mismo que un mensaje
    lindo con la cuenta mal. Sumar deja pasar la mitad rota."""
    e_ok = sum(1 for _, ok, _ in estado if ok)
    c_ok = sum(1 for _, ok, _ in comunicacion if ok)
    e = e_ok / max(1, len(estado))
    c = c_ok / max(1, len(comunicacion))
    return {"estado": f"{e_ok}/{len(estado)}", "comunicacion":
            f"{c_ok}/{len(comunicacion)}", "nota": round(100 * e * c)}


# ── LA CORRIDA DE CODIGO: las llamadas IDEALES ──────────────────────────────
def _llamadas_ideales(tienda_id: str) -> tuple:
    """Lo que el modelo TENDRIA que pedir, escrito a mano. Aisla la pregunta:
    si el modelo pide bien, ¿el codigo entrega bien? Es el mismo metodo de
    `banco_candidatos.py` y lo que falle aca no lo arregla ningun prompt."""
    from app.core import herramientas as H

    declarado = {
        "items": [{"que": "auriculares", "cantidad": 2},
                  {"que": "mouse", "cantidad": 2},
                  {"que": "memoria ram", "cantidad": 2}],
        "restricciones": ["las menos partes chinas posibles",
                          "divide el presupuesto en setenta treinta"],
        "destinos": ["Cordoba capital", "Concordia", "Posadas"],
        "pide_precio": True,
        "contradicciones": ["Nombro un teclado en el envio a Concordia que no "
                            "estaba en el pedido."]}
    llamadas = [{"herramienta": "registrar_pedido", "pedido": declarado,
                 "resultado": {"estado": "registrado", "pedido": declarado}}]
    ids = {}
    for cat in ("auriculares", "mouse", "memoria ram"):
        a = {"categoria": cat, "cuantos": 3, "filtros": [
            {"campo": "pais_fabricacion", "valor": "china",
             "operador": "no_contiene"},
            {"campo": "pais_marca", "valor": "china",
             "operador": "no_contiene"}]}
        r = H.ejecutar("buscar_productos", a, tienda_id)
        llamadas.append({"herramienta": "buscar_productos", "pedido": a,
                         "resultado": r})
        prods = r.get("productos") or []
        if prods:
            ids[cat] = prods[0]["id"]
    # La cuenta como la pediria un modelo que entendio: dos de cada uno, con su
    # destino. NO se le pone `pago`: se mide si el CODIGO repone el reparto.
    args = {"items": [
        {"product_id": ids.get("auriculares"), "cantidad": 1,
         "destino": "Cordoba capital"},
        {"product_id": ids.get("mouse"), "cantidad": 1,
         "destino": "Cordoba capital"},
        {"product_id": ids.get("auriculares"), "cantidad": 1,
         "destino": "Concordia"},
        {"product_id": ids.get("mouse"), "cantidad": 1, "destino": "Concordia"},
        {"product_id": ids.get("memoria ram"), "cantidad": 2,
         "destino": "Posadas"}],
        "destinos": ["Cordoba capital", "Concordia", "Posadas"]}
    llamadas.append({"herramienta": "armar_presupuesto", "pedido": args,
                     "resultado": H.ejecutar("armar_presupuesto", args,
                                             tienda_id)})
    return declarado, llamadas


def correr_codigo(tienda_id: str = TIENDA) -> dict:
    """La vara de codigo: se corren las reparaciones del hub sobre las llamadas
    ideales y se mide el material que le queda al modelo para redactar."""
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.core import hub_venta as HV
    from app.core import resolver as R

    declarado, llamadas = _llamadas_ideales(tienda_id)
    llamadas = R._cuenta_con_lo_declarado(llamadas, declarado, tienda_id, "obj")
    llamadas = R._reparto_de_pago_declarado(llamadas, declarado, tienda_id,
                                            "obj")
    llamadas = R._supuesto_de_pago(llamadas, declarado, tienda_id, "obj")
    llamadas = R._bloques_a_uno(llamadas, "obj")

    cuenta = next((l for l in llamadas
                   if l.get("herramienta") == "armar_presupuesto"), {})
    bloque = (cuenta.get("resultado") or {}).get("bloque") or ""
    hallazgo = HV._bloque_hallazgo(llamadas) or next(
        ((l.get("resultado") or {}).get("bloque") or "" for l in llamadas
         if l.get("herramienta") == "buscar_productos"
         and (l.get("resultado") or {}).get("bloque")), "")
    # El texto que se evalua es lo que el CODIGO le entrega escrito al modelo:
    # es el piso de lo que el cliente puede llegar a leer. La contradiccion no
    # esta en un bloque, viaja como obligacion de preguntar.
    from app.core import pedido as P
    rec = P.reconciliar(declarado, llamadas, "obj")
    material = "\n".join([hallazgo, bloque, P.instruccion_de_preguntas(rec)])
    est = medir_estado(bloque, cuenta.get("pedido") or {})
    com = medir_comunicacion(material)
    return {"modo": "codigo", "estado": est, "comunicacion": com,
            "nota": nota(est, com), "bloque": bloque, "hallazgo": hallazgo,
            "faltantes": rec.get("faltantes") or []}


# ── LA CORRIDA VIVA: las cinco redacciones por el camino del webhook ────────
def correr_vivo(tienda_id: str = TIENDA, repeticiones: int = 3) -> dict:
    """LA VARA VIVA, Y POR QUE SE REPITE.

    LA TRAMPA, medida el 7-ago y casi me la como. Con UNA corrida por redaccion
    el promedio dio 33 y despues 47, y parecia una mejora de catorce puntos.
    Mirando celda por celda: la redaccion textual de Martin dio 12 y despues
    100; la tercera dio 62 y despues 12. **El ruido entre corridas es mas
    grande que la diferencia que se queria medir.** Ese 47 no significaba nada.

    Es exactamente el error que este chat pago dos veces en el dia: dar algo
    por bueno con una sola prueba. Con el modelo de por medio, una corrida no
    es una medicion, es una anecdota. Por eso se repite y se reporta el
    promedio, el minimo y el maximo: el minimo es el que manda para vender,
    porque es lo que le puede tocar a un cliente real.

    tau-bench hace lo mismo y por lo mismo: su resultado principal se replica
    sobre un set de quince semillas distintas antes de afirmar nada.
    """
    import asyncio
    import os
    # LA CLAVE LA ELIGE UN SOLO LUGAR: `clon_produccion.preparar_entorno`,
    # que desde el 4-ago tiene el default en la GRATIS y pide
    # BANCO_CLAVE_PAGA=true para gastar. Aca habia dos lineas que la
    # pisaban con la paga ANTES de que esa guarda corriera, asi que la
    # guarda veia la paga puesta, decidia que "no hay clave gratis
    # distinta" y la dejaba. La regla existia y cuatro scripts la
    # esquivaban: la misma falla que este repo ya pago dos veces, una
    # regla escrita en dos lados que quedaron distintas.
    from banco_pruebas import clon_produccion as clon
    clon.instalar()

    from app.core import llm_reintento as LR

    filas, invalidas = [], 0
    for nombre, msg in VARIANTES.items():
        notas, corridas = [], []
        for i in range(max(1, repeticiones)):
            usuario = f"objetivo_{nombre}_{i}"
            clon.reiniciar_cliente(usuario)
            # EL CUPO SE MIDE POR TURNO. Si el proveedor nego la llamada, esta
            # corrida no probo el codigo: no se puntua, se descarta. Ver el
            # comentario largo en `app/core/llm_reintento.py`.
            LR.reiniciar_cupo()
            partes = asyncio.get_event_loop().run_until_complete(
                clon.turno(usuario, msg))
            texto = "\n".join(partes)
            cupo = LR.sin_cupo()
            if cupo["veces"]:
                invalidas += 1
                corridas.append({"invalida": True, "largo": len(texto),
                                 "texto": texto, "motivo": cupo["ultimo"],
                                 "estado": [], "comunicacion": [],
                                 "nota": {"nota": None}})
                continue
            # El estado se lee del texto final: es lo unico que el cliente ve.
            est = medir_estado(texto, _cuenta_del_texto(texto))
            com = medir_comunicacion(texto, msg)
            n = nota(est, com)
            notas.append(n["nota"])
            corridas.append({"nota": n, "estado": est, "comunicacion": com,
                             "largo": len(texto), "texto": texto,
                             "invalida": False})
        validas = [c for c in corridas if not c.get("invalida")]
        filas.append({"variante": nombre, "corridas": corridas,
                      "medidas": len(validas), "de": len(corridas),
                      "prom": round(sum(notas) / len(notas)) if notas else None,
                      "min": min(notas) if notas else None,
                      "max": max(notas) if notas else None,
                      "largo": (round(sum(c["largo"] for c in validas)
                                      / len(validas)) if validas else None)})
    con_nota = [f for f in filas if f["prom"] is not None]
    prom = (round(sum(f["prom"] for f in con_nota) / len(con_nota))
            if con_nota else None)
    peor = min((f["min"] for f in con_nota), default=None)
    return {"modo": "vivo", "variantes": filas, "repeticiones": repeticiones,
            "invalidas": invalidas,
            "nota": {"nota": prom, "peor": peor}}


def _cuenta_del_texto(texto: str) -> dict:
    """Reconstruye los items y el pago desde el bloque que salio, para poder
    medir el estado sobre el mensaje real. Solo lee lo que el codigo escribio:
    los renglones tienen forma fija."""
    import re
    items = []
    for m in re.finditer(r"(?im)^\s*-\s*(\d+)x\s", texto or ""):
        items.append({"cantidad": int(m.group(1)), "destino": ""})
    # el reparto de destinos lo escribe el codigo en su propio bloque
    if re.search(r"(?i)reparto de los envios", texto or ""):
        for it in items:
            it["destino"] = "declarado"
    pago = []
    for m in re.finditer(r"(?im)^\s*-\s*(transferencia|mercado pago)\s*\((\d+)%",
                         texto or ""):
        pago.append({"medio": m.group(1), "porcentaje": float(m.group(2))})
    return {"items": items, "pago": pago}


# ── EL DOCUMENTO, GENERADO ──────────────────────────────────────────────────
_ENCABEZADO = """# EL OBJETIVO, Y SI LLEGAMOS

> **ESTE ARCHIVO LO GENERA `banco_pruebas/objetivo.py`. No se edita a mano.**
> Un documento escrito a mano miente a la sesión siguiente; uno calculado no
> puede. Para moverlo, se cambia el código y se vuelve a correr.

## El objetivo

{objetivo}

## Cómo se mide, y por qué así

Copiado de **τ-bench**, el banco público de agentes de atención al cliente de
Sierra, que está probado:

1. **ESTADO FINAL** — qué quedó en la cuenta, no qué pasos se dieron. Cualquier
   camino que llegue al mismo estado pasa.
2. **COMUNICACIÓN** — ¿están las frases que sí o sí había que decir, y no están
   las que no se pueden decir?
3. **LA NOTA ES EL PRODUCTO DE LAS DOS.** Una cuenta perfecta que no dice lo que
   había que decir vale cero, y un mensaje lindo con la cuenta mal, también.
   **No se gana hablando.**

Y se mide sobre **varias redacciones** de la misma pregunta, no una. Ésa es la
falla que más costó: el reparto de pago se arregló leyendo `70/30` y se cayó con
`setenta treinta`, que es como lo escribió Martín.

```bash
python3 banco_pruebas/objetivo.py            # la nota de código, gratis
python3 banco_pruebas/objetivo.py --vivo     # las redacciones, con el modelo
python3 banco_pruebas/objetivo.py --anotar "qué cambié"
```
"""


def _tabla(res: dict) -> str:
    lineas = ["| vara | resultado |", "|---|---|"]
    if res["modo"] == "codigo":
        n = res["nota"]
        lineas.append(f"| estado final | {n['estado']} |")
        lineas.append(f"| comunicación | {n['comunicacion']} |")
        lineas.append(f"| **NOTA** | **{n['nota']}/100** |")
        lineas.append("")
        lineas.append("**Lo que falla hoy:**")
        malas = [f"- `{k}` — {d}" for k, ok, d in
                 (res["estado"] + res["comunicacion"]) if not ok]
        lineas += malas or ["- nada: la vara de código está en verde."]
    else:
        r = res.get("repeticiones", 1)
        lineas = [f"| redacción | promedio de {r} | peor | mejor | largo |",
                  "|---|---|---|---|---|"]
        def _v(x):
            return "sin medir" if x is None else x
        for f in res["variantes"]:
            marca = ("" if f.get("medidas") == f.get("de")
                     else f" — {f.get('medidas')} de {f.get('de')} medidas")
            lineas.append(f"| {f['variante']} | **{_v(f['prom'])}**{marca} | "
                          f"{_v(f['min'])} | {_v(f['max'])} | {_v(f['largo'])} |")
        lineas.append(f"\n**Promedio: {_v(res['nota']['nota'])}/100 — "
                      f"PEOR CASO: {_v(res['nota']['peor'])}/100**")
        # LA CORRIDA QUE EL PROVEEDOR NEGO NO ES UN CERO: NO SE MIDIO.
        if res.get("invalidas"):
            lineas.append(
                f"\n> ⚠️ **{res['invalidas']} corridas quedaron SIN MEDIR** "
                f"porque el proveedor negó la llamada por cuota. No cuentan "
                f"como nota. Si son muchas, el número de arriba vale poco: "
                f"conseguí cupo y volvé a correr.")
        lineas.append("\nEl que manda para vender es el PEOR, no el promedio: "
                      "es el que le puede tocar a un cliente real.")
        # QUE FALLA, NO SOLO CUANTO. La vara viva daba el numero y nada mas, y
        # el 9-ago costo una corrida entera de la clave paga -diez minutos- solo
        # para enterarse de en que se pierde. Se cuenta cada vara por las
        # cuentas en que fallo, sobre el total de corridas: la que aparece en
        # las quince es un defecto del sistema, la que aparece en una es ruido
        # del modelo, y esa diferencia es la que dice donde conviene tocar.
        conteo: dict = {}
        total = 0
        for f in res["variantes"]:
            for c in f["corridas"]:
                if c.get("invalida"):
                    continue
                total += 1
                for nombre, ok, _ in c["estado"] + c["comunicacion"]:
                    if not ok:
                        conteo[nombre] = conteo.get(nombre, 0) + 1
        if conteo and total:
            lineas.append(f"\n**Lo que falla, sobre {total} corridas medidas:**")
            for nombre, veces in sorted(conteo.items(), key=lambda x: -x[1]):
                lineas.append(f"- {veces}/{total} — {nombre}")
    return "\n".join(lineas)


def escribir(res: dict, anotar: str = "") -> None:
    previo = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
    hist = ""
    if "## Historial" in previo:
        hist = previo.split("## Historial", 1)[1]
    hist = hist.strip() or ("\n| fecha | vara | nota | qué se cambió |\n"
                            "|---|---|---|---|")
    if anotar:
        hist += (f"\n| {date.today().isoformat()} | {res['modo']} | "
                 f"{res['nota']['nota']} | {anotar} |")
    bifur = ""
    if "## Bifurcaciones abiertas" in previo:
        bifur = previo.split("## Bifurcaciones abiertas", 1)[1]
        bifur = bifur.split("## Historial", 1)[0].strip()
    DOC.write_text(
        _ENCABEZADO.format(objetivo=OBJETIVO)
        + f"\n## La medición de hoy — vara `{res['modo']}`\n\n"
        + _tabla(res)
        + "\n\n## Bifurcaciones abiertas\n\n"
        + (bifur or "_Cuando aparezcan dos caminos, se anotan acá con su razón "
                    "y su costo, para que la sesión siguiente no los vuelva a "
                    "descubrir._")
        + "\n\n## Historial\n\n" + hist + "\n", encoding="utf-8")


def main(argv: list) -> int:
    vivo = "--vivo" in argv
    anotar = ""
    if "--anotar" in argv:
        i = argv.index("--anotar")
        anotar = argv[i + 1] if len(argv) > i + 1 else "sin nota"
    reps = 3
    if "--repeticiones" in argv:
        reps = int(argv[argv.index("--repeticiones") + 1])
    res = correr_vivo(repeticiones=reps) if vivo else correr_codigo()
    print("=" * 78)
    print(f"OBJETIVO — vara {res['modo']}")
    print("=" * 78)
    print(_tabla(res))
    print("=" * 78)
    escribir(res, anotar)
    print(f"escrito en {DOC.relative_to(_RAIZ)}")
    if vivo:
        # LA PEOR CORRIDA DE CADA REDACCION, GUARDADA. El numero dice cuanto se
        # pierde y el conteo dice en que; para saber POR QUE hay que leer el
        # mensaje que le llego al cliente, y hasta hoy eso vivia diez minutos en
        # una terminal y se perdia. La PEOR y no todas: es la que le puede tocar
        # a un cliente real, y quince textos enteros no los lee nadie.
        import datetime
        d = _RAIZ / "banco_pruebas" / "corridas"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{datetime.datetime.now():%Y%m%d_%H%M}_objetivo.md"
        partes = [f"# La peor corrida de cada redaccion\n\n{_tabla(res)}\n"]
        for fila in res["variantes"]:
            medidas = [c for c in fila["corridas"] if not c.get("invalida")]
            if not medidas:
                partes.append(f"\n## {fila['variante']} — SIN MEDIR: el "
                              f"proveedor negó todas las llamadas por cuota\n")
                continue
            peor = min(medidas, key=lambda c: c["nota"]["nota"])
            fallas = [n for n, ok, _ in peor["estado"] + peor["comunicacion"]
                      if not ok]
            partes.append(f"\n## {fila['variante']} — {peor['nota']['nota']}"
                          f"/100, {peor['largo']} caracteres\n\n"
                          f"**Falla:** {', '.join(fallas) or 'nada'}\n\n"
                          f"```\n{peor['texto']}\n```\n")
        f.write_text("\n".join(partes), encoding="utf-8")
        print(f"la peor de cada una, en {f.relative_to(_RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
