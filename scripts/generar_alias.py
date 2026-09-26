"""GENERAR ALIAS — como nombra la gente cada cosa de la tienda (26-sep-2026).

Corre UNA VEZ por tienda, al cargarla, y no en cada turno. Le pide al modelo
las formas en que un cliente argentino nombra cada rubro, cada tema de la casa
y cada campo del catalogo: "el bicho del wifi" es router, "que pese poco" es
peso_gramos. El resultado queda en `data/clientes/<tienda>/alias.json`, al lado
del catalogo, y lo lee `app/core/agente.py` para ubicar las palabras que el
modelo traduce.

Es la idea de "Contextual Retrieval" de Anthropic aplicada al indice: el modelo
enriquece la fuente una vez y la busqueda queda simple, determinista y
verificable, sin un modelo ni un vector en cada consulta.

Los nombres salen de la fuente viva —rubros del catalogo, temas de la FAQ,
campos filtrables—, asi que una tienda nueva trae los suyos sin tocar codigo.

  BANCO_CLAVE_PAGA=true python3 scripts/generar_alias.py [tienda]
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PEDIDO = """Sos experto en como hablan los clientes argentinos cuando le escriben a una tienda online de tecnologia por WhatsApp.
Te doy una lista de {que}. Para CADA uno, escribi entre 5 y 12 formas en que un cliente lo nombraria: sinonimos, jerga, errores de tipeo frecuentes, descripciones ("el aparato con teclas"), marcas genericas usadas como nombre, y frases de uso ("para escuchar musica en el bondi").
Todo en minusculas y sin tildes. No repitas el nombre original. No inventes productos ni marcas especificas.
Devolve SOLO JSON: {{"<nombre>": ["alias", ...], ...}} con EXACTAMENTE estos nombres como claves:
{lista}"""


def _pedir(cli, modelo, que, nombres):
    r = cli.chat.completions.create(
        model=modelo, temperature=0.2,
        messages=[{"role": "user", "content": PEDIDO.format(que=que, lista=json.dumps(nombres, ensure_ascii=False))}])
    texto = r.choices[0].message.content or ""
    obj = json.loads(texto[texto.index("{"):texto.rindex("}") + 1])
    return {n: sorted({str(a).strip().lower() for a in (obj.get(n) or []) if str(a).strip()})
            for n in nombres}


def main():
    tienda = sys.argv[1] if len(sys.argv) > 1 else "verifika_prod"
    base = f"data/clientes/{tienda}/"
    from banco_pruebas import clon_produccion as C
    C.preparar_entorno()
    C.instalar()
    from app.core.filtros_catalogo import campos_filtrables
    from app.core.llm_reintento import _cliente, _modelo
    rubros = sorted({p["categoria"] for p in csv.DictReader(open(base + "productos.csv", encoding="utf-8"))})
    faq = json.load(open(base + "faq.json", encoding="utf-8"))
    temas = [f["tema"] for f in faq]
    campos = sorted(campos_filtrables(tienda))
    cli, modelo = _cliente(), _modelo()
    salida = {
        "_que_es": "Como nombran los clientes cada rubro, tema y campo. Lo genera scripts/generar_alias.py "
                   "con el modelo, una vez por tienda: no se edita a mano.",
        "rubros": _pedir(cli, modelo, "rubros de productos de la tienda", rubros),
        "temas": {},
        "campos": _pedir(cli, modelo, "campos (atributos) de los productos del catalogo; pensa en como el "
                                      "cliente pide ese atributo, por ejemplo 'que pese poco' para peso_gramos",
                         campos),
    }
    for i in range(0, len(temas), 25):  # de a tandas: una lista larga se corta
        salida["temas"].update(_pedir(cli, modelo, "temas de politicas y preguntas frecuentes de la tienda; "
                                                   "pensa en como pregunta el cliente, por ejemplo 'si viene "
                                                   "fallado que hago' para defectuoso", temas[i:i + 25]))
    with open(base + "alias.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1, sort_keys=False)
    vacios = [k for g in ("rubros", "temas", "campos") for k, v in salida[g].items() if not v]
    print(f"{len(rubros)} rubros, {len(temas)} temas, {len(campos)} campos -> {base}alias.json"
          + (f"  SIN ALIAS: {vacios}" if vacios else ""))


if __name__ == "__main__":
    main()
