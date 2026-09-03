"""
LOS CASOS DE ORO — la vara por CAPA, y lo que el cableado de hoy no cumple.

QUE ES. El paso 0 de `arquitectura/BRIEF_MOTOR_V2.md`. Las capas 2, 4 y 5 son
cableado puro -no hay modelo adentro- asi que su vara se escribe entera a mano:
la ENTRADA correcta y la SALIDA correcta, las dos en `tests/oro/`. Este archivo
corre el codigo de HOY contra esos casos y dice, capa por capa, cual no cumple.

    python3 banco_pruebas/oro.py            # las tres capas, offline y gratis
    python3 banco_pruebas/oro.py --capa 2   # una sola
    python3 banco_pruebas/oro.py --fijar    # refija el piso

POR QUE NO ALCANZABAN LOS CASETES. Un casete graba lo que el modelo DIJO,
incluso cuando lo dijo mal, y despues la bateria verde confirma un
comportamiento equivocado. Y cuando el vivo falla, nadie sabe en que capa se
perdio el dato, asi que se le echa la culpa al modelo. Un caso de oro no se
regraba nunca: se corrige a mano.

QUE MIDE CADA CAPA, y con que pieza del codigo de hoy:

    capa 2  RESOLVER   `resolver.resolver(declarado, memoria, tienda, trace)`
    capa 4  COMPUERTA  `salida.procedencia` + `salida.plata`
    capa 5  CIERRE     `cierre` + `leads` + `pago`, las decisiones deterministas

LO QUE ESTE ARCHIVO NO HACE, y es a proposito: no decide nada. El adaptador de
la capa 2 LEE hechos de las llamadas -que ids salieron certificados, que temas
volvieron con material, que localidades quedaron cotizadas- y los compara con
lo escrito a mano. Ninguna regla del motor nuevo vive aca.

DONDE ES GRUESO, dicho para que nadie lo lea como fino:
  - `restricciones:N` se da por cubierto si la busqueda derivada lleva CUALQUIER
    filtro, orden u operacion. No se verifica que sea la traduccion de ESA
    restriccion: eso no se puede leer del pedido derivado sin volver a
    interpretar castellano.
  - `temas:N` se cuenta por cantidad -el N-esimo tema declarado esta cubierto si
    volvieron al menos N temas con material-, no por atadura uno a uno.
"""
import json
import sys
import unicodedata
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import sim_firestore  # noqa: E402

sim_firestore.install()

from app.core import herramientas as H  # noqa: E402
from app.storage.firestore_client import get_product_by_id  # noqa: E402

TIENDA = "verifika_prod"
ORO = _RAIZ / "tests" / "oro"
PISO = _RAIZ / "banco_pruebas" / "oro_piso.json"


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _casos(capa: str) -> list:
    d = ORO / capa
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(d.glob("*.json"))]


def _falla(fallas: list, que: str) -> None:
    fallas.append(que)


# ══════════════════════════════════════════════════════════════════════════
# CAPA 2 — EL RESOLVER
# ══════════════════════════════════════════════════════════════════════════

def _productos_de(llamadas: list) -> list:
    """Todo producto que la fuente devolvio este turno, de cualquier proyeccion."""
    out = []
    for l in llamadas:
        r = l.get("resultado") or {}
        out += list(r.get("productos") or [])
        out += list(r.get("hay_en_la_categoria") or [])
        if isinstance(r.get("producto"), dict):
            out.append(r["producto"])
    return [p for p in out if isinstance(p, dict) and p.get("id")]


def _temas_con_material(llamadas: list) -> list:
    """Los temas que volvieron con algo escrito. Un tema certificado que llega
    sin politica, criterio ni movida no le sirve al redactor: es un nombre."""
    out = []
    for l in llamadas:
        for t in ((l.get("resultado") or {}).get("temas") or []):
            if not isinstance(t, dict):
                continue
            if t.get("politica") or t.get("criterio") or t.get("movida"):
                out.append(str(t.get("tema") or ""))
    return out


def _localidades_cotizadas(llamadas: list, bloque: str) -> list:
    out = []
    for l in llamadas:
        if l.get("herramienta") not in ("cotizar", "armar_presupuesto"):
            continue
        ped = l.get("pedido") or {}
        if ped.get("localidad"):
            out.append(str(ped["localidad"]))
        for d in (ped.get("destinos") or []):
            out.append(str(d))
        for it in (ped.get("items") or []):
            if isinstance(it, dict) and it.get("destino"):
                out.append(str(it["destino"]))
    for e in _envios_del_bloque(bloque):
        out.append(e)
    return out


def _envios_del_bloque(bloque: str) -> list:
    """Las localidades que el bloque de la cuenta nombra. El envio puede estar
    resuelto y no haber pasado por una llamada propia."""
    out = []
    for linea in (bloque or "").splitlines():
        n = norm(linea)
        if n.startswith("envio a") or " a " in n and n.startswith("envio"):
            out.append(linea.split(" a ", 1)[-1].strip(" .:"))
    return out


def _orden_derivado(llamadas: list) -> dict:
    for l in llamadas:
        ped = l.get("pedido") or {}
        if ped.get("ordenar_por"):
            return {"campo": str(ped["ordenar_por"]),
                    "direccion": str(ped.get("direccion") or "")}
    return {}


def _hay_filtro(llamadas: list) -> bool:
    for l in llamadas:
        ped = l.get("pedido") or {}
        if any(ped.get(k) for k in ("ordenar_por", "filtros", "excluir",
                                    "operacion", "campo")):
            return True
    return False


def _fichas_pedidas(llamadas: list) -> list:
    """Las fichas que el turno trajo, con el producto adentro."""
    out = []
    for l in llamadas:
        ped, res = l.get("pedido") or {}, l.get("resultado") or {}
        if ped.get("proyeccion") == "ficha" and res.get("estado") == "encontrado":
            out.append(res.get("producto") or {})
    return out


def _compat_pedidas(llamadas: list) -> list:
    out = []
    for l in llamadas:
        ped, res = l.get("pedido") or {}, l.get("resultado") or {}
        if ped.get("proyeccion") == "compatibilidad" and res.get("compatibilidad"):
            out.append(res)
    return out


# El NO honesto de la fuente. Que una busqueda vuelva sin productos no es
# quedarse sin material: "no vendemos celulares" es exactamente el dato que el
# turno necesita, y sale certificado del codigo.
_EL_NO_HONESTO = ("no_vendemos", "no_encontrado", "sin_resultados")


def _listas_con_veredicto(llamadas: list) -> list:
    """Las busquedas de lista que volvieron con material: productos, o el no
    honesto de la fuente.

    NO SE MIRA EL NOMBRE DEL ESTADO Y SE MIRA SI TRAJO ALGO, y la diferencia la
    encontro la primera corrida de esta vara. `ninguno_cumple_del_todo` -el
    estado que sale cuando el filtro no lo cumple nadie y la busqueda devuelve
    lo mas cercano- estaba fuera de la lista de estados buenos, asi que seis
    casos daban "se quedo sin material" con tres productos en la mano. Una lista
    de estados hay que mantenerla; que la llamada haya traido algo, no."""
    out = []
    for l in llamadas:
        ped, res = l.get("pedido") or {}, l.get("resultado") or {}
        if l.get("herramienta") != "consultar_productos":
            continue
        if ped.get("proyeccion") in ("ficha", "compatibilidad"):
            continue
        if res.get("productos") or res.get("hay_en_la_categoria") \
                or res.get("valores") or res.get("estado") in _EL_NO_HONESTO:
            out.append(l)
    return out


def _pega(que: str, texto: str) -> bool:
    """Comparte alguna raiz de cuatro letras. Misma regla que `indice_turno`."""
    raices = {w[:4] for w in norm(que).split() if len(w) >= 4}
    if not raices:
        return True
    n = norm(texto)
    return any(r in n for r in raices)


def _cubierto(renglon: str, declarado: dict, llamadas: list, bloque: str) -> bool:
    """Si el MATERIAL del turno trae algo para ese renglon de lo declarado.

    No mira el texto -no hay texto todavia- y no vuelve a interpretar el
    mensaje: solo pregunta si alguna llamada derivada contesta ese renglon."""
    campo, _, n = renglon.partition(":")
    i = int(n) - 1
    valores = declarado.get(campo) or []
    if campo == "pide_precio":
        return "total" in norm(bloque)
    if campo == "contradicciones":
        return False       # por contrato: una contradiccion se pregunta siempre
    if campo == "restricciones":
        return _hay_filtro(llamadas)
    if campo == "reparto_pago":
        partes = (declarado.get("reparto_pago") or [])
        return all(str(int(p.get("porcentaje", 0))) in (bloque or "")
                   for p in partes) and bool(partes)
    if i >= len(valores):
        return False
    v = valores[i]
    if campo == "items":
        que = f"{v.get('que','')} {v.get('categoria','') or ''}"
        for l in _listas_con_veredicto(llamadas):
            ped = l.get("pedido") or {}
            if _pega(que, f"{ped.get('descripcion','')} {ped.get('categoria','')}"):
                return True
        return False
    if campo == "stock":
        for l in _listas_con_veredicto(llamadas):
            ped = l.get("pedido") or {}
            if _pega(str(v), f"{ped.get('descripcion','')} {ped.get('categoria','')}"):
                return True
        return False
    if campo == "atributos":
        return _viaja_el_dato(str(v.get("de", "")), str(v.get("campo", "")),
                              llamadas)
    if campo == "compatibilidad":
        return bool(_compat_pedidas(llamadas))
    if campo == "temas":
        return len(_temas_con_material(llamadas)) > i
    if campo == "destinos":
        cotizadas = [norm(x) for x in _localidades_cotizadas(llamadas, bloque)]
        return any(_pega(str(v), c) or _pega(c, str(v)) for c in cotizadas)
    return False


def _viaja_el_dato(de: str, campo: str, llamadas: list) -> bool:
    """Si el DATO que el cliente pregunto llego en el material, no si se derivo
    tal o cual llamada.

    ES LA DIFERENCIA QUE ENCONTRO LA PRIMERA CORRIDA, y vale escribirla en los
    dos sentidos. La proyeccion `lista` NO lleva `garantia_meses`,
    `garantia_detalle`, `origen` ni `contenido_caja`, que solo estan en la
    `ficha`: un turno puede traer tres candidatos perfectos y no traer el dato
    que le preguntaron. Pero `specs` SI viaja en la lista y adentro hay
    `garantia`, `ram`, `hz` y quince mas, asi que exigir una ficha daba rojo
    donde el dato ya estaba. Ninguna de las dos se ve mirando que llamada se
    derivo; las dos se ven mirando si el campo llego con valor.

    El campo se busca por RAIZ CORTA contra los nombres de los campos del
    producto y de sus specs: 'garantia' pega en `garantia_meses`, 'peso' en
    `peso_gramos`, 'para que sirve' en `sirve_para`. Si ningun campo del
    material se llama parecido, el dato no viajo: el modelo lo contesta de su
    entrenamiento o no lo contesta."""
    candidatos = []
    for f in _fichas_pedidas(llamadas):
        candidatos.append(f)
    for p in _productos_de(llamadas):
        candidatos.append(p)
    propios = [c for c in candidatos
               if _pega(de, f"{c.get('nombre','')} {c.get('categoria','')}")]
    if not propios:
        # "ese", "esa notebook": lo que el cliente nombro sin raiz propia lo
        # resuelve la memoria, asi que sirve cualquier producto del turno.
        propios = candidatos
    raices = {w[:3] for w in norm(campo).split() if len(w) >= 3}
    if not raices:
        return bool(propios)
    for c in propios:
        campos = dict(c)
        campos.update(c.get("specs") or {})
        for k, val in campos.items():
            if k in ("specs",) or val in (None, "", [], {}):
                continue
            if any(r in norm(k) for r in raices):
                return True
    return False


def _sin_raices(que: str) -> bool:
    """'ese', 'esa notebook': lo que el cliente nombro sin ninguna raiz propia
    lo resuelve la memoria, asi que cualquier ficha del turno lo contesta."""
    return not {w for w in norm(que).split() if len(w) >= 4} - {
        "esa", "ese", "eso", "esos", "esas", "aquel", "otro", "otra",
        "alternativa", "producto", "notebook", "tablet", "mouse"}


def _correr_capa2(caso: dict) -> list:
    from app.core import resolver as R
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
    memoria = [p for p in (get_product_by_id(i, tienda_id=TIENDA)
                           for i in (caso.get("memoria") or [])) if p]
    memoria = [H._ficha(p, TIENDA) for p in memoria]
    declarado = json.loads(json.dumps(caso["declarado"]))
    r = R.resolver(declarado, memoria, TIENDA, f"oro-{caso['id']}")
    llamadas, bloque = r["llamadas"], str(r.get("bloque") or "")
    prods = _productos_de(llamadas)
    ids = {str(p.get("id")) for p in prods}
    e, fallas = caso["espera"], []

    for pid in (e.get("ids") or []):
        if pid not in ids:
            _falla(fallas, f"no salio el id {pid}")
    for pid in (e.get("ids_prohibidos") or []):
        if pid in ids:
            _falla(fallas, f"salio el id prohibido {pid}")
    for marca in (e.get("sin_marca") or []):
        sucios = [p.get("nombre") for p in prods if norm(marca) in norm(p.get("marca"))]
        if sucios:
            _falla(fallas, f"la marca excluida {marca} salio igual: {sucios[:2]}")
    if e.get("categorias"):
        buenas = {norm(c) for c in e["categorias"]}
        malas = sorted({norm(p.get("categoria")) for p in prods} - buenas)
        if malas:
            _falla(fallas, f"devolvio rubros que no son: {malas}")
        if not prods:
            _falla(fallas, "no devolvio un solo producto")
    if e.get("cuenta") and "total" not in norm(bloque):
        _falla(fallas, "no armo la cuenta: el bloque no tiene Total")
    if e.get("total_ars"):
        esperado = f"{e['total_ars']:,}".replace(",", ".")
        if esperado not in bloque:
            _falla(fallas, f"el total no es ${esperado}")
    for pedazo in (e.get("bloque_contiene") or []):
        if norm(pedazo) not in norm(bloque):
            _falla(fallas, f"el bloque no dice {pedazo!r}")
    temas = _temas_con_material(llamadas)
    for t in (e.get("temas") or []):
        if t not in temas:
            _falla(fallas, f"el tema {t} no volvio con material")
    cotizadas = [norm(x) for x in _localidades_cotizadas(llamadas, bloque)]
    for d in (e.get("envios") or []):
        if not any(_pega(d, c) or _pega(c, d) for c in cotizadas):
            _falla(fallas, f"no quedo cotizado el envio a {d}")
    if e.get("orden"):
        o = _orden_derivado(llamadas)
        if norm(o.get("campo")) != norm(e["orden"]["campo"]):
            _falla(fallas, f"no ordeno por {e['orden']['campo']}, "
                           f"ordeno por {o.get('campo') or 'nada'}")
        elif e["orden"].get("direccion") and \
                norm(o.get("direccion")) != norm(e["orden"]["direccion"]):
            _falla(fallas, f"ordeno por {o.get('campo')} pero hacia "
                           f"{o.get('direccion') or 'ninguna direccion'}")
    for rg in (e.get("cubre") or []):
        if not _cubierto(rg, declarado, llamadas, bloque):
            _falla(fallas, f"{rg} se quedo sin material")
    for rg in (e.get("no_cubre") or []):
        if _cubierto(rg, declarado, llamadas, bloque):
            _falla(fallas, f"{rg} se dio por cubierto y tenia que preguntarse")
    return fallas


# ══════════════════════════════════════════════════════════════════════════
# CAPA 4 — LA COMPUERTA
# ══════════════════════════════════════════════════════════════════════════

def _llamadas_del_material(material: dict) -> list:
    """El material del turno, armado de la FUENTE: las fichas salen del
    catalogo real y los temas de la FAQ real. Nada sale de una grabacion."""
    llamadas = []
    ids = material.get("productos") or []
    prods = [p for p in (get_product_by_id(i, tienda_id=TIENDA) for i in ids) if p]
    if prods:
        llamadas.append({
            "herramienta": "consultar_productos",
            "pedido": {"proyeccion": "lista"},
            "resultado": {"estado": "encontrado",
                          "productos": [H._ficha(p, TIENDA) for p in prods]}})
    if material.get("temas"):
        llamadas.append({
            "herramienta": "consultar_temas",
            "pedido": {"temas": list(material["temas"])},
            "resultado": H.ejecutar("consultar_temas",
                                    {"temas": list(material["temas"])}, TIENDA)})
    if material.get("bloque"):
        llamadas.append({"herramienta": "cotizar", "pedido": {"items": []},
                         "resultado": {"estado": "ok",
                                       "bloque": material["bloque"]}})
    return llamadas


# ── LA CAPA 4 QUEDO SIN MECANISMO QUE MEDIR (3-sep-2026) ──────────────────
#
# Sus diez casos estan escritos contra `salida.procedencia` y `salida.plata`, la
# compuerta de prosa que se apago con el resto de la plomeria, y su campo
# `texto` viene en el formato viejo, con las etiquetas `<d ID>...</d>` de la
# atadura. El modelo ya no escribe eso: devuelve la mesa llena.
#
# NO SE REESCRIBEN LOS CASOS ACA. Son la vara, y el que implementa no reescribe
# la vara. Lo que hay que hacer, y lo decide Martin caso por caso:
#
#   C4-01 dato que la ficha no tiene    ya no puede nacer: el material sale
#                                       vacio. Vara nueva en test_tabla.py.
#   C4-02 plata que no calculo el codigo  cubierto por `_limpiar`, y ademas el
#                                       modelo no tiene casilla de plata.
#   C4-09 cuenta retipeada              cubierto: la casilla sellada se ignora.
#   C4-10 volcado interno               cubierto por `_limpiar`.
#   C4-07 id que el turno no trajo      cubierto a medias: `_limpiar` corta la
#                                       oracion con el id, pero una afirmacion
#                                       SIN id colgada de nada sigue pasando.
#   C4-03, C4-04, C4-05, C4-06, C4-08   NO estan cubiertos por estructura. Son
#                                       contenido de la prosa adentro de una
#                                       casilla, y ahi el esquema no llega.
#                                       Hay que decidir si se reescriben contra
#                                       la mesa o si se aceptan como riesgo.
#
# Mientras tanto la capa 4 no da un numero: dar uno falso -verde porque no corre,
# o rojo porque el mecanismo no existe- es peor que decir que falta.
def _correr_capa4(caso: dict) -> list:
    return ["MECANISMO APAGADO: el caso mide `salida.procedencia`/`salida.plata`, "
            "que se fueron a archivo/. Hay que reescribirlo contra la mesa."]
    from app.core import salida as S
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
    material = caso.get("material") or {}
    llamadas = _llamadas_del_material(material)
    bloque = str(material.get("bloque") or "")
    trace = f"oro-{caso['id']}"
    texto = S.procedencia(caso["texto"], llamadas, trace, TIENDA)
    texto = S.plata(texto, llamadas, bloque, trace)
    e, fallas = caso["espera"], []
    for pedazo in (e.get("corta") or []):
        if norm(pedazo) in norm(texto):
            _falla(fallas, f"dejo pasar {pedazo!r}")
    for pedazo in (e.get("conserva") or []):
        if norm(pedazo) not in norm(texto):
            _falla(fallas, f"se llevo puesto {pedazo!r}, que era bueno")
    if not (texto or "").strip():
        _falla(fallas, "dejo al bot mudo")
    return fallas


# ══════════════════════════════════════════════════════════════════════════
# CAPA 5 — EL CIERRE
# ══════════════════════════════════════════════════════════════════════════

def _correr_capa5(caso: dict) -> list:
    from app.core import cierre as C
    from app.core import leads as L
    from app.core import pago as PG
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
    st, e, fallas = caso.get("estado") or {}, caso["espera"], []

    if "dispara_lead" in e:
        got = C.dispara_lead_fuerte(bool(st.get("pregunta_hecha")),
                                    str(st.get("respuesta") or ""))
        if got != e["dispara_lead"]:
            _falla(fallas, f"dispara_lead_fuerte dio {got}")
    if "es_no_interesado" in e:
        got = C.es_no_interesado(str(st.get("respuesta") or ""))
        if got != e["es_no_interesado"]:
            _falla(fallas, f"es_no_interesado dio {got}")
    if "pide_cobro" in e:
        got = bool(L._RE_PIDE_COBRO.search(str(st.get("respuesta") or "")))
        if got != e["pide_cobro"]:
            _falla(fallas, f"_RE_PIDE_COBRO dio {got}")
    if "medio_pago" in e:
        got = PG.elegir_medio_pago(str(st.get("forma_pago") or ""))
        if got != e["medio_pago"]:
            _falla(fallas, f"elegir_medio_pago dio {got!r}")
    if "faltantes" in e:
        got = C.faltantes(st.get("lead") or {})
        if sorted(got) != sorted(e["faltantes"]):
            _falla(fallas, f"faltantes dio {got}")
    if "cobro_contiene" in e or "cobro_no_contiene" in e:
        txt = PG.mensaje_transferencia(PG.datos_transferencia(TIENDA))
        for p in (e.get("cobro_contiene") or []):
            if norm(p) not in norm(txt):
                _falla(fallas, f"el mensaje de cobro no dice {p!r}")
        for p in (e.get("cobro_no_contiene") or []):
            if norm(p) in norm(txt):
                _falla(fallas, f"el mensaje de cobro dice {p!r}, que es inventado")
    if "confirmacion_contiene" in e or "confirmacion_no_contiene" in e:
        txt = C.mensaje_confirmacion(st.get("lead") or {})
        for p in (e.get("confirmacion_contiene") or []):
            if norm(p) not in norm(txt):
                _falla(fallas, f"la confirmacion no dice {p!r}")
        for p in (e.get("confirmacion_no_contiene") or []):
            if norm(p) in norm(txt):
                _falla(fallas, f"la confirmacion promete {p!r} sin el dato")
    return fallas


_CAPAS = {"2": ("capa2", _correr_capa2, "EL RESOLVER"),
          "4": ("capa4", _correr_capa4, "LA COMPUERTA"),
          "5": ("capa5", _correr_capa5, "EL CIERRE")}


def correr(capas=None) -> dict:
    out = {}
    for n in (capas or sorted(_CAPAS)):
        carpeta, fn, _ = _CAPAS[n]
        filas = []
        for caso in _casos(carpeta):
            try:
                fallas = fn(caso)
            except Exception as ex:  # noqa: BLE001 — un caso roto no tumba la vara
                import traceback
                fallas = [f"EXCEPCION {type(ex).__name__}: {str(ex)[:120]} "
                          f"({traceback.format_exc().splitlines()[-3][:80]})"]
            filas.append({"id": caso["id"], "de": caso.get("de", ""),
                          "que": caso.get("que", ""), "ok": not fallas,
                          "fallas": fallas, "nota": caso.get("nota", "")})
        out[n] = filas
    return out


def piso() -> dict:
    try:
        return json.loads(PISO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fijar(r: dict) -> None:
    p = {f"capa{n}": sum(1 for f in filas if f["ok"]) for n, filas in r.items()}
    p.update({f"capa{n}_total": len(filas) for n, filas in r.items()})
    PISO.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main() -> int:
    capas = None
    if "--capa" in sys.argv:
        capas = [sys.argv[sys.argv.index("--capa") + 1]]
    r = correr(capas)
    if "--fijar" in sys.argv:
        fijar(r)
        print(f"piso fijado en {PISO.name}")
        return 0
    print("=" * 78)
    print("LOS CASOS DE ORO — el cableado de HOY contra la vara escrita a mano")
    print("=" * 78)
    for n, filas in r.items():
        verdes = [f for f in filas if f["ok"]]
        print(f"\n{'─' * 78}\nCAPA {n} — {_CAPAS[n][2]}: "
              f"{len(verdes)} de {len(filas)}\n{'─' * 78}")
        for f in filas:
            print(f"[{'OK ' if f['ok'] else 'MAL'}] {f['id']}  {f['que']}")
            for x in f["fallas"]:
                print(f"        → {x}")
            if not f["ok"] and f["nota"]:
                print(f"        nota: {f['nota']}")
    print("\n" + "=" * 78)
    total_ok = sum(1 for filas in r.values() for f in filas if f["ok"])
    total = sum(len(filas) for filas in r.values())
    for n, filas in r.items():
        rojas = [f["id"] for f in filas if not f["ok"]]
        print(f"CAPA {n} EN ROJO ({len(rojas)}): "
              f"{', '.join(rojas) if rojas else 'ninguna'}")
    print(f"EL MARCADOR DE LAS TRES CAPAS: {total_ok} de {total}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
