"""
LOOP DEL SOLVER — la regla C auditada turno por turno, con preguntas sinteticas.

QUE ES LA REGLA C (acordada con Martin el 31-jul). Una sola regla para toda la
respuesta:
    EL DATO LO ESCRIBE SIEMPRE EL CODIGO.
    LA VENTA LA ESCRIBE SIEMPRE EL MODELO.
    LA FUENTE APORTA MATERIAL, NUNCA LA REDACCION FINAL.

POR QUE UN LOOP Y NO UN PROMPT. Hace semanas que la teoria dice una cosa y la
practica hace otra: se acuerda que el modelo no escribe datos, y despues en
WhatsApp aparece un numero inventado en la primera pregunta. Un prompt no
demuestra nada. Este banco CORRE preguntas contra el camino vivo, AUDITA cada
fragmento que el solver emitio, y devuelve las violaciones con el texto exacto.
Se corre, se arregla, se vuelve a correr. Eso es el loop.

QUE AUDITA, y todo es determinista, sin LLM de juez:
  1. DATO EN PROSA LIBRE: en los fragmentos `prosa` y `criterio` -los unicos que
     redacta el modelo- no puede haber plata, stock, plazo ni cifra de spec. Si
     hay, la regla C esta rota ahi, con nombre y apellido.
  2. DATO SIN RESPALDO: toda cifra que sobreviva al render tiene que existir en
     la fuente del turno (catalogo, FAQ o calculadora).
  3. SIN CONTESTAR: lo que el interprete DECLARO y el turno no cubrio.
  4. LA CAIDA: si el turno explota, produccion manda una disculpa. Eso es falla,
     no respuesta.

Las preguntas salen de la FUENTE (catalogo real + vocabulario del indice), asi
que se pueden auditar solas: se sabe de antemano que producto y que tema tocan.

Uso:
    python3 banco_pruebas/loop_solver.py            # una vuelta, 12 preguntas
    python3 banco_pruebas/loop_solver.py 30         # 30 preguntas
    BANCO_PAUSA_S=4 para espaciar los turnos.
Deja el informe en banco_pruebas/corridas/.
"""
import asyncio
import datetime as _dt
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas import clon_produccion

clon_produccion.preparar_entorno()

TIENDA = "verifika_prod"
_CORRIDAS = Path(__file__).resolve().parent / "corridas"

# Lo que el modelo NO puede escribir de su cabeza en prosa libre.
RE_PLATA = re.compile(
    r"\$|%|\bpesos\b|\bd[oó]lares\b|\b\d[\d.]{3,}\b|\b\d+\s*(?:mil|lucas|palos)\b",
    re.IGNORECASE)
RE_STOCK = re.compile(
    r"\b\d+\s*(?:unidades?|en stock|disponibles?)\b|\bstock\s*:?\s*\d+", re.IGNORECASE)
RE_PLAZO = re.compile(
    r"\b\d+\s*(?:a|-)?\s*\d*\s*(?:d[ií]as?|horas?|semanas?|meses)\b", re.IGNORECASE)
RE_SPEC_CIFRA = re.compile(
    r"\b\d+\s*(?:gb|tb|mb|hz|dpi|mah|w|pulgadas|\"|cm|kg|g)\b", re.IGNORECASE)

REGLAS = (("plata", RE_PLATA), ("stock", RE_STOCK),
          ("plazo", RE_PLAZO), ("spec", RE_SPEC_CIFRA))

# Los dos unicos tipos que redacta el modelo. El resto lo escribe el codigo.
TIPOS_DEL_MODELO = ("prosa", "criterio")


def _preguntas(n: int) -> list[tuple[str, str]]:
    """(eje, pregunta). Salen de la fuente real, asi que se auditan solas."""
    from app.storage.firestore_client import get_all_products
    prods = get_all_products(tienda_id=TIENDA) or []
    por_cat: dict = {}
    for p in prods:
        c = str(p.get("categoria") or "").strip()
        if c:
            por_cat.setdefault(c, []).append(p)
    cats = sorted(por_cat)
    def prod(cat, i=0):
        lista = sorted(por_cat.get(cat, []), key=lambda x: x.get("precio_ars") or 0)
        return lista[i] if lista else {}
    c0 = cats[0] if cats else "mouse"
    c1 = cats[1] if len(cats) > 1 else c0
    p0, p1 = prod(c0), prod(c1)
    n0 = p0.get("nombre", "el mas barato")
    n1 = p1.get("nombre", "el otro")

    base = [
        ("precio", f"hola, cuanto sale el {c0} mas barato?"),
        ("spec", f"el {n0} que medidas tiene y que trae en la caja?"),
        ("stock", f"tenes stock del {n0}?"),
        ("envio", f"cuanto me sale el envio a rosario del {n0}?"),
        ("politica", "puedo pagar en cuotas sin interes?"),
        ("politica", "si no me gusta lo puedo devolver? cuanto tiempo tengo?"),
        ("comparacion", f"que me conviene mas, el {n0} o el {n1}?"),
        ("compatibilidad", f"el {n0} me sirve para una notebook con windows?"),
        ("objecion", f"me parece caro el {n0}, no tenes algo mejor de precio?"),
        ("compuesta", f"cuanto sale el {c1} mas barato y tiene garantia?"),
        ("cierre", f"dale, quiero el {n0}, como seguimos?"),
        ("sin_dato", f"el {n0} viene en color rosa flúor?"),
        ("compuesta", f"necesito 2 {c0} y 1 {c1}, cuanto es todo con envio a mendoza?"),
        ("politica", "hacen factura A? y aceptan transferencia con descuento?"),
        ("spec", f"que garantia tiene el {n1} y de que material es?"),
        ("precio", f"cual es el {c1} mas caro que tenes?"),
        ("envio", "hacen envios a todo el pais? cuanto tarda a salta?"),
        ("objecion", "por que te compraria a vos y no en mercadolibre?"),
        ("sin_dato", f"el {n1} sirve para bucear?"),
        ("comparacion", f"entre {c0} y {c1}, cual me recomendas para regalo?"),
    ]
    return base[:n] if n <= len(base) else base * (n // len(base) + 1)


def _sin_nombres(texto: str, universo) -> str:
    """El texto sin los NOMBRES de los productos del turno.

    Nombrar un producto cuyo nombre lleva una cifra -"Kingston DataTraveler
    Exodia 1TB"- no es escribir un dato: es llamarlo por su nombre, y el modelo
    tiene que poder hacerlo para vender. Sin este descuento la auditoria marca
    como violacion cada vez que el bot nombra un producto, que es ruido y tapa
    las violaciones de verdad. La cifra que sobrevive a este descuento SI la
    puso el modelo de su cabeza."""
    t = str(texto or "")
    for p in (universo or []):
        nom = str((p or {}).get("nombre") or "").strip()
        if len(nom) > 3:
            t = re.sub(re.escape(nom), " ", t, flags=re.IGNORECASE)
            # el modelo acorta el nombre ("el DataTraveler Exodia de 1TB"): se
            # descuentan tambien los tramos largos del nombre con sus cifras.
            for tramo in re.findall(r"\S*\d\S*", nom):
                t = re.sub(rf"\b{re.escape(tramo)}\b", " ", t, flags=re.IGNORECASE)
    return t


def _violaciones_regla_c(fragmentos: list, universo=None) -> list[str]:
    """Dato duro escrito por el MODELO en su prosa libre. Es la regla C rota."""
    fallas = []
    for f in (fragmentos or []):
        if not isinstance(f, dict) or f.get("tipo") not in TIPOS_DEL_MODELO:
            continue
        txt = str(f.get("texto") or "").strip()
        if not txt:
            continue
        auditable = _sin_nombres(txt, universo)
        for nombre, patron in REGLAS:
            if patron.search(auditable):
                frase = next((o for o in re.split(r"(?<=[.!?])\s+", txt)
                              if patron.search(_sin_nombres(o, universo))), txt)
                fallas.append(f"{f.get('tipo')} trae {nombre.upper()}: "
                              f"«{frase.strip()[:150]}»")
    return fallas


async def _una_vuelta(preguntas, pausa_s, reporte) -> dict:
    from banco_pruebas.juez import juzgar
    import app.core.generador_v2 as g2

    capturados: list = []
    _render_orig = g2.renderizar

    def _render_espia(fragmentos, universo=None, *a, **kw):
        capturados.append((list(fragmentos or []), list(universo or [])))
        return _render_orig(fragmentos, universo, *a, **kw)

    g2.renderizar = _render_espia
    # hub_atado importa `renderizar` arriba: sin este reenganche el espia no ve
    # nada y la auditoria daria limpio siempre, que es el peor resultado posible.
    import app.core.hub_atado as ha
    if hasattr(ha, "renderizar"):
        ha.renderizar = _render_espia

    marcador = {"c": 0, "juez": 0, "caidas": 0, "turnos": 0}
    try:
        for i, (eje, pregunta) in enumerate(preguntas, 1):
            user = f"loop_{i}_{int(_dt.datetime.now().timestamp())}"
            clon_produccion.reiniciar_cliente(user)
            capturados.clear()
            print(f"[{i:02d}] ({eje}) {pregunta}")
            reporte.append(f"\n## {i:02d}. {eje} — {pregunta}\n")
            try:
                partes = await clon_produccion.turno(user, pregunta)
            except Exception as e:
                partes = [f"<<ERROR {type(e).__name__}: {e}>>"]
            texto = "\n\n".join(partes)
            marcador["turnos"] += 1
            for n, p in enumerate(partes, 1):
                reporte.append(f"\nmensaje {n}:\n\n```\n{p}\n```\n")

            if texto.startswith("<<ERROR") or clon_produccion.es_fallback(texto):
                marcador["caidas"] += 1
                print("     [CAIDA] el turno exploto")
                reporte.append("- **CAIDA: el turno exploto**")
                continue

            frags, universo = capturados[-1] if capturados else ([], [])
            vc = _violaciones_regla_c(frags, universo)
            for v in vc:
                marcador["c"] += 1
                print(f"     [REGLA C] {v}")
                reporte.append(f"- **REGLA C ROTA: {v}**")

            for p in juzgar(texto, tienda_id=TIENDA, mensaje=pregunta):
                marcador["juez"] += 1
                print(f"     [JUEZ] {p}")
                reporte.append(f"- **JUEZ: {p}**")

            if not vc and not marcador.get("_ultimo_juez"):
                reporte.append(f"- tipos emitidos: "
                               f"{[f.get('tipo') for f in frags if isinstance(f, dict)]}")
            if pausa_s and i < len(preguntas):
                await asyncio.sleep(pausa_s)
    finally:
        g2.renderizar = _render_orig
        if hasattr(ha, "renderizar"):
            ha.renderizar = _render_orig
    return marcador


async def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 12
    info = clon_produccion.instalar()
    pausa_s = float(os.environ.get("BANCO_PAUSA_S", "3") or 0)
    preguntas = _preguntas(n)
    banner = (f"[loop] {info['productos']} productos, {info['faq']} FAQ, "
              f"solver {info['solver_model']}, clave {info['clave']}, "
              f"cierre {info['modo_cierre']}. {len(preguntas)} preguntas.")
    print(banner + "\n")
    _CORRIDAS.mkdir(exist_ok=True)
    fecha = _dt.datetime.now()
    reporte = [f"# LOOP DEL SOLVER — {fecha:%Y-%m-%d %H:%M}", f"\n{banner}\n"]
    m = await _una_vuelta(preguntas, pausa_s, reporte)

    resumen = (f"\n{'=' * 62}\n"
               f"TURNOS: {m['turnos']}  |  REGLA C ROTA: {m['c']}  |  "
               f"JUEZ: {m['juez']}  |  CAIDAS: {m['caidas']}\n{'=' * 62}")
    print(resumen)
    reporte.append(f"\n## Resumen\n\n```{resumen}```\n")
    salida = _CORRIDAS / f"{fecha:%Y%m%d_%H%M}_loop_solver.md"
    salida.write_text("\n".join(reporte) + "\n", encoding="utf-8")
    print(f"[informe] {salida}")
    return m["c"] + m["juez"] + m["caidas"]


if __name__ == "__main__":
    sys.exit(min(asyncio.run(main()), 250))
