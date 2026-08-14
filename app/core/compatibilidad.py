"""
COMPATIBILIDAD — el eje que hasta hoy contestaba el modelo de memoria.

El reparto de poder es el mismo de siempre: el CODIGO decide, el modelo redacta.
La identidad la decide el certificador; la plata, el verificador de montos; la
spec, la fuente. La compatibilidad no tenia dueño: el criterio jurado dice "se
responde con la ficha, no de memoria", pero la ficha no traia ni el conector ni
el zocalo ni el sistema, asi que el modelo razonaba solo. De ahi salio la
alucinacion que cazo el juez el 29-jul -"es compatible con cualquier notebook",
dicha sobre una memoria RAM de escritorio, que en una notebook no entra-.

Ahora hay dato: `compatibilidad.csv`, una fila por MODELO, atada al vocabulario
CERRADO de `compatibilidad_vocabulario.json`. Este modulo lo lee y responde las
dos preguntas que hace un cliente, las dos deterministas:

  1. "¿anda con lo que YO tengo?"  -> `evaluar(prod, plataforma)`
  2. "¿este va con este otro?"     -> `evaluar_par(prod_a, prod_b)`, que cruza
     lo que uno REQUIERE contra lo que el otro PROVEE.

Tres veredictos de primera clase, igual que el certificador: `compatible`,
`incompatible` y `sin_dato`. `sin_dato` NO es un error, es el resultado honesto:
se le dice al cliente que no esta confirmado y que se verifica antes de comprar,
que es exactamente lo que pide el criterio jurado. Lo que NO puede pasar es que
el hueco lo llene el modelo.

La regla de INCOMPATIBLE es por FAMILIA, no por lista de pares: si los dos lados
declaran la misma familia (socket, ranura de memoria) con valores distintos, no
entra y punto. Sin esa nocion habria que cargar 482x482 pares; con ella, sumar
un producto es una fila.
"""
import csv
import json
import os
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

# columnas multivaluadas de la tabla, separadas por |
CAMPOS_LISTA = ("conecta_por", "plataformas", "requiere", "provee",
                "no_compatible")

_CACHE_TABLA: dict[str, dict] = {}
_CACHE_VOCAB: dict[str, dict] = {}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _ruta(tienda_id: str | None, archivo: str) -> str | None:
    """Ruta a un archivo de la tienda resuelta por scandir: el tienda_id puede
    venir de un path param HTTP y nunca se concatena crudo (mismo criterio que
    fuente_producto)."""
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
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
    """El vocabulario cerrado: {plataformas: {id: {...}}, conectores: {id: {...}},
    familias: {id: familia}, alias: {palabra: id}}. Si el archivo falta se
    devuelve vacio y todo el modulo queda en no-op honesto."""
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
    if tid in _CACHE_VOCAB:
        return _CACHE_VOCAB[tid]
    vocab = {"plataformas": {}, "conectores": {}, "familias": {},
             "alias_plataforma": {}, "alias_conector": {}, "preguntas": []}
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
        except Exception as e:
            log.warning("compatibilidad_vocab_error", tienda_id=tid,
                        error=str(e)[:150])
    _CACHE_VOCAB[tid] = vocab
    return vocab


def tabla(tienda_id: str | None = None) -> dict:
    """{(marca, modelo, categoria): {campo: [valores]}} desde compatibilidad.csv.
    Se valida contra el vocabulario al cargar: un id que no existe se DESCARTA y
    se loguea, asi un typo en la planilla no se convierte en una respuesta."""
    tid = tienda_id or os.getenv("TIENDA_ID", "verifika_prod")
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


def compat_de(prod: dict, tienda_id: str | None = None) -> dict:
    """La fila de compatibilidad de un producto, o {} si el modelo no esta
    cargado. Se busca por (marca, modelo, categoria), la misma clave con la que
    trabaja la capa de specs por modelo."""
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
    """Los equipos que el cliente nombro, por alias del vocabulario. El alias
    AMBIGUO no resuelve solo: "de apple" son macos e ios a la vez, y elegir uno
    seria decidir por el cliente. Se devuelven los dos y el que pregunta decide
    si alcanza para responder o hay que repreguntar."""
    m = _norm(mensaje)
    if not m:
        return []
    v = vocabulario(tienda_id)
    out: list[str] = []
    for alias in sorted(v["alias_plataforma"], key=len, reverse=True):
        if re.search(r"\b" + re.escape(alias) + r"\b", m):
            for pid in sorted(v["alias_plataforma"][alias]):
                if pid not in out:
                    out.append(pid)
    return out


def plataformas_de_interp(interp) -> list[str]:
    """Los equipos del cliente que DECLARO el interprete, atados al enum del
    vocabulario. Es la via PRINCIPAL: el modelo entiende "lo quiero para la
    compu del trabajo, que es una Mac" y una lista de alias no, por larga que
    sea. `plataformas_del_mensaje` queda de red para cuando el interprete no
    declaro nada. Una lista vacia significa que el modelo leyo el mensaje y dice
    que el cliente no nombro ningun equipo, y eso manda."""
    if not isinstance(interp, dict):
        return []
    return [str(p) for p in (interp.get("plataformas_cliente") or []) if p]


def etiqueta_plataforma(pid: str, tienda_id: str | None = None) -> str:
    v = vocabulario(tienda_id)
    return (v["plataformas"].get(pid) or {}).get("etiqueta", pid)


def etiqueta_conector(cid: str, tienda_id: str | None = None) -> str:
    v = vocabulario(tienda_id)
    return (v["conectores"].get(cid) or {}).get("etiqueta", cid)


# ── LOS DOS VEREDICTOS ───────────────────────────────────────────────────────
def evaluar(prod: dict, plataforma: str,
            tienda_id: str | None = None) -> tuple[str, str]:
    """¿Este producto anda con el equipo que tiene el cliente?

    Devuelve (veredicto, motivo) con veredicto en compatible / incompatible /
    sin_dato. El motivo es la frase para el cliente, armada desde el vocabulario:
    la escribe el CODIGO, no el modelo."""
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
    """¿Estos dos productos van juntos? Cruza lo que uno REQUIERE contra lo que
    el otro PROVEE, en las dos direcciones.

    Por FAMILIA, que es lo que evita cargar pares a mano:
      - familia que los dos declaran y comparten un valor -> compatible
      - familia que los dos declaran sin ningun valor en comun -> incompatible
      - familia que solo declara uno -> no alcanza para afirmar: sin_dato
    """
    ca, cb = compat_de(prod_a, tienda_id), compat_de(prod_b, tienda_id)
    if not ca or not cb:
        return "sin_dato", ""
    v = vocabulario(tienda_id)
    fam = v["familias"]
    na = str(prod_a.get("nombre") or "el primero")
    nb = str(prod_b.get("nombre") or "el segundo")

    # EL NO EXPLICITO MANDA, y va primero. Si la CATEGORIA de uno es una
    # plataforma que el otro declara no compatible, no hay cruce de familias que
    # valga: es el caso exacto de la memoria RAM de escritorio contra la
    # notebook, que por familias daba sin_dato -la notebook no declara ranuras de
    # memoria- y es justo el que hay que negar sin dudar.
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


# INSTRUCCIONES AL MODELO, no prosa al cliente: viajan en el JSON que se le
# inyecta al redactor. El candado de tests/test_prosa_en_la_fuente.py las
# reconoce por el prefijo _NOTA.
_NOTA_SIN_DATO = ("deci honesto que no lo tenes confirmado y que lo verificas")
_NOTA_BLOQUE_COMPAT = ("\n\nCOMPATIBILIDAD (dato REAL de la fuente, contestá "
                       "con esto y NO afirmes nada que no figure aca):\n")


# ── LO QUE CONSUME EL SOLVER Y EL JUEZ ───────────────────────────────────────
def bloque_ficha(prod: dict, tienda_id: str | None = None) -> str:
    """La compatibilidad de UN producto como texto de ficha, estampado por el
    codigo desde la tabla. Es lo que devuelve el campo `compatibilidad` del
    fragmento ficha."""
    compat = compat_de(prod, tienda_id)
    if not compat:
        return ""
    partes = []
    if compat.get("conecta_por"):
        partes.append("Se conecta por " + ", ".join(
            etiqueta_conector(c, tienda_id) for c in compat["conecta_por"]))
    if compat.get("plataformas"):
        partes.append("Anda con " + ", ".join(
            etiqueta_plataforma(p, tienda_id) for p in compat["plataformas"][:6]))
    if compat.get("requiere"):
        partes.append("Tu equipo necesita " + " o ".join(
            etiqueta_conector(c, tienda_id) for c in compat["requiere"][:3]))
    if compat.get("no_compatible"):
        partes.append("NO sirve para " + ", ".join(
            etiqueta_plataforma(p, tienda_id) for p in compat["no_compatible"]))
    texto = ". ".join(partes)
    if compat.get("nota"):
        texto = (texto + ". " if texto else "") + compat["nota"]
    return texto.strip()


_RE_AFIRMA_COMPAT = re.compile(
    r"[^.!?\n]*\b(?:si|sí|es|son|va|van|anda|andan|funciona|funcionan|sirve|"
    r"sirven|compatible|compatibles|se\s+conecta|se\s+conectan|entra|entran)\b"
    r"[^.!?\n]*\bcompatib|"
    r"[^.!?\n]*\b(?:sirve|sirven|anda|andan|funciona|funcionan|entra|entran|"
    r"se\s+conecta|se\s+conectan)\b[^.!?\n]*", re.IGNORECASE)


def estampar_veredicto(texto: str, productos, plataformas,
                       tienda_id: str | None = None) -> tuple[str, list]:
    """LINEA CERO DE LA COMPATIBILIDAD: el veredicto que sale al cliente lo pone
    el CODIGO, no el modelo.

    Mismo mecanismo que `estampar_honestidad_specs`, que es el que ya funciona:
    si la tabla dice INCOMPATIBLE, se podan las oraciones donde el modelo afirmo
    que anda y se estampa el no, con el motivo de la fuente. Si dice compatible,
    la prosa del modelo queda como esta -esta fundada- y no se toca nada. Si es
    SIN DATO no se estampa nada aca: de eso se ocupa el juez y el criterio
    jurado, porque podar toda afirmacion sin fila en la tabla se llevaria puesta
    prosa legitima de productos que todavia no estan cargados.

    Devuelve (texto, eventos) con eventos para el log.

    DOS COSAS QUE APRENDIO A LA MALA, las dos cazadas por las charlas grabadas
    (guiones 35 y 28, primera corrida de la maquina de casetes):

    1. SE AGRUPA POR MOTIVO, no por producto. Cuando el universo trae cuatro
       variantes del mismo modelo negado, pegar el aviso una vez por cada una
       daba cuatro veces la misma frase, y el recorte a 400 caracteres la cortaba
       a mitad de palabra: "andan en la compu,". Una respuesta cortada es una
       falla dura del juez del banco, y con razon.
    2. SI EL MODELO YA LO DIJO, NO SE ESTAMPA NADA. Con el grounding de
       compatibilidad en el prompt, el solver ya suele negar bien y con mejor
       prosa que la enlatada. Este estampado es la RED para cuando no lo dice,
       no una coletilla que se suma a lo que ya esta bien dicho.
    """
    if not (texto or "").strip() or not productos or not plataformas:
        return texto, []
    negados: list[tuple[dict, str, str]] = []
    for prod in productos:
        if not isinstance(prod, dict):
            continue
        for plat in plataformas:
            ver, motivo = evaluar(prod, plat, tienda_id)
            if ver == "incompatible":
                negados.append((prod, plat, motivo))
    if not negados:
        return texto, []
    eventos = [f"{p.get('nombre')}!={plat}" for p, plat, _m in negados]

    # se podan las oraciones que AFIRMAN que anda y nombran al producto negado
    lineas = []
    for linea in texto.split("\n"):
        conservar = True
        for prod, _plat, _motivo in negados:
            nom = _norm(prod.get("nombre"))[:26]
            if nom and nom in _norm(linea) and _RE_AFIRMA_COMPAT.search(linea):
                conservar = False
                break
        if conservar:
            lineas.append(linea)
    limpio = "\n".join(lineas).strip()

    # ¿el texto YA niega, por su cuenta, para cada plataforma negada? Si si, no
    # se le agrega nada: la prosa del modelo es mejor que la enlatada.
    faltan_plats = [p for p in dict.fromkeys(pl for _p, pl, _m in negados)
                    if not _ya_negada(limpio, p, tienda_id)]
    if not faltan_plats:
        return limpio or texto, eventos

    # UN aviso por motivo distinto, nombrando los productos que lo comparten.
    por_motivo: dict[str, list[str]] = {}
    for prod, plat, motivo in negados:
        if plat not in faltan_plats or not motivo:
            continue
        # el motivo trae el nombre del producto adelante; se guarda solo la
        # explicacion, que es la parte que comparten las variantes.
        nota = (compat_de(prod, tienda_id).get("nota") or "").strip()
        etq = etiqueta_plataforma(plat, tienda_id)
        clave = f"{etq}||{nota}"
        nom = str(prod.get("nombre") or "")
        if nom not in por_motivo.setdefault(clave, []):
            por_motivo[clave].append(nom)
    if not por_motivo:
        return limpio or texto, eventos
    frases = []
    for clave, nombres in list(por_motivo.items())[:2]:
        etq, _, nota = clave.partition("||")
        quienes = _lista(nombres[:2]) + (" y sus variantes"
                                         if len(nombres) > 2 else "")
        from app.core.guia_venta_prosa import mensaje
        frases.append(mensaje("compat_aviso_chasco",
                              "Te aviso para que no te lleves un chasco: ")
                      + quienes
                      + mensaje("compat_no_es_compatible", " no es compatible con ")
                      + f"{etq}." + (f" {nota}" if nota else ""))
    aviso = " ".join(frases)
    return ((limpio + "\n\n" + aviso).strip() if limpio else aviso), eventos


def _lista(nombres: list[str]) -> str:
    """'A', 'A y B' — sin la coma colgada que deja un join pelado."""
    nombres = [n for n in nombres if n]
    if len(nombres) <= 1:
        return nombres[0] if nombres else "ese producto"
    return " y ".join(nombres)


_RE_NIEGA = re.compile(
    r"\bno\s+(?:es|son|va|van|anda|andan|funciona|funcionan|sirve|sirven|"
    r"se\s+conecta|se\s+conectan|te\s+sirve|te\s+van)\b|\bno\s+compatible|"
    r"\bincompatible", re.IGNORECASE)


def _ya_negada(texto: str, plataforma: str, tienda_id: str | None) -> bool:
    """El texto YA le dice al cliente que no anda con ese equipo.

    Se pide que la negacion y el nombre del equipo esten en la MISMA oracion:
    un "no" suelto en otro parrafo no es una negacion de compatibilidad, y darlo
    por bueno dejaria pasar justo el caso que hay que cubrir."""
    v = vocabulario(tienda_id)
    alias = {a for a, ids in v["alias_plataforma"].items() if plataforma in ids}
    if not alias:
        return False
    for oracion in re.split(r"[.!?\n]", _norm(texto)):
        if not _RE_NIEGA.search(oracion):
            continue
        if any(re.search(r"\b" + re.escape(a) + r"\b", oracion) for a in alias):
            return True
    return False


def bloque_prompt(universo, plataformas, tienda_id: str | None = None) -> str:
    """El GROUNDING de compatibilidad del turno para el prompt del solver: la
    fila de cada producto del universo que la tenga, y el veredicto YA RESUELTO
    contra los equipos que declaro el cliente. El modelo redacta desde esto; no
    le queda nada que deducir."""
    lineas = []
    for p in (universo or [])[:8]:
        if not isinstance(p, dict):
            continue
        ficha = bloque_ficha(p, tienda_id)
        if not ficha:
            continue
        veredictos = []
        for plat in (plataformas or [])[:3]:
            ver, motivo = evaluar(p, plat, tienda_id)
            if ver != "sin_dato":
                veredictos.append(f"{ver.upper()} con {etiqueta_plataforma(plat, tienda_id)}")
            else:
                veredictos.append(
                    f"SIN DATO sobre {etiqueta_plataforma(plat, tienda_id)}: "
                    + _NOTA_SIN_DATO)
        lineas.append(f"  {p.get('nombre')}: {ficha}"
                      + (" || " + "; ".join(veredictos) if veredictos else ""))
    if not lineas:
        return ""
    return (_NOTA_BLOQUE_COMPAT + "\n".join(lineas))
