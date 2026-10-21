"""PASO 3: EL BANCO CURADO QUE ROTA — casos resueltos por clase, y el codigo elige para cada mensaje los mas parecidos.

  el banco     los seis ejemplos de la consigna de produccion, mas casos escritos a mano por clase, con otros productos,
               otros lugares y otras palabras que los turnos medidos. `limpio.fugas` controla que no compartan ninguna
               secuencia de tres palabras con ellos.
  el parecido  por la forma del mensaje, no por sus palabras: el marcador tapa productos, rubros, lugares, montos y
               porcentajes; se suman los tipos de las pistas que pidio el modelo y lo que hay en la libreta.
  la rotacion  cuatro casos por mensaje, a lo sumo dos de la misma clase. Van en el mensaje, no en la consigna, y los
               seis ejemplos fijos salen de la consigna: los tokens quedan parecidos.

Los casos se escribieron despues de ver las fallas: es una medida de clase, no una reserva limpia."""
import collections
import math
import re

import comandos as Cm
import variante3 as V3
from app.core.flujo import interprete as I
from app.core.flujo import marcador as M

TIENDA = "verifika_prod"
VACIA = "LIBRETA: vacia, es el primer mensaje."

# (clase, libreta, mensaje, comandos)
CASOS = [
    ("dos_destinos", VACIA, "quiero un JBL Go 3 para Salta y otro para Neuquen, que me cobran de envio a cada lado?",
     '1. AGREGAR producto="JBL Go 3" cantidad="1" destino="Salta" | "quiero un JBL Go 3 para Salta"\n'
     '2. AGREGAR producto="JBL Go 3" cantidad="1" destino="Neuquen" | "y otro para Neuquen,"\n'
     '3. ENVIO destino="Salta" | "que me cobran de envio a cada lado?"\n'
     '4. ENVIO destino="Neuquen" | "que me cobran de envio a cada lado?"'),
    ("dos_destinos", VACIA, "decime el costo de mandar a Tucuman y a Mar del Plata",
     '1. ENVIO destino="Tucuman" | "decime el costo de mandar a Tucuman"\n'
     '2. ENVIO destino="Mar del Plata" | "y a Mar del Plata"'),
    ("suma_envio", "LIBRETA:\n- CLIENTE: localidad Bahia Blanca",
     "y el K380 blanco en total puesto en casa?",
     '1. PRODUCTO producto="K380" quiere_saber="precio" color="blanco" | "y el K380 blanco"\n'
     '2. ENVIO destino="Bahia Blanca" | "puesto en casa?"\n'
     '3. CUENTA | "en total"'),
    ("suma_envio", VACIA, "el Flip 6 mas lo que sale mandarlo a La Plata, cuanto da?",
     '1. PRODUCTO producto="Flip 6" quiere_saber="precio" | "el Flip 6"\n'
     '2. ENVIO destino="La Plata" | "mas lo que sale mandarlo a La Plata,"\n'
     '3. CUENTA | "cuanto da?"'),
    ("elegir_por_dato", VACIA, "entre el K380 y el K120 me quedo con el que tenga bluetooth",
     '1. PRODUCTO producto="K380" quiere_saber="bluetooth" | "entre el K380"\n'
     '2. PRODUCTO producto="K120" quiere_saber="bluetooth" | "y el K120"\n'
     '3. AGREGAR producto="K380" cantidad="1" si="1:si" | "me quedo con el que tenga bluetooth"\n'
     '4. AGREGAR producto="K120" cantidad="1" si="2:si" | "me quedo con el que tenga bluetooth"'),
    ("elegir_por_dato", VACIA, "quiero el Flip 6 o el Charge 5, cualquiera de los dos que aguante el agua",
     '1. PRODUCTO producto="Flip 6" quiere_saber="resistencia al agua" | "quiero el Flip 6"\n'
     '2. PRODUCTO producto="Charge 5" quiere_saber="resistencia al agua" | "o el Charge 5,"\n'
     '3. AGREGAR producto="Flip 6" cantidad="1" si="1:si" | "cualquiera de los dos que aguante el agua"\n'
     '4. AGREGAR producto="Charge 5" cantidad="1" si="2:si" | "cualquiera de los dos que aguante el agua"'),
    ("condicion_precio", VACIA, "si el G915 TKL esta por debajo de 400 mil me lo llevo",
     '1. PRODUCTO producto="G915 TKL" quiere_saber="si esta por debajo de 400 mil" | "si el G915 TKL esta por debajo de 400 mil"\n'
     '2. AGREGAR producto="G915 TKL" cantidad="1" si="1:si" | "me lo llevo"'),
    ("condicion_precio", VACIA, "hay rebaja pagando por transferencia? porque si la Kiyo X no pasa los 60 mil compro tres",
     '1. POLITICA tema="descuento_transferencia" | "hay rebaja pagando por transferencia?"\n'
     '2. PRODUCTO producto="Kiyo X" quiere_saber="si no pasa los 60 mil" | "porque si la Kiyo X no pasa los 60 mil"\n'
     '3. AGREGAR producto="Kiyo X" cantidad="3" si="2:si" | "compro tres"'),
    ("corrige_destino", "LIBRETA:\n- MOSTRADO, del mas viejo al mas nuevo:\n  M-1 Webcam Logitech C920 HD Pro Negro $98.000, "
     "stock 6\n- LO ULTIMO:\n  CLIENTE: cuanto sale la C920 mandada a Neuquen?\n  VENDEDOR: ...Envío a Neuquen: $8.500.",
     "uh perdon, a Neuquen no, es para Salta",
     '1. OTRO que="corrige" | "uh perdon, a Neuquen no,"\n'
     '2. ENVIO destino="Salta" | "es para Salta"'),
    ("suelta_condicion", "LIBRETA:\n- MOSTRADO, del mas viejo al mas nuevo:\n  M-1 Teclado Corsair K55 RGB Pro Negro "
     "$89.000, stock 4\n  M-2 Teclado Corsair K70 RGB Pro Negro $240.000, stock 2\n- BUSCO: teclado, con luces, Corsair",
     "olvidate de Corsair, que otras marcas tenes?",
     '1. BUSCAR rubro="teclado" cantidad="1" orden="nada" condiciones="con luces; que no sea Corsair" | '
     '"olvidate de Corsair, que otras marcas tenes?"'),
    ("ver_mas_con_exclusion", "LIBRETA:\n- MOSTRADO, del mas viejo al mas nuevo:\n  M-1 Parlante Logitech Z313 Negro "
     "$61.000, stock 5\n  M-2 Parlante Edifier R1280T Negro $150.000, stock 3\n- BUSCO: parlante, que no sea Genius\n"
     "- EXCLUSIONES VIGENTES: que no sea Genius",
     "tenes otros a bateria?",
     '1. BUSCAR rubro="parlante" cantidad="1" orden="nada" condiciones="a bateria; que no sea Genius" | '
     '"tenes otros a bateria?"'),
    ("ese_varios", "LIBRETA:\n- MOSTRADO, del mas viejo al mas nuevo:\n  M-1 Webcam Logitech C270 HD Negro $32.000, stock 9\n"
     "  M-2 Webcam Logitech C920 HD Pro Negro $98.000, stock 6\n  M-3 Webcam Razer Kiyo X Negro $85.000, stock 4\n"
     "  M-4 Webcam Logitech Brio 100 Negro $70.000, stock 5",
     "y ese tiene microfono?",
     '1. PRODUCTO producto="[M-1, M-2, M-3, M-4]" quiere_saber="microfono" | "y ese tiene microfono?"'),
    ("ese_uno", "LIBRETA:\n- MOSTRADO, del mas viejo al mas nuevo:\n  M-1 Mouse Logitech MX Master 3S Negro $203.000, "
     "stock 7; conexion: inalambrico",
     "lo tenes en blanco?",
     '1. PRODUCTO producto="M-1" quiere_saber="color" color="blanco" | "lo tenes en blanco?"'),
    ("requisito_equipo", VACIA, "mi notebook tiene solo USB-C, cual es el mouse inalambrico mas liviano que pueda usar?",
     '1. OTRO que="dato" | "mi notebook tiene solo USB-C,"\n'
     '2. BUSCAR rubro="mouse" cantidad="1" orden="mas liviano" condiciones="inalambrico; que se conecte por USB-C" | '
     '"cual es el mouse inalambrico mas liviano que pueda usar?"\n'
     'CLIENTE equipo="notebook con USB-C"'),
    ("compat_si_no", VACIA, "uso una Mac, si la C920 no anda ahi que otra camara me ofreces?",
     '1. OTRO que="dato" | "uso una Mac,"\n'
     '2. COMPATIBILIDAD producto="C920" con="Mac" | "si la C920 no anda ahi"\n'
     '3. BUSCAR rubro="webcam" cantidad="1" orden="nada" condiciones="que ande con Mac" si="2:no" | '
     '"que otra camara me ofreces?"\n'
     'CLIENTE equipo="Mac"'),
    ("si_lo_dejo", "LIBRETA:\n- BORRADOR:\n  L-1 1 parlante a Salta: 1 Parlante JBL Go 3 Negro\n"
     "  L-2 1 webcam a Neuquen: 1 Webcam Logitech C270 HD Negro\n- ABIERTO, lo que el vendedor pregunto:\n"
     '  R-1 "¿Lo dejo así?", para: ',
     "dale de una",
     '1. CUENTA responde="R-1" | "dale de una"'),
    ("lista_con_destinos", VACIA, "cuanto salen un par de parlantes y una webcam, lo mas barato que tengas. un parlante "
     "y la webcam se mandan a Salta y el parlante que queda a Neuquen",
     '1. BUSCAR rubro="parlante" cantidad="2" orden="mas barato" | "cuanto salen un par de parlantes"\n'
     '2. BUSCAR rubro="webcam" cantidad="1" orden="mas barato" | "y una webcam, lo mas barato que tengas."\n'
     '3. AGREGAR producto="parlante" cantidad="1" destino="Salta" | "un parlante y la webcam se mandan a Salta"\n'
     '3. AGREGAR producto="webcam" cantidad="1" destino="Salta" | "un parlante y la webcam se mandan a Salta"\n'
     '4. AGREGAR producto="los otros" destino="Neuquen" | "y el parlante que queda a Neuquen"'),
    ("lista_con_destinos", VACIA, "necesito dos webcams y un parlante. una webcam y una notebook van a Tucuman, lo "
     "resto para La Plata",
     '1. BUSCAR rubro="webcam" cantidad="2" orden="nada" | "necesito dos webcams"\n'
     '2. BUSCAR rubro="parlante" cantidad="1" orden="nada" | "y un parlante."\n'
     '3. AGREGAR producto="webcam" cantidad="1" destino="Tucuman" | "una webcam y una notebook van a Tucuman,"\n'
     '3. AGREGAR producto="notebook" cantidad="1" destino="Tucuman" | "una webcam y una notebook van a Tucuman,"\n'
     '4. AGREGAR producto="los otros" destino="La Plata" | "el resto para La Plata"'),
]


def _todos():
    """El banco entero: los seis ejemplos de produccion, pasados a comandos, y los casos por clase."""
    out = []
    for i, (lib, msg, _t, sal) in enumerate(I.EJEMPLOS, 1):
        out.append((f"produccion_{i}", lib, msg, Cm.a_comandos(sal)))
    return out + CASOS


def _forma(texto: str) -> list:
    """El mensaje con lo de la tienda tapado: "mandame un PRODUCTO a LUGAR"."""
    from banco_pruebas.traduccion58 import plano
    from app.core.envio import clasificar_provincia
    p = " " + plano(texto) + " "
    for d, e in sorted(M.marcar(texto, TIENDA), key=lambda x: -len(x[0])):
        tag = ("PRODUCTO" if e.startswith(("el producto", "puede ser")) else "RUBRO" if e.startswith("el rubro")
               else "MONTO" if "pesos" in e else "PORCIENTO" if "por ciento" in e else None)
        if tag:
            p = p.replace(" " + plano(d) + " ", f" {tag} ")
    ws, out, i = p.split(), [], 0
    while i < len(ws):
        for n in (3, 2, 1):
            f = " ".join(ws[i:i + n])
            if f.upper() != f and len(f) > 3 and clasificar_provincia(f):
                out.append("LUGAR")
                i += n
                break
        else:
            out.append(ws[i])
            i += 1
    return out


def _rasgos(mensaje: str, libreta: str, tipos: list) -> list:
    r = _forma(mensaje)
    r += [f"#pista:{t}" for t in tipos]
    for marca, nombre in (("MOSTRADO", "mostrado"), ("BORRADOR", "borrador"), ("ABIERTO", "abierto"),
                          ("EXCLUSIONES", "exclusiones"), ("BUSCO", "busco"), ("CLIENTE", "cliente")):
        if f"- {marca}" in libreta:
            r.append(f"#libreta:{nombre}")
    mostrados = len(re.findall(r"^\s*M-\d+ ", libreta, re.M))
    if mostrados:
        r.append("#libreta:varios_mostrados" if mostrados > 1 else "#libreta:un_mostrado")
    if "vacia, es el primer mensaje" in libreta:
        r.append("#libreta:vacia")
    return r


_INDICE = {}


def _indice():
    if not _INDICE:
        banco = _todos()
        rasgos = [_rasgos(m, lib, []) for _c, lib, m, _s in banco]
        df = collections.Counter(w for r in rasgos for w in set(r))
        _INDICE.update(banco=banco, rasgos=rasgos, df=df)
    return _INDICE


def _vec(r, df, n):
    c = collections.Counter(r)
    v = {w: c[w] * math.log(1 + n / (1 + df.get(w, 0))) for w in c}
    s = math.sqrt(sum(x * x for x in v.values())) or 1
    return {w: x / s for w, x in v.items()}


def elegir(mensaje: str, libreta: str, pistas: list, k: int = 4) -> list:
    ix = _indice()
    n = len(ix["banco"])
    tipos = [str(p.get("tipo") or "") for p in pistas]
    q = _vec(_rasgos(mensaje, libreta, tipos), ix["df"], n)
    # Las pistas del banco no estan: se comparan por el tipo de comando que lleva cada caso.
    puntos = []
    for i, (clase, lib, msg, sal) in enumerate(ix["banco"]):
        r = ix["rasgos"][i] + [f"#pista:{t}" for t in _tipos_de(sal)]
        v = _vec(r, ix["df"], n)
        puntos.append((sum(q[w] * v.get(w, 0) for w in q), i))
    elegidos, por_clase = [], collections.Counter()
    for s, i in sorted(puntos, reverse=True):
        clase = ix["banco"][i][0]
        if por_clase[clase] >= 2:
            continue
        elegidos.append(ix["banco"][i])
        por_clase[clase] += 1
        if len(elegidos) == k:
            break
    return elegidos


def _tipos_de(comandos: str) -> list:
    """Los tipos de pista que tendria un caso, sacados de sus comandos."""
    t = []
    for linea in comandos.splitlines():
        if 'destino="' in linea:
            t.append("lugar")
        if re.search(r'producto="(?!\[|M-|L-)[A-Z]', linea):
            t.append("producto")
        if re.search(r'producto="\[?M-', linea):
            t.append("referencia")
        if "rubro=" in linea:
            t.append("rubro")
        if "condiciones=" in linea or "si=" in linea:
            t.append("condicion")
        if "POLITICA" in linea:
            t.append("tema")
        if re.search(r"AGREGAR|SACAR|CAMBIAR|CONFIRMAR|ACEPTAR", linea):
            t.append("pedido")
    return t


def texto(mensaje: str, libreta: str, pistas: list) -> str:
    casos = elegir(mensaje, libreta, pistas)
    return ("CASOS RESUELTOS PARECIDOS A ESTE MENSAJE. La libreta de cada caso es la de ESE caso, no la de esta charla:\n\n"
            + "\n\n".join(f"{lib}\nULTIMO MENSAJE: {msg}\nCOMANDOS:\n{sal}" for _c, lib, msg, sal in casos)
            + "\n\nAHORA ESTE MENSAJE:\n")


def instalar():
    """Sobre lo que ya este puesto en V3 —con o sin fichas—: sin los ejemplos fijos, con los que rotan."""
    base = V3.consigna

    def consigna(tienda_id: str) -> str:
        c = base(tienda_id)
        return c[:c.index("EJEMPLOS:")].rstrip()
    V3.consigna = consigna
    V3.EXTRA = texto
