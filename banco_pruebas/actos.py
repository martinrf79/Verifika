"""EL ACTO DE CADA PARTE — que quiere hacer el cliente con cada cosa, paso 3 del plan de Martin (23-oct-2026).

Lo que toca de la tienda ya lo encuentra la busqueda por significado, `cobertura_capas.py`. Lo que falta es el acto:
si lo lleva, mira, pregunta, cambia, saca, o si depende de otra parte. Ahi estuvieron 10 de los 12 turnos mal de las 48.

El modelo de produccion separa con el numero primero y le pone a cada parte un acto de una lista cerrada, de que otra
parte depende y la cantidad en palabras. Lo correcto es el `oro` de `pregunta_razonada/fichas.py`, escrito antes, con
sus tipos llevados a los actos. Dos variantes: sin ejemplos, y con pares de ejemplos de borde, frases nuevas que no son
de las 48, que van todos siempre.

Por turno: BIEN si los actos que pide la vara son los que puso el modelo, sin faltar ni sobrar; y aparte, si marca la
dependencia donde la vara dice que algo depende de otra cosa.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.20 python3 banco_pruebas/actos.py [--ver] [--sin-ejemplos] [--unida]
"""
import asyncio
import collections
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "pedido_documento"))
import medir_pedido as P  # noqa: E402  — el entorno, la clave y el estado de cada turno
from banco_pruebas import libro_paga  # noqa: E402
from app.core import agente  # noqa: E402
from app.core.flujo import interprete  # noqa: E402
from experimento import limpio  # noqa: E402
from fichas import CHARLAS  # noqa: E402

TOPE = float(os.environ.get("TOPE_CORRIDA", "0.20"))
UNIR = "--unida" in sys.argv

ACTOS = {
    "lleva": "decide comprar algo nuevo: lo suma al pedido",
    "mira": "quiere ver opciones de una clase de producto, sin decidir todavia",
    "pregunta_dato": "pregunta un dato de un producto: precio, stock, si hay cantidad, una caracteristica",
    "compara": "compara dos o mas productos por algo",
    "compatibilidad": "pregunta si un producto anda con algo que tiene",
    "cambia": "cambia algo de lo que ya esta en el pedido: producto, cantidad, color, destino, o el criterio de todo",
    "saca": "saca algo del pedido",
    "envio": "pregunta cuanto sale o tarda mandar a un lugar",
    "paga": "dice como paga, cuanto quiere gastar como maximo o pide el total",
    "regla_tienda": "pregunta como trabaja la tienda: cuotas, garantia, factura, descuentos, retiro",
    "saber_general": "pregunta algo de tecnologia en general, que no depende de la tienda",
    "dato_cliente": "dice algo de si mismo: su nombre, su localidad",
    "nada": "no pide ni pregunta nada: saluda, agradece, confirma sin cambiar nada",
}
# Los tipos del oro, en actos. ORD es "todo lo mas barato": cambia el criterio del pedido.
DEL_ORO = {"AG": "lleva", "B": "mira", "P": "pregunta_dato", "CMP": "compara", "CO": "compatibilidad", "CA": "cambia",
           "ORD": "cambia", "SA": "saca", "E": "envio", "CU": "paga", "PO": "regla_tienda", "EX": "saber_general",
           "CL": "dato_cliente", "NADA": "nada"}

# LO QUE TAMBIEN VALE, regla de Martin del 23-oct: si lo que dice el modelo se responde con la fuente, no alucina y no va
# contra vender, se toma. Solo los cuatro casos que reviso; el resto de la vara queda como estaba.
TAMBIEN = {
    ("S15", 1): [{"lleva", "envio"}],                                  # "¿cuanto tarda a Tucuman?" como envio
    ("S13", 0): [{"pregunta_dato"}],                                    # "precio de cuatro mouse" como pregunta de precio
    ("S09", 0): [{"pregunta_dato", "regla_tienda"}],
    ("S14", 2): [{"dato_cliente", "cambia"}],                           # "otro pendrive igual" como cambio del renglon
    ("S07", 2): [{"compatibilidad", "dato_cliente", "lleva"}],          # "si sirven, cerramos": compra que depende
}

# Pares de borde: la misma forma, otro acto. Frases nuevas, no de las 48.
EJEMPLOS = [
    ("quiero tres K120", "lleva", ""), ("¿te quedan tres K120?", "pregunta_dato", ""),
    ("armame el presupuesto con dos monitores", "lleva", ""), ("mostrame monitores hasta 200 mil", "mira", ""),
    ("sumame otro igual al que ya tengo", "cambia", "uno mas"), ("sumame un mouse", "lleva", ""),
    ("el teclado mejor en blanco", "cambia", ""), ("¿el teclado viene en blanco?", "pregunta_dato", ""),
    ("si viene en blanco, llevo ese", "lleva", "depende"), ("¿viene en blanco?", "pregunta_dato", ""),
    ("sacá los auriculares", "saca", ""), ("¿los auriculares son inalambricos?", "pregunta_dato", ""),
    ("pasá todo a lo mas barato", "cambia", ""), ("¿cual es el mas barato de estos dos?", "compara", ""),
    ("lo de Rosario mandalo a Paraná", "cambia", ""), ("¿cuanto sale mandar a Paraná?", "envio", ""),
    ("no quiero gastar mas de 300 mil", "paga", ""), ("¿tienen cuotas sin interes?", "regla_tienda", ""),
    ("¿anda con mi iPad?", "compatibilidad", ""), ("¿que conviene, mecanico o de membrana?", "saber_general", ""),
    ("soy Laura, de Mendoza", "dato_cliente", ""), ("dale, gracias", "nada", ""),
]

CONSIGNA = """Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. Con la
LIBRETA de la charla y el ULTIMO MENSAJE, llena esta ficha en JSON:
{{
  "numero": cuantas cosas pide o pregunta el cliente en este mensaje,
  "partes": una por cada cosa, en su orden: [{{"texto": la parte dicha simple, con los modelos y marcas tal cual,
     "acto": uno de la lista, "depende_de": el numero de la parte de la que depende, 0 si no depende de nada,
     "cantidad": la cantidad con las palabras del cliente, "" si no dice}}]
}}
Los destinos, el color y las condiciones son detalles de su parte, no partes aparte.
ACTOS, uno por parte:
{actos}{ejemplos}"""


# LA CONSIGNA UNIDA: el acto, los nombres de la tienda con los modelos tal cual, y el destino como campo de la parte.
UNIDA = """
Cada parte nombra lo que pide o pregunta con el nombre que usa la tienda, si es uno de estos:
- productos: {rubros}
- temas de la tienda: {temas}
Un modelo, una marca o un producto concreto que nombra el cliente se copia TAL CUAL lo escribio, con sus errores.
A donde va cada cosa se pone en "destino" de su parte: un destino nunca es una parte."""


def consigna_unida() -> str:
    i = agente.indice(P.TID)
    return consigna(True) + UNIDA.format(rubros=", ".join(sorted(i["rubros"])),
                                         temas=", ".join(t.replace("_", " ") for t in i["temas"]))


def formato_unido() -> dict:
    import copy
    f = copy.deepcopy(FORMATO)
    item = f["json_schema"]["schema"]["properties"]["partes"]["items"]
    item["properties"]["destino"] = {"type": "string"}
    item["required"].append("destino")
    return f


def consigna(con_ejemplos: bool) -> str:
    ej = "\nEJEMPLOS, de a pares que se parecen y son otro acto:\n" + "\n".join(
        f'- "{t}" -> {a}' + (f" ({c})" if c else "") for t, a, c in EJEMPLOS) if con_ejemplos else ""
    return CONSIGNA.format(actos="\n".join(f"- {a}: {d}" for a, d in ACTOS.items()), ejemplos=ej)


FORMATO = {"type": "json_schema", "json_schema": {"name": "actos", "schema": {
    "type": "object", "required": ["numero", "partes"], "properties": {
        "numero": {"type": "integer"},
        "partes": {"type": "array", "items": {"type": "object", "required": ["texto", "acto", "depende_de", "cantidad"],
                                              "properties": {"texto": {"type": "string"},
                                                             "acto": {"type": "string", "enum": list(ACTOS)},
                                                             "depende_de": {"type": "integer"},
                                                             "cantidad": {"type": "string"}}}}}}}}


async def leer(tu: dict, con_ejemplos: bool) -> dict:
    estado, historial = P.estado_de(tu["mem"])
    if UNIR:
        msgs = [{"role": "system", "content": consigna_unida()},
                {"role": "user", "content": interprete.libreta(estado, historial, P.TID)
                 + f"\nULTIMO MENSAJE: {limpio(tu['msg'])}"}]
        return interprete._json(await interprete._pedir(msgs, "actos", formato_unido()))
    msgs = [{"role": "system", "content": consigna(con_ejemplos)},
            {"role": "user", "content": interprete.libreta(estado, historial, P.TID)
             + f"\nULTIMO MENSAJE: {limpio(tu['msg'])}"}]
    return interprete._json(await interprete._pedir(msgs, "actos", FORMATO))


def main() -> None:
    ver = "--ver" in sys.argv
    con = "--sin-ejemplos" not in sys.argv
    desde = libro_paga.gastado(libro_paga._hoy())
    cuenta, por_acto, dep = collections.Counter(), collections.Counter(), collections.Counter()
    for ch in CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                print(f"TOPE de la corrida: {TOPE} dolares")
                break
            oro = [x for x in tu["oro"] if not x.get("opt")]
            quiere = {DEL_ORO[x["tipo"]] for x in oro}
            r = asyncio.run(leer(tu, con))
            partes = [p for p in r.get("partes") or [] if isinstance(p, dict)]
            puso = {p.get("acto") for p in partes}
            bien = puso == quiere or puso in TAMBIEN.get((ch["id"], i), [])
            cuenta["BIEN" if bien else "MAL"] += 1
            for a in quiere:
                por_acto[(a, "esta" if a in puso else "falta")] += 1
            for a in puso - quiere:
                por_acto[(a, "sobra")] += 1
            if any(x.get("si") for x in oro):
                dep["con dependencia"] += 1
                dep["la marca"] += any(K_dep(p) for p in partes)
            if ver and not bien:
                print(f"--- {ch['id']} t{i}: {limpio(tu['msg'])[:170]}")
                print(f"    quiere {sorted(quiere)} · puso {sorted(puso)}")
                for p in partes:
                    print(f"      [{p.get('acto')}] {p.get('texto')}" + (f" · depende de {p['depende_de']}"
                                                                          if p.get("depende_de") else "")
                          + (f" · {p['cantidad']}" if p.get("cantidad") else ""))
    print(f"\nACTOS {'consigna unida' if UNIR else ('con' if con else 'sin') + ' ejemplos'}, 48 turnos: BIEN {cuenta['BIEN']} · MAL {cuenta['MAL']}")
    print(f"  dependencias: {dep['la marca']} de {dep['con dependencia']} turnos que tienen una")
    for a in ACTOS:
        e, f, s = por_acto[(a, "esta")], por_acto[(a, "falta")], por_acto[(a, "sobra")]
        if e or f or s:
            print(f"  {a:15} esta {e:2} · falta {f:2} · sobra {s:2}")
    print(f"\nGasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


def K_dep(p: dict) -> bool:
    try:
        return int(p.get("depende_de") or 0) > 0
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
