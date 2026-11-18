"""EL NEXO DEL PRODUCTO NOMBRADO: LA MARCA O EL MODELO QUE DICE EL CLIENTE, POR PALABRA EXACTA.

Pasado de `banco_pruebas/flujo/nexo_nombrado.py` el 17-nov-2026, orden de Martin, tal cual: el banco importa de aca. El
rubro lo dan los embeddings del nexo de producto, o la palabra exacta; la identidad, `catalogo._identificar`: exists,
ambiguous o not_found. Regla 7.0: el modelo nunca inventa identidad.
"""
import collections
import csv
import os

from . import rubro as NR


def _codigo(w):
    return any(c.isdigit() for c in w) and any(c.isalpha() for c in w)


class Nexo:
    def __init__(self, indice):
        from app.core.flujo.agenda import _VACIAS
        self.idx, self.vacias = indice, _VACIAS
        fs = indice.filas
        sp = {(r["marca"], r["modelo"]): r for r in csv.DictReader(
            open(os.path.join(NR.DATOS, indice.tid, "specs_por_modelo.csv"), encoding="utf-8"))}
        propios = {"id", "nombre", "marca", "modelo", "tags", "descripcion", "descripcion_rica", "categoria",
                   "precio_ars", "stock"}
        self.marcas = {NR.n(f["marca"]) for f in fs}
        self.por_rubro, self.rub = collections.defaultdict(list), {}
        for f in fs:
            self.por_rubro[f["categoria"]].append(f)
        for r, ps in self.por_rubro.items():
            atributos = {w for f in ps for k, v in f.items() if k not in propios for w in NR.n(v).split()}
            atributos |= {w for f in ps for k, v in (sp.get((f["marca"], f["modelo"])) or {}).items()
                          if k not in ("marca", "modelo", "categoria") for w in NR.n(v).split()}
            vocab = set(NR.n(r).split()) | {w for x in indice.alias.get(r, []) for w in NR.n(x).split()}
            tokens = {w for f in ps for w in NR.n(f["modelo"]).split()}
            # Un nombre nombra solo a sus modelos: si la palabra esta en las etiquetas o la descripcion de un modelo que
            # no la lleva en el nombre, es un atributo. "hd" esta en las etiquetas de webcams que no se llaman HD.
            describe = {w for f in ps for w in NR.n(f"{f.get('tags')} {f.get('descripcion')}").split()
                        if w not in NR.n(f["modelo"]).split()}
            self.rub[r] = {"marcas": {NR.n(f["marca"]) for f in ps}, "vocab": vocab, "tokens": tokens,
                           "nombres": {w for w in tokens - atributos - vocab - describe if not w.isdigit()},
                           "no_nombre": atributos | vocab | describe,
                           "modelos": {f["modelo"]: NR.n(f["modelo"]).split() for f in ps},
                           "colores": {NR.n(f["color"]) for f in ps if f.get("color")},
                           "por_marca": {m: {w for f in ps if NR.n(f["marca"]) == m for w in NR.n(f["modelo"]).split()}
                                         for m in {NR.n(f["marca"]) for f in ps}}}

    def palabras(self, busqueda, rubro):
        """PIEZA 2: las palabras de identidad de la busqueda en ese rubro, en orden.

        Fuertes: marca de la tienda, nombre de modelo del rubro, o codigo con letras y numeros que esta dentro de un
        modelo del rubro. Pegadas a una de identidad, encadenadas, "ryzen 5 5600": un numero o una palabra corta que
        esta en un modelo, o un codigo con letras y numeros aunque la tienda no lo tenga, "sony xm4", para que la
        identidad diga que no esta en vez de traer todos los Sony."""
        R = self.rub[rubro]
        ws = self._acomodar([w for w in NR.n(busqueda).split() if w not in self.vacias], R)

        def codigo(w):
            return any(c.isdigit() for c in w) and any(c.isalpha() for c in w)
        dentro = [any(w in t for t in R["tokens"]) for w in ws]
        # Un codigo es de identidad si lo usa una sola marca del rubro: "g305" es de Logitech; "16gb" o "750w" los
        # usan todas, son medidas metidas en el campo modelo y las resuelve el nexo de condicion.
        propio = [len({m for m, toks in R["por_marca"].items() if any(w in t for t in toks)}) == 1 for w in ws]
        # Los nombres de modelo de otro rubro no: medido el 15-nov, "parlante para smart tv" tomaba "smart" de las
        # impresoras Smart Tank y "keyboard switches red" el "red" de la Red Devil, y daban un falso "no lo tengo".
        si = [w in self.marcas or w in R["nombres"] or (codigo(w) and p) for w, p in zip(ws, propio)]
        cambio = True
        while cambio:
            cambio = False
            for i, w in enumerate(ws):
                pegada = (i > 0 and si[i - 1]) or (i + 1 < len(ws) and si[i + 1])
                if not si[i] and pegada and w not in R["vocab"] and (
                        codigo(w) or ((w.isdigit() or len(w) <= 3) and dentro[i])):
                    si[i] = cambio = True
        # La identidad de produccion exige palabra entera a lo corto: "xm5" se lleva al codigo del catalogo que lo
        # contiene, "1000xm5", si es uno solo.
        out = []
        for w, s in zip(ws, si):
            if s:
                con = {t for t in R["tokens"] if w in t}
                lleva = len(con) == 1 and (_codigo(w) or next(iter(con)).startswith(w))
                out.append(con.pop() if w not in R["tokens"] and lleva else w)
        return out

    @staticmethod
    def _acomodar(ws, R):
        """La busqueda escrita como el catalogo escribe sus codigos. Se juntan dos palabras seguidas si juntas estan en
        un codigo del rubro y alguna de las dos sola no esta: "5600 x" es "5600x", "g 305" es "g305". Se parte un codigo
        pegado que no esta en el rubro, entre letras y numeros, si sus partes son codigos exactos del rubro: "rtx4060",
        "flip6", "4060ti"; "xm4" no, porque "xm" solo esta dentro de "1000xm5"."""
        def esta(w):
            return any(w in t for t in R["tokens"])
        out, i = [], 0
        while i < len(ws):
            w = ws[i]
            if i + 1 < len(ws) and (not esta(w) or not esta(ws[i + 1]) or len(w) == 1 or len(ws[i + 1]) == 1) \
                    and _codigo(w + ws[i + 1]) and esta(w + ws[i + 1]):
                out.append(w + ws[i + 1])
                i += 2
                continue
            if _codigo(w) and not esta(w):
                cortes = [k for k in range(1, len(w)) if w[k - 1].isdigit() != w[k].isdigit()]
                partes = next(([w[:k], w[k:]] for k in cortes if w[:k] in R["tokens"] and w[k:] in R["tokens"]), None)
                if partes:
                    out.extend(partes)
                    i += 1
                    continue
            out.append(w)
            i += 1
        return out

    @staticmethod
    def _solo(prods, modelos):
        return [p for p in prods if p["modelo"] in modelos]

    def _sufijo(self, v, ids, color, prods, R):
        """Un numero dicho elige el modelo donde ese numero termina: el sufijo que el cliente no dijo, "Ti" o "Super", es
        otro modelo, si hay alguno sin sufijo. "rtx 4060" no trae las 4060 Ti; "rtx 4070" no trae las 4070 Super."""
        if v["veredicto"] != "ambiguous":
            return v
        # Solo numeros puros, los de generacion: "ddr5" o "32gb" son medidas y el sufijo de un DDR5 es su velocidad.
        numeros = {w for w in ids if w.isdigit()}

        def con_sufijo(m):
            t = R["modelos"][m]
            return any(x in numeros and k + 1 < len(t) and t[k + 1] not in ids for k, x in enumerate(t))
        ms = [o["modelo"] for o in v["opciones"]]
        sin = [m for m in ms if not con_sufijo(m)]
        if not sin or len(sin) == len(ms) or not any(x in numeros for m in sin for x in R["modelos"][m]):
            return v
        from app.core.flujo.catalogo import _identificar
        return _identificar(" ".join(ids), color, self._solo(prods, sin))

    def _numero_suelto(self, v, ids, color, prods, R):
        """Un numero suelto que calza de casualidad no elige: si el modelo hallado lleva un nombre que el cliente no dijo
        y sin ese numero calzan otros, es ambiguo y se pregunta. "hyperx cloud 2" no es el Cloud Stinger 2: el Cloud II
        se escribe con romanos."""
        if v["veredicto"] != "exists":
            return v
        # Suelto es el numero que coincide entero con una palabra del modelo, el "2" de Stinger 2; el que esta dentro de
        # un codigo, "13400" en "13400f", no.
        sueltos = [w for w in ids if w.isdigit() and w in R["modelos"][v["producto"]["modelo"]]]
        no_dicho = [x for x in R["modelos"][v["producto"]["modelo"]]
                    if x in R["nombres"] and x not in ids and not any(w in x for w in sueltos)]
        if not sueltos or not no_dicho:
            return v
        from app.core.flujo.catalogo import _identificar
        sin = _identificar(" ".join(w for w in ids if w not in sueltos), color, prods)
        if sin["veredicto"] != "ambiguous":
            return v
        # Si los otros modelos de la familia llevan otro numero, el del cliente elige de verdad: "rtx 4070" es la 4070,
        # no cualquier RTX. En la familia Cloud los otros no llevan numero, y ahi el 2 calzo de casualidad.
        otros = [o["modelo"] for o in sin["opciones"] if o["modelo"] != v["producto"]["modelo"]]
        return v if any(x.isdigit() for m in otros for x in R["modelos"][m]) else sin

    def _nombra(self, busqueda, rubro):
        """Cuantas palabras de la busqueda nombran algo de ese rubro: marca, nombre de modelo o codigo de su catalogo."""
        R = self.rub[rubro]
        ws = self._acomodar([w for w in NR.n(busqueda).split() if w not in self.vacias], R)
        return sum(w in R["marcas"] or w in R["nombres"] or (_codigo(w) and any(w in t for t in R["tokens"])) for w in ws)

    def rubro(self, busqueda, elegido):
        """PIEZA 1, la mitad exacta: el rubro lo eligen los embeddings. Solo si no eligieron ninguno, lo propone la
        palabra exacta: el rubro donde la busqueda nombra un modelo y donde mas palabras suyas estan en los modelos.
        "lenovo legion 5 i7" no trae notebook entre los tres rubros de los embeddings; "legion" solo nombra notebooks."""
        if elegido:
            return elegido
        crudas = [w for w in NR.n(busqueda).split() if w not in self.vacias]
        cuenta = {}
        for r, R in self.rub.items():
            ws = self._acomodar(crudas, R)
            # Tiene que nombrar una marca del rubro, o traer un codigo exacto del rubro, ademas de un nombre o un codigo
            # del rubro: "repetidor wifi" no es una motherboard WiFi y "resma a4" no es un SSD A400; "g-305" y
            # "rtx4060" si dicen que son.
            exacto = any(_codigo(w) and w in R["tokens"] for w in ws) or any(_codigo(w) for w in crudas if w not in ws)
            nombra = any(w in R["nombres"] or (_codigo(w) and w in R["tokens"]) for w in ws)
            if nombra and (exacto or any(w in R["marcas"] for w in ws)):
                cuenta[r] = sum(any(w in t for t in R["tokens"]) for w in ws)
        mejor = [r for r, k in cuenta.items() if k == max(cuenta.values())] if cuenta else []
        return mejor[0] if len(mejor) == 1 else None

    def nombrado(self, linea):
        """PIEZAS 1 A 3. None si el nexo no corre."""
        p = self.idx.producto(linea.consulta())
        elegido = self.rubro(linea.busqueda, p["elegido"]["rubro"] if p["elegido"] else None)
        exacto = self.rubro(linea.busqueda, None)
        # La identidad la decide la palabra exacta, regla 7.0: si otro rubro nombra mas palabras de la busqueda, con
        # marca o codigo exacto, gana ese. Los embeddings desempatan. Medido el 16-nov: con el indice calibrado,
        # "jbl tune 520" caia en parlantes y "hyperx cloud 2" en microfonos.
        rubro = exacto if exacto and (not elegido or self._nombra(linea.busqueda, exacto)
                                      > self._nombra(linea.busqueda, elegido)) else elegido
        ids = self.palabras(linea.busqueda, rubro) if rubro else []
        if not ids:
            return None
        from app.core.flujo.catalogo import _identificar
        R = self.rub[rubro]
        color = next((c for c in R["colores"] if c and c in NR.n(linea.busqueda).split()), "")
        prods = [dict(f, stock=int(f["stock"] or 0)) for f in self.por_rubro[rubro]]
        v = _identificar(" ".join(ids), color, prods)
        v = self._sufijo(v, ids, color, prods, R)
        v = self._numero_suelto(v, ids, color, prods, R)
        if v["veredicto"] == "exists":
            modelos, prod = [v["producto"]["modelo"]], v["producto"]
        elif v["veredicto"] == "ambiguous":
            modelos, prod = [o["modelo"] for o in v["opciones"]], None
        else:
            modelos, prod = [], None
        # Si ninguna palabra es marca, nombre o codigo de este rubro, nombra otra cosa: "motherboard compatible procesador
        # intel" no pide una motherboard Intel. El not_found vale, pero no es un "no lo tengo": lo contestan el de
        # producto y el de condicion.
        de_otro = not any(w in R["marcas"] or w in R["nombres"] or (_codigo(w) and any(w in t for t in R["tokens"]))
                          for w in ids)
        return {"busqueda": linea.busqueda, "rubro": rubro, "palabras": ids, "color": color, "de_otro_rubro": de_otro,
                "veredicto": v["veredicto"], "modelos": modelos, "producto": prod and {
                    "id": prod["id"], "nombre": prod["nombre"], "precio": int(float(prod["precio_ars"])),
                    "stock": int(prod["stock"])}}

