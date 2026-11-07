"""EL DIAGRAMA DEL FLUJO, GENERADO DEL CODIGO — 7-nov-2026, a pedido de Martin: un diagrama que no dependa de la memoria de
una sesion. Lee `app/` con `ast` (libreria estandar, sin instalar nada) y escribe `arquitectura/DIAGRAMA_FLUJO.md`.

  Nivel 1  las cajas del turno, numeradas, con el cableado REAL entre ellas: cuantas referencias de codigo van de una a otra.
  Nivel 2  por caja, sus modulos y sus funciones: lineas, quien las referencia desde otras cajas, si alguna entrada las alcanza.
  Nivel 3  los campos de la memoria del agente: que funcion los lee y cual los escribe.

COMO NO SE OLVIDA NADA: cada funcion y clase de `app/` tiene que caer en una caja de CAJAS. `tests/test_diagrama.py` falla si
una queda sin caja, o si el archivo generado no es el de hoy. Para regenerar: `python3 banco_pruebas/diagrama.py`.

LIMITES, dichos de entrada: es analisis estatico. Una referencia es un nombre que aparece en el codigo, no una llamada
probada en vivo: llamadas por `getattr`, por diccionarios de funciones o por texto no se ven. "Sin referencia" quiere decir
que ningun codigo alcanzable desde la entrada la nombra; no prueba que sobre, y "alcanzable" no prueba que se use."""
import ast
import collections
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(REPO, "arquitectura", "DIAGRAMA_FLUJO.md")

# LAS CAJAS, en el orden en que un mensaje las atraviesa. 0 es lo que no es del turno: configuracion, logs, administracion.
CAJAS = {
    1: ("CANAL", "el mensaje entra y la respuesta sale: webhooks de WhatsApp y Telegram, conectores, audio"),
    2: ("PUERTA", "antes del turno: anti-jailbreak y la palabra de reset"),
    3: ("MEMORIA", "cargar y guardar la charla: historial, memoria del agente, estado del pedido, Firestore"),
    4: ("CONTEXTO", "lo que ve el modelo: reglas, mapa de la tabla, lo que el cliente dijo, lo que la tienda no vende"),
    5: ("BUCLE", "la llamada al modelo, el despacho de sus herramientas y el armado final del turno"),
    6: ("BUSCAR", "el catalogo y la FAQ: la tabla con SQL, el motor, los filtros, la compatibilidad, los embeddings de temas"),
    7: ("PEDIDO Y CUENTA", "el pedido que vive en el codigo, la cuenta, el envio, el reparto del pago y el ejecutor heredado"),
    8: ("COBRO", "el link de pago, los datos de transferencia, el lead y el aviso al dueno"),
    9: ("RESPUESTA Y CONTROL", "la respuesta atada, el verificador y los controles de lo que el modelo omitio"),
    10: ("TEXTOS Y GUARDAS", "la prosa fija de la casa y las guardas de salida"),
    0: ("INFRA", "configuracion, logs, administracion de la tienda y arranque"),
}
CABLE_NOMBRE = {i: f"{i} {n}" for i, (n, _) in CAJAS.items()}

# (caja, regex del modulo, regex del nombre de nivel superior o None). Gana la primera que coincide.
REGLAS = [
    (1, r"^app\.connectors\.", None), (1, r"^app\.core\.transcriber$", None),
    (1, r"^app\.main$", r"^(whatsapp_webhook|whatsapp_verify|telegram_webhook|_process_and_reply_telegram|"
                        r"_process_and_reply_whatsapp|_sobrecarga|_prosa)$"),
    (0, r"^app\.main$", None), (0, r"^app\.(config|logger)$", None),
    (2, r"^app\.core\.(orchestrator|antijailbreak)$", None),
    (3, r"^app\.core\.flujo\.(turno|estado)$", None), (3, r"^app\.core\.(contexto_turno|estado_venta)$", None),
    (3, r"^app\.storage\.", None),
    (3, r"^app\.core\.flujo\.agente$", r"^(memoria_de|estado_de|MEMORIA)$"),
    (4, r"^app\.core\.flujo\.agente$", r"^(hoja_reglas|charla|memoria_texto)$"),
    (4, r"^app\.core\.flujo\.(marcador)$", None), (4, r"^app\.core\.(fuente|guia_compra)$", None),
    (4, r"^app\.core\.flujo\.tabla$", r"^(mapa|resumen)$"),
    (4, r"^app\.core\.flujo\.respuesta$", r"^(Citas|orden_del_cliente|_COL)$"),
    (5, r"^app\.core\.flujo\.agente$", r"^(responder|_llamar)$"), (5, r"^app\.core\.llm_reintento$", None),
    (6, r"^app\.core\.flujo\.agente$", r"^(_agenda|_vectores|_base|_parecidos|_lugares|_orden_de|_tema_por_clave|buscar)$"),
    (6, r"^app\.core\.flujo\.(tabla|catalogo)$", None),
    (6, r"^app\.core\.(agente|motor|filtros_catalogo|fuente_producto|compatibilidad|coherencia_datos|curadas|huecos)$", None),
    (8, r"^app\.core\.flujo\.agente$", r"^cobrar$"), (8, r"^app\.core\.(pago|leads|notificador)$", None),
    (9, r"^app\.core\.flujo\.agente$", r"^(sin_buscar|omitidos|destinos_dichos)$"),
    (9, r"^app\.core\.flujo\.(respuesta|verificador)$", None),
    (7, r"^app\.core\.flujo\.agente$", None),
    (7, r"^app\.core\.flujo\.(agenda|borrador|ejecutor|normal|interprete|redaccion)$", None),
    (7, r"^app\.core\.(calculadora|calc_defensiva|envio|geo_cp|pago_split)$", None),
    (10, r"^app\.core\.(guardas_salida|guia_venta_prosa)$", None),
]


def _modulo(ruta: str) -> str:
    return os.path.relpath(ruta, REPO)[:-3].replace(os.sep, ".")


def _caja(modulo: str, nombre: str) -> int:
    for caja, rm, rn in REGLAS:
        if re.search(rm, modulo) and (rn is None or re.search(rn, nombre)):
            return caja
    return -1


def leer() -> dict:
    """{nodos, aristas, entradas, memoria}: un nodo es una funcion o clase de nivel superior, con sus metodos adentro."""
    mods, tree = {}, {}
    for raiz, _, fs in os.walk(os.path.join(REPO, "app")):
        for f in fs:
            if f.endswith(".py"):
                ruta = os.path.join(raiz, f)
                m = _modulo(ruta)
                mods[m] = ruta
                tree[m] = ast.parse(open(ruta, encoding="utf-8").read())
    nodos, defs = {}, collections.defaultdict(dict)
    for m, t in tree.items():
        for n in t.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                id_ = f"{m}.{n.name}"
                deco = [ast.unparse(d) for d in getattr(n, "decorator_list", [])]
                nodos[id_] = {"id": id_, "modulo": m, "nombre": n.name, "linea": n.lineno, "lineas": n.end_lineno - n.lineno + 1,
                              "tipo": "clase" if isinstance(n, ast.ClassDef) else "funcion", "caja": _caja(m, n.name),
                              "entrada": any(d.startswith("app.") for d in deco), "ast": n,
                              "doc": (ast.get_docstring(n) or "").split("\n")[0][:110]}
                defs[m][n.name] = id_
    # Lo que cada modulo trae con sus import, en cualquier parte del archivo: {alias: ("modulo", m) | ("nombre", id)}
    trae = {}
    for m, t in tree.items():
        pkg = m.rsplit(".", 1)[0] if not mods[m].endswith("__init__.py") else m
        al = {}
        for n in ast.walk(t):
            if isinstance(n, ast.ImportFrom):
                base = n.module or ""
                if n.level:
                    partes = pkg.split(".")[: len(pkg.split(".")) - (n.level - 1)]
                    base = ".".join(partes + ([n.module] if n.module else []))
                for a in n.names:
                    nom, ali = a.name, a.asname or a.name
                    if f"{base}.{nom}" in mods:
                        al[ali] = ("modulo", f"{base}.{nom}")
                    elif base in mods and nom in defs[base]:
                        al[ali] = ("nombre", defs[base][nom])
            elif isinstance(n, ast.Import):
                for a in n.names:
                    if a.name in mods:
                        al[a.asname or a.name] = ("modulo", a.name)
        trae[m] = al

    # Un accesor es una funcion que devuelve un modulo importado adentro: `def _motor(): from app.core import motor; return motor`.
    accesores = {}
    for id_, nd in nodos.items():
        a = nd["ast"]
        if isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(a.body) <= 3:
            ret = [r for r in ast.walk(a) if isinstance(r, ast.Return) and isinstance(r.value, ast.Name)]
            for imp in [i for i in ast.walk(a) if isinstance(i, ast.ImportFrom)]:
                for al in imp.names:
                    if ret and ret[0].value.id == (al.asname or al.name) and f"{imp.module}.{al.name}" in mods:
                        accesores[id_] = f"{imp.module}.{al.name}"

    def alcanza(modulo, attr, out):
        if attr in defs[modulo]:
            out.add(defs[modulo][attr])
        elif trae[modulo].get(attr, ("", ""))[0] == "nombre":  # re-exportado: `leads.notificar_lead`
            out.add(trae[modulo][attr][1])

    def refs(cuerpo, m) -> set:
        out = set()
        for raiz in cuerpo:
            for n in ast.walk(raiz):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    if n.id in defs[m]:
                        out.add(defs[m][n.id])
                    elif trae[m].get(n.id, ("", ""))[0] == "nombre":
                        out.add(trae[m][n.id][1])
                elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                    t = trae[m].get(n.value.id)
                    if t and t[0] == "modulo":
                        alcanza(t[1], n.attr, out)
                elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name):
                    f = defs[m].get(n.value.func.id) or (trae[m].get(n.value.func.id) or ("", ""))[1]
                    if f in accesores:
                        out.add(f)
                        alcanza(accesores[f], n.attr, out)
        return out

    aristas, modulos_importados = collections.defaultdict(set), collections.defaultdict(set)
    for id_, nd in nodos.items():
        aristas[id_] = refs([nd["ast"]], nd["modulo"]) - {id_}
    for m, t in tree.items():  # el codigo de nivel superior de cada modulo corre al importarlo
        suelto = [n for n in t.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        aristas[f"<{m}>"] = refs(suelto, m)
        modulos_importados[m] = {v[1] if v[0] == "modulo" else v[1].rsplit(".", 1)[0]
                                 for v in trae[m].values()} - {m}
    entradas = [i for i, n in nodos.items() if n["entrada"]] + ["app.core.orchestrator.process_message"]
    vistos, pila, mods_vistos = set(), list(entradas), set()
    while pila:
        x = pila.pop()
        if x in vistos:
            continue
        vistos.add(x)
        m = x.rsplit(".", 1)[0] if x in nodos else x.strip("<>")
        for dep in ([f"<{m}>"] if m not in mods_vistos else []):
            mods_vistos.add(m)
            pila.append(dep)
            pila += [f"<{o}>" for o in modulos_importados[m] if o in mods]
        pila += list(aristas.get(x, ()))
    fuente_texto = {m: open(r, encoding="utf-8").read() for m, r in mods.items()}
    for n in nodos.values():
        n["alcanzable"] = n["id"] in vistos
        # Si no se alcanza, se busca su nombre como texto en todo app/: nombrada = puede entrar por un camino que el analisis no ve.
        n["nombrada"] = (not n["alcanzable"]) and sum(
            len(re.findall(r"(?<![A-Za-z0-9_])" + re.escape(n["nombre"]) + r"(?![A-Za-z0-9_])", t)) for t in fuente_texto.values()) > 1
        n["ast"] = None
    memoria = _memoria(tree)
    return {"nodos": nodos, "aristas": {k: v for k, v in aristas.items() if k in nodos}, "entradas": entradas, "memoria": memoria,
            "externas": {n["id"]: n["caja"] for n in nodos.values()}}


def _memoria(tree: dict) -> dict:
    """{campo: {"lee": {funciones}, "escribe": {funciones}}} para la variable `memoria` del agente."""
    out = collections.defaultdict(lambda: {"lee": set(), "escribe": set()})
    for m, t in tree.items():
        for f in t.body:
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            quien = f"{m.split('.')[-1]}.{f.name}"
            for n in ast.walk(f):
                if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == "memoria" \
                        and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str):
                    out[n.slice.value]["escribe" if isinstance(n.ctx, ast.Store) else "lee"].add(quien)
                elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) \
                        and n.func.value.id == "memoria" and n.args and isinstance(n.args[0], ast.Constant) \
                        and isinstance(n.args[0].value, str):
                    out[n.args[0].value]["lee" if n.func.attr == "get" else "escribe"].add(quien)
    return out


def escribir(d: dict) -> str:
    nodos, aristas = d["nodos"], d["aristas"]
    cruce = collections.Counter()
    for a, hacia in aristas.items():
        for b in hacia:
            if nodos[a]["caja"] != nodos[b]["caja"]:
                cruce[(nodos[a]["caja"], nodos[b]["caja"])] += 1
    entrantes = collections.defaultdict(set)
    for a, hacia in aristas.items():
        for b in hacia:
            if nodos[a]["caja"] != nodos[b]["caja"]:
                entrantes[b].add(nodos[a]["caja"])
    L = ["# DIAGRAMA DEL FLUJO — GENERADO, NO SE EDITA",
         "", "Lo escribe `python3 banco_pruebas/diagrama.py` leyendo `app/`. `tests/test_diagrama.py` falla si una funcion queda sin caja "
         "o si este archivo no es el de hoy. Las cajas y sus reglas estan en `CAJAS` y `REGLAS`, en el script.", "",
         "Limites: analisis estatico. Una referencia es un nombre que aparece en el codigo, no una llamada probada. Lo que se llama por "
         "`getattr`, o por texto, no se ve. Columna ALCANCE: `si` = alguna entrada la alcanza; `?` = ninguna la alcanza pero su nombre "
         "aparece escrito en otra parte de `app/`, hay que mirarla; `-` = ninguna la alcanza y su nombre no aparece en ningun otro lado "
         "de `app/`. Un `-` no prueba que sobre: puede usarla un script o un test.", "",
         f"Funciones y clases de nivel superior: {len(nodos)}. Entradas: " + ", ".join(f"`{e.split('.', 3)[-1]}`" for e in sorted(d["entradas"])), "",
         "## Nivel 1 — el turno", "", "```mermaid", "flowchart LR"]
    for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
        n = sum(1 for x in nodos.values() if x["caja"] == i)
        L.append(f'  C{i}["{i} {CAJAS[i][0]}<br/>{n} funciones"]')
    L += ["  C1 --> C2 --> C3 --> C4 --> C5", "  C5 --> C6", "  C5 --> C7", "  C5 --> C8", "  C5 --> C9", "  C9 --> C10", "  C10 --> C3"]
    L += ["```", "", "Orden del turno: 1 CANAL, 2 PUERTA, 3 MEMORIA, 4 CONTEXTO, 5 BUCLE (el modelo llama 6 BUSCAR, 7 PEDIDO Y CUENTA y 8 COBRO), "
          "9 RESPUESTA Y CONTROL, 10 TEXTOS Y GUARDAS, y vuelve a 3 para guardar.", ""]
    for i in range(1, 11):
        L.append(f"- **{i} {CAJAS[i][0]}**: {CAJAS[i][1]}.")
    L += ["", "### El cableado real entre cajas", "",
          "Cada celda cuenta cuantas funciones de la caja de la fila nombran a una funcion de la caja de la columna. "
          "Es lo que hace el codigo, no lo que dice el orden de arriba. Una celda debajo de la diagonal es una vuelta hacia atras.", "",
          "| de \\ a | " + " | ".join(str(j) for j in range(0, 11)) + " |", "|" + "---|" * 12]
    for i in range(0, 11):
        L.append(f"| **{i}** {CAJAS[i][0]} | " + " | ".join(str(cruce[(i, j)] or "") if i != j else "·" for j in range(0, 11)) + " |")
    L += ["", "## Nivel 2 — cada caja", ""]
    for i in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 0]:
        ns = sorted((n for n in nodos.values() if n["caja"] == i), key=lambda n: (n["modulo"], n["linea"]))
        L += [f"### {i} {CAJAS[i][0]}", "", CAJAS[i][1].capitalize() + f". {len(ns)} funciones, {sum(n['lineas'] for n in ns)} lineas.", "",
              "| modulo | funcion | lineas | nombrada desde las cajas | alcance |", "|---|---|---|---|---|"]
        for n in ns:
            desde = ",".join(str(c) for c in sorted(entrantes[n["id"]]))
            L.append(f"| {n['modulo'].replace('app.', '')} | `{n['nombre']}`{' (clase)' if n['tipo'] == 'clase' else ''} | {n['lineas']} | "
                     f"{desde or '·'} | {'si' if n['alcanzable'] else ('?' if n['nombrada'] else '-')} |")
        L.append("")
    L += ["## Nivel 3 — la memoria del agente", "",
          "Los campos de la variable `memoria` que tocan las funciones de `app/`, leidos del codigo. Es lo que viaja de un turno al siguiente, "
          "ademas del historial. Solo ve el nombre `memoria`: lo que otras partes guarden en otras variables no esta aca.", "",
          "| campo | lo lee | lo escribe |", "|---|---|---|"]
    for campo, v in sorted(d["memoria"].items()):
        L.append(f"| `{campo}` | {', '.join(sorted(v['lee'])) or '-'} | {', '.join(sorted(v['escribe'])) or '-'} |")
    sin = [n for n in sorted(nodos.values(), key=lambda n: (n["modulo"], n["linea"])) if not n["alcanzable"]]
    muertas = [n for n in sin if not n["nombrada"]]
    L += ["", f"## Sin alcance desde las entradas: {len(sin)} ({len(muertas)} con `-`, {len(sin) - len(muertas)} con `?`)", "",
          "Ningun codigo alcanzable desde los webhooks o el orquestador las nombra. Se revisan una por una antes de borrar.", "",
          "| alcance | caja | modulo | funcion | lineas |", "|---|---|---|---|---|"]
    for n in sin:
        L.append(f"| {'?' if n['nombrada'] else '-'} | {n['caja']} | {n['modulo'].replace('app.', '')} | `{n['nombre']}` | {n['lineas']} |")
    return "\n".join(L) + "\n"


def sin_caja(d: dict) -> list:
    return [n["id"] for n in d["nodos"].values() if n["caja"] < 0]


if __name__ == "__main__":
    d = leer()
    if sin_caja(d):
        sys.exit("SIN CAJA: " + ", ".join(sin_caja(d)))
    texto = escribir(d)
    open(SALIDA, "w", encoding="utf-8").write(texto)
    por_caja = collections.Counter(n["caja"] for n in d["nodos"].values())
    print(f"{len(d['nodos'])} funciones y clases en {len(por_caja)} cajas, {sum(1 for n in d['nodos'].values() if not n['alcanzable'])} "
          f"sin referencia desde las entradas -> {os.path.relpath(SALIDA, REPO)}")
