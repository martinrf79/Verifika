"""LA ATADURA Y EL RELOJ — las dos preguntas del 10-ago, en una sola corrida.

PREGUNTA UNO, la atadura de la prosa. El sistema ya ataba la PLATA: el bloque de
la cuenta lo escribe el codigo y todo peso sin respaldo se poda. Fuera de la
plata no habia nada, asi que una garantia o un peso inventados salian limpios.
Ahora el redactor tiene que MARCAR de donde saco cada dato y el codigo lo
contrasta. Lo que este banco contesta es lo unico que importa antes de seguir:
**el modelo obedece la marca, o la ignora?**

PREGUNTA DOS, el reloj. El turno logueaba UN solo `latency_ms` total, asi que
"tarda 26 segundos" no se podia repartir. Con `etapas_ms` cada corrida dice
cuanto se fue en el decisor, cuanto en las herramientas y cuanto en el redactor,
y cuantas veces entro cada uno. Sin ese reparto, cambiar de proveedor es fe.

COMPARAR PROVEEDORES SIN TOCAR CODIGO. El decisor -la llamada que elige
herramientas- ya sale por `DECISOR_BASE_URL` si esta puesta, y el redactor
nunca. Entonces la comparacion es config y se corre dos veces:

    python3 banco_pruebas/atadura.py

    DECISOR_BASE_URL=https://api.groq.com/openai/v1 \\
    DECISOR_API_KEY=gsk_... DECISOR_MODEL=llama-3.3-70b-versatile \\
    python3 banco_pruebas/atadura.py

La segunda corrida solo cambia QUIEN decide. Si el reparto del reloj baja en la
fila `decisor` y la columna `marcadas` no se mueve, el cambio conviene. Si baja
el tiempo y se cae la atadura, no conviene y el numero lo dice.

LA CLAVE la elige `clon_produccion.preparar_entorno`: gratis por default, la
paga solo con BANCO_CLAVE_PAGA=true. Este banco no la pisa.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"

# LAS PREGUNTAS QUE FUERZAN UN DATO DURO QUE NO ES PLATA. Elegidas a proposito:
# cada una tiene la respuesta escrita en el catalogo, campo por campo, asi que
# si el modelo contesta de memoria se puede probar que lo hizo. La de plata
# queda afuera: esa ya la gobierna `_sin_plata_inventada`.
CASOS = {
    "garantia_de_uno": "que garantia tiene el mouse logitech g203?",
    "peso_y_medidas": "cuanto pesa el g203 y que medidas tiene?",
    "origen": "de donde viene el logitech g203, es chino?",
    "contenido_caja": "que trae la caja del g203?",
    "specs_notebook": "que procesador y cuanta ram tiene la notebook hp 245 g9?",
    "comparacion": "entre el g203 y el m170, cual conviene y por que?",
}


def correr(repeticiones: int = 1) -> dict:
    import asyncio

    from banco_pruebas import clon_produccion as clon
    from app.core import atadura_prosa as AP
    from app.core import hub_venta as HV
    clon.instalar()

    # SE ESPIA LO QUE EL MODELO ESCRIBIO ANTES DE LIMPIARLO. Es el unico lugar
    # donde el texto todavia tiene las etiquetas: despues de `verificar` ya no
    # existen, justamente porque no pueden llegar al cliente.
    crudos: list = []
    orig_ver = AP.verificar

    def espia_verificar(texto, llamadas, trace_id=""):
        crudos.append(texto or "")
        return orig_ver(texto, llamadas, trace_id)

    # Y SE ESPIA EL RELOJ, que sale en el log del turno y no vuelve por return.
    etapas: list = []
    orig_info = HV.log.info

    def espia_info(evento, **kw):
        if evento == "hub_venta_ok" and kw.get("etapas_ms"):
            etapas.append(dict(kw["etapas_ms"]))
        return orig_info(evento, **kw)

    AP.verificar = espia_verificar
    HV.log.info = espia_info

    filas = []
    try:
        for nombre, msg in CASOS.items():
            for i in range(max(1, repeticiones)):
                crudos.clear()
                etapas.clear()
                usuario = f"atadura_{nombre}_{i}"
                clon.reiniciar_cliente(usuario)
                partes = asyncio.get_event_loop().run_until_complete(
                    clon.turno(usuario, msg))
                final = "\n".join(partes)
                crudo = crudos[-1] if crudos else ""
                marcas = list(AP._RE_MARCA.finditer(crudo))
                idx = AP.fuentes([])  # solo para no romper si no hubo llamadas
                filas.append({
                    "caso": nombre, "msg": msg,
                    "marcadas": len(marcas),
                    "sin_marcar": len(AP._oraciones_con_dato_sin_marcar(crudo)),
                    "largo": len(final),
                    "etapas": etapas[-1] if etapas else {},
                    "crudo": crudo, "final": final,
                    "ejemplo": (marcas[0].group(0)[:90] if marcas else ""),
                    "fugada": ("<d" in final.lower()),
                })
                del idx
    finally:
        AP.verificar = orig_ver
        HV.log.info = orig_info
    return {"filas": filas}


def _suma_etapas(filas: list) -> dict:
    """El reparto promedio del turno, etapa por etapa."""
    acum: dict = {}
    for f in filas:
        for k, v in (f["etapas"] or {}).items():
            acum[k] = acum.get(k, 0) + v
    n = max(1, len(filas))
    return {k: round(v / n) for k, v in sorted(acum.items())}


def main(argv: list) -> int:
    import os
    from banco_pruebas import clon_produccion as clon
    detalle = clon.preparar_entorno()
    reps = 1
    if "--repeticiones" in argv:
        reps = int(argv[argv.index("--repeticiones") + 1])
    res = correr(reps)
    filas = res["filas"]

    decisor = os.environ.get("DECISOR_BASE_URL") or "gemini (el mismo que redacta)"
    print("=" * 78)
    print(f"LA ATADURA DE LA PROSA Y EL RELOJ — {len(CASOS)} preguntas x {reps}")
    print(f"clave: {detalle.get('clave')}")
    print(f"decisor: {decisor}")
    print("=" * 78)
    print("| caso | marcadas | sin marcar | largo | etiqueta fugada | ejemplo |")
    print("|---|---|---|---|---|---|")
    for f in filas:
        print(f"| {f['caso']} | **{f['marcadas']}** | {f['sin_marcar']} | "
              f"{f['largo']} | {'SI' if f['fugada'] else 'no'} | "
              f"{f['ejemplo'].replace('|', ' ')} |")

    marcadas = sum(f["marcadas"] for f in filas)
    sin_marcar = sum(f["sin_marcar"] for f in filas)
    fugadas = sum(1 for f in filas if f["fugada"])
    total = marcadas + sin_marcar
    print(f"\nMARCADAS {marcadas} — SIN MARCAR {sin_marcar} — "
          f"ATADO {round(100 * marcadas / max(1, total))}% de las afirmaciones "
          f"con dato duro")
    print(f"ETIQUETAS QUE SE FUGARON AL CLIENTE: {fugadas} "
          f"(tiene que ser 0 SIEMPRE)")

    print("\nEL RELOJ, promedio por turno en milisegundos:")
    for k, v in _suma_etapas(filas).items():
        print(f"  {k:16} {v}")

    # LA CORRIDA QUEDA ESCRITA. Sin esto, para releer que escribio el modelo hay
    # que volver a gastar seis turnos, y el texto CRUDO -el unico momento en que
    # las etiquetas existen- se pierde apenas termina el proceso.
    import datetime
    import json
    destino = (_RAIZ / "banco_pruebas" / "corridas" /
               f"atadura_{datetime.datetime.now():%Y%m%d_%H%M}.json")
    destino.write_text(json.dumps(
        {"decisor": decisor, "clave": detalle.get("clave"),
         "reloj_ms": _suma_etapas(filas), "filas": filas},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ncorrida guardada en {destino.relative_to(_RAIZ)}")

    if fugadas:
        print("\nROJO: una etiqueta llego al cliente.")
        return 1
    if marcadas == 0:
        print("\nROJO: el modelo IGNORO la marca en las "
              f"{len(filas)} preguntas. La atadura de prosa no ata nada.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
