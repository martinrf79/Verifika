"""V2: el idioma de comandos. El modelo escribe un renglon por cosa pedida, como lo hizo solo en la entrevista; el codigo
lo pasa a la agenda de `flujo/agenda.py` sin interpretar nada, y el ejecutor de hoy la cumple."""
import json
import re

import contexto
import pistas as P
from app.core.flujo import agenda as A
from app.core.flujo import interprete as I

CONSIGNA = """Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente: traducis su ULTIMO
MENSAJE en comandos para el codigo de la tienda, y el codigo responde cada uno con datos exactos. El codigo no razona: hace
exactamente lo que dice cada comando, nada mas.

COMO SE HACE:
1. Corta el ULTIMO MENSAJE entero, en su orden, en las cosas que pide, pregunta, decide o dice. Cada una es un renglon con
   UN comando. Todo el mensaje queda citado, tambien los saludos.
2. Cada renglon: numero, comando, sus datos campo="valor", y al final | "las palabras literales del cliente".
3. Lo que senala de la charla va con el numero de la LIBRETA: M-2, L-1. Si contesta lo que pregunto el vendedor, el
   renglon lleva responde="R-1".
4. Lo que depende de otro renglon —"si no hay", "si anda", "si sale menos de"— lleva si="n:si" o si="n:no", con el numero
   del renglon del que depende.
5. Lo que el codigo contesto a tus pistas dice que es cada cosa y que comando la toma. Usalo.
6. Nunca escribas un precio ni un dato de la tienda que el cliente no dijo: el codigo los busca.

LOS COMANDOS:
BUSCAR rubro="" cantidad="" orden="" condiciones="" entre_lo_mostrado="si"
   productos sin modelo concreto, uno por rubro. orden: "mas barato", "mas caro", "mas <dato>" o "nada". condiciones en
   palabras del cliente, separadas por ";": marca, color, precio por unidad, "que no sea X". Las exclusiones de la libreta
   van en cada busqueda. entre_lo_mostrado si elige entre lo ya mostrado.
PRODUCTO producto="" quiere_saber="" color="" afirma=""
   un modelo concreto: lo que dijo, o el numero de la libreta, "M-2". Si lo que senala puede ser varios, la lista:
   producto="[M-1, M-2]", y el codigo pregunta cual. quiere_saber: precio, stock o el dato que pide.
ENVIO destino=""
   cotizar el envio a UN lugar. Dos lugares, dos renglones.
CUENTA tope="" si_pasa="" reparto=""
   sumar: el total, "cuanto sale todo", "con envio", un presupuesto. tope: un monto del total. reparto: "medio porcentaje;
   medio porcentaje", sin medio "sin decir".
POLITICA tema="" afirma=""
   SOLO una regla de la tienda que pregunta: factura, garantia, cuotas, promociones. tema de la lista de TEMAS.
COMPATIBILIDAD producto="" con="" falta_modelo="si"
   si un producto anda con algo. falta_modelo si es un equipo suyo sin modelo, "mi notebook".
AGREGAR producto="" cantidad="" color="" destino=""
   lo que decide llevar: un modelo, un "M-2", un rubro o "los otros". Un renglon por producto y destino.
SACAR renglon="L-1"  |  CAMBIAR renglon="L-1" y producto, cantidad, color o destino  |  CONFIRMAR renglon="L-2"  |
ACEPTAR renglon="L-2"  |  TOTAL cantidad=""  |  REEMPLAZAR
   cambios a un pedido que YA esta en la LIBRETA, BORRADOR. CONFIRMAR si dice que si a lo que falta confirmar, ACEPTAR si
   acepta lo SUPUESTO, TOTAL si dice cuantos son, REEMPLAZAR si rehace el pedido entero y los AGREGAR son como queda.
EXPLICAR pregunta=""
   saber general de tecnologia, no de la tienda.
OTRO que=""
   lo que no pide nada al codigo: saludo, dato, corrige —lo que retira en el mensaje—, humano, fuera_de_tema, catalogo.
CLIENTE es="" nombre="" localidad="" equipo=""
   lo que dice de si mismo, sin numero de renglon.

RUBROS: {rubros}
TEMAS: {temas}

Devolve SOLO los renglones, sin explicaciones.

EJEMPLOS:
{ejemplos}"""

_CAMPOS = re.compile(r'(\w+)\s*=\s*("[^"]*"|\[[^\]]*\]|\S+)')
_RENGLON = re.compile(r'^\s*(\d+)\s*[.)-]?\s*([A-Za-z_]+)\b(.*)$')


def _v(x: str):
    x = x.strip()
    return x[1:-1].strip() if len(x) > 1 and x[0] == '"' and x[-1] == '"' else x


def _lista(x: str):
    x = _v(x)
    if x.startswith("[") and x.endswith("]"):
        return [p.strip().strip('"') for p in x[1:-1].split(",") if p.strip()]
    return x


def _reparto(x: str) -> list:
    out = []
    for parte in re.split(r"[;,]", _v(x)):
        m = re.match(r"\s*(.*?)\s*(\d{1,3})\s*%?\s*$", parte) or re.match(r"\s*(\d{1,3})\s*%?\s*(.*)$", parte)
        if not m:
            continue
        a, b = m.groups()
        medio, pct = (a, b) if b.isdigit() else (b, a)
        out.append({"medio": medio.strip() or "sin decir", "porcentaje": int(pct)})
    return out


def _entero(x):
    m = re.search(r"\d+", str(x))
    return int(m.group()) if m else x


def a_agenda(texto: str) -> dict:
    preguntas, cliente = [], {}
    for linea in texto.splitlines():
        cita = ""
        if "|" in linea:
            linea, cita = linea.rsplit("|", 1)
            cita = cita.strip().strip('"').strip()
        m = _RENGLON.match(linea)
        com = m.group(2).upper() if m else (linea.strip().split() or [""])[0].upper()
        resto = m.group(3) if m else linea.strip()[len(com):]
        d = {k.lower(): v for k, v in _CAMPOS.findall(resto)}
        if com == "CLIENTE":
            cliente.update({k: _v(v) for k, v in d.items() if _v(v)})
            continue
        if not m:
            continue
        p = {"n": int(m.group(1)), "cita": cita}
        if com == "BUSCAR":
            p.update(accion="buscar", rubro=_v(d.get("rubro", "")), cantidad=_entero(_v(d.get("cantidad", "1")) or 1),
                     orden=_v(d.get("orden", "nada")) or "nada",
                     condiciones=[c.strip() for c in _v(d.get("condiciones", "")).split(";") if c.strip()],
                     entre_lo_mostrado=_v(d.get("entre_lo_mostrado", "")).lower() in ("si", "true"))
        elif com == "PRODUCTO":
            p.update(accion="producto", producto=_lista(d.get("producto", "")),
                     quiere_saber=_v(d.get("quiere_saber", "precio")) or "precio")
            for k in ("color", "afirma"):
                if _v(d.get(k, "")):
                    p[k] = _v(d[k])
        elif com == "ENVIO":
            p.update(accion="envio", destino=_v(d.get("destino", "")))
        elif com == "CUENTA":
            p["accion"] = "cuenta"
            if _v(d.get("tope", "")):
                p["tope"] = _v(d["tope"])
            if _v(d.get("si_pasa", "")):
                p["si_pasa"] = _v(d["si_pasa"])
            if _v(d.get("reparto", "")):
                p["reparto"] = _reparto(d["reparto"])
        elif com == "POLITICA":
            p.update(accion="politica", tema=_v(d.get("tema", "")))
            if _v(d.get("afirma", "")):
                p["afirma"] = _v(d["afirma"])
        elif com == "COMPATIBILIDAD":
            p.update(accion="compatibilidad", producto=_v(d.get("producto", "")), con=_v(d.get("con", "")),
                     falta_modelo=_v(d.get("falta_modelo", "")).lower() in ("si", "true"))
        elif com == "AGREGAR":
            a = {k: _v(d[k]) for k in ("producto", "color", "destino") if _v(d.get(k, ""))}
            if _v(d.get("cantidad", "")):
                a["cantidad"] = _entero(_v(d["cantidad"]))
            p.update(accion="comprar", agrega=[a])
        elif com in ("SACAR", "CONFIRMAR", "ACEPTAR"):
            clave = {"SACAR": "saca", "CONFIRMAR": "confirma", "ACEPTAR": "acepta"}[com]
            r = _lista(d.get("renglon", ""))
            p.update(accion="comprar", **{clave: r if isinstance(r, list) else [r]})
        elif com == "CAMBIAR":
            c = {"es": _v(d.get("renglon", ""))}
            c.update({k: _v(d[k]) for k in ("producto", "color", "destino") if _v(d.get(k, ""))})
            if _v(d.get("cantidad", "")):
                c["cantidad"] = _entero(_v(d["cantidad"]))
            p.update(accion="comprar", cambia=[c])
        elif com == "TOTAL":
            p.update(accion="comprar", total=_entero(_v(d.get("cantidad", ""))))
        elif com == "REEMPLAZAR":
            p.update(accion="comprar", reemplaza=True, agrega=[])
        elif com == "EXPLICAR":
            p.update(accion="explicar", pregunta=_v(d.get("pregunta", "")) or cita)
        elif com == "OTRO":
            p.update(accion="otro", que=_v(d.get("que", "")) or "dato")
        else:
            continue
        if _v(d.get("si", "")):
            s = re.match(r"(\d+)\s*[:=,]?\s*(si|no)", _v(d["si"]).lower())
            if s:
                p["si"] = {"de": int(s.group(1)), "da": s.group(2)}
        if _v(d.get("responde", "")):
            p["responde"] = _v(d["responde"])
        preguntas.append(p)
    # Varios renglones de compra con el mismo numero son una sola pregunta: "un auricular a Rosario y lo demas a Mendoza".
    juntas = []
    for p in preguntas:
        prev = juntas[-1] if juntas else None
        if prev and p["accion"] == "comprar" == prev["accion"] and p["n"] == prev["n"]:
            for k in ("agrega", "saca", "confirma", "acepta", "cambia"):
                if p.get(k):
                    prev[k] = (prev.get(k) or []) + p[k]
            for k in ("total", "reemplaza", "si", "responde"):
                if p.get(k):
                    prev[k] = p[k]
        else:
            juntas.append(p)
    preguntas = juntas
    # REEMPLAZAR: los AGREGAR del mensaje son como queda el pedido.
    if any(p.get("reemplaza") for p in preguntas):
        r = next(p for p in preguntas if p.get("reemplaza"))
        for p in [p for p in preguntas if p.get("agrega") and p is not r]:
            r["agrega"] += p["agrega"]
            preguntas.remove(p)
    return {"preguntas": preguntas, "cliente": cliente}


def a_comandos(ag: dict) -> str:
    """Una agenda de los ejemplos, escrita en comandos."""
    out = []
    q = lambda v: "[" + ", ".join(v) + "]" if isinstance(v, list) else str(v)  # noqa: E731
    for p in ag["preguntas"]:
        a, extra = p["accion"], ""
        if p.get("si"):
            extra += f' si="{p["si"]["de"]}:{p["si"]["da"]}"'
        if p.get("responde"):
            extra += f' responde="{p["responde"]}"'
        cita = f' | "{p.get("cita", "")}"'
        n = p["n"]
        if a == "buscar":
            out.append(f'{n}. BUSCAR rubro="{p["rubro"]}" cantidad="{p.get("cantidad", 1)}" orden="{p.get("orden", "nada")}"'
                       + (f' condiciones="{"; ".join(p["condiciones"])}"' if p.get("condiciones") else "") + extra + cita)
        elif a == "producto":
            out.append(f'{n}. PRODUCTO producto="{q(p["producto"])}" quiere_saber="{p.get("quiere_saber", "precio")}"'
                       + "".join(f' {k}="{p[k]}"' for k in ("color", "afirma") if p.get(k)) + extra + cita)
        elif a == "envio":
            out.append(f'{n}. ENVIO destino="{p["destino"]}"' + extra + cita)
        elif a == "cuenta":
            r = "; ".join(f'{x["medio"]} {x["porcentaje"]}' for x in p.get("reparto") or [])
            out.append(f'{n}. CUENTA' + (f' reparto="{r}"' if r else "") + extra + cita)
        elif a == "politica":
            out.append(f'{n}. POLITICA tema="{p["tema"]}"' + (f' afirma="{p["afirma"]}"' if p.get("afirma") else "")
                       + extra + cita)
        elif a == "explicar":
            out.append(f'{n}. EXPLICAR pregunta="{p["pregunta"]}"' + extra + cita)
        elif a == "otro":
            out.append(f'{n}. OTRO que="{p["que"]}"' + extra + cita)
        elif a == "comprar":
            subs = []
            for x in p.get("agrega") or []:
                subs.append("AGREGAR " + " ".join(f'{k}="{x[k]}"' for k in ("producto", "cantidad", "color", "destino")
                                                  if k in x))
            for x in p.get("saca") or []:
                subs.append(f'SACAR renglon="{x}"')
            for x in p.get("confirma") or []:
                subs.append(f'CONFIRMAR renglon="{x}"')
            if p.get("total"):
                subs.append(f'TOTAL cantidad="{p["total"]}"')
            for i, s in enumerate(subs):
                out.append(f'{n}. {s}' + extra + cita)
    for k, v in (ag.get("cliente") or {}).items():
        out.append(f'CLIENTE {k}="{v}"')
    return "\n".join(out)


def consigna(tienda_id: str) -> str:
    from app.core import agente
    ix = agente.indice(tienda_id)
    ejs = "\n\n".join(f"{i}. {lib}\nULTIMO MENSAJE: {msg}\nCOMANDOS:\n{a_comandos(sal)}"
                      for i, (lib, msg, _t, sal) in enumerate(I.EJEMPLOS, 1))
    return CONSIGNA.format(rubros=", ".join(sorted(ix["rubros"])), temas=", ".join(ix["temas"]), ejemplos=ejs)


DEVUELTA = """Revisa tus comandos antes de que los use el codigo:
{faltas}
Devolve todos los renglones de nuevo, con la misma forma."""


def instalar():
    async def interpretar(mensaje, historial, estado, tienda_id, trace_id=""):
        hay = bool([m for m in historial if m.get("role") == "user"])
        respuestas = P.contestar(P.paso1(mensaje, hay), estado)
        msgs = [{"role": "system", "content": consigna(tienda_id)},
                {"role": "user", "content": I.libreta(estado, historial, tienda_id) + "\n" + respuestas
                 + f"\nULTIMO MENSAJE: {mensaje}"}]
        try:
            crudo, uso = contexto.llamar(msgs)
            P.USO.append({"paso": 2, **uso})
            salida = a_agenda(crudo)
            faltas = A.faltas(mensaje, salida, set(I.numeros(estado)))
            if faltas:
                crudo2, uso = contexto.llamar(msgs + [{"role": "assistant", "content": crudo},
                                                      {"role": "user", "content": DEVUELTA.format(faltas="\n".join(faltas))}])
                P.USO.append({"paso": 3, **uso})
                salida = a_agenda(crudo2) if a_agenda(crudo2)["preguntas"] else salida
                crudo = crudo + "\n---DEVUELTA---\n" + crudo2
        except Exception as e:  # noqa: BLE001
            print("V2 error", type(e).__name__, str(e)[:200], flush=True)
            return None
        salida["_crudo"] = crudo
        return salida
    I.interpretar = interpretar
