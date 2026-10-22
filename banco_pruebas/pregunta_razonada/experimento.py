"""EL EXPERIMENTO — la pregunta razonada: partir, decirla en comun y escribirla en Python (22-oct-2026).

El modelo no ve la fuente: solo el menu de funciones y la memoria de la charla. Tres consignas:
  1. partir el mensaje en pedidos;
  2. decir cada pedido completo y explicito, en lenguaje comun, con la memoria resuelta;
  3. escribirlo como llamadas a las funciones del menu, con los datos en palabras.

Dos formas:
  A   las tres consignas en una sola llamada.
  B   tres llamadas encadenadas: partir, explicitar y escribir el Python. La tercera no ve el mensaje del cliente: solo
      lo explicitado y la memoria, para medir si el lenguaje comun alcanza.

Va con la clave gratis. Con la paga solo si la gratis se agoto, con la marca de Martin y su tope de 30 centavos:
    MARTIN_AUTORIZO_LA_PAGA=<fecha> PAGA=1 python3 banco_pruebas/pregunta_razonada/experimento.py

    python3 banco_pruebas/pregunta_razonada/experimento.py [--solo S01] [--forma A]
Lo que devuelve el modelo queda en `resultados.jsonl`; `calificar.py` lo compara con las fichas.
"""
import asyncio
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
sys.path.insert(0, AQUI)
os.chdir(REPO)
PAGA = os.environ.get("PAGA") == "1"
if PAGA:
    os.environ["BANCO_CLAVE_PAGA"] = "true"  # clon_produccion pasa a la paga solo con esto
else:
    os.environ.pop("GEMINI_API_KEY_PROD", None)  # la gratis: clon_produccion no la cambia por la paga

from banco_pruebas import clon_produccion as C  # noqa: E402
C.preparar_entorno()
C.instalar()
from app.core import llm_reintento  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402
from app.core.flujo.interprete import _json  # noqa: E402
from banco_pruebas import libro_paga  # noqa: E402
from fichas import CHARLAS  # noqa: E402

TID = "verifika_prod"
SALIDA = os.path.join(AQUI, "resultados.jsonl")
TOPE_USD = 0.30

MENU = '''# Lo que sabe hacer el codigo de la tienda. Los datos van en palabras, claras y completas, nunca datos de la tienda.
buscar(que, cantidad=None, condiciones=[], orden=None, tope=None)
    # productos sin modelo concreto: que = la clase de producto, "auriculares", "mouse", "teclado".
    # condiciones: lo que pide que tengan, cada una completa: "inalambrico", "que no sea fabricado en China".
    # orden: "mas barato", "mas caro" o el dato por el que ordena. tope: el precio maximo por unidad, en pesos.
producto(cual, quiere_saber)      # un producto concreto, por su nombre o su numero de la memoria: "M2"
comparar(cuales, por)             # dos o mas productos por un dato: comparar(["M1", "M2"], "peso")
compatibilidad(cual, con)         # si un producto anda con algo que tiene el cliente
envio(destino)                    # cuanto sale o cuanto tarda mandar a un lugar
cuenta(tope=None, reparto=None, destino=None)
    # sumar todo lo pedido. tope: lo maximo que quiere gastar en total.
    # reparto: como paga, {"transferencia": 70, "sin decir": 30}; un solo medio es {"visa": 100}
politica(sobre)                   # una regla de la tienda: cuotas, garantia, factura, retiro, descuentos, medios de pago
agregar(que, cantidad=1, destino=None, color=None, condiciones=[], orden=None)
    # lo que decide llevar o mandar a un lugar: que = la clase de producto, el nombre de un producto o "M2"
sacar(cual)                       # quitar del pedido: "L1" o ["L1", "L2"]
cambiar(cual, que=None, cantidad=None, destino=None, color=None, condiciones=[], orden=None)
    # cambiar algo del pedido: cual = "L1" o la lista; lo demas, solo lo que cambia
explicar(pregunta)                # saber general de tecnologia, que no depende de la tienda
cliente(nombre=None, localidad=None, es=None)   # lo que dice de si mismo
preguntar(que)                    # lo que no se puede saber sin preguntarle al cliente
nada()                            # saludos, risas, relleno

# Para lo que depende de otra cosa, el resultado va en una variable y se usa con if:
#   a = producto("M2", "si es inalambrico")
#   if cumple(a): agregar("M2", destino="Cordoba")
# hay(x): si hay stock; anda(x): si es compatible; cumple(x): si cumple lo que se pregunto; barato(x): si cuesta poco.'''

REGLAS = """- Todo el mensaje queda en algun pedido, tambien los saludos y lo que no pide nada.
- Lo que senala de la charla —"ese", "el segundo", "lo de Rosario", "los dos"— sale de la MEMORIA: en el Python va su
  numero, "M2" o "L1"; en lenguaje comun, su nombre.
- Lo que dice para varios —"de cada uno", "a cada uno", "todo"— va en cada pedido al que toca.
- Nunca escribas un precio, un modelo o un dato de la tienda que no este en el mensaje o en la memoria."""

CONSIGNA_A = f"""Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente. Tu trabajo
tiene tres pasos, y los haces los tres:
1. PARTIR: corta el ULTIMO MENSAJE en pedidos, uno por cada cosa que pide, pregunta, decide o dice, en su orden.
   "cita" son sus palabras literales.
2. EN COMUN: dice cada pedido completo y explicito, como lo entenderia cualquiera sin leer la charla: con lo que senala
   de la memoria nombrado, con sus condiciones, cantidades y destinos.
3. PYTHON: escribe cada pedido como llamadas a las funciones del MENU.

{REGLAS}

EL MENU:
{MENU}

Devolve SOLO el JSON: {{"pedidos": [{{"cita": "...", "en_comun": "...", "python": "..."}}]}}"""

CONSIGNA_B1 = """Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente.
Corta el ULTIMO MENSAJE en pedidos, uno por cada cosa que pide, pregunta, decide o dice, en su orden. "cita" son sus
palabras literales. Todo el mensaje queda en algun pedido, tambien los saludos y lo que no pide nada. Lo que dice para
varios —"de cada uno", "todo"— no se parte: va en el pedido donde lo dice.
Devolve SOLO el JSON: {"pedidos": [{"cita": "..."}]}"""

CONSIGNA_B2 = """Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente.
El ULTIMO MENSAJE ya esta cortado en PEDIDOS. Deci cada uno completo y explicito en "en_comun", como lo entenderia
cualquiera sin leer la charla ni el resto del mensaje: lo que senala de la MEMORIA —"ese", "el segundo", "lo de Rosario",
"los dos"— con su nombre y su numero, M2 o L1; y lo que el resto del mensaje dice para ese pedido —cantidades, destinos,
condiciones, "a cada uno", "si no hay"— escrito adentro. Nunca escribas un precio, un modelo o un dato de la tienda que
no este en el mensaje o en la memoria.
Devolve SOLO el JSON, un renglon por pedido, en el mismo orden: {"pedidos": [{"cita": "...", "en_comun": "..."}]}"""

CONSIGNA_B3 = f"""Sos el interprete de una tienda online de tecnologia de Argentina. NO le contestas al cliente.
Escribi cada PEDIDO como llamadas a las funciones del MENU. Los pedidos ya estan dichos completos; lo que nombran de la
charla lleva su numero de la MEMORIA, M2 o L1, y en el Python va ese numero.

{REGLAS}

EL MENU:
{MENU}

Devolve SOLO el JSON, un renglon por pedido, en el mismo orden: {{"pedidos": [{{"python": "..."}}]}}"""


def limpio(msg: str) -> str:
    return " ".join(msg.replace("|", "").split())


def _plata(v) -> str:
    return f"${K.entero(v):,}".replace(",", ".")


def memoria(mem: dict) -> str:
    if not mem:
        return "MEMORIA: vacia, es el primer mensaje."
    por_id = {str(p["id"]): p for p in K.productos(TID)}
    r = []
    if mem.get("M"):
        r.append("- LO QUE EL VENDEDOR MOSTRO:")
        for i, pid in enumerate(mem["M"], 1):
            p = por_id[pid]
            colores = sorted({q.get("color") for q in K._colores_de(p, list(por_id.values()))
                              if q.get("color") and K.con_stock(q)})
            datos = [f"conexion: {(p.get('specs') or {}).get('conexion')}" if (p.get("specs") or {}).get("conexion") else "",
                     f"peso: {p['peso_gramos']} g" if p.get("peso_gramos") else "",
                     f"colores: {', '.join(colores)}" if len(colores) > 1 else ""]
            r.append(f"  M{i} {p['nombre']}, {_plata(p.get('precio_ars'))}" + "".join(f"; {d}" for d in datos if d))
    if mem.get("L"):
        r.append("- EL PEDIDO:")
        for i, (cant, que, pid, dest) in enumerate(mem["L"], 1):
            cual = por_id[pid]["nombre"] if pid else "FALTA cual"
            r.append(f"  L{i} {cant} {que}" + (f" a {dest}" if dest else "") + f": {cual}")
    if mem.get("R"):
        r += ["- LO QUE EL VENDEDOR PREGUNTO Y SIGUE ABIERTO:"] + [f'  R{i} "{t}"' for i, t in enumerate(mem["R"], 1)]
    if mem.get("dijo"):
        r.append(f'- LO ULTIMO QUE DIJO EL VENDEDOR: "{mem["dijo"]}"')
    return "MEMORIA:\n" + "\n".join(r)


GASTO = {"usd": 0.0}


async def pedir(sistema: str, usuario: str) -> tuple:
    cli = llm_reintento._cliente()
    if cli is None:
        raise RuntimeError("sin clave del modelo")
    if PAGA and GASTO["usd"] >= TOPE_USD:
        raise RuntimeError(f"tope de la corrida: {TOPE_USD} dolares")
    r = await llm_reintento.llamar_con_reintento(
        lambda: cli.chat.completions.create(model=llm_reintento._modelo(), temperature=0,
                                            response_format={"type": "json_object"},
                                            messages=[{"role": "system", "content": sistema},
                                                      {"role": "user", "content": usuario}]),
        timeout_s=90, trace_id="pregunta_razonada")
    u = getattr(r, "usage", None)
    ent, sal = (getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0) if u else (0, 0)
    if PAGA:
        from banco_pruebas import costo
        GASTO["usd"] += costo.dolares(ent, sal, llm_reintento._modelo())
    return r.choices[0].message.content or "", ent, sal


async def forma_a(mem: str, msg: str) -> dict:
    crudo, e, s = await pedir(CONSIGNA_A, f"{mem}\n\nULTIMO MENSAJE: {msg}")
    return {"pedidos": (_json(crudo) or {}).get("pedidos") or [], "crudo": [crudo], "entrada": e, "salida": s}


async def forma_b(mem: str, msg: str) -> dict:
    c1, e1, s1 = await pedir(CONSIGNA_B1, f"{mem}\n\nULTIMO MENSAJE: {msg}")
    citas = [p.get("cita", "") for p in (_json(c1) or {}).get("pedidos") or [] if isinstance(p, dict)]
    lista = "\n".join(f"{i}. {c}" for i, c in enumerate(citas, 1))
    c2, e2, s2 = await pedir(CONSIGNA_B2, f"{mem}\n\nULTIMO MENSAJE: {msg}\n\nPEDIDOS:\n{lista}")
    comun = [p.get("en_comun", "") for p in (_json(c2) or {}).get("pedidos") or [] if isinstance(p, dict)]
    lista = "\n".join(f"{i}. {c}" for i, c in enumerate(comun, 1))
    c3, e3, s3 = await pedir(CONSIGNA_B3, f"{mem}\n\nPEDIDOS:\n{lista}")
    py = [p.get("python", "") for p in (_json(c3) or {}).get("pedidos") or [] if isinstance(p, dict)]
    n = max(len(citas), len(comun), len(py))
    pedidos = [{"cita": (citas[i:i + 1] or [""])[0], "en_comun": (comun[i:i + 1] or [""])[0],
                "python": (py[i:i + 1] or [""])[0]} for i in range(n)]
    return {"pedidos": pedidos, "crudo": [c1, c2, c3], "entrada": e1 + e2 + e3, "salida": s1 + s2 + s3}


def hechos() -> set:
    if not os.path.exists(SALIDA):
        return set()
    out = set()
    for l in open(SALIDA, encoding="utf-8"):
        r = json.loads(l)
        if not r.get("error"):
            out.add((r["charla"], r["turno"], r["forma"]))
    return out


async def main(solo: str = "", formas: str = "AB") -> None:
    ya = hechos()
    print(f"clave: {'PAGA' if PAGA else 'gratis'} · modelo {llm_reintento._modelo()} · ya hechos {len(ya)}", flush=True)
    for ch in CHARLAS:
        if solo and ch["id"] != solo:
            continue
        for t, turno in enumerate(ch["turnos"]):
            mem, msg = memoria(turno["mem"]), limpio(turno["msg"])
            for forma in formas:
                if (ch["id"], t, forma) in ya:
                    continue
                t0 = time.time()
                try:
                    r = await (forma_a if forma == "A" else forma_b)(mem, msg)
                    err = None
                except Exception as e:  # noqa: BLE001
                    r, err = {}, f"{type(e).__name__}: {str(e)[:300]}"
                fila = {"charla": ch["id"], "turno": t, "forma": forma, "clave": "paga" if PAGA else "gratis",
                        "ms": int((time.time() - t0) * 1000), "error": err, **r}
                with open(SALIDA, "a", encoding="utf-8") as f:
                    f.write(json.dumps(fila, ensure_ascii=False) + "\n")
                print(f"{ch['id']} t{t} {forma}: " + (f"ERROR {err}" if err else
                      f"{len(r['pedidos'])} pedidos, {r['entrada']}+{r['salida']} tokens, {fila['ms']} ms"), flush=True)
                if err and ("429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err):
                    print("la gratis se agoto: se sigue con la paga, con la marca de Martin", flush=True)
                    return
    if PAGA:
        print(f"gasto de la corrida: {GASTO['usd']:.4f} dolares")


if __name__ == "__main__":
    a = sys.argv[1:]
    asyncio.run(main(a[a.index("--solo") + 1] if "--solo" in a else "",
                     a[a.index("--forma") + 1] if "--forma" in a else "AB"))
