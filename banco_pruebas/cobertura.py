"""COBERTURA DEL BUSCADOR — los 22 rubros y los 50 temas, dichos como cliente (23-oct-2026, opcion B de Martin).

Mensajes escritos a mano ANTES de correr, con lo correcto de cada uno. No usan las frases de `alias.json`, que son las
que ya conoce el buscador. Cada rubro va tres veces: simple, de razonamiento sin nombrar el rubro y con errores de
tipeo. Cada tema va dos veces. Veinte multipreguntas mezclan rubros y temas. Donde dos temas de la FAQ contestan lo mismo
se acepta cualquiera: va como un conjunto.

El modelo de produccion traduce y separa con el numero primero, la consigna A de `cuenta_preguntas.py`; el buscador de
hoy, `agente.ubicar`, busca sobre cada parte. Se compara contra buscar sobre el mensaje crudo entero.

    MARTIN_AUTORIZO_LA_PAGA=<fecha> TOPE_CORRIDA=0.10 python3 banco_pruebas/cobertura.py [--ver]
"""
import asyncio
import collections
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import cuenta_preguntas as CP  # noqa: E402  — arma el entorno y la llamada que traduce y separa
from banco_pruebas import libro_paga  # noqa: E402
from app.core import agente  # noqa: E402

TIENDA = "verifika_prod"
SEIS = 6
TOPE = float(os.environ.get("TOPE_CORRIDA", "0.10"))

# (id, mensaje, rubros, temas): cada tema es un conjunto de los que valen.
RUBROS = [
    ("almacenamiento externo", "Necesito un disco externo de 1 tera",
     "Quiero algo para hacer copia de las fotos de la familia y llevarlas a la casa de mi vieja",
     "tenes algun dsico extreno para guardar backup"),
    ("auriculares", "Busco auriculares inalambricos",
     "Algo para escuchar musica en el colectivo sin molestar a nadie",
     "quiero unos auricualres con microfno para jugar"),
    ("cargador", "Necesito un cargador para el celular",
     "Se me rompio lo que uso para enchufar el telefono a la pared, necesito otro que cargue rapido",
     "tenes cargadro rapido tipo c"),
    ("cooler", "Busco un cooler para el procesador",
     "Mi compu levanta mucha temperatura cuando juego y se apaga sola, que me recomendas para enfriarla",
     "quiero un coler para el cpu que no haga ruido"),
    ("fuente", "Necesito una fuente de 650W",
     "Voy a poner una placa de video nueva y me dijeron que lo que le da energia a la PC no va a alcanzar",
     "tenes fuetne de poder certificada"),
    ("gabinete", "Busco un gabinete para armar una PC",
     "Estoy armando la compu de cero y me falta la caja donde va todo adentro, que tenga vidrio al costado",
     "quiero un gabiente con ventiladores"),
    ("impresora", "Necesito una impresora",
     "Los chicos tienen que entregar trabajos en papel todas las semanas y no quiero ir mas a la fotocopiadora",
     "tenes impersora multifuncion con wifi"),
    ("memoria ram", "Quiero una memoria RAM de 16 GB",
     "La notebook anda lenta cuando abro muchas pestañas, me dijeron que le agregue mas memoria para que no se trabe",
     "necesito una memroia ddr4 de 8"),
    ("microfono", "Busco un microfono para streaming",
     "Hago podcast y la voz se escucha con eco y lejos, quiero algo que capte mejor lo que hablo",
     "tenes microfno usb"),
    ("monitor", "Necesito un monitor de 24 pulgadas",
     "Quiero una pantalla mas grande para trabajar con dos planillas al lado sin forzar la vista",
     "busco un monitro gamer de 144hz"),
    ("motherboard", "Busco una motherboard para Ryzen",
     "Cambie el procesador y me dicen que la placa donde va enchufado todo no es compatible, necesito otra",
     "tenes mother b550 o algo asi"),
    ("mouse", "Quiero un mouse inalambrico",
     "Lo que uso para mover la flechita en la pantalla ya no responde bien, necesito uno nuevo",
     "busco un maus gamer liviano"),
    ("notebook", "Busco una notebook para la facultad",
     "Necesito una compu que pueda llevar a la facultad en la mochila y que la bateria aguante todo el dia",
     "tenes notbook con 16 de ram"),
    ("parlante", "Busco un parlante bluetooth",
     "Quiero algo para poner musica fuerte en el patio cuando hacemos asado",
     "un parlnte portatil que aguante el agua"),
    ("placa de video", "Necesito una placa de video",
     "Los juegos nuevos me andan a pocos cuadros por segundo y quiero mejorar los graficos de la PC",
     "tenes plca de vido rtx"),
    ("procesador", "Busco un procesador Intel i5",
     "Quiero cambiar el cerebro de la PC por uno mas rapido para editar video",
     "necesito un porcesador ryzen 5"),
    ("router", "Necesito un router",
     "El wifi no llega al cuarto del fondo y se corta todo el tiempo cuando estamos todos conectados",
     "tenes ruter de doble banda"),
    ("silla gamer", "Quiero una silla gamer",
     "Paso muchas horas sentado frente a la compu y me duele la espalda, busco algo comodo para sentarme",
     "busco sila gamer reclinable"),
    ("ssd", "Busco un SSD de 500 GB",
     "La PC tarda mucho en prender y en abrir los programas, me dijeron que cambie el disco por uno de los rapidos",
     "tenes un sdd m2 de 1tb"),
    ("tablet", "Busco una tablet",
     "Quiero algo con pantalla tactil para que mi hijo vea dibujitos y haga la tarea, mas grande que un celular",
     "tenes tablte de 10 pulgadas"),
    ("teclado", "Quiero un teclado mecanico",
     "Escribo todo el dia y quiero algo para tipear mas comodo que lo que trae la notebook",
     "busco un teclaod inalambrico en español"),
    ("webcam", "Necesito una webcam",
     "Tengo reuniones por video y en la notebook me veo oscuro y borroso, quiero algo para que me vean bien",
     "tenes wecam full hd"),
]

TEMAS = [
    ({"ubicacion", "retiro_local"}, "¿Donde estan ubicados?", "¿Puedo pasar a ver los productos en persona antes de comprar?"),
    ({"horarios", "formas_contacto", "contacto_humano"}, "¿En que horario atienden?", "¿Hasta que hora me contestan un sabado?"),
    ({"formas_pago", "monedas_aceptadas"}, "¿Que formas de pago aceptan?", "¿Como te pago, aceptan Mercado Pago?"),
    ({"cuotas"}, "¿Tienen cuotas sin interes?", "¿Lo puedo pagar en varios meses con la Visa?"),
    ({"envios"}, "¿Hacen envios al interior?", "¿Me lo pueden mandar a Neuquen o tengo que buscarlo?"),
    ({"costo_envio"}, "¿Cuanto cuesta el envio?", "¿Cuanto me sale que me lo traigan a casa?"),
    ({"plazo_envio"}, "¿Cuanto tarda en llegar?", "Si pago hoy, ¿para cuando lo tengo en Cordoba?"),
    ({"garantia"}, "¿Que garantia tienen los productos?", "¿Y si se rompe al mes, me cubren?"),
    ({"devoluciones", "cambios"}, "¿Puedo devolver un producto?", "Si me arrepiento despues de comprarlo, ¿me lo toman de vuelta?"),
    ({"factura", "datos_fiscales"}, "¿Hacen factura A?", "Lo necesito para la empresa, ¿me dan comprobante para descontar el IVA?"),
    ({"descuento_transferencia", "promociones"}, "¿Hay descuento por transferencia?", "¿Me hacen un precio mejor si te pago por banco?"),
    ({"redes"}, "¿Tienen Instagram?", "¿Donde puedo ver mas fotos de lo que venden?"),
    ({"contacto_humano", "formas_contacto"}, "Quiero hablar con una persona", "Prefiero que me atienda alguien de carne y hueso"),
    ({"asesoramiento"}, "¿Me pueden asesorar antes de comprar?", "No se nada de computacion, ¿me ayudan a elegir?"),
    ({"reservas", "reposicion_stock"}, "¿Puedo reservar un producto sin stock?", "Si no lo tienen ahora, ¿me lo guardan dejando una seña?"),
    ({"marcas_originales"}, "¿Los productos son originales?", "¿No me van a vender una copia trucha?"),
    ({"usados"}, "¿Venden productos usados?", "¿Tienen algo reacondicionado mas barato?"),
    ({"precios_iva"}, "¿Los precios incluyen IVA?", "¿El precio que veo es el final o despues me suman impuestos?"),
    ({"defectuoso", "garantia_como_usar"}, "¿Que pasa si llega defectuoso?", "Si cuando lo abro no prende, ¿que hago?"),
    ({"envio_urgente"}, "¿Tienen envio express?", "Lo necesito para mañana sin falta en Capital, ¿se puede?"),
    ({"mayoristas"}, "¿Venden por mayor?", "Tengo un local y quiero comprar para revender, ¿me hacen precio?"),
    ({"formas_contacto", "contacto_humano", "horarios"}, "¿Por que medios los puedo contactar?", "¿Tienen mail o solo este chat?"),
    ({"envoltorio_regalo"}, "¿Lo envuelven para regalo?", "Es para el cumple de mi novia, ¿viene con moño?"),
    ({"contenido_caja"}, "¿Que trae la caja?", "¿Viene con el cable o lo tengo que comprar aparte?"),
    ({"origen_procedencia", "fabricacion"}, "¿Los productos son importados?", "¿De donde traen la mercaderia?"),
    ({"material_composicion"}, "¿De que material esta hecho?", "¿Es de plastico o de metal?"),
    ({"fabricacion", "origen_procedencia"}, "¿Donde se fabrica?", "¿Es hecho en China?"),
    ({"especificaciones"}, "¿Me pasas las especificaciones tecnicas?", "¿Cuales son las caracteristicas completas de ese modelo?"),
    ({"compatibilidad"}, "¿Es compatible con Mac?", "¿Me va a andar con la compu que ya tengo?"),
    ({"garantia_como_usar", "defectuoso", "garantia"}, "¿Como hago para usar la garantia?", "Se me rompio a los dos meses, ¿que pasos sigo para que me lo arreglen?"),
    ({"stock_disponibilidad", "reposicion_stock"}, "¿Tienen stock?", "¿Lo tienen disponible ahora o hay que esperar?"),
    ({"embalaje_envio"}, "¿Como lo embalan para el envio?", "Tengo miedo de que llegue golpeado en el correo"),
    ({"retiro_local", "ubicacion"}, "¿Puedo retirar en el local?", "¿Lo puedo pasar a buscar yo para no pagar envio?"),
    ({"reembolso", "devoluciones"}, "¿Como me devuelven la plata?", "Si lo devuelvo, ¿en cuantos dias me reintegran?"),
    ({"seguimiento_pedido"}, "¿Como sigo mi pedido?", "¿Me pasan el numero para ver por donde viene el paquete?"),
    ({"cancelacion_pedido"}, "Quiero cancelar mi pedido", "Me equivoque, ¿puedo anular la compra que hice ayer?"),
    ({"envio_exterior"}, "¿Envian a Uruguay?", "Vivo en Chile, ¿me lo pueden mandar?"),
    ({"confianza_seguridad", "verificacion_pagos"}, "¿Es seguro comprar aca?", "¿Como se que no es una estafa?"),
    ({"como_comprar"}, "¿Como compro?", "Nunca compre online, ¿cuales son los pasos para hacer el pedido?"),
    ({"pago_contra_entrega"}, "¿Puedo pagar cuando me llega?", "¿Se paga en efectivo al recibirlo?"),
    ({"monedas_aceptadas", "formas_pago"}, "¿Aceptan dolares?", "¿Puedo pagar con bitcoin?"),
    ({"datos_fiscales", "factura"}, "¿Me pasas tu CUIT para la factura?", "¿A que razon social tengo que hacer la transferencia?"),
    ({"cambios", "devoluciones"}, "¿Puedo cambiar el producto por otro?", "Me quedo chico el monitor, ¿lo cambio por uno mas grande?"),
    ({"promociones", "descuento_transferencia"}, "¿Tienen alguna promocion?", "¿Hay alguna oferta este mes?"),
    ({"teclado_mecanico_membrana"}, "¿Que diferencia hay entre teclado mecanico y de membrana?", "¿Vale la pena pagar mas por las teclas que hacen clic?"),
    ({"mouse_dpi"}, "¿Que es el DPI de un mouse?", "¿Que significa ese numero de sensibilidad que ponen en los mouse?"),
    ({"cambio_direccion"}, "Quiero cambiar la direccion de envio", "Me mude, ¿me lo pueden mandar a otra casa?"),
    ({"reposicion_stock", "reservas", "stock_disponibilidad"}, "¿Cuando vuelven a tener stock?", "¿Me avisan cuando les entre de nuevo?"),
    ({"soporte_configuracion", "asesoramiento"}, "¿Me ayudan a configurarlo?", "No se como instalarlo, ¿me dan una mano?"),
    ({"verificacion_pagos", "confianza_seguridad"}, "Ya te mande el comprobante, ¿lo despachan?", "Te pase la foto de la transferencia, ¿ya sale?"),
]

MEZCLA = [
    ("Necesito un disco externo y una memoria ram, ¿hacen envios a Salta y cuanto tarda?",
     {"almacenamiento externo", "memoria ram"}, [{"envios", "costo_envio"}, {"plazo_envio"}]),
    ("Quiero armar una compu: procesador, mother y gabinete. ¿Tienen cuotas sin interes?",
     {"procesador", "motherboard", "gabinete"}, [{"cuotas"}]),
    ("Mi compu se recalienta y la fuente hace ruido, necesito cambiar las dos cosas. ¿Los productos tienen garantia?",
     {"cooler", "fuente"}, [{"garantia"}]),
    ("Busco algo para que me escuchen bien en las reuniones y una camara. ¿Hacen factura A?",
     {"microfono", "webcam"}, [{"factura", "datos_fiscales"}]),
    ("Para la oficina: una impresora y dos monitores. ¿Venden por mayor?",
     {"impresora", "monitor"}, [{"mayoristas"}]),
    ("Quiero una notebook y un mouse inalambrico, ¿hay descuento pagando por transferencia?",
     {"notebook", "mouse"}, [{"descuento_transferencia", "promociones"}]),
    ("Para mi hijo una tablet y unos auriculares. ¿Lo envuelven para regalo?",
     {"tablet", "auriculares"}, [{"envoltorio_regalo"}]),
    ("El wifi no llega al fondo, necesito algo para eso y un cargador rapido. ¿Puedo pasar a retirarlo?",
     {"router", "cargador"}, [{"retiro_local", "ubicacion"}]),
    ("Quiero una silla comoda para jugar y un teclado mecanico. ¿Cuanto sale el envio a Rosario?",
     {"silla gamer", "teclado"}, [{"costo_envio", "envios"}]),
    ("Necesito una placa de video y un SSD, ¿son originales?",
     {"placa de video", "ssd"}, [{"marcas_originales"}]),
    ("Busco un parlante para el patio. ¿Puedo pagar cuando me llega?",
     {"parlante"}, [{"pago_contra_entrega"}]),
    ("Quiero un teclado y no se si me conviene mecanico o de membrana, ¿que diferencia hay?",
     {"teclado"}, [{"teclado_mecanico_membrana"}]),
    ("Necesito un mouse para diseño, ¿que es eso del DPI? Y ¿tienen stock?",
     {"mouse"}, [{"mouse_dpi"}, {"stock_disponibilidad", "reposicion_stock"}]),
    ("Compre una memoria la semana pasada y quiero cambiarla por una de 32. ¿Como hago?",
     {"memoria ram"}, [{"cambios", "devoluciones"}]),
    ("Me falta el gabinete y la fuente para terminar la PC. ¿Me ayudan a elegir?",
     {"gabinete", "fuente"}, [{"asesoramiento"}]),
    ("Quiero un monitor y una webcam, ¿los precios incluyen IVA?",
     {"monitor", "webcam"}, [{"precios_iva"}]),
    ("Busco un procesador nuevo, ¿es compatible con mi placa? ¿Lo tienen para mañana?",
     {"procesador"}, [{"compatibilidad"}, {"envio_urgente", "plazo_envio"}]),
    ("Necesito una impresora y cartuchos, ¿aceptan dolares?",
     {"impresora"}, [{"monedas_aceptadas", "formas_pago"}]),
    ("Quiero un cooler y un SSD, ¿envian a Uruguay?",
     {"cooler", "ssd"}, [{"envio_exterior"}]),
    ("Necesito una notebook, una mochila y un router. ¿Como sigo el pedido cuando lo despachan?",
     {"notebook", "router"}, [{"seguimiento_pedido"}]),
]


def casos() -> list:
    out = []
    for rub, *frases in RUBROS:
        for forma, f in zip(("simple", "razonamiento", "tipeo"), frases):
            out.append((f"R {rub} {forma}", f, {rub}, []))
    for i, (temas, *frases) in enumerate(TEMAS):
        for j, f in enumerate(frases):
            out.append((f"T {min(temas)} {j + 1}", f, set(), [temas]))
    for i, (f, rubros, temas) in enumerate(MEZCLA, 1):
        out.append((f"M {i}", f, rubros, temas))
    return out


def nota(rubros: set, temas: list, cand_r: list, cand_t: list) -> dict:
    return {"rubros": len(rubros), "rubro_en_6": sum(any(r in c for c in cand_r) for r in rubros),
            "rubro_1ro": sum(any(c[:1] == [r] for c in cand_r) for r in rubros),
            "temas": len(temas), "tema_en_6": sum(any(t & set(c) for c in cand_t) for t in temas),
            "tema_1ro": sum(any(set(c[:1]) & t for c in cand_t) for t in temas)}


def main() -> None:
    ver = "--ver" in sys.argv
    desde = libro_paga.gastado(libro_paga._hoy())
    total = {"partes": collections.Counter(), "crudo": collections.Counter()}
    por_clase = collections.defaultdict(collections.Counter)
    for cid, msg, rubros, temas in casos():
        if libro_paga.gastado(libro_paga._hoy()) - desde >= TOPE:
            print(f"TOPE de la corrida: {TOPE} dolares")
            break
        partes = asyncio.run(CP.contar(msg, "A")).get("partes") or [msg]
        for nombre, textos in (("partes", partes), ("crudo", [msg])):
            cr = [agente.ubicar(t, "rubros", TIENDA, SEIS) for t in textos]
            ct = [agente.ubicar(t, "temas", TIENDA, SEIS) for t in textos]
            n = nota(rubros, temas, cr, ct)
            total[nombre].update(n)
            if nombre == "partes":
                por_clase[cid.split()[0] + " " + cid.split()[-1] if cid[0] == "R" else cid[0]].update(n)
            if ver and nombre == "partes" and (n["rubro_en_6"] < n["rubros"] or n["tema_en_6"] < n["temas"]):
                print(f"--- {cid}: {msg}")
                for t, a, b in zip(textos, cr, ct):
                    print(f"    {t[:100]!r}\n      rubros {a}\n      temas  {b}")
    for nombre, t in total.items():
        print(f"\nBUSCADOR sobre {'las partes traducidas' if nombre == 'partes' else 'el mensaje crudo entero'}:")
        print(f"  rubro entre los seis {t['rubro_en_6']} de {t['rubros']}, primero {t['rubro_1ro']}")
        print(f"  tema entre los seis  {t['tema_en_6']} de {t['temas']}, primero {t['tema_1ro']}")
    print("\nPOR CLASE, sobre las partes:")
    for k, t in sorted(por_clase.items()):
        print(f"  {k:16} rubro {t['rubro_en_6']}/{t['rubros']} · tema {t['tema_en_6']}/{t['temas']}")
    print(f"\nGasto: {libro_paga.gastado(libro_paga._hoy()) - desde:.3f} dolares")


if __name__ == "__main__":
    main()
