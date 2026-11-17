"""LA VARA DEL NEXO DE CONDICION, ESCRITA ANTES DE CORRERLO (16-nov-2026).

Orden de Martin del 16-nov, FICHA 98 seccion 4. Se escribio mirando solo lo que le llega al nexo, las busquedas de la
llamada 0 y la agenda a mano, y la fuente de la tienda; ninguna salida del nexo. No se toca despues de correr.

LOS TRES VEREDICTOS, decididos con Martin el 16-nov, mas lo que el codigo ya sabe hacer:
  ata         la condicion es un valor de un campo de la tienda en ese rubro: filtra y se presupuesta.
  no hay      el campo existe en el rubro pero ningun producto trae ese valor: se dice y se ofrece lo mas cercano.
  no se ata   ningun campo de la fuente lo dice: se repregunta.
  orden       el mas barato, el mas caro, el mas liviano, el mas pesado: lo que `catalogo.ORDEN` sabe ordenar.
  tope        un tope de plata.

CADA CONDICION es una tupla de alternativas que valen; vale cualquiera:
  "ata c1 c2"      ata en alguno de esos campos.            "niega c1"   ata negada en ese campo, "que no sea".
  "no hay c1"      no hay, en ese campo.                    "no se ata"  ningun campo.
  "orden x"        ese orden.                               "tope max"   tope de plata.
  "trivial"        lo dicho vale para todo el rubro: bien si no sale nada, si sale no se ata, o si sale un filtro que
                   no deja afuera ningun producto. Mal si deja afuera alguno.
La vara es por mensaje y rubro, en los cuatro bancos: vale para cualquier llamada 0. Un rubro sin condiciones es
[]: cualquier filtro que salga es inventado. Lo que la tienda no vende no esta.

LO QUE DECIDE LA FUENTE Y NO EL SENTIDO COMUN: el tamano en pulgadas de los monitores no esta en ningun campo, entonces
"monitor 24 pulgadas" no se ata. El peso que aguanta una silla, el idioma de un teclado y si un auricular trae microfono
tampoco. "Wifi 6" en un router es no hay: el campo wifi existe y dice wifi 5.
"""


def C(*alternativas):
    return tuple(alternativas)


T = C("trivial")
NS = C("no se ata")
BARATO = C("orden mas barato")
LIVIANO = C("orden mas liviano")
INALAMBRICO = C("ata conexion bluetooth")
CHINAS = C("no hay pais_fabricacion", "niega pais_marca", "niega pais_fabricacion")

# ══ LAS 140, `nuevas70` Y `nuevas70b`: POR MENSAJE Y RUBRO, PARA CUALQUIER LLAMADA 0 ═════════════════════════════════
# Reescrita el 17-nov, orden de Martin, FICHA 101 seccion 7: la de antes estaba por la busqueda que tradujo Gemini y con
# otra llamada 0 las lineas quedaban afuera. Lo que pedia cada busqueda paso tal cual al rubro de su mensaje; las lineas
# que Gemini escribia distinto de cuando se hizo la vara, 46, y las que caian en nombrado o en un rubro equivocado, 15, se
# escribieron mirando el mensaje. Una condicion por rubro: la cantidad no es de este nexo. Un rubro sin condiciones es []:
# cualquier filtro que salga es inventado. Lo que la tienda no vende no esta. La de antes, en la historia: 17568cf.
LAS_140 = {
    ("nuevas70", "A01"): {"mouse": [T, C("ata retroiluminacion")]},
    ("nuevas70", "A02"): {"notebook": [C("ata ram", "trivial"), LIVIANO]},
    ("nuevas70", "A03"): {"auriculares": [T, C("trivial", "no se ata")]},
    ("nuevas70", "A04"): {"teclado": [C("ata switch_teclado caracteristicas_extra tags"), NS]},
    ("nuevas70", "A05"): {"ssd": [C("ata almacenamiento caracteristicas_extra"), T]},
    ("nuevas70", "A06"): {"monitor": [NS, C("ata nombre modelo tags")]},
    ("nuevas70", "A07"): {"placa de video": [C("trivial", "no se ata"), NS]},
    ("nuevas70", "A08"): {"parlante": [C("ata marca"), C("ata nombre modelo tags"), C("ata color")]},
    ("nuevas70", "A09"): {"cargador": [T, C("ata potencia"), C("trivial", "no se ata")]},
    ("nuevas70", "A10"): {"silla gamer": [C("ata color")]},
    ("nuevas70", "A11"): {"impresora": [C("no se ata", "trivial"), C("ata wifi conexion"), C("no se ata", "ata nombre modelo tags")]},
    ("nuevas70", "F01"): {},
    ("nuevas70", "F02"): {},
    ("nuevas70", "F05"): {},
    ("nuevas70", "F06"): {"notebook": []},
    ("nuevas70", "F11"): {},
    ("nuevas70", "M01"): {"mouse": [BARATO], "auriculares": [BARATO]},
    ("nuevas70", "M02"): {"monitor": [NS], "teclado": [C("ata switch_teclado caracteristicas_extra tags")]},
    ("nuevas70", "M03"): {"mouse": [INALAMBRICO], "notebook": []},
    ("nuevas70", "M04"): {"memoria ram": [C("ata ram caracteristicas_extra"), C("ata nombre modelo tags")], "ssd": [C("ata almacenamiento caracteristicas_extra")]},
    ("nuevas70", "M05"): {"auriculares": [C("trivial", "no se ata")], "impresora": [T], "webcam": []},
    ("nuevas70", "M06"): {"silla gamer": [], "monitor": [C("ata nombre modelo tags")]},
    ("nuevas70", "M07"): {"cargador": [C("trivial", "no se ata")], "parlante": [C("ata bluetooth conexion")]},
    ("nuevas70", "M08"): {"procesador": [C("ata procesador nombre modelo tags")], "motherboard": [C("ata procesador", "no se ata")], "memoria ram": [C("ata ram caracteristicas_extra")], "fuente": [C("ata potencia")]},
    ("nuevas70", "M09"): {"router": [C("no hay wifi caracteristicas_extra"), BARATO, C("trivial", "ata nombre modelo tags")]},
    ("nuevas70", "M10"): {"tablet": []},
    ("nuevas70", "M11"): {"microfono": [T]},
    ("nuevas70", "M12"): {"mouse": [BARATO], "teclado": [BARATO]},
    ("nuevas70", "M13"): {"monitor": [NS, C("ata hz")], "placa de video": [], "gabinete": [C("ata nombre modelo tags")]},
    ("nuevas70", "M14"): {"almacenamiento externo": [C("ata almacenamiento caracteristicas_extra")]},
    ("nuevas70", "M15"): {"auriculares": [INALAMBRICO, C("ata marca")], "parlante": [C("ata marca"), C("no se ata", "orden mas pesado")]},
    ("nuevas70", "M16"): {"silla gamer": [T], "impresora": []},
    ("nuevas70", "M17"): {"cooler": [T], "fuente": [C("no se ata", "trivial")]},
    ("nuevas70", "M18"): {"webcam": [T]},
    ("nuevas70", "O01"): {"mouse": [BARATO]},
    ("nuevas70", "O02"): {"teclado": [NS]},
    ("nuevas70", "O03"): {"notebook": [C("orden mas caro", "no se ata")]},
    ("nuevas70", "O04"): {"auriculares": [INALAMBRICO, CHINAS]},
    ("nuevas70", "O05"): {"monitor": [C("tope max")]},
    ("nuevas70", "O06"): {"placa de video": [C("orden mas caro", "no se ata", "trivial")]},
    ("nuevas70", "O07"): {"silla gamer": [NS]},
    ("nuevas70", "O08"): {"almacenamiento externo": [T]},
    ("nuevas70", "O09"): {"parlante": [C("ata resistencia_agua")]},
    ("nuevas70", "O10"): {"cargador": [NS, C("no se ata", "trivial")]},
    ("nuevas70", "O11"): {"notebook": [LIVIANO, C("trivial", "no se ata")]},
    ("nuevas70", "O12"): {"router": [C("no se ata", "trivial", "ata nombre modelo tags")]},
    ("nuevas70", "R01"): {"microfono": [T]},
    ("nuevas70", "R02"): {"router": [C("trivial", "ata nombre modelo tags"), NS]},
    ("nuevas70", "R03"): {"monitor": [T]},
    ("nuevas70", "R04"): {"notebook": [C("no se ata", "no hay tactil")]},
    ("nuevas70", "R05"): {"almacenamiento externo": [C("trivial", "no se ata")]},
    ("nuevas70", "R06"): {"impresora": [T]},
    ("nuevas70", "R07"): {"placa de video": []},
    ("nuevas70", "R08"): {"gabinete": []},
    ("nuevas70", "R09"): {"cooler": [T]},
    ("nuevas70", "R10"): {"auriculares": [C("trivial", "no se ata")]},
    ("nuevas70", "R11"): {"webcam": [T]},
    ("nuevas70", "R12"): {},
    ("nuevas70", "R13"): {"motherboard": []},
    ("nuevas70", "R14"): {"procesador": [C("no se ata", "trivial")]},
    ("nuevas70", "R15"): {"tablet": [C("trivial", "no se ata")]},
    ("nuevas70", "R16"): {"memoria ram": [C("no se ata", "trivial")]},
    ("nuevas70", "R17"): {"parlante": [C("no se ata", "ata resistencia_agua conexion bateria")]},
    ("nuevas70", "R18"): {"silla gamer": []},
    ("nuevas70b", "B01"): {"mouse": [INALAMBRICO], "teclado": [INALAMBRICO]},
    ("nuevas70b", "B02"): {"parlante": [C("ata conexion", "trivial"), C("no se ata", "ata potencia")], "auriculares": [C("no se ata", "trivial", "no hay resistencia_agua")]},
    ("nuevas70b", "B03"): {"fuente": [C("ata potencia")], "gabinete": [T]},
    ("nuevas70b", "B04"): {"procesador": [C("ata procesador nombre modelo tags")], "motherboard": [C("trivial", "no se ata")]},
    ("nuevas70b", "B05"): {"webcam": [C("trivial", "no se ata")], "microfono": [C("trivial", "no se ata")]},
    ("nuevas70b", "B06"): {"cargador": [C("trivial", "no se ata")], "router": [C("trivial", "ata nombre modelo tags")]},
    ("nuevas70b", "B07"): {"almacenamiento externo": [T], "impresora": []},
    ("nuevas70b", "B08"): {"memoria ram": [C("ata ram caracteristicas_extra")], "ssd": [T]},
    ("nuevas70b", "B09"): {"placa de video": [T, C("trivial", "no se ata")], "cooler": [T]},
    ("nuevas70b", "B10"): {"notebook": [], "monitor": [C("no se ata", "trivial")]},
    ("nuevas70b", "B11"): {"tablet": [NS], "silla gamer": [C("no se ata", "trivial")]},
    ("nuevas70b", "B12"): {"mouse": [INALAMBRICO], "teclado": [NS], "webcam": []},
    ("nuevas70b", "B13"): {"auriculares": [T, C("ata conexion caracteristicas_extra bluetooth")], "microfono": [C("no se ata", "trivial"), T]},
    ("nuevas70b", "B14"): {"placa de video": [C("ata memoria_video caracteristicas_extra")], "fuente": [C("ata nombre modelo tags", "no se ata"), C("ata potencia")]},
    ("nuevas70b", "B15"): {"tablet": [C("no se ata", "trivial"), NS], "parlante": [C("ata bluetooth conexion"), C("ata resistencia_agua")]},
    ("nuevas70b", "B16"): {"monitor": [T, C("ata hz"), C("orden mas barato", "trivial")], "silla gamer": [T, BARATO]},
    ("nuevas70b", "B17"): {"cargador": [T, C("no se ata", "trivial")], "router": [C("trivial", "ata nombre modelo tags")]},
    ("nuevas70b", "B18"): {"cooler": [NS, C("no se ata", "no hay potencia")], "gabinete": []},
    ("nuevas70b", "B19"): {"impresora": [T], "almacenamiento externo": [C("ata almacenamiento caracteristicas_extra")]},
    ("nuevas70b", "B20"): {"motherboard": [C("ata procesador")], "memoria ram": [C("ata ram caracteristicas_extra"), C("ata nombre modelo tags")], "procesador": [C("ata marca", "ata procesador nombre modelo tags"), C("trivial", "no se ata")]},
    ("nuevas70b", "B21"): {"mouse": [INALAMBRICO, C("no se ata", "orden mas liviano")], "notebook": []},
    ("nuevas70b", "B22"): {"impresora": [NS]},
    ("nuevas70b", "B23"): {"cargador": [C("trivial", "no se ata")], "auriculares": [INALAMBRICO]},
    ("nuevas70b", "B24"): {"parlante": [C("no se ata", "trivial", "ata conexion")]},
    ("nuevas70b", "B25"): {"webcam": [T]},
    ("nuevas70b", "B26"): {"silla gamer": []},
    ("nuevas70b", "B27"): {"auriculares": [T, NS]},
    ("nuevas70b", "B28"): {"cooler": [T]},
    ("nuevas70b", "B29"): {"fuente": [C("ata potencia")]},
    ("nuevas70b", "B30"): {"placa de video": []},
    ("nuevas70b", "B31"): {"auriculares": [C("trivial", "no se ata")]},
    ("nuevas70b", "B32"): {"monitor": [T]},
    ("nuevas70b", "B33"): {"almacenamiento externo": [T]},
    ("nuevas70b", "B34"): {"router": [C("trivial", "ata nombre modelo tags"), C("no se ata", "trivial"), C("ata nombre modelo tags")]},
    ("nuevas70b", "B35"): {"placa de video": []},
    ("nuevas70b", "B36"): {"cooler": [T]},
    ("nuevas70b", "B37"): {"memoria ram": []},
    ("nuevas70b", "B38"): {"webcam": [C("trivial", "no se ata")]},
    ("nuevas70b", "B39"): {"mouse": [T]},
    ("nuevas70b", "B40"): {"impresora": []},
    ("nuevas70b", "B41"): {"notebook": [T, C("no se ata", "trivial")]},
    ("nuevas70b", "B42"): {"gabinete": [C("trivial", "no se ata"), C("ata retroiluminacion")]},
    ("nuevas70b", "B43"): {"fuente": []},
    ("nuevas70b", "B44"): {"motherboard": []},
    ("nuevas70b", "B45"): {"procesador": [NS]},
    ("nuevas70b", "B46"): {"ssd": []},
    ("nuevas70b", "B47"): {"webcam": [T], "auriculares": [C("trivial", "no se ata")], "microfono": [C("trivial", "no se ata")]},
    ("nuevas70b", "B48"): {"impresora": [C("ata wifi conexion"), C("no se ata", "trivial")], "notebook": []},
    ("nuevas70b", "B49"): {"router": [C("trivial", "ata nombre modelo tags")]},
    ("nuevas70b", "B50"): {"memoria ram": [C("ata ram caracteristicas_extra"), C("ata nombre modelo tags")], "ssd": [C("ata almacenamiento caracteristicas_extra")]},
    ("nuevas70b", "B51"): {"mouse": [C("ata marca")], "teclado": [C("ata marca")], "auriculares": [C("ata marca")]},
    ("nuevas70b", "B52"): {"fuente": [C("ata potencia")], "gabinete": [C("no se ata", "trivial")]},
    ("nuevas70b", "B53"): {"tablet": [C("no se ata", "trivial")], "cargador": [C("trivial", "no se ata")]},
    ("nuevas70b", "B54"): {"silla gamer": [], "monitor": [C("ata nombre modelo tags"), NS]},
    ("nuevas70b", "B55"): {"parlante": [C("tope max")]},
    ("nuevas70b", "B56"): {"ssd": [C("no hay almacenamiento caracteristicas_extra")], "memoria ram": [C("ata ram caracteristicas_extra")]},
    ("nuevas70b", "B57"): {"silla gamer": []},
    ("nuevas70b", "B58"): {"auriculares": [C("trivial", "no se ata"), BARATO]},
    ("nuevas70b", "B59"): {"motherboard": [BARATO], "cooler": [T, BARATO], "procesador": [BARATO]},
    ("nuevas70b", "B60"): {"monitor": [NS], "teclado": []},
    ("nuevas70b", "B61"): {"impresora": []},
    ("nuevas70b", "B62"): {"placa de video": []},
    ("nuevas70b", "B63"): {"notebook": [NS]},
    ("nuevas70b", "B64"): {"webcam": []},
    ("nuevas70b", "B65"): {"router": [C("trivial", "ata nombre modelo tags")]},
    ("nuevas70b", "B66"): {"mouse": [], "teclado": [T, C("no hay switch_teclado", "no se ata", "ata switch_teclado")]},
    ("nuevas70b", "B67"): {"parlante": [C("ata marca", "trivial", "no se ata")], "auriculares": [C("trivial", "no se ata", "ata conexion", "ata nombre modelo tags")]},
    ("nuevas70b", "B68"): {"procesador": [C("ata procesador nombre modelo tags", "trivial")], "placa de video": [C("ata nombre modelo tags", "ata memoria_video", "no se ata"), C("trivial", "no se ata")]},
    ("nuevas70b", "B69"): {"impresora": [C("ata marca"), C("no se ata", "ata nombre modelo tags")], "almacenamiento externo": [C("no hay almacenamiento caracteristicas_extra")]},
    ("nuevas70b", "B70"): {"monitor": [NS], "webcam": [C("no se ata", "trivial")]},
}

# ══ LAS 365 DE `traduccion58`: POR LA AGENDA A MANO, `agendas58.py` ══════════════════════════════════════════════════
# Cada condicion y cada orden de un `buscar` de la agenda, con lo que vale en la fuente. La linea se busca por el rubro.
DE_LA_AGENDA = {
    "16 GB de RAM": C("ata ram", "trivial"),
    "inalambrico": INALAMBRICO,
    "preferentemente Logitech": C("ata marca"),
    "que no sea Genius": C("niega marca"),
    "que no sea Logitech": C("niega marca"),
    "que no sea Redragon": C("niega marca"),
    "lo menos china posible": CHINAS,
    "menos partes chinas posibles": CHINAS,
    "mecanico": C("ata switch_teclado caracteristicas_extra tags"),
    "JBL": C("ata marca"),
    "Logitech": C("ata marca"),
    "gamer": T,
    "con cable": C("ata conexion bluetooth"),
    "blanco": C("ata color"),
    "DDR5": C("ata nombre modelo tags"),
    "64 GB de RAM": C("no hay ram"),
    "menos de 200 mil": C("tope max"),
    "que aguante una fuente de 550 watts": NS,
    "para la oficina": C("no hay uso_recomendado", "no se ata"),
    "con microfono": C("trivial", "no se ata"),
    "playstation 5": C("trivial", "no se ata"),
    "grande": NS,
    "2 TB": C("ata almacenamiento caracteristicas_extra"),
    "buena imagen": T,
    "que cubra toda la casa": C("trivial", "no se ata", "ata nombre modelo tags"),
    "ergonomica": T,
    "para jugar": T,
}
ORDEN_DE_LA_AGENDA = {"mas barato": BARATO, "mas caro": C("orden mas caro"), "mas liviano": LIVIANO,
                      "mas potente": NS}

# ══ LOS 40 REALES: POR MENSAJE Y RUBRO ═══════════════════════════════════════════════════════════════════════════════
REALES = {
    "R07": {"notebook": [BARATO], "microfono": [BARATO], "memoria ram": [BARATO]},
    "R10": {"teclado": [BARATO, T]},
    "R12": {"placa de video": [NS]},
    "R14": {r: [CHINAS] for r in ("auriculares", "mouse", "memoria ram")},
    "R18": {r: [C("niega pais_marca", "trivial")] for r in ("auriculares", "mouse", "memoria ram")},
    "R31": {"mouse": [C("ata retroiluminacion")]},
    "R35": {"auriculares": [BARATO]},
    "R36": {"teclado": [BARATO]},
    "R37": {"auriculares": [C("trivial", "no se ata")]},
    "R39": {"mouse": [LIVIANO]},
}

# ══ LAS 26 CHARLAS, `segunda.py`: EL PRIMER TURNO, QUE NO NECESITA MEMORIA ══════════════════════════════════════════
# Escrita el 17-nov mirando el mensaje, antes de correr el nexo con estas lineas. Los productos nombrados, "G305", son del
# nexo de nombrado y no estan. K20 y K21 son el mensaje que Martin mando por WhatsApp el 17-nov.
CHARLAS = {
    "C27|0": {"mouse": [C("ata marca")]},
    "C35|0": {"mouse": [T, C("ata marca")]},
    "C45|0": {"mouse": [C("ata marca"), C("ata conexion bluetooth")]},
    "C46|0": {"teclado": [C("niega marca")]},
    "C52|0": {"mouse": [C("ata marca")], "teclado": [C("ata marca")], "auriculares": [C("ata marca")]},
    "K07|0": {"mouse": [BARATO], "teclado": [BARATO], "auriculares": [BARATO]},
    "K10|0": {"mouse": [], "auriculares": []},
    "K11|0": {"mouse": [C("no hay uso_recomendado", "no se ata", "trivial")],
              "teclado": [C("no hay uso_recomendado", "no se ata", "trivial")]},
    "K13|0": {"notebook": [BARATO]},
    "K17|0": {"mouse": [C("niega marca"), C("niega marca")]},
    "K20|0": {r: [CHINAS] for r in ("auriculares", "mouse", "memoria ram", "teclado")},
    "K21|0": {r: [CHINAS] for r in ("auriculares", "mouse", "memoria ram", "teclado")},
}
