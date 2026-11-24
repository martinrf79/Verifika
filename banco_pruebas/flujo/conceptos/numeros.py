"""LOS LECTORES DE NUMEROS: PLATA, CAPACIDAD, POTENCIA, HZ, PULGADAS Y CANTIDAD, POR CODIGO (24-nov-2026, paso 1).

leer(frase, rubro=None) -> [{"tipo", "campo", "op", "valor", "texto"}]
  plata      precio max o min: "hasta 30 lucas", "menos de 10 mil", "$50.000", "mas de 200k"
  capacidad  capacidad_gb, o ram_gb y disco_gb en notebooks: "16 gigas", "1 tera", "dieciseis de ram", "512 de disco"
  potencia   potencia_w: "65 watts", "sesenta y cinco w"
  hz         hz minimo: "144hz", "de 165 hz"
  pulgadas   pulgadas, igual: de la ficha, `pulgadas` de specs_por_modelo.csv
  cantidad   cuantas unidades: "dos teclados", "me llevo 3"; no filtra
Los numeros en letras se pasan a cifras antes de leer. Un codigo de modelo, "k380", "g305", no es numero.
"""
import re, unicodedata

UNI = {"cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
       "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
       "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiun": 21,
       "veintiuno": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
       "veintisiete": 27, "veintiocho": 28, "veintinueve": 29}
DEC = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90}
CEN = {"cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300, "cuatrocientos": 400, "quinientos": 500,
       "seiscientos": 600, "setecientos": 700, "ochocientos": 800, "novecientos": 900}
MILES = {"luca": 1000, "lucas": 1000, "luquita": 1000, "luquitas": 1000, "mil": 1000, "k": 1000, "palo": 10 ** 6,
         "palos": 10 ** 6, "millon": 10 ** 6, "millones": 10 ** 6, "mangos": 1, "pesos": 1}


def nrm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    s = re.sub(r"(\d)\.(\d{3})\b", r"\1\2", s)          # 50.000 -> 50000
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)               # 4,5 -> 4.5
    s = re.sub(r"(\d)([a-z])", r"\1 \2", s)             # 16gb -> 16 gb, 144hz -> 144 hz
    s = re.sub(r"\b(k|g)\s+(\d)", r"\1\2", s)           # deshace "k 380" si venia pegado como codigo
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9. $]", " ", s)).strip()


def letras(s):
    """'sesenta y cinco watts' -> '65 watts'; 'ciento cuarenta y cuatro' -> '144'."""
    ws, out, i = s.split(), [], 0
    while i < len(ws):
        n, j = None, i
        if ws[j] in CEN:
            n = CEN[ws[j]]; j += 1
        if j < len(ws) and ws[j] in DEC:
            n = (n or 0) + DEC[ws[j]]; j += 1
            if j + 1 < len(ws) and ws[j] == "y" and ws[j + 1] in UNI:
                n += UNI[ws[j + 1]]; j += 2
        elif j < len(ws) and ws[j] in UNI and ws[j] not in ("un", "una", "uno") or (n and j < len(ws) and ws[j] in UNI):
            n = (n or 0) + UNI[ws[j]]; j += 1
        if n is None:
            out.append(ws[i]); i += 1
        else:
            out.append(str(n)); i = j
    return " ".join(out)


def leer(frase, rubro=None):
    s = letras(nrm(frase))
    out = []

    tramos = []

    def poner(tipo, campo, op, valor, texto, m=None):
        out.append({"tipo": tipo, "campo": campo, "op": op, "valor": valor, "texto": texto})
        if m is not None:
            tramos.append(m.span())

    # plata
    for m in re.finditer(r"(?:\$\s*)?(\d+(?:\.\d+)?)\s*(lucas?|luquitas?|mil|k|palos?|millon(?:es)?|mangos|pesos)?\b", s):
        n, u = float(m.group(1)), m.group(2)
        antes = s[max(0, m.start() - 25):m.start()]
        if not u and "$" not in m.group(0):
            if n < 1000 or re.search(r"\b(gb|tb|w|hz|de ram|teras?|gigas?)\b", s[m.end():m.end() + 8]):
                continue
        valor = int(n * MILES.get(u or "", 1))
        if valor < 1000:
            continue
        op = "min" if re.search(r"\b(mas de|desde|minimo|arriba de|mayor a)\s*$", antes) else "max"
        poner("plata", "precio", op, valor, m.group(0).strip(), m)
    # capacidad
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(gb|g|gigas?|tb|teras?|t)?\s*(de (ram|memoria|disco|ssd|almacenamiento))?\b", s):
        n, u, de = float(m.group(1)), m.group(2), m.group(4)
        if not u and not de:
            continue
        if u in ("g", "t") and not de:
            continue
        gb = int(n * (1000 if u and u.startswith("t") else 1))
        if rubro == "notebook" or de in ("ram",) and rubro in (None, "notebook"):
            campo = "ram_gb" if de in ("ram", "memoria") or (not de and gb <= 64) else "disco_gb"
        else:
            campo = "capacidad_gb"
        poner("capacidad", campo, "igual", gb, m.group(0).strip(), m)
    # potencia
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(w|watts?|vatios?)\b", s):
        poner("potencia", "potencia_w", "igual", float(m.group(1)), m.group(0), m)
    # hz
    for m in re.finditer(r"(\d+)\s*(hz|hertz)\b", s):
        poner("hz", "hz", "min", float(m.group(1)), m.group(0), m)
    # pulgadas
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(pulgadas?|pulg|\")", s + " ") or []:
        poner("pulgadas", "pulgadas", "igual", float(m.group(1)), m.group(0), m)
    m = re.search(r"\b(monitor|pantalla|moni|tele)\s+de\s+(\d{2})\b(?!\s*(hz|gb|w))", s)
    if m and not any(o["tipo"] == "pulgadas" for o in out):
        poner("pulgadas", "pulgadas", "igual", float(m.group(2)), m.group(0), m)
    # cantidad: un numero chico pegado a un producto o a "llevo"; no los que ya leyo otro lector
    for m in re.finditer(r"\b(llevo|quiero|necesito|dame|pasame|serian|son)?\s*(\d{1,2})\b(?!\s*(gb|tb|w|hz|de ram|pulg|lucas|mil|k\b))", s):
        n = int(m.group(2))
        a, b = m.span(2)
        if 1 < n < 100 and not any(a < y and x < b for x, y in tramos):
            poner("cantidad", "cantidad", "igual", n, m.group(0).strip())
    return out


CASOS = [  # (frase, rubro, lo que tiene que salir como (tipo, campo, op, valor))
    ("hasta 30 lucas un mouse", "mouse", [("plata", "precio", "max", 30000)]),
    ("si el k120 negro sale menos de 10 mil llevo dos", "teclado", [("plata", "precio", "max", 10000), ("cantidad", "cantidad", "igual", 2)]),
    ("los 3 K380 negros", "teclado", [("cantidad", "cantidad", "igual", 3)]),
    ("notebook de 64 gb de ram por menos de 200 mil", "notebook", [("plata", "precio", "max", 200000), ("capacidad", "ram_gb", "igual", 64)]),
    ("notebooks con dieciseis de ram", "notebook", [("capacidad", "ram_gb", "igual", 16)]),
    ("un charger de sesenta y cinco watts", "cargador", [("potencia", "potencia_w", "igual", 65)]),
    ("monitor 24 pulgadas 144hz", "monitor", [("hz", "hz", "min", 144), ("pulgadas", "pulgadas", "igual", 24)]),
    ("un monitor de 27 con envio", "monitor", [("pulgadas", "pulgadas", "igual", 27)]),
    ("agregame un ssd samsung 980 de 1tb", "ssd", [("capacidad", "capacidad_gb", "igual", 1000)]),
    ("mostrame mouse hasta 50 mil", "mouse", [("plata", "precio", "max", 50000)]),
    ("tenes el g305?", "mouse", []),
    ("memoria ram de 16gb", "memoria ram", [("capacidad", "capacidad_gb", "igual", 16)]),
    ("algo de mas de $150.000", None, [("plata", "precio", "min", 150000)]),
    ("que le corra a ciento cuarenta y cuatro hz", None, [("hz", "hz", "min", 144)]),
]

if __name__ == "__main__":
    mal = 0
    for fr, rub, esp in CASOS:
        got = sorted((o["tipo"], o["campo"], o["op"], o["valor"]) for o in leer(fr, rub))
        ok = got == sorted(esp)
        mal += not ok
        print("ok " if ok else "MAL", fr, "->", got)
    print(f"{len(CASOS) - mal} de {len(CASOS)} casos")
