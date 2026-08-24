"""EL PUNTO DE OFERTA — lo que el BOT tiene que proponer (FICHA 15).

POR QUE EXISTE ESTE ARCHIVO. Los diez tipos de punto del indice representan lo
que el CLIENTE pregunto: nacen de lo declarado y se cierran cuando la respuesta
llego al texto. Ninguno representa lo que el BOT debe PROPONER, y por eso un
turno podia contestar la ficha tecnica perfecta y no ofrecer cargar el producto:
cumplia la cobertura entera y no tenia nada que lo obligara a avanzar. Medido
sobre las charlas grabadas: 26 turnos rojos en avance, TODOS con el carrito en
cero de punta a punta, y tres charlas enteras sin un solo pedido.

LO QUE ESTE ARCHIVO DEFIENDE NO ES QUE LA OFERTA EXISTA: ES QUE NO SE VUELVA
INSISTENCIA. Un punto que obliga a ofrecer es facil de escribir y facil de
convertir en un bot que pregunta dos veces por mensaje, y eso vende MENOS que no
ofrecer nada. Los cuatro frenos se miden uno por uno:

  1. UNA CORTESIA INTERROGATIVA NO ES UNA OFERTA. Es la gemela exacta del
     candado que ya tiene la vara de venta para el cierre: si "¿te ayudo en algo
     mas?" contara como ofrecer, el punto saldria verde en todos lados y no
     mediria nada.
  2. LA AMBIGUEDAD MANDA. Con una herramienta que volvio ambigua el turno esta
     OBLIGADO a repreguntar, asi que la oferta ni se abre: cede y queda para el
     turno siguiente.
  3. NO SE OFRECE LO QUE EL PEDIDO YA TIENE.
  4. NO SE OFRECE ENCIMA DE UN CIERRE. Pedirle el nombre o la forma de pago ya
     ES el paso siguiente.

Y LA OFERTA NO NECESITA SIGNO DE PREGUNTA, que es lo que hace que todo esto
cierre: "Te lo cargo al pedido y te paso el total" propone sin gastar la unica
repregunta que el turno tiene permitida.

CORRE OFFLINE: sin modelo, sin clave, sin red.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core import indice_turno as IT  # noqa: E402

_MOUSE = {"herramienta": "buscar_productos",
          "pedido": {"descripcion": "mouse logitech"},
          "resultado": {"estado": "encontrado", "productos": [
              {"id": "MOU-001", "nombre": "Mouse Logitech M170 Negro",
               "precio": "$12.000"}]}}

_AMBIGUA = {"herramienta": "buscar_productos",
            "pedido": {"descripcion": "g pro x"},
            "resultado": {"estado": "ambiguo", "productos": [
                {"id": "AUR-010", "nombre": "Logitech G Pro X"},
                {"id": "AUR-011", "nombre": "Logitech G Pro X 2"}]}}

_CUENTA = {"herramienta": "armar_presupuesto",
           "pedido": {"items": [{"product_id": "MOU-001", "cantidad": 1}]},
           "resultado": {"estado": "ok", "total_ars": 12000, "detalle": [
               {"id": "MOU-001", "nombre": "Mouse Logitech M170 Negro",
                "cantidad": 1}]}}


# (que pasa, con que herramientas, con que texto, en que estado termina)
CASOS = [
    # ── SE ABRE Y NO SE OFRECIO: la casilla vacia, que es lo que frena ──
    ("la ficha tecnica perfecta que no ofrece nada",
     [_MOUSE], "El Logitech M170 es inalámbrico y tiene 1000 DPI.", ""),

    ("una cortesia interrogativa NO es ofrecer el paso siguiente",
     [_MOUSE], "El Logitech M170 es inalámbrico. ¿Te ayudo con algo más?", ""),

    ("otra cortesia, con la misma cara amable y el mismo cero adentro",
     [_MOUSE], "Ahí te paso los datos del M170. ¿Alguna otra consulta?", ""),

    ("la accion sin el producto tampoco: coordinar por mail no es cargar nada",
     [_MOUSE], "El Logitech M170 tiene 1000 DPI.\nCoordinamos por mail.", ""),

    # ── SE OFRECIO ─────────────────────────────────────────────────────
    ("ofrecer cargarlo, SIN preguntar, que es la forma que no gasta la "
     "repregunta del turno",
     [_MOUSE], "El Logitech M170 es inalámbrico. Te lo cargo al pedido y te "
     "paso el total.", "OFRECIDO"),

    ("ofrecer preguntando tambien vale, cuando el turno no pregunto otra cosa",
     [_MOUSE], "El M170 sale $12.000. ¿Te lo reservo?", "OFRECIDO"),

    ("la accion sobre el producto NOMBRADO, sin pronombre",
     [_MOUSE], "Puedo cotizar el Mouse Logitech M170 Negro ahora mismo.",
     "OFRECIDO"),

    # ── NO CORRESPONDE, con motivo tipado ──────────────────────────────
    ("el pedido ya lo tiene: ofrecerselo seria preguntarle si quiere lo que "
     "acaba de pedir",
     [_MOUSE, _CUENTA], "Total: $12.000", "NO_CORRESPONDE"),

    ("el turno esta cerrando: pedirle el nombre YA es el paso siguiente",
     [_MOUSE], "El M170 sale $12.000. ¿A nombre de quién lo emito?",
     "NO_CORRESPONDE"),
]


def test_cada_caso_termina_donde_tiene_que():
    """LOS NUEVE CASOS, uno por uno, con el estado en que termina el punto."""
    assert len(CASOS) == 9, f"se declararon 9 casos y hay {len(CASOS)}"
    fallan = []
    for nombre, llamadas, texto, esperado in CASOS:
        idx = IT.cobertura({"items": [{"que": "mouse", "cantidad": 1}]},
                           texto, "test", llamadas=llamadas)
        punto = next((p for p in idx["puntos"] if p["tipo"] == "oferta"), None)
        if punto is None:
            fallan.append(f"{nombre}: no se abrio el punto de oferta")
            continue
        if punto["estado"] != esperado:
            fallan.append(
                f"{nombre}: termino en '{punto['estado'] or 'SIN_ESTADO'}' y "
                f"tenia que terminar en '{esperado or 'SIN_ESTADO'}'")
    assert not fallan, "\n  ".join([""] + fallan)


def test_la_ambiguedad_manda_y_la_oferta_cede():
    """LA TRAMPA QUE MAS IMPORTA. Con una herramienta ambigua el turno esta
    obligado a repreguntar cual de los dos era; sumarle la oferta seria la
    segunda pregunta del mismo mensaje, o sea pedirle al cliente que administre
    una agenda. El punto NI SE ABRE: cede y queda para el turno siguiente.

    Y no se abre marcado `NO_CORRESPONDE`, que seria decir que se decidio no
    ofrecer: lo que pasa es otra cosa, la oferta todavia esta por hacerse."""
    idx = IT.cobertura({"items": [{"que": "g pro x", "cantidad": 1}]},
                       "Tengo dos G Pro X. ¿Cuál de los dos querés?",
                       "test", llamadas=[_AMBIGUA])
    assert not [p for p in idx["puntos"] if p["tipo"] == "oferta"], (
        "con ambigüedad la oferta no se abre")
    # Y EL TURNO SALE. Si la ambigüedad abriera el punto, la puerta frenaria
    # justo al turno que hizo lo correcto.
    assert IT.puede_salir(idx["puntos"])["puede"]


def test_sin_producto_certificado_no_hay_nada_que_ofrecer():
    """EL PUNTO LO ABRE EL CODIGO CON UN HECHO SUYO. Sin producto traido por una
    herramienta no hay nada concreto que proponer, y una oferta sin producto es
    la cortesia interrogativa que este archivo prohibe."""
    for llamadas in ([],
                     [{"herramienta": "consultar_temas", "pedido": {},
                       "resultado": {"estado": "ok", "temas": []}}],
                     [{"herramienta": "buscar_productos", "pedido": {},
                       "resultado": {"estado": "no_vendemos", "productos": []}}]):
        assert IT.punto_de_oferta(llamadas) is None, llamadas


def test_la_puerta_frena_el_turno_que_no_ofrecio_y_deja_salir_al_que_si():
    """LA MITAD 1 NO ES UN LOG. El punto sin estado frena igual que los otros
    seis tipos, y su prueba es por construccion: una herramienta certifico un
    producto que el pedido no tiene. Sin esto, el turno que contesta perfecto y
    no ofrece nada saldria tan verde como el que vende."""
    declarado = {"items": [{"que": "mouse", "cantidad": 1}]}
    mudo = IT.cobertura(declarado, "El Logitech M170 tiene 1000 DPI.", "t",
                        llamadas=[_MOUSE])
    puerta = IT.puede_salir(mudo["puntos"])
    assert not puerta["puede"]
    assert [p["id"] for p in puerta["omitidos"]] == ["oferta:1"]

    ofrece = IT.cobertura(declarado, "El Logitech M170 tiene 1000 DPI. Te lo "
                          "cargo al pedido.", "t", llamadas=[_MOUSE])
    assert IT.puede_salir(ofrece["puntos"])["puede"]


def test_nombrar_el_producto_no_lo_da_por_ofrecido():
    """LA OFERTA NO ANCLA, Y ESTA ES LA RAZON. Todos los demas puntos se dan por
    contestados cuando su producto certificado aparece en el mensaje; si la
    oferta usara esa misma regla, quedaria ofrecida apenas el bot nombre el
    equipo —que es exactamente el turno que no ofrece nada—."""
    idx = IT.cobertura({"items": [{"que": "mouse", "cantidad": 1}]},
                       "Tenemos el Mouse Logitech M170 Negro a $12.000.",
                       "t", llamadas=[_MOUSE])
    oferta = next(p for p in idx["puntos"] if p["tipo"] == "oferta")
    assert oferta["anclajes"] == []
    assert oferta["atendido"] is False
    # Y el item SI se da por contestado con el mismo texto: son dos varas
    # distintas sobre el mismo mensaje, y tienen que dar distinto.
    assert next(p for p in idx["puntos"] if p["id"] == "item:1")["atendido"]


def test_la_instruccion_pide_ofrecer_y_no_pide_preguntar():
    """LA MITAD 2, MEDIDA DEL LADO DEL CODIGO. La atadura es UNA linea que va
    solo en los turnos que tienen algo concreto que ofrecer, con el producto
    nombrado —"te falto algo, fijate" ya se midio dos veces en este repo y no
    mueve al modelo—, y con el candado contra la insistencia adentro."""
    idx = IT.cobertura({"items": [{"que": "mouse", "cantidad": 1}]},
                       "El Logitech M170 tiene 1000 DPI.", "t",
                       llamadas=[_MOUSE])
    linea = IT.instruccion(idx["faltan"])
    assert "Mouse Logitech M170 Negro" in linea, linea
    assert "sin sumarle otra pregunta" in linea, linea
    # NO ENTRA EN LA LISTA DEL CLIENTE. Ese encabezado dice "esto el cliente sí
    # lo pidió", y la oferta es lo contrario: es lo que el cliente NO pidió.
    assert "- proponerle el paso siguiente" not in linea, linea
    # Y CUANDO NO CORRESPONDE, NO SE PIDE NADA. Un turno que ya cerró no puede
    # recibir una instruccion de ofrecer: seria el interrogatorio.
    cerrando = IT.cobertura({"items": [{"que": "mouse", "cantidad": 1}]},
                            "El M170 sale $12.000. ¿A nombre de quién lo emito?",
                            "t", llamadas=[_MOUSE])
    assert "paso siguiente" not in IT.instruccion(cerrando["faltan"])


def test_cuanto_pesa_la_linea_de_oferta_queda_escrito():
    """CUANTO CRECE EL PROMPT, dicho en bytes y no en adjetivos.

    `_INSTRUCCION_DOS` NO SE TOCA: la atadura viaja por el mismo canal
    condicional que ya usa la cobertura, asi que el turno que no tiene nada que
    ofrecer pesa exactamente lo que pesaba. Este numero es el costo del turno
    que SI tiene algo que ofrecer, y queda afirmado para que una sesion futura
    no lo infle sin que nadie lo vea."""
    from app.core import hub_venta as HV

    idx = IT.cobertura({"items": [{"que": "mouse", "cantidad": 1}]},
                       "El Logitech M170 tiene 1000 DPI.", "t",
                       llamadas=[_MOUSE])
    linea = IT.instruccion(idx["faltan"])
    print(f"\n  la linea de oferta: {len(linea.encode('utf-8'))} bytes")
    print(f"  _INSTRUCCION_DOS:   {len(HV._INSTRUCCION_DOS.encode('utf-8'))} bytes")
    assert len(linea.encode("utf-8")) <= 260, (
        f"la atadura de UNA linea pesa {len(linea.encode('utf-8'))} bytes: "
        "dejo de ser una linea")
    # EL PROMPT FIJO NO SE MOVIO. Si algun dia la oferta se escribe adentro de
    # `_INSTRUCCION_DOS`, la paga cada llamada de cada turno de cada cliente, y
    # eso se decide a la vista, no de costado.
    assert "ofrec" not in HV._INSTRUCCION_DOS.lower()


def test_sobre_cuantos_casos_se_midio():
    """UN TEST DICE SOBRE CUANTOS CASOS PASO, no solo que paso. Sin esta
    afirmacion el archivo entero se pone verde midiendo cero, que es como el CI
    estuvo verde cinco dias sin correr un casete."""
    estados = {c[3] for c in CASOS}
    print(f"\n  el punto de oferta se midio sobre {len(CASOS)} turnos armados, "
          f"en {len(estados)} finales distintos")
    assert len(CASOS) == 9
    assert estados == {"", "OFRECIDO", "NO_CORRESPONDE"}
    # LOS DOS FINALES DE LA OFERTA Y NINGUN OTRO. Si el punto pudiera terminar
    # RESUELTO o NO_SE_SABE, se estaria colando por el vocabulario de los
    # puntos del cliente.
    assert set(IT.MOTIVOS_NO_CORRESPONDE) == {"ya_en_el_pedido", "cerrando"}
