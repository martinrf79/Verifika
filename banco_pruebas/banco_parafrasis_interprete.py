"""
BANCO DE PARAFRASIS — mide que el interprete NORMALICE las mil formas de decir
lo mismo a la estructura finita (16-jul, pedido de Martin: "quiero gastar lo
menos posible", "mi presupuesto es muy ajustado", "la situacion economica...",
todas son UN criterio; "sin partes chinas" y sus variantes son UNA exclusion).

La interpretacion deja de ser una sensacion: es este numero. Cada campo del
idioma tiene su tanda de parafrasis reales, incluidas negativas (mensajes que
NO deben prender el campo). Cada falla real de produccion se suma como caso.

Uso:  python3 banco_pruebas/banco_parafrasis_interprete.py
Vivo (llama al LLM del interprete). Sale != 0 bajo el piso (0.85).
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas.sim_firestore import install

PISO = 0.85

_VISTOS = [
    {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "precio": 8500},
    {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro", "precio": 12000},
    {"id": "TEC0011", "nombre": "Teclado Redragon Kumara K552", "precio": 55000},
]

_HIST = [
    {"role": "user", "content": "hola, busco un mouse y un teclado"},
    {"role": "assistant", "content":
        "Tengo el Mouse Genius DX-110 Negro a $8.500, el Mouse Logitech M170 "
        "Negro a $12.000 y el Teclado Redragon Kumara K552 a $55.000. ¿Qué "
        "estás buscando?"},
]


def _criterio_barato(i):
    return str(i.get("criterio") or "").strip() == "mas_barato"


def _sin_criterio(i):
    return not i.get("criterio")


def _tope(valor):
    def _chk(i):
        return i.get("tope_presupuesto") == valor
    return _chk


def _sin_tope(i):
    return not i.get("tope_presupuesto")


def _excluye(tipo, fragmento):
    def _chk(i):
        return any(e.get("tipo") == tipo
                   and fragmento in str(e.get("valor") or "").lower()
                   for e in (i.get("exclusiones") or []))
    return _chk


def _sin_exclusiones(i):
    return not i.get("exclusiones")


def _uso_contiene(fragmento):
    def _chk(i):
        return fragmento in str(i.get("uso_previsto") or "").lower()
    return _chk


# (descripcion, mensaje, [(nombre_chequeo, chequeo)])
CASOS = [
    # ── CRITERIO ECONOMICO: las parafrasis de Martin y mas ──────────────────
    ("criterio: gastar lo menos posible",
     "quiero gastar lo menos posible",
     [("lee mas_barato", _criterio_barato)]),
    ("criterio: presupuesto muy ajustado",
     "mi presupuesto es muy ajustado, que me conviene?",
     [("lee mas_barato", _criterio_barato)]),
    ("criterio: situacion economica",
     "con la situacion economica actual dame algo acorde",
     [("lee mas_barato", _criterio_barato)]),
    ("criterio: no estoy para gastar",
     "la verdad no estoy para gastar mucho",
     [("lee mas_barato", _criterio_barato)]),
    ("criterio: algo accesible",
     "tenes algo accesible?",
     [("lee mas_barato", _criterio_barato)]),
    ("criterio: bolsillo flaco",
     "ando flaco de bolsillo, que me recomendas",
     [("lee mas_barato", _criterio_barato)]),
    ("negativa: pregunta comun no prende criterio",
     "el teclado viene en otro color?",
     [("sin criterio", _sin_criterio)]),

    # ── TOPE DE PRESUPUESTO: solo con cifra ─────────────────────────────────
    ("tope: tengo 100 lucas",
     "tengo 100 lucas para el mouse y el teclado",
     [("tope 100000", _tope(100000))]),
    ("tope: no mas de 50 mil",
     "no quiero gastar mas de 50 mil",
     [("tope 50000", _tope(50000))]),
    ("tope: hasta 80000",
     "hasta 80000 puedo estirarme",
     [("tope 80000", _tope(80000))]),
    ("negativa: ajustado sin cifra NO es tope",
     "estoy re ajustado este mes",
     [("sin tope", _sin_tope), ("lee mas_barato", _criterio_barato)]),

    # ── EXCLUSIONES por origen ──────────────────────────────────────────────
    ("origen: sin partes chinas",
     "si no tiene partes chinas mejor",
     [("excluye china", _excluye("origen", "chin"))]),
    ("origen: que no sea chino",
     "dame un mouse que no sea chino",
     [("excluye china", _excluye("origen", "chin"))]),
    ("origen: marcas que no sean chinas",
     "quiero marcas que no sean chinas",
     [("excluye china", _excluye("origen", "chin"))]),
    ("origen: nada made in china",
     "nada made in china por favor",
     [("excluye china", _excluye("origen", "chin"))]),

    # ── EXCLUSIONES por marca ───────────────────────────────────────────────
    ("marca: nada de Redragon",
     "nada de Redragon, tuve mala experiencia",
     [("excluye redragon", _excluye("marca", "redragon"))]),
    ("marca: esa marca no, referida",
     "el teclado esta bien pero esa marca no me gusta",
     [("excluye redragon", _excluye("marca", "redragon"))]),
    ("marca: menos Genius",
     "cualquier mouse menos Genius",
     [("excluye genius", _excluye("marca", "genius"))]),
    ("negativa: pregunta por una marca NO la excluye",
     "tenes algo de Logitech?",
     [("sin exclusiones", _sin_exclusiones)]),

    # ── USO PREVISTO ────────────────────────────────────────────────────────
    ("uso: para la oficina",
     "es para la oficina, uso de todos los dias",
     [("uso oficina", _uso_contiene("oficina"))]),
    ("uso: hijo que juega",
     "es para mi hijo que juega en la compu",
     [("uso juego/gaming", lambda i: any(
         x in str(i.get("uso_previsto") or "").lower()
         for x in ("gam", "jug", "juego")))]),
    ("uso: editar videos",
     "lo necesito para editar videos",
     [("uso edicion", lambda i: any(
         x in str(i.get("uso_previsto") or "").lower()
         for x in ("edic", "edit", "video")))]),

    # ── COMBINADAS: varios campos en un mensaje ─────────────────────────────
    ("combinada: tope + origen + uso",
     "tengo 60 mil, que no sea chino, es para trabajar en casa",
     [("tope 60000", _tope(60000)),
      ("excluye china", _excluye("origen", "chin")),
      ("uso trabajo/casa", lambda i: bool(i.get("uso_previsto")))]),
    ("combinada: barato + marca",
     "lo mas economico que tengas pero nada de Redragon",
     [("lee mas_barato", _criterio_barato),
      ("excluye redragon", _excluye("marca", "redragon"))]),
]


async def correr(verbose: bool = True) -> float:
    install()
    from app.core.interpretador import interpretar_mensaje

    ok_total = 0
    fallas = []
    for idx, (desc, msg, checks) in enumerate(CASOS, 1):
        interp = await interpretar_mensaje(
            msg, _HIST, f"paraf{idx:02d}",
            estado_anterior="explorando", productos_vistos=_VISTOS)
        fallos_caso = [n for n, chk in checks if not chk(interp)]
        if fallos_caso:
            fallas.append((idx, desc, fallos_caso, {
                "criterio": interp.get("criterio"),
                "tope": interp.get("tope_presupuesto"),
                "exclusiones": interp.get("exclusiones"),
                "uso": interp.get("uso_previsto")}))
            estado = "FALLA"
        else:
            ok_total += 1
            estado = "ok"
        if verbose:
            print(f"[{idx:02d}] {estado}  {desc}")
    score = ok_total / len(CASOS)
    if verbose:
        print(f"\nPUNTAJE: {ok_total}/{len(CASOS)} = {score:.0%} (piso {PISO:.0%})")
        for idx, desc, fallos, leido in fallas:
            print(f"  [{idx:02d}] {desc}\n       fallo: {fallos}\n       leyo: {leido}")
    return score


if __name__ == "__main__":
    puntaje = asyncio.run(correr())
    sys.exit(0 if puntaje >= PISO else 1)
