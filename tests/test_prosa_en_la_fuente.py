"""
EL CANDADO DE LA PROSA — ningun texto al cliente puede vivir en el codigo.

POR QUE EXISTE (Martin, 11-ago-2026, y es la bronca mas justa de todas).

Durante meses se le dijo que la fuente de verdad estaba unificada. Era media
verdad, y ahora se sabe exactamente cual mitad: el DATO si se unifico -catalogo,
FAQ, compatibilidad, specs, localidades-, pero de la PROSA se mudaron CINCO
mensajes el 3-ago y nada mas. Todo lo que se escribio despues quedo en el
codigo. Cuando Martin pregunto, el que contesto miro el dato y dijo que si.

Nadie mintio a proposito. **Faltaba con que mirar.** El candado que habia
verificaba una lista blanca de cinco claves, asi que un texto NUEVO en el
codigo no rompia nada y nadie se enteraba. Una regla que solo vive en un
documento se cumple mientras alguien se acuerde; despues de dos sesiones, no.

Este archivo la convierte en una accion: si alguien escribe una frase para el
cliente adentro de `app/`, el CI se pone rojo y dice donde.

COMO DISTINGUE PROSA DE LO DEMAS, sin adivinar. En los modulos que le hablan al
cliente, un literal de texto es prosa SALVO que sea una de estas cuatro cosas,
todas verificables leyendo el codigo y no interpretando el idioma:

  1. EL RESPALDO de una llamada a `mensaje("clave", "respaldo")`. Ese literal
     tiene que existir, porque es la red si el archivo faltara —y el test exige
     ademas que sea IDENTICO al de la fuente, que es como se despegan las
     copias—.
  2. UNA INSTRUCCION AL MODELO. No la lee el cliente: le dice al modelo como
     trabajar. Se reconoce por donde vive -constantes `_INSTRUCCION*`,
     `*_PROMPT`, `_SISTEMA*`, `_NOTA*`- o por la clave `mensaje_para_llm`.
  3. TEXTO OPERATIVO que no sale por WhatsApp: errores del panel de admin,
     avisos al dueño, etiquetas internas. Van declarados uno por uno abajo.
  4. Fragmentos cortos de armado -una coma, un guion, un salto-.

LO QUE ESTE CANDADO NO PRETENDE. No revisa `app/core/herramientas.py` ni
`calculadora.py` entera: ahi la enorme mayoria de los literales son
instrucciones al modelo (`mensaje_para_llm`) y esquemas de herramientas, y
tratarlos como prosa daria un rojo permanente que se aprende a ignorar, que es
peor que no tenerlo. Se cubren los NUEVE modulos por donde sale el texto que el
cliente lee. Si mañana un modulo nuevo escribe al cliente, se agrega aca.
"""
import ast
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

APP = _RAIZ / "app"
FUENTE = _RAIZ / "data" / "clientes" / "verifika_prod" / "base_conocimiento.json"

# Los modulos por donde sale el texto que el cliente LEE.
HABLAN_AL_CLIENTE = [
    "main.py",
    "core/cierre.py",
    "core/leads.py",
    "core/pago.py",
    "core/guardas_salida.py",
    "core/orchestrator.py",
    "core/compatibilidad.py",
    "core/indice.py",
]

# Constantes que son INSTRUCCION AL MODELO, no prosa al cliente.
_PREFIJOS_PROMPT = ("_INSTRUCCION", "INSTRUCCION", "_SISTEMA", "_PROMPT",
                    "_NOTA", "_GUIA", "_EXTRACTOR")

# LOS LECTORES DE LA FUENTE. Un literal que viaja como argumento de una de
# estas es el RESPALDO, no una copia suelta: existe por si el archivo faltara,
# y `test_el_respaldo_del_codigo_es_identico_al_de_la_fuente` lo ata al texto
# real. Si alguien agrega otro lector, va aca y en ningun otro lado.
_LECTORES_DE_LA_FUENTE = ("mensaje", "_prosa", "etiqueta_dato", "_msj",
                          "_mensaje_de_la_fuente")

# Donde puede vivir un respaldo que NO va escrito adentro de la llamada: una
# variable `respaldo` (cuando la clave se elige con un if) o un dict
# `*_RESPALDO`. Es convencion, y el test de arriba igual los ata a la fuente.
_NOMBRES_DE_RESPALDO = ("respaldo",)

# TEXTO OPERATIVO QUE NO SALE POR WHATSAPP. Cada uno declarado a mano y con su
# motivo: si aparece uno nuevo, alguien tiene que venir aca y decir por que no
# es prosa. Ese roce es el punto.
DECLARADOS = {
    # panel de admin: errores de carga de CSV, los lee Martin en la web
    "El archivo debe ser .csv", "archivo muy grande (máx 5MB)",
    "archivo muy grande (máx 1MB)", "CSV vacío o sin filas válidas",
    "No se pudo decodificar el archivo: ", "id duplicado en el CSV: ",
    "tema duplicado en el CSV: ", "): falta 'categoria'",
    "): precio o stock negativo", "): falta 'respuesta'",
    "): precio_ars inválido ('", "): stock inválido ('",
    "Si True, mantiene productos viejos. Por defecto reemplaza.",
    "Si True, mantiene FAQ vieja. Por defecto reemplaza.",
    "admin deshabilitado: falta ADMIN_TOKEN", "tienda no registrada",
    # endpoint de diagnostico de latencia: no le habla a ningun cliente
    "Sos un vendedor argentino. ", " sobre productos y precios",
    "herramientas (hub_venta)",
    ("Te muestro opciones: Mouse Genius DX-110 $8.500, Teclado Genius KB-110X "
     "$12.000, Monitor Samsung 24 $165.000. "),
    # etiquetas internas y fragmentos de armado
    "asistente automatico", "auriculares bluetooth",
}


def _mensajes_de_la_fuente() -> set:
    d = json.loads(FUENTE.read_text(encoding="utf-8"))
    fuera = {str(v) for k, v in (d.get("mensajes") or {}).items()
             if not k.startswith("_")}
    fuera |= {str(v) for k, v in (d.get("etiquetas_datos") or {}).items()
              if not k.startswith("_")}
    return fuera


def _literales_sueltos(py: Path) -> list:
    """Los literales de texto del modulo que NO son ninguna de las cuatro cosas
    permitidas. Devuelve [(linea, texto)]."""
    arbol = ast.parse(py.read_text(encoding="utf-8"))
    padres = {}
    for n in ast.walk(arbol):
        for h in ast.iter_child_nodes(n):
            padres[id(h)] = n

    docs = set()
    for n in ast.walk(arbol):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                          ast.AsyncFunctionDef)):
            d = ast.get_docstring(n, clean=False)
            if d:
                docs.add(d)

    perdonados = set()
    for n in ast.walk(arbol):
        if not isinstance(n, ast.Call):
            continue
        nom = getattr(n.func, "attr", "") or getattr(n.func, "id", "")
        # logs, regex, envs: no son texto al cliente
        if nom in ("info", "warning", "error", "debug", "exception",
                   "get_logger", "compile", "match", "search", "sub",
                   "fullmatch", "finditer", "getenv"):
            for s in ast.walk(n):
                if isinstance(s, ast.Constant) and isinstance(s.value, str):
                    perdonados.add(id(s))
        # el respaldo de mensaje("clave", "respaldo") / _prosa(...) / etiqueta_dato
        if nom in _LECTORES_DE_LA_FUENTE:
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    perdonados.add(id(a))

    # instrucciones al modelo: por el nombre de la constante que las contiene
    def es_respaldo_declarado(nodo) -> bool:
        p = padres.get(id(nodo))
        saltos = 0
        while p is not None and saltos < 6:
            if isinstance(p, ast.Assign) and p.targets:
                t = p.targets[0]
                if isinstance(t, ast.Name) and (
                        t.id in _NOMBRES_DE_RESPALDO
                        or t.id.upper().endswith("_RESPALDO")):
                    return True
            p = padres.get(id(p))
            saltos += 1
        return False

    def es_prompt(nodo) -> bool:
        p = padres.get(id(nodo))
        saltos = 0
        while p is not None and saltos < 10:
            if isinstance(p, ast.Assign) and p.targets:
                t = p.targets[0]
                if isinstance(t, ast.Name) and t.id.upper().startswith(_PREFIJOS_PROMPT):
                    return True
            # el valor de la clave mensaje_para_llm de un dict
            if isinstance(p, ast.Dict):
                for k, v in zip(p.keys, p.values):
                    if (isinstance(k, ast.Constant)
                            and k.value in ("mensaje_para_llm", "pista", "guia")
                            and any(id(nodo) == id(s) for s in ast.walk(v))):
                        return True
            p = padres.get(id(p))
            saltos += 1
        return False

    sueltos = []
    for n in ast.walk(arbol):
        if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
            continue
        s = n.value
        if id(n) in perdonados or s in docs or s in DECLARADOS:
            continue
        if len(s.strip()) < 20 or " " not in s.strip():
            continue
        if s.strip().startswith(("^", "\\", "(?i", "http")):
            continue
        if es_prompt(n) or es_respaldo_declarado(n):
            continue
        sueltos.append((n.lineno, s))
    return sueltos


def test_ningun_texto_al_cliente_vive_en_el_codigo():
    """LA REGLA, y ahora es una accion y no un pedido: en los modulos que le
    hablan al cliente, toda frase sale de `base_conocimiento.json`.

    Si este test se pone rojo, NO se agrega el texto a la lista de declarados:
    se mueve a la fuente y se lee con `mensaje("clave", "respaldo")`. La lista
    es solo para texto que el cliente NO lee -errores del panel de admin,
    avisos al dueño-, y agregar algo ahi es una decision consciente que queda
    escrita."""
    culpables = []
    for rel in HABLAN_AL_CLIENTE:
        for linea, texto in _literales_sueltos(APP / rel):
            culpables.append(f"app/{rel}:{linea}  {texto[:70]!r}")
    assert not culpables, (
        f"{len(culpables)} textos al cliente escritos en el codigo. Moverlos a "
        f"base_conocimiento.json y leerlos con mensaje():\n  "
        + "\n  ".join(culpables))


def test_el_respaldo_del_codigo_es_identico_al_de_la_fuente():
    """LA SEGUNDA MITAD, y es la que evita la copia que se despega. Cada
    `mensaje("clave", "respaldo")` deja un literal en el codigo a proposito: es
    la red si el archivo faltara. Pero si ese respaldo dice una cosa y la
    fuente otra, volvimos a tener dos versiones del mismo mensaje y la de la
    fuente es la que nadie ve. Se exige que sean IGUALES."""
    from app.core.guia_venta_prosa import mensaje

    distintos = []
    for py in sorted(APP.rglob("*.py")):
        arbol = ast.parse(py.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if not isinstance(n, ast.Call):
                continue
            nom = getattr(n.func, "attr", "") or getattr(n.func, "id", "")
            if nom not in _LECTORES_DE_LA_FUENTE or nom == "etiqueta_dato":
                continue
            if len(n.args) < 2:
                continue
            clave, respaldo = n.args[0], n.args[1]
            if not (isinstance(clave, ast.Constant)
                    and isinstance(respaldo, ast.Constant)):
                continue
            en_fuente = mensaje(str(clave.value), "")
            if en_fuente and en_fuente != respaldo.value:
                distintos.append(
                    f"{py.relative_to(_RAIZ)}:{n.lineno} clave "
                    f"'{clave.value}': el codigo dice {respaldo.value[:50]!r} y "
                    f"la fuente {en_fuente[:50]!r}")
    assert not distintos, (
        "el respaldo del codigo se despego de la fuente:\n  " + "\n  ".join(distintos))


def test_toda_clave_pedida_al_codigo_existe_en_la_fuente():
    """Una clave mal escrita cae al respaldo y no se nota nunca: el cliente
    recibe el texto viejo del codigo y el de la fuente queda muerto. Se exige
    que toda clave que el codigo pide exista de verdad."""
    de_la_fuente = json.loads(FUENTE.read_text(encoding="utf-8"))
    claves = {k for k in (de_la_fuente.get("mensajes") or {})
              if not k.startswith("_")}
    claves |= set(de_la_fuente.get("etiquetas_datos") or {})
    faltan = []
    for py in sorted(APP.rglob("*.py")):
        arbol = ast.parse(py.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if not isinstance(n, ast.Call):
                continue
            nom = getattr(n.func, "attr", "") or getattr(n.func, "id", "")
            if nom not in _LECTORES_DE_LA_FUENTE:
                continue
            if not n.args or not isinstance(n.args[0], ast.Constant):
                continue
            k = str(n.args[0].value)
            if k and k not in claves:
                faltan.append(f"{py.relative_to(_RAIZ)}:{n.lineno} pide '{k}'")
    assert not faltan, ("el codigo pide claves que la fuente no tiene:\n  "
                        + "\n  ".join(faltan))


def test_el_mismo_texto_no_esta_escrito_en_dos_archivos():
    """El duplicado silencioso, que es como empieza siempre. El 11-ago habia
    DOS copias de "Perdón, estoy con mucha demanda" -en main.py y en
    hub_venta.py- y dos de "No pude entender el audio". Cambiar una y olvidar
    la otra deja al bot diciendo dos cosas distintas segun por donde salga."""
    vistos = {}
    for rel in HABLAN_AL_CLIENTE:
        py = APP / rel
        arbol = ast.parse(py.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                s = n.value.strip()
                if len(s) >= 30 and " " in s and not s.startswith(("^", "\\")):
                    vistos.setdefault(s, set()).add(rel)
    repes = {s: sorted(f) for s, f in vistos.items() if len(f) > 1}
    assert not repes, ("el mismo texto escrito en dos archivos:\n  "
                       + "\n  ".join(f"{f}: {s[:60]!r}" for s, f in repes.items()))
