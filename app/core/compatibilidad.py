"""COMPATIBILIDAD — el eje que hasta hoy contestaba el modelo de memoria."""
import csv
import json
import os
import re

from app.core.contexto_turno import tienda_por_defecto
from app.core.filtros_catalogo import _norm
from app.logger import get_logger

log = get_logger(__name__)

# columnas multivaluadas de la tabla, separadas por |
CAMPOS_LISTA = ("conecta_por", "plataformas", "requiere", "provee",
                "no_compatible")

_CACHE_TABLA: dict[str, dict] = {}
_CACHE_VOCAB: dict[str, dict] = {}


def _ruta(tienda_id: str | None, archivo: str) -> str | None:
    """Ruta a un archivo de la tienda resuelta por scandir: el tienda_id puede venir de un path param HTTP y
    nunca se concatena crudo (mismo criterio que fuente_producto)."""
    tid = tienda_id or tienda_por_defecto()
    base = os.path.join(os.path.dirname(__file__), "..", "..", "data", "clientes")
    try:
        with os.scandir(base) as it:
            for entry in it:
                if entry.is_dir() and entry.name == tid:
                    ruta = os.path.join(entry.path, archivo)
                    return ruta if os.path.exists(ruta) else None
    except OSError:
        pass
    return None


def vocabulario(tienda_id: str | None = None) -> dict:
    """El vocabulario cerrado: {plataformas: {id: {...}}, conectores: {id: {...}}, familias: {id: familia},
    alias: {palabra: id}}."""
    tid = tienda_id or tienda_por_defecto()
    if tid in _CACHE_VOCAB:
        return _CACHE_VOCAB[tid]
    vocab = {"plataformas": {}, "conectores": {}, "familias": {},
             "alias_plataforma": {}, "alias_conector": {}, "preguntas": [],
             "familias_adentro": list(FAMILIAS_ADENTRO)}
    ruta = _ruta(tid, "compatibilidad_vocabulario.json")
    if ruta:
        try:
            with open(ruta, encoding="utf-8") as f:
                crudo = json.load(f)
            for p in (crudo.get("plataformas") or []):
                pid = str(p.get("id") or "").strip()
                if not pid:
                    continue
                vocab["plataformas"][pid] = {"etiqueta": p.get("etiqueta") or pid}
                for a in ([pid] + list(p.get("alias") or [])):
                    # el alias ambiguo NO se pisa: "de apple" lo declaran macos e
                    # ios, y quedarse con el primero seria elegir por el cliente.
                    a = _norm(a)
                    if a:
                        vocab["alias_plataforma"].setdefault(a, set()).add(pid)
            for c in (crudo.get("conectores") or []):
                cid = str(c.get("id") or "").strip()
                if not cid:
                    continue
                vocab["conectores"][cid] = {"etiqueta": c.get("etiqueta") or cid}
                vocab["familias"][cid] = str(c.get("familia") or cid)
                for a in ([cid] + list(c.get("alias") or [])):
                    a = _norm(a)
                    if a:
                        vocab["alias_conector"].setdefault(a, set()).add(cid)
            vocab["preguntas"] = [_norm(q) for q in (crudo.get("preguntas") or [])
                                  if q]
            if crudo.get("familias_adentro") is not None:
                vocab["familias_adentro"] = [str(f) for f in crudo["familias_adentro"]]
        except Exception as e:
            log.warning("compatibilidad_vocab_error", tienda_id=tid,
                        error=str(e)[:150])
    _CACHE_VOCAB[tid] = vocab
    return vocab


def tabla(tienda_id: str | None = None) -> dict:
    """{(marca, modelo, categoria): {campo: [valores]}} desde compatibilidad.csv."""
    tid = tienda_id or tienda_por_defecto()
    if tid in _CACHE_TABLA:
        return _CACHE_TABLA[tid]
    out: dict = {}
    ruta = _ruta(tid, "compatibilidad.csv")
    if ruta:
        vocab = vocabulario(tid)
        validos = {"plataformas": set(vocab["plataformas"]),
                   "no_compatible": set(vocab["plataformas"]),
                   "conecta_por": set(vocab["conectores"]),
                   "requiere": set(vocab["conectores"]),
                   "provee": set(vocab["conectores"])}
        desconocidos: set = set()
        try:
            with open(ruta, encoding="utf-8") as f:
                for fila in csv.DictReader(f):
                    clave = (_norm(fila.get("marca")), _norm(fila.get("modelo")),
                             _norm(fila.get("categoria")))
                    datos: dict = {}
                    for campo in CAMPOS_LISTA:
                        vals = []
                        for v in str(fila.get(campo) or "").split("|"):
                            v = v.strip()
                            if not v:
                                continue
                            if v in validos[campo]:
                                vals.append(v)
                            else:
                                desconocidos.add(f"{campo}:{v}")
                        datos[campo] = vals
                    datos["nota"] = str(fila.get("nota") or "").strip()
                    if any(datos[c] for c in CAMPOS_LISTA) or datos["nota"]:
                        out[clave] = datos
        except Exception as e:
            log.warning("compatibilidad_tabla_error", tienda_id=tid,
                        error=str(e)[:150])
        if desconocidos:
            log.warning("compatibilidad_valores_fuera_de_vocabulario",
                        tienda_id=tid, valores=sorted(desconocidos)[:12])
    _CACHE_TABLA[tid] = out
    return out


# LO QUE VA ADENTRO DEL EQUIPO depende de su placa, no de la plataforma: una memoria pide la ranura, no "PC". Son
# familias de conectores; cada tienda las cambia con "familias_adentro" en su vocabulario. Un nombre que termina en
# "_" es un prefijo: "ranura_" son todas las ranuras.
FAMILIAS_ADENTRO = ("socket", "ranura_", "formato_")


def va_adentro(prod: dict, tienda_id: str | None = None) -> bool:
    """Si lo que el producto requiere va adentro del equipo: entonces el equipo dicho no alcanza, hace falta su modelo."""
    v = vocabulario(tienda_id)
    adentro = v["familias_adentro"]
    return any(any(f == a or (a.endswith("_") and f.startswith(a)) for a in adentro)
               for f in (v["familias"].get(c, "") for c in compat_de(prod, tienda_id).get("requiere") or []))


def compat_de(prod: dict, tienda_id: str | None = None) -> dict:
    """La fila de compatibilidad de un producto, o {} si el modelo no esta cargado."""
    if not isinstance(prod, dict):
        return {}
    ya = prod.get("compat")
    if isinstance(ya, dict) and ya:
        return ya
    clave = (_norm(prod.get("marca")), _norm(prod.get("modelo")),
             _norm(prod.get("categoria")))
    return dict(tabla(tienda_id).get(clave) or {})


# ── LECTURA DEL MENSAJE: que equipo declaro el cliente ───────────────────────
def plataformas_del_mensaje(mensaje: str,
                            tienda_id: str | None = None) -> list[str]:
    """Los equipos que el cliente nombro, por alias del vocabulario."""
    m = _norm(mensaje)
    if not m:
        return []
    v = vocabulario(tienda_id)
    out: list[str] = []
    for alias in sorted(v["alias_plataforma"], key=len, reverse=True):
        patron = r"\b" + re.escape(alias) + r"\b"
        if re.search(patron, m):
            for pid in sorted(v["alias_plataforma"][alias]):
                if pid not in out:
                    out.append(pid)
            # LO LEIDO NO SE LEE DOS VECES: en "tablet android", "tablet" ya es parte de lo dicho y no suma el iPad.
            m = re.sub(patron, " ", m)
    return out


def conectores_del_mensaje(mensaje: str, tienda_id: str | None = None) -> list[str]:
    """Las ranuras, zocalos y puertos que el cliente dijo que tiene su equipo, por alias del vocabulario."""
    m = _norm(mensaje)
    v = vocabulario(tienda_id)
    out: list[str] = []
    for alias in sorted(v["alias_conector"], key=len, reverse=True):
        if m and re.search(r"\b" + re.escape(alias) + r"\b", m):
            out += [c for c in sorted(v["alias_conector"][alias]) if c not in out]
    return out


def por_conector(prod: dict, mensaje: str, tienda_id: str | None = None) -> tuple[str, str]:
    """EL EQUIPO DICHO SOLO POR SU RANURA: "una placa DDR5", "un zocalo AM5". Si el producto requiere un conector de esa
    familia, anda si es ese y no anda si es otro. ("", "") si el mensaje no nombra un conector de una familia que el
    producto requiera."""
    compat = compat_de(prod, tienda_id)
    fam = vocabulario(tienda_id)["familias"]
    requiere = compat.get("requiere") or []
    nombre = str(prod.get("nombre") or "el producto")
    for c in conectores_del_mensaje(mensaje, tienda_id):
        mismos = [r for r in requiere if fam.get(r, r) == fam.get(c, c)]
        if not mismos:
            continue
        nota = (" " + compat["nota"]) if compat.get("nota") else ""
        if c in mismos:
            return "compatible", f"{nombre} va en un equipo con {etiqueta_conector(c, tienda_id)}.{nota}"
        return "incompatible", (f"{nombre} no va en un equipo con {etiqueta_conector(c, tienda_id)}: necesita "
                                f"{etiqueta_conector(mismos[0], tienda_id)}.{nota}")
    return "", ""


def choca_con_lo_dicho(prod: dict, mensaje: str, tienda_id: str | None = None) -> str:
    """EL EQUIPO DICHO CON SU RANURA: "una PC con placa DDR5". Si el cliente nombra un conector de la misma familia que
    uno que el producto requiere, y no es ese, y la nota de la ficha dice que en ese no va, no es compatible aunque la
    plataforma lo sea. Devuelve la etiqueta del conector que choca, o "". Sin la nota no se afirma nada."""
    compat = compat_de(prod, tienda_id)
    fam = vocabulario(tienda_id)["familias"]
    requiere = set(compat.get("requiere") or [])
    nota = _norm(compat.get("nota"))
    v = vocabulario(tienda_id)
    for c in conectores_del_mensaje(mensaje, tienda_id):
        if c in requiere or not any(fam.get(r, r) == fam.get(c, c) for r in requiere):
            continue
        alias = [a for a, ids in v["alias_conector"].items() if c in ids]
        if any(re.search(r"\b" + re.escape(a) + r"\b", nota) for a in alias):
            return etiqueta_conector(c, tienda_id)
    return ""


def etiqueta_plataforma(pid: str, tienda_id: str | None = None) -> str:
    v = vocabulario(tienda_id)
    return (v["plataformas"].get(pid) or {}).get("etiqueta", pid)


def etiqueta_conector(cid: str, tienda_id: str | None = None) -> str:
    v = vocabulario(tienda_id)
    return (v["conectores"].get(cid) or {}).get("etiqueta", cid)


# ── LOS DOS VEREDICTOS ────────────────────────────────────────────
def evaluar(prod: dict, plataforma: str,
            tienda_id: str | None = None) -> tuple[str, str]:
    """¿Este producto anda con el equipo que tiene el cliente?"""
    compat = compat_de(prod, tienda_id)
    if not compat or not plataforma:
        return "sin_dato", ""
    nombre = str(prod.get("nombre") or "el producto")
    etq = etiqueta_plataforma(plataforma, tienda_id)
    if plataforma in (compat.get("no_compatible") or []):
        from app.core.guia_venta_prosa import mensaje
        return "incompatible", (
            mensaje("compat_no_va_con",
                    "{producto} no es compatible con {plataforma}. ",
                    producto=nombre, plataforma=etq)
            + (compat.get("nota") or ""))
    if plataforma in (compat.get("plataformas") or []):
        conectores = compat.get("conecta_por") or []
        via = ", ".join(etiqueta_conector(c, tienda_id) for c in conectores[:2])
        return "compatible", (f"{nombre} anda con {etq}"
                              + (f", se conecta por {via}." if via else ".")
                              + (" " + compat["nota"] if compat.get("nota") else ""))
    return "sin_dato", ""


def evaluar_par(prod_a: dict, prod_b: dict,
                tienda_id: str | None = None) -> tuple[str, str]:
    """¿Estos dos productos van juntos? Cruza lo que uno REQUIERE contra lo que el otro PROVEE, en las dos
    direcciones."""
    ca, cb = compat_de(prod_a, tienda_id), compat_de(prod_b, tienda_id)
    if not ca or not cb:
        return "sin_dato", ""
    v = vocabulario(tienda_id)
    fam = v["familias"]
    na = str(prod_a.get("nombre") or "el primero")
    nb = str(prod_b.get("nombre") or "el segundo")

    # EL NO EXPLICITO MANDA, y va primero. Si la CATEGORIA de uno es una plataforma que el otro declara no
    # compatible, no hay cruce de familias que valga: es el caso exacto de la memoria RAM de escritorio contra
    # la notebook, que por familias daba sin_dato -la notebook no declara ranuras de memoria- y es justo el
    # que hay que negar sin dudar.
    for compat, otro_prod, quien, otro in ((ca, prod_b, na, nb),
                                           (cb, prod_a, nb, na)):
        cat_otro = _norm(otro_prod.get("categoria")).replace(" ", "_")
        if cat_otro and cat_otro in (compat.get("no_compatible") or []):
            from app.core.guia_venta_prosa import mensaje
            return "incompatible", (
                mensaje("compat_no_van_juntos",
                        "No van juntos: {producto} no es compatible con "
                        "{plataforma}. ", producto=quien,
                        plataforma=etiqueta_plataforma(cat_otro, tienda_id))
                + (compat.get("nota") or "")).strip()

    def _por_familia(ids):
        d: dict = {}
        for i in ids or []:
            d.setdefault(fam.get(i, i), set()).add(i)
        return d

    veredicto, motivos = "sin_dato", []
    for req, prov, quien, otro in ((ca.get("requiere"), cb.get("provee"), na, nb),
                                   (cb.get("requiere"), ca.get("provee"), nb, na)):
        fr, fp = _por_familia(req), _por_familia(prov)
        for familia, pedidos in fr.items():
            ofrecidos = fp.get(familia)
            if not ofrecidos:
                continue
            if pedidos & ofrecidos:
                if veredicto != "incompatible":
                    veredicto = "compatible"
                    comun = sorted(pedidos & ofrecidos)[0]
                    motivos.append(f"{quien} pide {etiqueta_conector(comun, tienda_id)} "
                                   f"y {otro} lo tiene")
            else:
                pide = etiqueta_conector(sorted(pedidos)[0], tienda_id)
                tiene = etiqueta_conector(sorted(ofrecidos)[0], tienda_id)
                return "incompatible", (f"No van juntos: {quien} necesita {pide} "
                                        f"y {otro} tiene {tiene}.")
    if veredicto == "compatible":
        from app.core.guia_venta_prosa import mensaje
        return "compatible", (mensaje("compat_van_juntos", "Van juntos sin problema: ")
                              + "; ".join(motivos[:2]) + ".")
    return "sin_dato", ""
