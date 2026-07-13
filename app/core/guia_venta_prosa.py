"""
GUIA DE VENTA EN PROSA — el "desde donde contestar" del solver para las
preguntas de RAZONAMIENTO (si un producto sirve para un uso, cual conviene,
por que uno sale mas, comparaciones). Es fuente de verdad de CRITERIO, no de
dato: NO trae numeros, precios ni stock (eso sale siempre de las tools). El
solver la consulta con la tool `consultar_guia_venta` y razona desde aca, en
vez de improvisar un criterio.

Semilla acotada (Martin, 12-jul): para un cliente real esta guia se extiende
mucho mas y por familia de producto. El MECANISMO es el que importa; sumar
temas es cargar texto, no tocar codigo. Registro: argentino, voseo, criterio
de vendedor, cero dato duro.
"""
from difflib import get_close_matches

# Cada tema es criterio de venta en prosa, sin un solo numero.
GUIA_VENTA: dict[str, str] = {
    "mouse": (
        "Para uso de oficina y diario, un mouse optico comodo alcanza y sobra; "
        "no hace falta gastar de mas. Para gaming competitivo conviene mejor "
        "sensor, menor peso y buen agarre. Los inalambricos dan libertad pero "
        "dependen del receptor y la pila; para escritorio fijo el cable no "
        "molesta. Mano grande pide un cuerpo mas alto; mano chica, algo compacto."),
    "teclado": (
        "Membrana es silencioso, blando y economico, ideal para oficina y "
        "escribir horas sin molestar. Mecanico es mas durable y preciso; los "
        "switches suaves tipo red son comodos y de los mas silenciosos dentro "
        "de lo mecanico, buenos para tipear y para jugar. Para escribir todo el "
        "dia prioriza comodidad y bajo ruido; para gaming, respuesta y "
        "durabilidad. La estructura de aluminio suma resistencia."),
    "marcas": (
        "Genius es marca de entrada confiable, buena relacion precio-uso para lo "
        "basico. Logitech es un clasico de confianza para trabajo y uso diario, "
        "muy probado. Razer apunta a gaming de alto rendimiento, premium. Todas "
        "las que vendemos son originales con garantia oficial."),
    "gaming_setup": (
        "Un setup gamer que rinda sin gastar de mas prioriza un mouse con buen "
        "sensor y un teclado con respuesta pareja; se puede arrancar en gama "
        "media y subir despues. Mejor pocos componentes buenos que muchos "
        "flojos."),
    "durabilidad": (
        "La durabilidad depende del tipo y del uso: lo mecanico y las "
        "estructuras rigidas aguantan mas uso intenso que lo economico de "
        "plastico; para uso suave de oficina, casi cualquiera dura bien."),
    "compatibilidad": (
        "Mouse y teclados USB o inalambricos estandar andan en Windows, Mac y "
        "Linux sin drivers para lo basico; el software extra de macros suele ser "
        "solo Windows. Para tablet o TV depende de que el equipo acepte USB o "
        "Bluetooth; si la ficha no lo confirma, no lo garantices."),
    "notebook": (
        "Para estudio y oficina pesa mas la comodidad: buena pantalla, teclado "
        "agradable y que no queme el bolsillo; casi cualquier equipo moderno "
        "sobra para navegar y documentos. Para diseno, edicion o juegos manda "
        "la placa de video y la memoria; ahi conviene mirar la ficha y no la "
        "marca. Si el cliente duda entre dos, pregunta el uso principal antes "
        "de recomendar. El detalle de procesador, memoria y disco de cada "
        "modelo sale SIEMPRE de la ficha, no de memoria."),
    "memoria_ram": (
        "Una memoria no es universal: tiene que coincidir el tipo y la "
        "generacion que acepta el equipo, y el formato es distinto en notebook "
        "que en PC de escritorio (modulo corto versus largo). El criterio "
        "honesto: pedirle al cliente el modelo exacto de su equipo o mother, "
        "cruzarlo con el tipo y formato que dice la ficha del modulo, y si el "
        "dato del equipo del cliente no esta, decirle que lo confirme en el "
        "manual o con el fabricante antes de comprar. Jamas garantizar "
        "compatibilidad de memoria sin ese cruce."),
    "ssd_almacenamiento": (
        "Un disco solido interno mejora muchisimo un equipo lento, es el "
        "upgrade de mejor impacto. Hay formatos distintos: los de bahia clasica "
        "van en casi cualquier equipo con esa bahia, los de tarjeta chica "
        "necesitan que el mother o la notebook tengan ese zocalo, y de ese "
        "zocalo hay variantes; la ficha del disco dice el formato y la "
        "interfaz, y hay que cruzarlo con lo que acepta el equipo del cliente. "
        "Un disco externo USB en cambio anda practicamente en cualquier "
        "computadora moderna, y en TV o consola depende del formateo. Ante la "
        "duda del zocalo interno, confirmar antes de vender."),
    "componentes_pc": (
        "Armar o mejorar una PC cruza varias compatibilidades y ninguna se "
        "adivina: procesador y mother tienen que compartir zocalo y chipset, "
        "la memoria tiene que ser del tipo que el mother acepta, la placa de "
        "video necesita una fuente con potencia y conectores suficientes y "
        "lugar fisico en el gabinete, y el cooler tiene que corresponder al "
        "zocalo del procesador. El metodo de venta: pedir la lista de piezas "
        "que ya tiene el cliente, cruzar ficha contra ficha, y lo que la ficha "
        "no confirme se le dice honestamente que lo verifique con el "
        "fabricante. Vender un combo armado por nosotros con fichas cruzadas "
        "es mas seguro que piezas sueltas a ciegas."),
    "auriculares": (
        "Para musica y llamadas diarias, comodidad y microfono decente pesan "
        "mas que cualquier sigla. Para gaming importa el microfono y que sea "
        "comodo horas. Los de conector clasico andan en casi todo lo que tenga "
        "esa salida; los USB son para computadora; los Bluetooth dependen de "
        "que el otro equipo tenga Bluetooth. Para consolas conviene revisar la "
        "ficha porque no toda conexion anda en toda consola; si la ficha no "
        "nombra la consola del cliente, no lo garantices."),
    "monitor": (
        "Para oficina alcanza un panel comodo de tamano razonable; para juegos "
        "importa la fluidez y la respuesta; para diseno, el color. Revisar "
        "SIEMPRE que la entrada del monitor coincida con la salida de la "
        "computadora del cliente (las fichas de ambos lo dicen); existen "
        "adaptadores pero no los prometas si no los vendemos. La ficha manda "
        "sobre cualquier suposicion de conexiones."),
    "perifericos_conexion": (
        "Webcam, microfono y parlante USB andan en cualquier computadora "
        "moderna sin drivers para lo basico. Las impresoras con wifi imprimen "
        "desde el celular con la aplicacion del fabricante; las de solo cable "
        "son para computadora. Un router mejora la cobertura y el orden de la "
        "red del cliente, pero la velocidad maxima la pone su proveedor de "
        "internet, no el aparato: no prometas velocidades. Los cargadores "
        "tienen que respetar el conector y la potencia que pide el equipo del "
        "cliente; ante la duda, cruzar con la ficha o que lo confirme el "
        "fabricante."),
    "sillas_gamer": (
        "Una silla se elige por horas de uso y por cuerpo: para jornadas "
        "largas importan el apoyo lumbar y la regulacion. La ficha trae "
        "medidas y materiales reales; no prometas peso maximo ni medidas de "
        "memoria, salen de la ficha."),
    "streaming": (
        "Para arrancar a streamear o grabar clases alcanza un microfono USB "
        "decente y una webcam definida; la mejora mas notoria para la "
        "audiencia es el audio, antes que la camara. Un microfono dedicado "
        "siempre suena mejor que el integrado del equipo. Si piden asesoria "
        "fina de conexion con placas o mezcladoras que no vendemos, ser "
        "honesto con el limite."),
    "tablet": (
        "Para consumo (video, lectura, clases) una tablet de gama media va "
        "sobrada; para dibujar o trabajar conviene mirar ficha y accesorios. "
        "Que acepte teclado o lapiz depende del modelo: la ficha manda. No "
        "garantizar accesorios de terceros que no figuran en la ficha."),
}


# Palabras del cliente -> tema de la guia. Se consulta ANTES del match difuso
# (get_close_matches con temas parecidos devolvia cualquier cosa: 'ram' caia
# en 'streaming', 'router' en 'mouse').
_ALIAS: dict[str, str] = {
    "ram": "memoria_ram", "memoria": "memoria_ram", "sodimm": "memoria_ram",
    "dimm": "memoria_ram",
    "ssd": "ssd_almacenamiento", "disco": "ssd_almacenamiento",
    "almacenamiento": "ssd_almacenamiento", "nvme": "ssd_almacenamiento",
    "pendrive": "ssd_almacenamiento",
    "procesador": "componentes_pc", "micro": "componentes_pc",
    "cpu": "componentes_pc", "mother": "componentes_pc",
    "motherboard": "componentes_pc", "placa": "componentes_pc",
    "gpu": "componentes_pc", "fuente": "componentes_pc",
    "cooler": "componentes_pc", "gabinete": "componentes_pc",
    "socket": "componentes_pc", "zocalo": "componentes_pc",
    "auricular": "auriculares", "auriculares": "auriculares",
    "headset": "auriculares", "vincha": "auriculares",
    "monitor": "monitor", "pantalla": "monitor",
    "webcam": "perifericos_conexion", "camara": "perifericos_conexion",
    "microfono": "streaming", "mic": "streaming",
    "parlante": "perifericos_conexion", "parlantes": "perifericos_conexion",
    "impresora": "perifericos_conexion", "router": "perifericos_conexion",
    "wifi": "perifericos_conexion", "cargador": "perifericos_conexion",
    "silla": "sillas_gamer", "sillas": "sillas_gamer",
    "notebook": "notebook", "laptop": "notebook", "compu": "notebook",
    "tablet": "tablet",
}


def consultar_guia_venta(tema: str | None = None, **_) -> dict:
    """Devuelve el criterio de venta de un tema (o la lista de temas). Match
    tolerante: exacto, alias por palabra, aproximado y por palabra suelta."""
    if not tema:
        return {"temas": list(GUIA_VENTA)}
    t = str(tema).lower().strip()
    if t in GUIA_VENTA:
        return {"tema": t, "texto": GUIA_VENTA[t]}
    # Por palabra, en orden: tema literal o alias, lo primero que aparezca.
    # Cubre 'ram', 'compatibilidad de placa de video', 'sirve esta memoria
    # para mi notebook' (gana 'memoria', que aparece antes).
    for palabra in t.replace("/", " ").split():
        tema_p = palabra if palabra in GUIA_VENTA else _ALIAS.get(palabra)
        if tema_p:
            return {"tema": tema_p, "texto": GUIA_VENTA[tema_p]}
    m = get_close_matches(t, GUIA_VENTA.keys(), n=1, cutoff=0.6)
    if m:
        return {"tema": m[0], "texto": GUIA_VENTA[m[0]]}
    for k in GUIA_VENTA:
        if k in t or t in k:
            return {"tema": k, "texto": GUIA_VENTA[k]}
    return {"tema": None, "temas": list(GUIA_VENTA),
            "nota": "sin guia para ese tema; razona desde la ficha o se honesto"}


def tool_schema() -> dict:
    """Schema OpenAI de la tool, para sumarla al menu del solver."""
    return {
        "type": "function",
        "function": {
            "name": "consultar_guia_venta",
            "description": (
                "Guia de venta con CRITERIO (uso, comparativa, marcas, "
                "durabilidad, compatibilidad general). Usala para OPINAR, "
                "comparar o decir si un producto sirve para un uso. No trae "
                "numeros; el dato duro sale de las otras tools. Temas: "
                + ", ".join(GUIA_VENTA)),
            "parameters": {
                "type": "object",
                "properties": {"tema": {
                    "type": "string",
                    "description": "uno de: " + ", ".join(GUIA_VENTA)}},
                "required": ["tema"]}}}
