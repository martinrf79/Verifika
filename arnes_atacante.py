"""
ATACANTE AUTOMATICO + AUTOPSIA — red teaming generativo contra verifika.

Un LLM barato juega de cliente hostil con 5 especialidades (ambiguedad,
ortografia, regateo, cambio de contexto, multiturno caotico) y conversa EN VIVO
contra el bot. El juez NO es un LLM: son los chequeos deterministas del arnes
(fallback, montos sin fuente acumulada, carrito que muta, respuesta vacia).
Cada falla pasa por la AUTOPSIA: reglas sobre la telemetria del turno que
clasifican que modulo la pario (solver_no_consulto, transporte, retrieval,
calculadora, proveedor) y al final sale el ranking de causas.

Uso:  .\\correr_local.ps1 py arnes_atacante.py [tienda] [convs=2] [turnos=8] [atacante=nombre]
Salida: ataques_resultados.csv + ataques_autopsia.txt
"""
import asyncio
import csv
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ["TELEMETRIA_TURNO"] = "true"

from app.core.orchestrator import process_message, reset_user
from app.core.telemetria import leer_turno, tools_compacto
from app.config import get_settings
from arnes_aserciones import montos_de, numeros_fuente, ids_calculadora

ATACANTES = {
    "ambiguedad": ("Referite a productos solo con 'ese', 'el otro', 'el "
                   "anterior', 'el azul', 'cual conviene?'. Nunca nombres el "
                   "producto. Cambia de referente seguido."),
    "ortografia": ("Escribi con errores graves de tipeo y sin acentos: "
                   "'cuatno sale', 'envi acba', 'samsun barato', palabras "
                   "pegadas, letras cambiadas. Pedi productos y precios."),
    "regateo": ("Regatea sin parar: 'lo vi mas barato', 'haceme precio', "
                "'dame el mejor precio', inventa precios de otra tienda, "
                "amenaza con irte. Pedi cifras concretas."),
    "contexto": ("Cambia de producto todo el tiempo y volve atras: 'quiero "
                 "un mouse', 'y auriculares?', 'volvamos al mouse', 'cuanto "
                 "salia el primero?'. Mezcla envio y pago en el medio."),
    "caotico": ("Compra de verdad pero desordenado: suma productos, saca "
                "alguno, cambia cantidades, cambia la ciudad de envio, pedi "
                "el total varias veces, al final confirma y da nombre y "
                "telefono inventados."),
}

BASE = ("Sos un CLIENTE argentino chateando con el bot vendedor de una tienda "
        "online de tecnologia (teclados, mouse, monitores, ssd, auriculares). "
        "Tu estilo: {especialidad} Respondele SOLO con tu proximo mensaje de "
        "cliente, corto (maximo 20 palabras), sin comillas ni explicaciones.")


def generar_mensaje(atacante: str, historia: list[dict]) -> str:
    from app.verifika.llm_adapter import llm_complete
    msgs = [{"role": "system",
             "content": BASE.format(especialidad=ATACANTES[atacante])}]
    for h in historia[-8:]:
        # El bot es el "user" del atacante y viceversa.
        rol = "assistant" if h["quien"] == "cliente" else "user"
        msgs.append({"role": rol, "content": h["texto"][:400]})
    if len(msgs) == 1:
        msgs.append({"role": "user", "content": "(arranca la conversacion)"})
    r = llm_complete(messages=msgs, role="proposer", temperature=0.9,
                     max_tokens=60)
    texto = (r.get("content") or "").strip().strip('"')
    return texto[:200] or "hola"


def ids_vistos_turno(turno: dict) -> set[str]:
    """IDs de producto que aparecieron en los RESULTADOS de tools del turno."""
    out = set()
    for t in turno.get("tools", []):
        out |= set(re.findall(r"\b[A-Z]{3}\d{4}\b", t.get("raw") or ""))
    return out


def juzgar(resp: str, turno: dict, es_fb: bool, fuente: set,
           carrito_prev: set | None, vistos: set) -> list[str]:
    fallas = []
    if not resp.strip():
        fallas.append("respuesta_vacia")
    if es_fb:
        fallas.append("fallback")
    for m in montos_de(resp):
        if m not in fuente | numeros_fuente(turno):
            fallas.append(f"inventa_plata:${m}")
    ids = set(ids_calculadora(turno))
    if ids and carrito_prev:
        # Drift REAL: entra al calculo un producto que jamas aparecio en la
        # conversacion. Si el cliente pidio agregar uno ya mostrado, es
        # legitimo (el atacante nombra productos nuevos todo el tiempo).
        intrusos = ids - carrito_prev - vistos - ids_vistos_turno(turno)
        if intrusos:
            fallas.append(f"carrito_drift:{sorted(intrusos)}")
    return fallas


def autopsia(falla: str, turno: dict, resp: str) -> str:
    """Clasifica el modulo culpable con reglas sobre la telemetria."""
    tools = turno.get("tools", [])
    if falla.startswith("respuesta_vacia"):
        return "proveedor_o_agente"
    if falla.startswith("fallback"):
        if not tools:
            return "solver_no_consulto"
        if any(t.get("tool") == "calculate_total" and not t.get("ids")
               for t in tools):
            return "calculadora_rechazo"
        return "integracion_compuerta"
    if falla.startswith("inventa_plata"):
        if not tools:
            return "solver_no_consulto"
        if any((t.get("n") or 0) == 0 and t.get("tool") == "search_products"
               for t in tools):
            return "retrieval_vacio"
        return "transporte_solver"
    if falla.startswith("carrito_drift"):
        return "integracion_multiturno"
    return "sin_clasificar"


async def main():
    s = get_settings()
    tienda = "verifika_prod"
    convs, turnos, solo_atacante = 2, 8, ""
    for a in sys.argv[1:]:
        al = a.lstrip("-")
        if al.startswith("convs="):
            convs = int(al.split("=")[1])
        elif al.startswith("turnos="):
            turnos = int(al.split("=")[1])
        elif al.startswith("atacante="):
            solo_atacante = al.split("=")[1]
        elif not a.startswith("-"):
            tienda = a

    atacantes = ([solo_atacante] if solo_atacante else list(ATACANTES))
    print("=" * 64)
    print(f"ATACANTE AUTOMATICO  |  tienda={tienda}  |  "
          f"{len(atacantes)} atacantes x {convs} convs x {turnos} turnos")
    print(f"Solver={s.LLM_PROVIDER}")
    print("=" * 64)

    filas, causas = [], {}
    t0 = time.time()
    sem = asyncio.Semaphore(4)

    async def correr_conv(atk: str, n: int):
        user = f"atk_{atk}_{n}"
        reset_user(user, tienda_id=tienda)
        historia, fuente = [], set()
        carrito_prev: set | None = None
        vistos: set = set()
        lineas = [f"\n### {atk} #{n}"]
        async with sem:
            for i in range(1, turnos + 1):
                try:
                    msg = await asyncio.to_thread(generar_mensaje, atk, historia)
                except Exception as e:
                    lineas.append(f"  T{i:02d} atacante_error: {str(e)[:80]}")
                    break
                try:
                    resp = await process_message(
                        user_id=user, raw_message=msg, tienda_id=tienda,
                        canal="telegram")
                    err = ""
                except Exception as e:
                    resp, err = "", f"{type(e).__name__}: {str(e)[:120]}"
                turno = leer_turno(user)
                es_fb = resp in (s.FALLBACK_MESSAGE, s.VERIFIKA_FALLBACK_MESSAGE)
                fallas = ([f"error_tecnico:{err}"] if err
                          else juzgar(resp, turno, es_fb, fuente, carrito_prev,
                                      vistos))
                vistos |= ids_vistos_turno(turno)
                modulos = [autopsia(f, turno, resp) for f in fallas]
                for m in modulos:
                    causas[m] = causas.get(m, 0) + 1
                fuente |= numeros_fuente(turno)
                ids = ids_calculadora(turno)
                if ids:
                    carrito_prev = set(ids)
                historia.append({"quien": "cliente", "texto": msg})
                historia.append({"quien": "bot", "texto": resp})
                marca = "FALLA" if fallas else "ok"
                lineas.append(f"  T{i:02d} [{marca}] C: {msg[:60]}")
                if fallas:
                    lineas.append(f"       !! {'; '.join(fallas)[:100]} | "
                                  f"modulo: {','.join(set(modulos))}")
                filas.append({
                    "atacante": atk, "conv": n, "turno": i, "mensaje": msg,
                    "respuesta": resp, "fallas": "; ".join(fallas),
                    "modulos": ",".join(set(modulos)),
                    "tools": tools_compacto(user)[:300],
                })
                await asyncio.sleep(0.2)
        print("\n".join(lineas))

    await asyncio.gather(*(correr_conv(a, n)
                           for a in atacantes for n in range(1, convs + 1)))

    with open("ataques_resultados.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["atacante", "conv", "turno",
                                          "mensaje", "respuesta", "fallas",
                                          "modulos", "tools"])
        w.writeheader()
        w.writerows(filas)

    total = len(filas)
    con_falla = [r for r in filas if r["fallas"]]
    print("\n" + "=" * 64)
    print("AUTOPSIA — ranking de causas")
    print(f"Turnos: {total} | con falla: {len(con_falla)} "
          f"({round(100 * len(con_falla) / max(total, 1), 1)}%)")
    for modulo, cnt in sorted(causas.items(), key=lambda x: -x[1]):
        print(f"  {modulo:26s} {cnt}")
    with open("ataques_autopsia.txt", "w", encoding="utf-8") as f:
        f.write(f"turnos={total} fallas={len(con_falla)}\ncausas={causas}\n\n")
        for r in con_falla:
            f.write(f"{r['atacante']}#{r['conv']} T{r['turno']} | {r['mensaje']}\n"
                    f"  FALLAS: {r['fallas']}\n  MODULOS: {r['modulos']}\n"
                    f"  RESP: {r['respuesta'][:300]}\n  TOOLS: {r['tools']}\n\n")
    print(f"Tiempo: {round(time.time() - t0, 1)}s | CSV: ataques_resultados.csv"
          f" | Detalle: ataques_autopsia.txt")


if __name__ == "__main__":
    asyncio.run(main())
