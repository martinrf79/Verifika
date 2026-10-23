"""COBERTURA DE LAS CAPAS DE PRODUCTO Y DE CAMPO — ¿el buscador trae lo correcto entre los seis? (23-oct-2026)

Sigue a `cobertura.py`, que midio rubros y temas. Pedido de Martin: medir todo y bien. Lo correcto esta escrito antes de
correr o lo calcula el codigo de la tienda, nunca a ojo:

  CAMPO     las condiciones de `jev/vagas.py`, `jev/reserva.py` y `jev/redactadas.py`, con sus nombres viejos llevados a
            los campos de hoy, y las de formato, puertos, sensor y caracteristicas extra, que no tenian ninguna.
  PRODUCTO  un modelo por rubro dicho de tres formas que arma el codigo —marca y modelo, el modelo con un error de
            tipeo, el modelo solo—, doce apodos escritos a mano, y diez nombres que la identidad da como varios: ahi lo
            correcto es que traiga todos.

El modelo de produccion traduce y separa con la consigna de la opcion 1 de `cobertura.py`. Sobre cada parte:
  codigo       lo que ata hoy: `catalogo.atar` para el campo, `marcador._productos` con la identidad para el producto
  palabras     `agente.ubicar` sobre los campos; el producto no tiene buscador de palabras
  significado  gemini-embedding-001: cada campo con su etiqueta, sus alias y sus valores; cada modelo con su rubro, su
               marca y el principio de su descripcion

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.20 python3 banco_pruebas/cobertura_capas.py [--ver]
"""
import ast
import asyncio
import collections
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.argv = [a for a in sys.argv]  # cobertura lee sus marcas de aca
import cobertura as CO  # noqa: E402  — el entorno, la traduccion de la opcion 1 y los embeddings
from banco_pruebas import libro_paga  # noqa: E402
from app.core import agente  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo.marcador import _productos  # noqa: E402

TIENDA, SEIS = CO.TIENDA, CO.SEIS
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.20"))

# Los nombres viejos de los bancos de Jev, en los campos de hoy. Lo que no es un campo del catalogo no se mide aca.
VIEJOS = {"origen": {"pais_fabricacion", "pais_marca"}, "peso": {"peso_gramos"},
          "garantia": {"garantia_meses", "garantia_detalle"}, "precio": {"precio_ars"}}
NO_ES_CAMPO = {"uso_recomendado", "anda_con"}

# Los campos que ningun banco tenia, escritos a mano antes de correr, con su rubro.
NUEVOS = [
    ("Busco una mother que use memorias DDR4", "motherboard", {"formato"}),
    ("Necesito un gabinete ATX de los grandes", "gabinete", {"formato"}),
    ("Una fuente ATX normal, de las estandar", "fuente", {"formato"}),
    ("Quiero un monitor que tenga DisplayPort", "monitor", {"puertos"}),
    ("Un monitor con dos entradas HDMI, para la play y la compu", "monitor", {"puertos"}),
    ("Que el monitor se pueda enchufar por USB-C a la notebook", "monitor", {"puertos"}),
    ("Un mouse con sensor optico", "mouse", {"sensor", "caracteristicas_extra"}),
    ("Un mouse que no salte el puntero cuando lo muevo rapido", "mouse", {"sensor"}),
    ("Un teclado chato de tijera, como el de la notebook", "teclado", {"caracteristicas_extra", "switch_teclado"}),
    ("Unos auriculares con cable de los de enchufe comun de 3.5", "auriculares", {"caracteristicas_extra", "conexion"}),
    ("Un teclado de membrana, que no sea mecanico", "teclado", {"caracteristicas_extra", "switch_teclado"}),
]

APODOS = [
    ("el tecladito Logitech que se conecta a la tablet y al celu", "Teclado Logitech K380 Negro"),
    ("el Haste de HyperX", "Mouse HyperX Pulsefire Haste 2 Negro"),
    ("los Sony con cancelacion de ruido, los XM5", "Auriculares Sony WH-1000XM5 Blanco"),
    ("la Tab S9 de Samsung", "Tablet Samsung Galaxy Tab S9 FE Gris"),
    ("el Master de Logitech para la oficina", "Mouse Logitech MX Master 3S Negro"),
    ("el Basilisk de Razer", "Mouse Razer Basilisk V3 Negro"),
    ("el Superlight", "Mouse Logitech G Pro X Superlight Negro"),
    ("los JBL Tune inalambricos", "Auriculares JBL Tune 510BT Negro"),
    ("el Viper de Razer", "Mouse Razer Viper V3 Pro Blanco"),
    ("el K120 de Logitech, el comun de oficina", "Teclado Logitech K120 Negro"),
    ("el micro FIFINE K669", "Microfono FIFINE K669B Negro"),
    ("el Nano II de Anker de 65W", "Cargador Anker Nano II 65W Negro"),
]
VARIOS = ["Redragon Cobra", "Fury Beast", "Deco", "FIFINE", "Seagate Expansion", "Anker Nano", "Logitech G",
          "HyperX Pulsefire", "Samsung Galaxy Tab", "Kingston Fury"]


def _literal(archivo: str, nombre: str):
    for n in ast.parse(open(os.path.join(AQUI, "jev", archivo), encoding="utf-8").read()).body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == nombre:
            return ast.literal_eval(n.value)
    return []


def _campos(viejo) -> set:
    if viejo in NO_ES_CAMPO:
        return set()
    return VIEJOS.get(viejo, {viejo})


def casos_campo() -> list:
    """(id, mensaje, rubro o "", [conjunto de campos que valen por cada condicion])"""
    out = [(f"vaga {i}", t, "", [_campos(c)]) for i, (t, c) in enumerate(_literal("vagas.py", "VAGAS"), 1)
           if _campos(c)]
    for rid, msg, conds, *_ in _literal("reserva.py", "RESERVA"):
        cs = [_campos(c) for _, c, _ in conds if _campos(c)]
        if cs:
            out.append((rid, msg, conds[0][0], cs))
    for i, (msg, rubros, _, _, specs) in enumerate(_literal("redactadas.py", "CASOS"), 1):
        cs = [_campos(c) for c in specs if _campos(c)]
        if cs:
            out.append((f"redactada {i}", msg, next(iter(rubros), ""), cs))
    out += [(f"nuevo {i}", t, r, [c]) for i, (t, r, c) in enumerate(NUEVOS, 1)]
    return out


def familia(p: dict) -> str:
    return f"{p.get('marca')} {p.get('modelo') or p.get('nombre')}"


def _tipeo(modelo: str) -> str:
    """El modelo con dos letras cambiadas de lugar en su palabra mas larga: el error de tipeo mas comun."""
    ws = modelo.split()
    i = max(range(len(ws)), key=lambda j: len(ws[j]))
    w = ws[i]
    if len(w) >= 3:
        ws[i] = w[:1] + w[2] + w[1] + w[3:]
    return " ".join(ws)


def casos_producto() -> list:
    """(id, mensaje, [familias que tienen que estar]) — un modelo con stock por rubro, el de nombre mas corto."""
    out, por_rubro = [], collections.defaultdict(list)
    for p in K.productos(TIENDA):
        if K.con_stock(p) and p.get("modelo"):
            por_rubro[p["categoria"]].append(p)
    for rub, ps in sorted(por_rubro.items()):
        p = sorted(ps, key=lambda x: (len(str(x["modelo"])), x["nombre"]))[0]
        f = familia(p)
        out += [(f"{rub} exacto", f"¿Tenes el {p['marca']} {p['modelo']}?", [f]),
                (f"{rub} tipeo", f"quiero el {_tipeo(str(p['modelo']))}", [f]),
                (f"{rub} modelo", f"cuanto sale el {p['modelo']}", [f])]
    for i, (t, nombre) in enumerate(APODOS, 1):
        idt = K.identificar(nombre, "", TIENDA)
        out.append((f"apodo {i}", t, [familia(idt["producto"])]))
    for nombre in VARIOS:
        idt = K.identificar(nombre, "", TIENDA)
        out.append((f"varios {nombre}", f"Me interesa el {nombre}, ¿que precio tiene?",
                    sorted({familia(p) for p in idt.get("opciones") or []})))
    return out


# ── los buscadores ──────────────────────────────────────────────────────────

_IDX = {}


def _indice() -> dict:
    if not _IDX:
        import json
        from app.core.filtros_catalogo import _valor_crudo, campos_filtrables
        al = agente._alias(TIENDA).get("campos") or {}
        specs = {s["id"]: s.get("etiqueta") or "" for s in json.load(open(os.path.join(
            os.path.dirname(AQUI), "data", "clientes", TIENDA, "specs_preguntables.json"), encoding="utf-8"))["specs"]}
        docs = {}
        for c in campos_filtrables(TIENDA):
            vals = collections.Counter(str(_valor_crudo(p, c))[:40] for p in K.productos(TIENDA)
                                       if _valor_crudo(p, c) not in (None, ""))
            docs[c] = (f"{c.replace('_', ' ')}: {specs.get(c, '')}. " + ", ".join(al.get(c, []))
                       + ". Valores: " + ", ".join(v for v, _ in vals.most_common(6)))
        _IDX["campos"] = dict(zip(docs, CO._vectores(list(docs.values()))))
        fams = {}
        for p in K.productos(TIENDA):
            fams.setdefault(familia(p), f"{p.get('categoria')} {familia(p)}: {str(p.get('descripcion') or '')[:160]}")
        _IDX["productos"] = dict(zip(fams, CO._vectores(list(fams.values()))))
    return _IDX


def por_significado(textos: list, grupo: str) -> list:
    idx = _indice()[grupo]
    return [[k for k, _ in sorted(((k, CO._coseno(v, q)) for k, v in idx.items()), key=lambda x: -x[1])[:SEIS]]
            for q in CO._vectores(textos)]


def campo_del_codigo(texto: str, rubro: str) -> list:
    universo = [p for p in K.productos(TIENDA) if not rubro or p.get("categoria") == rubro]
    f = K.atar(texto, universo, TIENDA)
    return [f["campo"]] if "campo" in f else []


def productos_del_codigo(texto: str) -> list:
    out = []
    for tramo, _ in _productos([w for w in re.findall(r"[a-z0-9]+", K.n(texto)) if w not in K._RELLENO], TIENDA):
        idt = K.identificar(tramo, "", TIENDA)
        for p in [idt["producto"]] if idt["veredicto"] == "exists" else idt.get("opciones") or []:
            if familia(p) not in out:
                out.append(familia(p))
    return out


def main() -> None:
    ver = "--ver" in sys.argv
    desde = libro_paga.gastado(libro_paga._hoy())
    nota = collections.defaultdict(collections.Counter)

    for cid, msg, rubro, conds in casos_campo():
        partes = asyncio.run(CO.contar(msg, CO.FORMA if CO.FORMA == "U" else "N")).get("partes") or [msg]
        cands = {"codigo": [campo_del_codigo(t, rubro) for t in partes],
                 "palabras": [agente.ubicar(t, "campos", TIENDA, SEIS) for t in partes],
                 "significado": por_significado(partes, "campos")}
        for nombre, cs in cands.items():
            for gold in conds:
                nota[f"campo {nombre}"]["casos"] += 1
                nota[f"campo {nombre}"]["en_6"] += any(gold & set(c) for c in cs)
                nota[f"campo {nombre}"]["primero"] += any(gold & set(c[:1]) for c in cs)
        if ver and not all(any(g & set(c) for c in cands["significado"]) for g in conds):
            print(f"--- campo {cid}: {msg}\n    quiere {conds}\n    partes {partes}\n    significado {cands['significado']}")
        if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
            print(f"TOPE de la corrida: {TOPE} dolares")
            break

    for cid, msg, fams in casos_producto():
        partes = asyncio.run(CO.contar(msg, CO.FORMA if CO.FORMA == "U" else "N")).get("partes") or [msg]
        clase = cid.split()[0] if cid.split()[0] in ("apodo", "varios") else cid.split()[-1]
        cands = {"codigo": [productos_del_codigo(t) for t in partes],
                 "codigo sobre el mensaje crudo": [productos_del_codigo(msg)],
                 "significado": por_significado(partes, "productos"),
                 "significado sobre el mensaje crudo": por_significado([msg], "productos")}
        for nombre, cs in cands.items():
            todas = set().union(*map(set, cs)) if cs else set()
            # Un nombre que puede ser varios esta bien si trae al menos dos de los que puede ser: detecta la duda.
            bien = len(set(fams) & todas) >= 2 if clase == "varios" else set(fams) <= todas
            nota[f"producto {nombre}"]["casos"] += 1
            nota[f"producto {nombre}"]["en_6"] += bien
            nota[f"producto {nombre}"]["primero"] += any(c[:1] == fams[:1] for c in cs) if len(fams) == 1 else 0
            nota[f"producto {nombre} · {clase}"]["casos"] += 1
            nota[f"producto {nombre} · {clase}"]["en_6"] += bien
        if ver and not set(fams[:1]) <= set().union(*map(set, cands["significado"])):
            print(f"--- producto {cid}: {msg}\n    quiere {fams}\n    partes {partes}\n    significado {cands['significado']}")
        if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
            print(f"TOPE de la corrida: {TOPE} dolares")
            break

    print("\nCOBERTURA DE LAS CAPAS, sobre las partes traducidas")
    for k in sorted(nota):
        t = nota[k]
        print(f"  {k:46} entre los seis {t['en_6']:3} de {t['casos']:3}" + (f" · primero {t['primero']}"
                                                                         if "·" not in k else ""))
    print(f"\nGasto de la traduccion: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares; los embeddings van "
          "aparte, unos centavos")


if __name__ == "__main__":
    main()
