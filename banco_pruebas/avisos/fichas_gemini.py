"""Gemini reescribe las nueve fichas con sus palabras, viendo casos resueltos de cada tipo. Los casos salen de charlas que
NO se miden: ni el turno ni su charla estan entre los 20 de la prueba. Guarda fichas_gemini.txt y controla las fugas."""
import collections
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import contexto  # noqa: E402
import comandos as Cm  # noqa: E402
import fichas as F  # noqa: E402
import limpio as L  # noqa: E402
import pistas as P  # noqa: E402

TIPO = {"producto": "PRODUCTO", "buscar": "BUSCAR", "envio": "ENVIO", "cuenta": "CUENTA", "politica": "POLITICA",
        "compatibilidad": "COMPATIBILIDAD", "comprar": "COMPRA", "explicar": "EXPLICAR", "otro": "OTRO"}

PEDIDO = """Esto es una tarea de diseño, no un turno con un cliente. Arriba de todo va la parte de la consigna que vas a usar
para traducir los mensajes de los clientes a comandos: los nueve tipos de pedido. Abajo, casos ya resueltos de cada tipo,
con la libreta que veia el traductor, el mensaje y los comandos correctos.

<<<LOS NUEVE TIPOS
{fichas}
LOS NUEVE TIPOS>>>

CASOS RESUELTOS:
{casos}

Reescribi los nueve tipos con tus palabras, para que vos mismo traduzcas bien siempre, dicho como venga el mensaje.
- Mismo orden, mismos nombres de comandos y de casillas, la misma linea de comando de cada tipo.
- Cada tipo con VA y NO VA, y la frontera con el tipo con que mas lo confundirias.
- Lo que te hubiera hecho fallar en estos casos, dicho en general, para cualquier mensaje parecido.
- No copies los mensajes de los casos ni nombres de productos.
- Que no sea mas largo que lo de arriba.
Devolve SOLO el texto de los nueve tipos, empezando por "LOS NUEVE TIPOS DE PEDIDO"."""


def casos() -> str:
    medidas = {c for c, _ in P.TURNOS}
    por_tipo = collections.defaultdict(list)
    for ch in contexto.CHARLAS.values():
        if ch["id"] in medidas:
            continue
        for k, _t in enumerate(ch["turnos"]):
            ag = contexto.AGENDAS[ch["id"]][k]
            for acc in {p["accion"] for p in ag["preguntas"]}:
                por_tipo[acc].append((ch["id"], k))
    out = []
    for acc in TIPO:
        for cid, k in por_tipo[acc][:2]:
            x = contexto.contexto(cid, k, uid=f"fg_{cid}")
            out.append(f"--- {TIPO[acc]}: {cid}\n{x['entrada'].split('LO QUE EL CODIGO RECONOCIO')[0].strip()}\n"
                       f"ULTIMO MENSAJE: {x['texto']}\nCOMANDOS:\n{Cm.a_comandos(x['mano'])}")
    return "\n\n".join(out)


def main():
    L.instalar()
    texto = PEDIDO.format(fichas=F.FICHAS, casos=casos())
    resp, uso = contexto.llamar([{"role": "user", "content": texto}])
    resp = resp.strip().strip("`").strip()
    open(os.path.join(AQUI, "fichas_gemini.txt"), "w", encoding="utf-8").write(resp)
    open(os.path.join(AQUI, "fichas_gemini_pedido.txt"), "w", encoding="utf-8").write(texto)
    print(uso, len(F.FICHAS), "->", len(resp))
    faltan = [c for c in ("PRODUCTO", "BUSCAR", "ENVIO", "CUENTA", "POLITICA", "COMPATIBILIDAD", "AGREGAR", "SACAR",
                          "CAMBIAR", "CONFIRMAR", "ACEPTAR", "TOTAL", "REEMPLAZAR", "EXPLICAR", "OTRO", "CLIENTE")
              if c not in resp]
    print("comandos que faltan:", faltan)
    f = {(n, tri) for n, *_r, tri in L.fugas({"GEMINI": resp})}
    print("fugas:", sorted(f))


if __name__ == "__main__":
    main()
