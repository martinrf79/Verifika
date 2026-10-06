"""LOS 58 COMO NUMEROS (6-oct-2026, idea de Martin): el modelo parte el mensaje y a cada parte le pone el numero
de la combinacion de la ficha 58 que le corresponde, con la lista de los 58 y un ejemplo de cada uno delante.

Mide si el modelo reconoce la combinacion. Las 58 no son una particion: una parte puede ser de mas de una
("si anda me lo llevo" es 29 y tambien 15), asi que cada parte esperada trae el CONJUNTO de numeros que valen,
escrito antes de correr. Nota por caso: partes cubiertas y numeros que no caben en ninguna parte.

  python3 banco_pruebas/nexos/numeros58.py --modelos deepseek-chat,gemini-3.1-flash-lite --reps 2
  python3 banco_pruebas/nexos/numeros58.py --preguntar        la entrevista: si les sirve y que afinarian
"""
import argparse, json, os, re, sys
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.dirname(os.path.dirname(AQUI)))
SALIDA = os.path.join(AQUI, "numeros58_corridas.jsonl")

C58 = [c for c in json.load(open(os.path.join(os.path.dirname(AQUI), "vara_58.json")))["charlas"] if c["id"].startswith("C")]
LISTA = "\n".join(f"{int(c['id'][1:])} {c['clase']}: \"{c['turnos'][-1]['texto']}\"" for c in C58)

PIDE = """Sos el traductor de una tienda online de tecnologia de Argentina. No le contestas al cliente.
Parti el ULTIMO mensaje del cliente en partes, una por cada cosa que pide o dice, y a cada parte ponele el numero de la lista que mejor la describe. La lista tiene un ejemplo de cada numero: no busques la misma frase, busca el mismo tipo de pedido.
Una linea por parte, con esta forma exacta:
<n de parte> | <numero de la lista> | <la parte con las palabras del cliente>
Solo las lineas.

LISTA:
""" + LISTA

# (id, contexto en dos lineas, mensaje, partes esperadas: cada una el conjunto de numeros que valen)
CASOS = [
    ("X01", "El bot mostro: 1. G203 con cable $37.500, 2. G305 inalambrico $80.500, 3. MX Master 3S $203.000.",
     "El inalambrico mas barato de esos anda con mi Mac? si anda quiero dos, uno a Rosario y otro a Cordoba, cuanto es "
     "todo pagando por transferencia y que garantia tiene",
     [{27, 43, 9}, {36}, {29, 15}, {26, 10}, {16, 21, 25}, {11, 1, 3}]),
    ("X02", "", "Hola, necesito un teclado inalambrico que no sea Logitech y un mouse barato, los dos negros. Hacen "
                "factura A? y cuanto tarda el envio a Mendoza",
     [{5, 7, 2, 23}, {9, 2, 24}, {24, 23, 5}, {11}, {10, 11}]),
    ("X03", "El pedido tiene 1 G305 negro y 1 teclado K380 negro, envio a Rosario.",
     "saca el teclado, el mouse que sean dos y mandalo todo a Cordoba. Puedo pagar 70 transferencia y 30 con Mercado Pago?",
     [{33, 34, 48, 55}, {25, 34, 48}, {34, 10, 48}, {16, 21}]),
    ("X04", "El bot mostro: 1. Ryzen 5 5600, 2. Motherboard B550M DS3H, 3. Placa de video RTX 4060.",
     "El procesador ese entra en la placa que me pasaste? Y la placa de video necesita fuente aparte? Si todo es "
     "compatible anotame los tres y decime cuantas cuotas sin interes hay",
     [{36, 43}, {36, 3, 1}, {29, 15}, {11}]),
    ("X05", "", "Tienen celulares? si no, algo parecido que no pase de 250 mil, y aceptan tarjeta naranja?",
     [{2, 57}, {28, 30, 5, 42}, {11}]),
    ("X07", "El bot mostro tres mouse.",
     "ninguno me convence, mostrame teclados mecanicos que no sean Redragon, los dos mas baratos",
     [{2, 5, 45}, {7}, {9}]),
    ("X08", "El cliente pidio auriculares que no sean Redragon y el bot le mostro tres.",
     "y en mouse que tenes inalambrico?", [{46, 45, 2}, {5, 46}]),
    ("X09", "", "Okay dame el precio de los dos articulos mas baratos que tengas en la tienda y de los dos mas caros en "
                "total serian cuatro articulos de los cuales luego te dire a donde seria el envio Dime que medios de pago "
                "reciben Y si tienen descuentos por cantidad",
     [{9, 2}, {9, 2}, {11}, {13, 11, 41}]),
    ("X13", "El bot ya le anoto un G305.", "si el G305 anda con Mac, me lo llevo", [{36}, {29, 15}]),
    ("X14", "", "tienen 50 off, no? porque me dijeron que con transferencia hay descuento", [{12, 40}, {11, 12, 40}]),
    ("X20", "", "Necesito ampliar la ram de mi notebook Lenovo IdeaPad 3, la Fury Beast DDR4 de 8GB le sirve?",
     [{36, 37}]),
    ("X25", "El bot mostro: 1. G203, 2. G305, 3. MX Master 3S.",
     "el ultimo que me mostraste tiene bluetooth? y el del medio cuanto pesa?", [{43, 44, 49, 1, 3}, {43, 44, 49, 1, 3}]),
    ("X28", "", "Si el G502 Hero blanco tiene stock damelo, si no el negro, y cuanto sale mandarlo a Salta",
     [{28, 23}, {15, 29, 28}, {10}]),
    ("X29", "", "cuanto sale el envio a Ushuaia y cuanto tarda? hacen envios al exterior, a Montevideo?",
     [{10}, {10, 11}, {11}]),
    ("X30", "El bot mostro: 1. Ryzen 5 5600, 2. Motherboard B550M DS3H, 3. Placa de video RTX 4060.",
     "el procesador ese viene con cooler? y si compro las tres cosas me hacen precio?", [{1, 3, 43}, {13, 11, 41}]),
]


def corregir(esp, salida):
    nums = [int(m) for m in re.findall(r"^\s*\d+\s*\|\s*(\d+)\s*\|", salida, re.M)]
    usados, cubiertas = set(), 0
    for conj in esp:  # cada parte esperada toma un numero distinto que le quepa
        i = next((k for k, x in enumerate(nums) if k not in usados and x in conj), None)
        if i is not None:
            usados.add(i)
            cubiertas += 1
    todos = set().union(*esp)
    sueltos = [x for x in nums if x not in todos]
    return {"nums": nums, "cubiertas": cubiertas, "esperadas": len(esp), "sueltos": sueltos,
            "ok": cubiertas == len(esp) and not sueltos}


def uno(modelo, caso, rep):
    from necesita import llamar
    cid, ctx, msg, esp = caso
    user = (f"ANTES EN LA CHARLA: {ctx}\n" if ctx else "") + f"ULTIMO MENSAJE DEL CLIENTE: {msg}"
    out = llamar(modelo, [{"role": "system", "content": PIDE}, {"role": "user", "content": user}], temp=0.0)
    nota = corregir(esp, out)
    fila = {"modelo": modelo, "id": cid, "rep": rep, "salida": out, **nota}
    with open(SALIDA, "a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila


PREGUNTA = """Te muestro una idea y quiero tu opinion franca, corta, en cinco renglones.
Para traducir los mensajes de los clientes, el sistema te daria esta lista de 58 tipos de pedido, cada uno con un ejemplo, y vos partirias cada mensaje en partes y a cada parte le pondrias un numero de la lista. Despues el codigo hace lo que corresponde a cada numero.
1. Te resulta facil o dificil reconocer el numero de cada parte con esta lista? Cuales numeros se te confunden entre si?
2. Un numero solo alcanza para que el codigo sepa que hacer, o hace falta ademas el producto, la cantidad, el destino?
3. Que cambiarias de la lista para que la uses mejor: menos numeros, dos ejes, mas ejemplos, nombres en vez de numeros?
4. Con palabras (buscar, agregar, compatibilidad) o con numeros: que te sale mas confiable y por que?
5. Cualquier otra cosa que te ayude.

LISTA:
""" + LISTA


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", default="deepseek-chat")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--preguntar", action="store_true")
    a = ap.parse_args()
    from banco_pruebas import clon_produccion as CP
    CP.preparar_entorno()
    modelos = a.modelos.split(",")
    if a.preguntar:
        from necesita import llamar
        for m in modelos:
            r = llamar(m, [{"role": "user", "content": PREGUNTA}], temp=0.2)
            with open(os.path.join(AQUI, "numeros58_entrevista.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"modelo": m, "respuesta": r}, ensure_ascii=False) + "\n")
            print(f"\n== {m}\n{r}")
        return 0
    tareas = [(m, c, r) for r in range(1, a.reps + 1) for m in modelos for c in CASOS]
    with ThreadPoolExecutor(6) as ex:
        filas = list(ex.map(lambda t: uno(*t), tareas))
    for m in modelos:
        fs = [f for f in filas if f["modelo"] == m]
        print(f"\n{m}: casos enteros {sum(f['ok'] for f in fs)}/{len(fs)} · partes {sum(f['cubiertas'] for f in fs)}"
              f"/{sum(f['esperadas'] for f in fs)} · numeros que no caben {sum(len(f['sueltos']) for f in fs)}")
        for f in fs:
            if not f["ok"]:
                print(f"  {f['id']} r{f['rep']}: {f['nums']} cubre {f['cubiertas']}/{f['esperadas']} sueltos {f['sueltos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
