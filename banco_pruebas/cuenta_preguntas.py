"""CUANTAS COSAS PIDE EL CLIENTE — el modelo cuenta, traduce y separa, en la misma llamada (23-oct-2026).

Pregunta de Martin: si el modelo separa bien una multipregunta, ¿cuenta igual de bien cuantas cosas pidio o pregunto
el cliente? En teoria la cuenta tiene que dar igual que la separacion. Se mide con las 16 multipreguntas de
`pregunta_razonada/fichas.py` y la de los siete articulos de produccion, con lo correcto escrito a mano ANTES de correr:
una por cada cosa que pide o pregunta; condiciones, destinos y pago son detalles de esas cosas, no cuentan aparte.

Dos ordenes de la ficha, para ver si contar antes o despues de separar cambia algo:
  A  primero el numero, despues la traduccion y las partes
  B  primero la traduccion y las partes, despues el numero

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.30 python3 banco_pruebas/cuenta_preguntas.py [--ver]
"""
import asyncio
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(AQUI, "pregunta_razonada"))
os.chdir(REPO)
if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"

from banco_pruebas import clon_produccion as C  # noqa: E402
from banco_pruebas import libro_paga  # noqa: E402
C.preparar_entorno()
C.instalar()
from fichas import CHARLAS  # noqa: E402

TOPE = float(os.environ.get("TOPE_CORRIDA", "0.30"))

# Lo correcto, escrito a mano antes de correr: las cosas que pide o pregunta.
VERDAD = {
    "S01": ["auriculares", "mouse", "memorias"],
    "S02": ["teclado", "mouse"],
    "S03": ["que le sirve para escribir en el iPad", "si la Kingston DDR4 le va a la PC DDR5", "si no, cual si"],
    "S04": ["cual pesa menos", "llevar el mas liviano", "auriculares que no sean Redragon"],
    "S05": ["camara", "microfono"],
    "S06": ["si hay descuento en efectivo", "dos teclados con cable, si hay descuento"],
    "S07": ["auriculares", "mouse"],
    "S08": ["teclados", "mouse", "cuanto tarda"],
    "S09": ["auriculares", "teclados", "mouse", "formas de pago"],
    "S10": ["microfono", "camara", "monitor"],
    "S11": ["teclado", "mouse"],
    "S12": ["parlantes", "cuanto sale cada envio"],
    "S13": ["mouse", "monitores", "camara"],
    "S14": ["almacenamiento para fotos", "cargador"],
    "S15": ["que silla conviene", "mostrar sillas hasta 300 mil"],
    "S16": ["que recomienda para el wifi"],
    # El "teclado" de los destinos no lo pidio: es la contradiccion del caso real.
    "P_siete": ["auriculares", "mouse", "memorias"],
}

BASE = """Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. Lee el
MENSAJE del cliente y llena esta ficha en JSON.
"""
CAMPOS = {
    "numero": '  "numero": cuantas cosas pide o pregunta el cliente en total. Cada producto que pide y cada pregunta '
              'cuenta una; las condiciones, los destinos y el pago son detalles de esas cosas y no cuentan aparte.',
    "traduccion": '  "traduccion": el mensaje dicho simple y claro, en una o dos oraciones.',
    "partes": '  "partes": el mensaje separado, una oracion por cada cosa que pide o pregunta, con sus detalles adentro.',
}
ORDEN = {"A": ["numero", "traduccion", "partes"], "B": ["traduccion", "partes", "numero"]}


def consigna(orden: str) -> str:
    return BASE + "{\n" + ",\n".join(CAMPOS[c] for c in ORDEN[orden]) + "\n}"


def formato(orden: str) -> dict:
    tipos = {"numero": {"type": "integer"}, "traduccion": {"type": "string"},
             "partes": {"type": "array", "items": {"type": "string"}}}
    return {"type": "json_schema", "json_schema": {"name": "cuenta", "schema": {
        "type": "object", "properties": {c: tipos[c] for c in ORDEN[orden]}, "required": ORDEN[orden]}}}


def mensajes() -> dict:
    out = {c["id"]: c["turnos"][0]["msg"].replace("|", "") for c in CHARLAS}
    real = json.load(open(os.path.join(AQUI, "reales", "f7a8520ddf.json"), encoding="utf-8"))["turnos"][0]
    out["P_siete"] = real["mensaje"]
    return out


async def contar(msg: str, orden: str) -> dict:
    from app.core.flujo import interprete
    crudo = await interprete._pedir([{"role": "system", "content": consigna(orden)},
                                     {"role": "user", "content": f"MENSAJE: {msg}"}], "cuenta", formato(orden))
    return interprete._json(crudo)


def main() -> None:
    ver = "--ver" in sys.argv
    desde = libro_paga.gastado(libro_paga._hoy())
    filas = []
    for orden in ORDEN:
        for cid, msg in mensajes().items():
            if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
                print(f"TOPE de la corrida alcanzado: {TOPE} dolares")
                break
            r = asyncio.run(contar(msg, orden))
            n, partes, verdad = r.get("numero"), r.get("partes") or [], len(VERDAD[cid])
            filas.append({"orden": orden, "id": cid, "numero": n, "partes": len(partes), "verdad": verdad})
            if ver:
                print(f"--- {orden} {cid} verdad {verdad} · numero {n} · partes {len(partes)}")
                print(f"    {r.get('traduccion')}")
                for p in partes:
                    print(f"    - {p}")
    for orden in ORDEN:
        fs = [f for f in filas if f["orden"] == orden]
        if not fs:
            continue
        print(f"\nORDEN {orden}, {len(fs)} mensajes:")
        print(f"  numero igual a lo correcto   {sum(f['numero'] == f['verdad'] for f in fs)}")
        print(f"  partes igual a lo correcto   {sum(f['partes'] == f['verdad'] for f in fs)}")
        print(f"  numero igual a sus partes    {sum(f['numero'] == f['partes'] for f in fs)}")
        print("  " + " ".join(f"{f['id']}:{f['verdad']}/{f['numero']}/{f['partes']}" for f in fs))
    print(f"\nGasto de la corrida: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    main()
