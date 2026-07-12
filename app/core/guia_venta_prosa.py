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
}


def consultar_guia_venta(tema: str | None = None, **_) -> dict:
    """Devuelve el criterio de venta de un tema (o la lista de temas). Match
    tolerante: exacto, aproximado y por palabra suelta."""
    if not tema:
        return {"temas": list(GUIA_VENTA)}
    t = str(tema).lower().strip()
    if t in GUIA_VENTA:
        return {"tema": t, "texto": GUIA_VENTA[t]}
    m = get_close_matches(t, GUIA_VENTA.keys(), n=1, cutoff=0.4)
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
                    "description": ("mouse, teclado, marcas, gaming_setup, "
                                    "durabilidad o compatibilidad")}},
                "required": ["tema"]}}}
