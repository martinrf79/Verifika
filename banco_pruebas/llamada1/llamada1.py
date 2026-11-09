"""Llamada 1, intención de compra: la consigna del 21-oct (A) contra la misma con el párrafo (B). Clave gratis.
Corre en el árbol viejo, git 28d956c, con su intérprete tal cual. Graba las agendas en llamada1.jsonl, reanudable."""
import asyncio, json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.chdir(AQUI)
from banco_pruebas import clon_produccion as C
C.preparar_entorno(); C.instalar()
from app.core.flujo import interprete, estado as E

INTENCION_B = """

LA INTENCION DE COMPRA: si el cliente dice que lo quiere, lo lleva, lo pide o que se lo manden —"quiero un K120", "me
llevo el G305", "dos G305 negros y tres K120, cuanto es", "mandame uno a Rosario"— es comprar, aunque en el mismo mensaje
pregunte el precio o el total: el precio sale del presupuesto. Es producto solo si pregunta algo del producto sin decir
que lo lleva: "tenes el K120?", "el G305 es inalambrico?". Si lo lleva con una condicion —"me llevo el G305 si anda con
Mac"—, la condicion es su propia pregunta y la compra depende de ella con "si"."""

INTENCION = """

LA INTENCION DE COMPRA: si el cliente dice que lleva, quiere o pide UN MODELO CONCRETO, o algo de la libreta —"quiero un
K120", "me llevo el G305", "dos G305 negros y tres K120, cuanto es", "el segundo me lo llevo"—, es comprar, aunque en el
mismo mensaje pregunte el total: el total sale del presupuesto. Un rubro sin modelo es buscar aunque diga "quiero": "quiero
un mouse inalambrico" busca. Preguntar cuanto sale algo, o cuanto sale mandarlo, es producto y envio, no comprar. Si lleva
un modelo con una condicion —"me llevo el G305 si anda con Mac"—, la condicion es su propia pregunta y la compra depende
de ella con "si"."""

base = interprete.consigna
SALIDA = os.path.join(AQUI, "llamada1.jsonl")
hechas = {(r["v"], r["charla"], r["forma"]) for r in map(json.loads, open(SALIDA))} if os.path.exists(SALIDA) else set()


async def main():
    textos = json.load(open(os.path.join(AQUI, "textos.json")))
    sem = asyncio.Semaphore(2)

    async def uno(v, cid, forma, texto):
        if (v, cid, forma) in hechas:
            return
        async with sem:
            for i in range(6):
                interprete.consigna = (lambda t: base(t) + INTENCION) if v == "B2" else base
                ag = await interprete.interpretar(texto, [], E.leer({}), "verifika_prod", f"l1-{v}-{cid}")
                if ag is not None:
                    break
                await asyncio.sleep(20 * (i + 1))
            with open(SALIDA, "a") as fh:
                fh.write(json.dumps({"v": v, "charla": cid, "forma": forma, "texto": texto, "agenda": ag}, ensure_ascii=False) + "\n")

    # A y B intercaladas, una tarea a la vez por version: la consigna es global del modulo
    for cid, forma, texto in textos:
        for v in ("B2",):
            await uno(v, cid, forma, texto)
    print("listo", sum(1 for _ in open(SALIDA)))


asyncio.run(main())
