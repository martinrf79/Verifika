"""EL NEXO DE ORDEN: TODO LO QUE EL CLIENTE PIDE CON MAS O MENOS (17-nov-2026).

Orden de Martin del 17-nov: un nexo abarcativo para "mas..." y "menos...", no una palabra por caso. Reemplaza a la pieza
2b del nexo de condicion, que solo sabia los cuatro ordenes de `catalogo.ORDEN`. Lo usa el de condicion sobre un rubro, y
el flujo sobre la tienda entera cuando el cliente no nombra producto: "el articulo mas caro que vendes".

Lo que sigue a "mas" o "menos" se resuelve contra la tienda, en este orden:
  1. un orden del vocabulario de la tienda, `marcador.vocabulario_respuestas` y `catalogo.ORDEN`: "mas barato", "lo mas
     economico", "gama alta", "lo mejor". "Menos caro" es "mas barato". Una palabra de orden sola tambien: "barata".
  2. un campo con numeros del rubro, por su nombre o su etiqueta: "mas ram", "mas potencia", "menos peso".
  3. un valor de un campo del rubro: "mas" lo pone primero y "menos" lo deja ultimo, sin sacar nada: "las menos partes
     chinas" ordena lo fabricado en China al final, como `respuesta.orden_del_cliente` en produccion. "Menos X" sin
     articulo antes, "todo menos Redragon", es una exclusion y queda para el nexo de condicion.
Lo que no se resuelve queda sin atar, y el de condicion lo repregunta.

El valor de cada item es un texto: la clave de `catalogo.ORDEN`, "mas barato"; "mas ram" o "menos ram" para un campo con
numeros; "menos pais_fabricacion=china" para un valor. `ordenar` lo aplica.
"""
import re

ARTICULOS = {"el", "la", "lo", "los", "las"}
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _ordenes(fx):
    """{prefijo de palabra: clave de catalogo.ORDEN} y {frase: clave}, del vocabulario de la tienda."""
    from app.core.flujo import marcador as MK
    from nexo_condicion import TID
    voc = MK.vocabulario_respuestas(TID)["ordenes"]
    palabra, frase = {k.split()[-1]: k for k in fx.C.ORDEN}, {}
    for k, fs in voc.items():
        if k not in fx.C.ORDEN:
            continue
        for f in fs:
            f = fx.C.n(f)
            if f.startswith("mas ") and len(f.split()) == 2:
                palabra[f.split()[1]] = k
            else:
                frase[f] = k
    return palabra, frase


_INVERSO = {"mas barato": "mas caro", "mas caro": "mas barato", "mas liviano": "mas pesado", "mas pesado": "mas liviano"}


def _clave_orden(w, palabra, suelta=False):
    """La clave de orden de una palabra, por comienzo: "barata", "economicos", "caro". Suelta, sin "mas" antes, solo con
    un comienzo largo: "alt" y "buen" del vocabulario son orden en "mas alto" y "mas bueno", no en "alternativa"."""
    from nexo_condicion import variantes
    for x in variantes(w):
        if x in palabra:
            return palabra[x]
    return next((k for p, k in palabra.items() if len(p) >= (5 if suelta else 3) and w.startswith(p)), None)


def _campo_numerico(w, r, fx):
    """El campo con numeros del rubro que la palabra nombra: por su nombre, su etiqueta o la pregunta de la ficha."""
    from nexo_condicion import variantes
    if r is None:
        return None
    vs = set(variantes(w))
    for c, valores in fx.campos[r].items():
        if not any(_NUM.search(v) for v in valores[:5]):
            continue
        nombres = set(c.split("_")) | set(fx.C.n(fx.etiquetas.get(c, "")).split())
        if vs & {x for x in nombres if len(x) >= 3}:
            return c
        s = fx.specs.get(c)
        if s and s.get("rx_pregunta") is not None and s["rx_pregunta"].fullmatch(w):
            return c
    return None


def _valor(ws, r, fx, hasta_inicio=2):
    """(campo, valor, hasta) del pedazo mas largo de las palabras que es un valor del rubro, o de alguno si no hay rubro;
    hasta es cuantas palabras de `ws` usa."""
    from nexo_condicion import _hallar
    rubros = [r] if r else list(fx.campos)
    for largo in range(min(4, len(ws)), 0, -1):
        for i in range(len(ws) - largo + 1):
            frase = " ".join(ws[i:i + largo])
            if frase in fx.C._RELLENO:
                continue
            for x in rubros:
                hit = _hallar(frase, x, fx, fx.busca[x])
                if hit and i <= hasta_inicio:
                    return hit[0], hit[1], i + largo
    return None


def detectar(tokens, usados, r, fx):
    """[(indices, item)] de lo que la busqueda pide con mas o menos, sin las palabras ya usadas. r None es la tienda."""
    palabra, frase = _ordenes(fx)
    out, tomadas = [], set(usados)
    texto = " ".join(tokens)
    # Las frases del vocabulario: "gama alta", "lo mejor".
    for f, k in sorted(frase.items(), key=lambda x: -len(x[0])):
        m = re.search(rf"(?<![a-z0-9]){re.escape(f)}(?![a-z0-9])", texto)
        if m:
            ini = len(texto[:m.start()].split())
            ks = list(range(ini, ini + len(f.split())))
            if not tomadas & set(ks):
                out.append((ks, {"parte": f, "veredicto": "orden", "valor": k, "por": "codigo"}))
                tomadas |= set(ks)
    for i, w in enumerate(tokens):
        if i in tomadas:
            continue
        # "Mayor" y "menor" son "mas" y "menos": "la menor cantidad posible de partes chinas".
        w = {"mayor": "mas", "menor": "menos"}.get(w, w)
        if w in ("mas", "menos") and i + 1 < len(tokens):
            sig = [j for j in range(i + 1, min(i + 7, len(tokens))) if j not in tomadas]
            if not sig or sig[0] != i + 1:
                continue
            ks, valor = [i], None
            k = _clave_orden(tokens[i + 1], palabra)
            if k:
                valor, ks = (k if w == "mas" else _INVERSO[k]), [i, i + 1]
            elif (c := _campo_numerico(tokens[i + 1], r, fx)):
                valor, ks = f"{w} {c}", [i, i + 1]
            elif w == "mas" or (i > 0 and tokens[i - 1] in ARTICULOS):
                ws = [tokens[j] for j in sig]
                # Con articulo antes, "las menos partes de...", el valor puede venir unas palabras despues.
                hit = _valor(ws, r, fx, 4 if i > 0 and tokens[i - 1] in ARTICULOS else 2)
                if hit:
                    # Hasta la ultima palabra del valor hallado: "las menos partes de estados unidos".
                    valor, ks = f"{w} {hit[0]}={hit[1]}", [i] + sig[:hit[2]]
            if valor:
                while ks[0] > 0 and ks[0] - 1 not in tomadas and tokens[ks[0] - 1] in ARTICULOS:
                    ks.insert(0, ks[0] - 1)
                # "posible" y "posibles" despues del orden van con el: "lo mas barato posible".
                while ks[-1] + 1 < len(tokens) and tokens[ks[-1] + 1].startswith("posible"):
                    ks.append(ks[-1] + 1)
                out.append((ks, {"parte": " ".join(tokens[x] for x in ks), "veredicto": "orden", "valor": valor,
                                 "por": "codigo"}))
                tomadas |= set(ks)
            continue
        # Una palabra de orden sola: "notebook barata", "economico".
        k = _clave_orden(w, palabra, suelta=True) if w not in fx.C._RELLENO else None
        if k and (r is None or not fx.es_valor(w, r)):
            ks = [i]
            while ks[0] > 0 and ks[0] - 1 not in tomadas and tokens[ks[0] - 1] in ARTICULOS | {"mas"}:
                ks.insert(0, ks[0] - 1)
            out.append((ks, {"parte": " ".join(tokens[x] for x in ks), "veredicto": "orden", "valor": k, "por": "codigo"}))
            tomadas |= set(ks)
    return out


def palabras(texto, fx):
    """El texto en palabras, sin signos, como lo lee el nexo de condicion."""
    return re.sub(r"[,;:!?¿¡()]", " ", fx.C.n(texto)).split()


def hay(texto, fx):
    """Si el texto pide algo con mas o menos que se resuelve en la tienda entera."""
    return bool(detectar(palabras(texto, fx), set(), None, fx))


def _numero(v):
    """El primer numero del valor; un tera son mil gigas: "1tb" va despues de "500gb"."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s?(tb)?", str(v or "").lower())
    return float(m.group(1).replace(",", ".")) * (1000 if m.group(2) else 1) if m else None


def ordenar(prods, valores, fx):
    """Los productos en el orden pedido: el primer item manda y los demas desempatan. Los que no tienen el dato, al final."""
    C = fx.C

    def clave(p):
        out = []
        for v in valores:
            if v in C.ORDEN:
                campo, sentido = C.ORDEN[v]
                x = float(p.get(campo) or 0)
                out += [0, sentido * x]
            elif "=" in v:
                lado, resto = v.split(" ", 1)
                campo, valor = resto.split("=", 1)
                tiene = C._contiene(C._valores(p, campo), valor)
                out += [0, (1 if tiene else 0) if lado == "menos" else (0 if tiene else 1)]
            else:
                lado, campo = v.split(" ", 1)
                x = _numero(C._valores(p, campo))
                out += [1, 0] if x is None else [0, -x if lado == "mas" else x]
        return out
    return sorted(prods, key=clave)
