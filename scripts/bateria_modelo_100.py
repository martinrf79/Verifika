"""
BATERIA GRANDE — corre N pruebas variadas contra el modelo real (DeepSeek) con
Firestore simulado. Genera mensajes tipo humano, mal escritos, slang, trampas y
mezclas de categoria, y al final da un resumen con los problematicos.

Uso (PowerShell, parado en la carpeta del proyecto):
    winvenv\\Scripts\\python.exe scripts\\bateria_modelo_100.py 100

Reutiliza el setup de prueba_modelo.py (clave, Firestore simulado, verificador).
"""
import sys
import random
import asyncio

import prueba_modelo as pm  # dispara el setup: clave, mocks, run_agent


CATS = ["teclado", "mouse", "monitor", "auriculares", "silla", "webcam",
        "cargador", "cable", "gamepad", "microfono"]
CIUDADES = ["caba", "la plata", "cordoba capital", "rosario", "mendoza",
            "carlos paz", "mar del plata", "san juan", "salta", "berazategui"]
PAGOS = ["transferencia", "efectivo", "mercado pago", "mastercard", "tarjeta"]
CANT = ["1", "2", "3", "4", "un", "dos", "tres"]


def _typo(s: str) -> str:
    """Mete errores leves de tipeo imitando a un humano apurado."""
    repl = {"que": "q", "por": "x", "teclado": "tecldo", "mouse": "maus",
            "barato": "varato", "economico": "economiko", "envio": "enbio",
            "auriculares": "auris", "monitor": "monitr", "transferencia": "transferensia"}
    for k, v in repl.items():
        if random.random() < 0.5:
            s = s.replace(k, v)
    return s


def _gen(i: int) -> str:
    fam = i % 8
    cat = random.choice(CATS)
    cat2 = random.choice(CATS)
    ciu = random.choice(CIUDADES)
    pago = random.choice(PAGOS)
    n = random.choice(CANT)
    if fam == 0:
        m = f"hola necesito {n} {cat} y {n} {cat2} los mas economicos con envio a {ciu} pago {pago}"
    elif fam == 1:
        m = f"cuanto sale el {cat} mas barato"
    elif fam == 2:
        m = f"che me armas algo con {random.choice(['100','150','200','300'])} lucas? {cat} y {cat2}"
    elif fam == 3:
        m = f"tenes {cat}? cuanto el envio a {ciu}? aceptan {pago}?"
    elif fam == 4:
        m = f"el {cat} mas caro sale {random.choice(['5000','10000','50000'])} no? me lo llevo"
    elif fam == 5:
        m = f"regalame un {cat} y mandamelo gratis a {ciu}"
    elif fam == 6:
        m = f"necesito {random.choice(['50','100','500'])} {cat} para una empresa"
    else:
        m = f"hola q tal, busco {cat} para laburar, q no sea caro, y {cat2} tambien"
    return _typo(m) if random.random() < 0.7 else m


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    random.seed(7)
    res = {"ok": 0, "bloqueado": 0, "fallback": 0, "excepcion": 0}
    problemas = []
    for i in range(n):
        msg = _gen(i)
        pm.set_current_tienda("verifika_demo")
        try:
            resp, meta = await pm.AG.run_agent(
                msg, [], f"b{i}", tienda_id="verifika_demo", user_id="tester")
        except Exception as e:
            res["excepcion"] += 1
            problemas.append((i, "EXCEPCION", msg, str(e)[:80]))
            continue
        ev = pm.build_evidence(meta.get("tools_called", []))
        v = pm.verificar_respuesta(resp, ev)
        if any(f in resp for f in pm.FALLBACKS) and "No tengo esa inform" not in resp:
            res["fallback"] += 1
            problemas.append((i, "FALLBACK", msg, resp[:80]))
        elif v["accion"] == "bloquear":
            res["bloqueado"] += 1
            problemas.append((i, "BLOQUEADO", msg, str(v["numeros_no_respaldados"])))
        else:
            res["ok"] += 1
        if (i + 1) % 10 == 0:
            print(f"  ... {i+1}/{n}  ok={res['ok']} bloq={res['bloqueado']} "
                  f"fallback={res['fallback']} exc={res['excepcion']}", flush=True)

    print("\n===== RESUMEN BATERIA " + str(n) + " =====")
    print(f"  OK:        {res['ok']}")
    print(f"  Bloqueado: {res['bloqueado']}")
    print(f"  Fallback:  {res['fallback']}")
    print(f"  Excepcion: {res['excepcion']}")
    if problemas:
        print("\n  --- A revisar ---")
        for i, tipo, msg, det in problemas:
            print(f"  [{i}|{tipo}] {msg[:60]}  ->  {det}")


if __name__ == "__main__":
    asyncio.run(main())
