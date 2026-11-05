"""EL CANDADO DE LO QUE YA ANDA — FICHA 87, solucion 1, 5-nov-2026, con Martin.

Las 41 charlas reales grabadas el 3-nov, `corrida_3nov.jsonl`, pasan por el codigo de hoy SIN MODELO: un modelo falso
repite lo que pidio y escribio el modelo ese dia, y las herramientas, el pegado y el verificador corren de nuevo. De cada
turno se guarda lo que pone el codigo: los presupuestos y el cobro que lee el cliente, lo que marca el verificador y el
texto final, que cambia si el verificador borra una oracion.

La foto de hoy queda en `candado_3nov.json`. `tests/test_candado_examen.py` vuelve a correr y compara los turnos que
estaban bien el 3-nov, los que no figuran en `fallas_3nov.md` como mal, dudosos o sin correr. Si un cambio altera uno,
el test falla y se mira el turno antes de seguir: o el cambio lo rompio, o lo mejoro y se vuelve a sacar la foto en el
mismo commit, diciendo cual turno y por que.

Los embeddings no se piden: los rubros y temas parecidos de cada consulta estan en `parecidos_3nov.json`, sacados una
vez con la clave gratis. Una consulta que no esta en la tabla da ninguno, y el test lo cuenta.

    python3 banco_pruebas/examen_real/candado.py --parecidos   la tabla de parecidos, con la clave gratis
    python3 banco_pruebas/examen_real/candado.py --foto        la foto de hoy, sin modelo
    python3 banco_pruebas/examen_real/candado.py               compara contra la foto, sin modelo
"""
import asyncio
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
GRABADA = os.path.join(AQUI, "corrida_3nov.jsonl")
PARECIDOS = os.path.join(AQUI, "parecidos_3nov.json")
FOTO = os.path.join(AQUI, "candado_3nov.json")

# LOS TURNOS QUE NO ESTABAN BIEN EL 3-nov, de `fallas_3nov.md`: 25 mal y 5 dudosos. Los 3 sin correr, de b8df72a33c,
# no estan en la corrida. El resto, 80 turnos, es lo que el candado cuida.
MAL = {"7f8cd4a5ca": [3, 6], "bf4a05c745": [2], "b8bb001ee8": [1, 2, 3, 4], "58b5a11775": [1, 4], "c3391deb1a": [1],
       "33dbb56c1b": [4], "854f1bea2c": [1], "781919fa60": [1, 2], "fe67b477ec": [1, 6], "badf4f114b": [2],
       "d0c439c575": [1], "b5ddaad494": [1], "83e58acb78": [1], "386b8a84eb": [1], "6344deed8c": [1],
       "08e6c44238": [1], "157b658bc8": [1], "96b39fa8fd": [1]}
DUDOSOS = {"7f8cd4a5ca": [2], "06d02631b7": [1], "e105d5a00b": [1], "a96e63a0cb": [1], "815c0c9b65": [4]}


def cuidado(charla: str, turno: int) -> bool:
    """El turno, contado desde 1, estaba bien el 3-nov."""
    return turno not in MAL.get(charla, []) + DUDOSOS.get(charla, [])


def _instalar(vivo: bool):
    """El clon con el modelo falso. Con `vivo`, los embeddings de verdad y cada consulta anotada; sin, la tabla."""
    from banco_pruebas import agente_replay as R
    from banco_pruebas import clon_produccion as C
    from app.core.flujo import agente
    parecidos = agente._parecidos
    falso, vistos = R.instalar()  # el modelo falso devuelve juntas las llamadas grabadas del turno
    anotados, faltan = {}, []
    if vivo:
        R._precargar(agente, C.TIENDA)

        def _anota(consulta, tipo, tienda_id):
            r = parecidos(consulta, tipo, tienda_id)
            anotados[f"{tipo}|{consulta}"] = [[k, round(x, 4)] for k, x in r[:3]]
            return r
        agente._parecidos = _anota
    else:
        tabla = json.load(open(PARECIDOS, encoding="utf-8"))

        def _tabla(consulta, tipo, tienda_id):
            k = f"{tipo}|{consulta}"
            if k not in tabla:
                faltan.append(k)
            return [tuple(x) for x in tabla.get(k, [])]
        agente._parecidos = _tabla
    return falso, vistos, anotados, faltan


# LO QUE PEGO EL CODIGO EL 3-nov VUELVE A SER LA ETIQUETA, 5-nov: la respuesta grabada ya trae el presupuesto y el cobro
# pegados. Repetida tal cual, el verificador de hoy marcaba esos montos como inventados y los borraba, y el presupuesto
# de hoy no se veia. Un bloque de presupuesto son las lineas seguidas con la forma que escribe el ejecutor.
_LINEA_PRESUPUESTO = re.compile(
    r"^(Presupuesto:|- \d+x .+: |Subtotal: |Total( final| general)?: |Envio a .+: |Pago dividido:|- [^:]+ \(\d+%\): |"
    r"La parte con .+ descuento|¿Con qué medio pagás |El pedido esta vacio)")


def a_etiquetas(bot: str, pasos: list) -> str:
    """La respuesta grabada con [[PRESUPUESTO]] y [[COBRO]] donde el codigo habia pegado, como la escribio el modelo."""
    lineas, out, i = bot.split("\n"), [], 0
    while i < len(lineas):
        if lineas[i].startswith("Presupuesto:"):
            j = i
            while j + 1 < len(lineas) and (_LINEA_PRESUPUESTO.match(lineas[j + 1]) or (
                    not lineas[j + 1].strip() and j + 2 < len(lineas) and _LINEA_PRESUPUESTO.match(lineas[j + 2]))):
                j += 1
            out.append("[[PRESUPUESTO]]")
            i = j + 1
        else:
            out.append(lineas[i])
            i += 1
    texto = "\n".join(out)
    for p in pasos:
        cobro = (p.get("devuelve") or "").strip() if p["h"] == "cobrar" else ""
        if cobro and cobro in texto:
            texto = texto.replace(cobro, "[[COBRO]]")
    return texto


def correr(vivo: bool = False) -> dict:
    """{"turnos": {"<charla> t<n>": lo que puso el codigo}, "faltan": consultas sin parecidos, "anotados": ...}."""
    from banco_pruebas import clon_produccion as C
    falso, vistos, anotados, faltan = _instalar(vivo)
    out = {}
    for c in map(json.loads, open(GRABADA, encoding="utf-8")):
        uid = f"candado_{c['id']}"
        C.reiniciar_cliente(uid)
        for i, t in enumerate(c["turnos"], 1):
            falso.turno({"pasos": [{"herramienta": p["h"], "pide": p["pide"]} for p in t["pasos"]],
                         "respuesta": a_etiquetas(t["bot"], t["pasos"])})
            vistos.clear()
            texto = "\n".join(asyncio.run(C.turno(uid, t["cliente"])))
            v = vistos[-1] if vistos else {}
            pasos = v.get("pasos") or []
            out[f"{c['id']} t{i}"] = {
                "presupuestos": [p.get("al_cliente", "") for p in pasos if p["herramienta"] == "presupuesto"],
                "cobros": [p.get("al_cliente", "") for p in pasos if p["herramienta"] == "cobrar"],
                "verificador": [list(x) for x in v.get("hallazgos") or []],
                "texto": texto, "error": v.get("error") or ""}
    return {"turnos": out, "faltan": sorted(set(faltan)), "anotados": anotados}


def diferencias(foto: dict, hoy: dict) -> list:
    """Los turnos cuidados cuyo resultado del codigo cambio, con que parte cambio."""
    out = []
    for k, f in foto.items():
        charla, _, t = k.partition(" t")
        if not cuidado(charla, int(t)):
            continue
        h = hoy.get(k)
        partes = [p for p in f if h is None or f[p] != h.get(p)]
        if partes:
            out.append(f"{k}: cambio {', '.join(partes)}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--parecidos" in args:
        r = correr(vivo=True)
        json.dump(r["anotados"], open(PARECIDOS, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
        print(f"{len(r['anotados'])} consultas con sus parecidos en {PARECIDOS}")
    elif "--foto" in args:
        r = correr()
        json.dump(r["turnos"], open(FOTO, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        cuidados = sum(cuidado(k.split(" t")[0], int(k.split(" t")[1])) for k in r["turnos"])
        print(f"foto: {len(r['turnos'])} turnos, {cuidados} cuidados; consultas sin parecidos: {len(r['faltan'])}")
    else:
        r = correr()
        foto = json.load(open(FOTO, encoding="utf-8"))
        malos = diferencias(foto, r["turnos"])
        print("\n".join(malos) or "ningun turno cuidado cambio")
        print(f"consultas sin parecidos: {len(r['faltan'])}")
