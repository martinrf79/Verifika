"""
CONSTITUCION DEL SISTEMA — la regla madre y su tabla de articulos.

Es la UNICA fuente de reglas. La leen los dos lados del sistema: el prompt de la
capa de venta (para saber que puede y que no) y el gate por codigo (para saber
que gatear). Mezcla las dos caras: prohibiciones que no dejan alucinar y deberes
que empujan la venta. Cambiar una regla del sistema = cambiarla ACA, en un solo
lugar.

REGLA MADRE: el modelo es libre en la FORMA, nunca en el HECHO.

Codigo puro, sin LLM ni Firestore. Es configuracion viva, no logica.
"""

# ── Definicion oficial del sistema (cerrada con Martin, sesion 2026-06-03) ──
# Guardada en el codigo para que sea el norte contra el que se mide cada pieza.
DEFINICION_SISTEMA = """\
El sistema recibe el mensaje y un primer modelo, junto al codigo, SOLO lo
entiende y lo ubica en la etapa de venta, dejandolo en datos; NO elige la puerta.
El CODIGO enruta por suficiencia de evidencia hacia una de cuatro salidas:
responder, ofrecer opcion A o B, pedir que confirme a que se refiere, o decir que
lo consulta. Con la salida elegida, el codigo va a la fuente de verdad y resuelve
los hechos: los numeros desde la calculadora y las politicas desde la tabla de
FAQ, nunca de la cabeza del modelo. Recien entonces un segundo modelo redacta
libre y calido, como vendedor, segun la etapa, pero solo vistiendo de lenguaje
los hechos que el codigo ya le entrego firmados. Antes de salir todo cruza el
piso: un gate por codigo que controla por GRAVEDAD, durisimo en precio, stock,
compatibilidad y politica, donde no deja pasar afirmacion sin respaldo en la
fuente, y blando en lo blando, tono, color y opiniones que ya estan en el
catalogo. Si el gate caza un dato sin respaldo, autofix lo reescribe hasta dos
veces con el dato correcto antes de mandar nada; si la fuente no tiene el dato,
el sistema no inventa, dice que lo consulta. No puede alucinar en las fases de
RESOLVER HECHOS y de GATEAR, donde mandan el codigo y la fuente de verdad; es
libre para VENDER en la fase de REDACCION, donde el modelo solo le pone lenguaje
a lo que ya es verdad. Un error de interpretacion no puede terminar en
alucinacion: en el peor caso manda a confirmar, preguntar o consultar.\
"""

# ── Articulos. Prohibiciones (piso) + deberes (venta), en un solo lugar. ──
# Esta tabla es la fuente canonica. La leen los DOS lados del sistema:
#   - el PROMPT del Solver, con PROMPT_CONSTITUCION on (constitucion_como_prompt).
#   - el GATE por codigo, que enforcea las prohibiciones de alta gravedad:
#       art 1-3 (precio/stock/compatibilidad) -> app/core/verificador.py (plata)
#       art 4   (politicas mal narradas)       -> app/core/verificador_hechos.py
#       art 5   (servicios inventados)         -> app/core/verificador_servicios.py
#       art 6   (dia de entrega / plazo)       -> app/core/verificador_hechos.py
# Los deberes de venta (art 7-10) los empuja el prompt (Regla 9 + capa venta de
# la FAQ). Cambiar una regla del sistema = cambiarla ACA y, si es de gate, en su
# verificador. No duplicar el texto de la regla en otro lado.
ARTICULOS = [
    # Prohibiciones — las gatea el codigo, no se negocian.
    "Nunca afirmar un precio que no venga de la calculadora o del catalogo.",
    "Nunca afirmar stock que no venga del catalogo.",
    "Nunca afirmar compatibilidad sin respaldo en las specs del catalogo.",
    "Nunca afirmar una politica (envio, pago, garantia, plazo, devolucion, "
    "retiro) que no este en la tabla de FAQ.",
    "Nunca prometer un servicio o capacidad que la tienda no ofrece.",
    "Nunca prometer un dia exacto de entrega; el plazo se cita en dias habiles "
    "tal cual la fuente.",
    # Deberes — empujan la venta, los habilita el piso firme.
    "Siempre intentar ayudar con lo que SI existe en la fuente.",
    "Siempre que haya oportunidad, avanzar la venta hacia el cierre.",
    "Ante ambiguedad, preguntar o confirmar; nunca adivinar el dato.",
    "Si la fuente no tiene el dato, decir que se consulta; nunca inventar.",
]

# ── Gravedad. Cuanta prueba necesita cada clase de afirmacion. ──
# ALTA: el gate es durisimo, sin respaldo NO pasa.
# BAJA: mano blanda, es tono o algo ya presente en el catalogo.
GRAVEDAD_ALTA = (
    "precio", "stock", "compatibilidad", "envio", "pago", "garantia",
    "plazo", "politica", "servicio",
)
GRAVEDAD_BAJA = ("color", "opinion", "tono", "descripcion", "uso_recomendado")


def gravedad_de(clase: str) -> str:
    """Devuelve 'alta' o 'baja' para una clase de afirmacion. Ante la duda, alta:
    es mas seguro tratar lo desconocido como grave que dejarlo pasar."""
    c = (clase or "").strip().lower()
    if c in GRAVEDAD_BAJA:
        return "baja"
    return "alta"


def es_alta_gravedad(clase: str) -> bool:
    return gravedad_de(clase) == "alta"


def constitucion_como_prompt() -> str:
    """Renderiza los articulos como bloque de prompt para la capa de venta, asi
    el modelo lee EXACTAMENTE las mismas reglas que despues gatea el codigo."""
    lineas = "\n".join(f"{i + 1}. {a}" for i, a in enumerate(ARTICULOS))
    return "CONSTITUCION (reglas que mandan sobre todo):\n" + lineas
