"""COMO BUSCA CADA NEXO: EL REGISTRO UNICO, PARA QUE LA PROXIMA SESION NO LO RECONSTRUYA (15-nov-2026).

Orden de Martin del 15-nov: la configuracion de busqueda de cada nexo es la que da los numeros del banco, y tiene que
pasar de una sesion a otra. Los nexos toman sus numeros de aca; lo que cambie aca cambia los numeros del banco.

Un solo pedido de embeddings por mensaje: vectoriza las busquedas y los fragmentos de todas las lineas. Lo que cambia
por nexo es que campo de la linea usa como consulta, contra que indice de la tienda la compara, cuantos candidatos
deja y que funcion de codigo elige. Los indices de la tienda se calculan una vez, al subir el catalogo o la FAQ.

LOS VECTORES no se guardan en el repo: pesan decenas de megas. Se guardan los puntajes, que alcanzan para repetir los
numeros sin gasto. Si cambia una consulta o un documento, se recalculan; el 15-nov se recalcularon los del catalogo y
dieron diferencia cero contra los puntajes de la sesion anterior.

    python3 banco_pruebas/busquedas.py     # imprime el registro
"""

MODELO = "gemini-embedding-001"
CONSULTA = "RETRIEVAL_QUERY"
DOCUMENTO = "RETRIEVAL_DOCUMENT"

NEXOS = {
    "rubro y producto": {
        "archivo": "banco_pruebas/nexo_rubro.py",
        "consulta": "busqueda, lo que tradujo el modelo en la llamada 0",
        "indice": ["rubro: sus alias, `nexo_rubro.doc_rubro`; y lo que la tienda declara que no vende, "
                   "`no_vendidas.json`, como rubro sin productos, `nexo_rubro.indice_rubros`",
                   "modelo de la tienda: rubro con sus alias, marca, modelo y etiquetas, `nexo_rubro.doc_producto`"],
        "candidatos": {"rubros": 3, "productos": 5},
        "elige": "la primera palabra de la busqueda contra el nombre y el rubro de cada candidato; si solo esta en "
                 "etiquetas o alias, o no esta, es dudoso y lo confirma Jev entre los cinco candidatos con los alias de "
                 "su rubro, o ninguno; lo que no se vende gana solo si queda primero y la busqueda lo dice",
        "calibrado": "16-nov, `nexo_rubro.py --calibrar` y `--jev`: elige bien 74, 72, 73 y 106, rubro equivocado 1, "
                     "lo que no se vende 14 de 14; antes 71, 70, 71 y 104, 5 y 8",
        "puntajes": ["banco_pruebas/nexo_rubro_puntajes.json", "banco_pruebas/flujo_nuevo_puntajes.json",
                     "banco_pruebas/nexo_rubro_jev.jsonl"],
    },
    "destino": {
        "archivo": "banco_pruebas/flujo_nuevo.py, nexo_destino",
        "consulta": "destino, el lugar que marco el modelo",
        "indice": ["sin embeddings: el padron de lugares de produccion, `normal.lugares` y `fuente._cotizar`"],
        "candidatos": {},
        "elige": "el codigo de lugares",
        "puntajes": [],
    },
    "tema de la FAQ": {
        "archivo": "banco_pruebas/nexo_tema.py",
        "consulta": "fragmento, las palabras del cliente: en una pregunta de la tienda la busqueda queda vacia",
        "indice": ["cada alias de cada tema como documento suelto, pregunta contra pregunta; el puntaje del tema es el "
                   "de su alias mas parecido"],
        "candidatos": {"temas": 3},
        "elige": "palabra clave de la FAQ compartida, menos el vocabulario de productos; Jev confirma lo dudoso",
        "puntajes": ["banco_pruebas/nexo_tema_puntajes.json", "banco_pruebas/nexo_tema_dudoso.jsonl"],
    },
    "producto nombrado": {
        "archivo": "banco_pruebas/nexo_nombrado.py",
        "consulta": "busqueda",
        "indice": ["el mismo de rubro y producto, sin vectores nuevos: da el rubro",
                   "palabra exacta: marca, nombre de modelo y codigo del catalogo en ese rubro"],
        "candidatos": {"rubros": 1},
        "elige": "el rubro donde calzan mas palabras de identidad, con marca o codigo exacto, y los embeddings "
                 "desempatan; despues la identidad de produccion, `catalogo._identificar`: exists, ambiguous, not_found",
        "puntajes": ["banco_pruebas/flujo_nuevo_puntajes.json", "banco_pruebas/nexo_nombrado_puntajes.json"],
    },
    "condicion": {
        "archivo": "banco_pruebas/nexo_condicion.py",
        "consulta": "cada parte de la busqueda que el codigo no ato, con el rubro adelante: \"mouse: economico\"",
        "indice": ["cada campo del rubro elegido, su etiqueta de `specs_preguntables` y sus valores; y dos ordenes, "
                   "precio y peso, `nexo_condicion.docs_campo`"],
        "candidatos": {"campos": 3},
        "variante": "V2 segmento con rubro, documento por campo",
        "elige": "primero el codigo, sin modelo: el tope de plata; el numero con su unidad contra los campos que miden "
                 "en ella, si no hay ninguno no se ata; el valor de un campo con plural, genero y negacion; el campo de "
                 "si o no por su clave; el orden. Lo que queda lo confirma Jev entre los valores reales de los tres "
                 "campos, los ordenes, solo producto o ninguno, que es no se ata. Lo que vale para todo el rubro se "
                 "saca; lo atado sin ningun producto con stock es no hay",
        "calibrado": "16-nov, `nexo_condicion.py --calibrar` con Jev perfecto: V1, V2 y V3 dan 150 de 188 en las 140; "
                     "V2 con 3 candidatos, la elegida. La busqueda no es el cuello: el codigo solo da 144. V4, un "
                     "documento por valor, sin medir: la gratis se trabo",
        "puntajes": ["banco_pruebas/nexo_condicion_puntajes.json", "banco_pruebas/nexo_condicion_jev.jsonl"],
    },
}


if __name__ == "__main__":
    print(f"embeddings: {MODELO}, consultas {CONSULTA}, indices {DOCUMENTO}; un pedido por mensaje")
    for nombre, x in NEXOS.items():
        print(f"\n{nombre.upper()} · {x['archivo']}")
        print(f"  consulta    {x['consulta']}")
        for i in x["indice"]:
            print(f"  indice      {i}")
        if x["candidatos"]:
            print("  candidatos  " + ", ".join(f"{v} {k}" for k, v in x["candidatos"].items()))
        print(f"  elige       {x['elige']}")
        if x.get("calibrado"):
            print(f"  calibrado   {x['calibrado']}")
        for p in x["puntajes"]:
            print(f"  puntajes    {p}")
