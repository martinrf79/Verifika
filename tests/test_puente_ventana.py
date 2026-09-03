"""EL INSTRUMENTO: que el numero de defectos por charla se pueda comparar.

POR QUE EXISTE ESTE ARCHIVO (3-sep-2026). `banco_pruebas/produccion.py` es el
unico lugar del repo que da un numero sobre las charlas REALES, y ese numero se
movio entre 0,8 y 0,20 en dos corridas seguidas sin que cambiara un solo
defecto: pedia una pagina de conversaciones, Firestore la devuelve por orden de
NOMBRE de documento -o sea siempre las mismas charlas viejas- y el denominador
de la division terminaba siendo `--limite`, que es una cantidad del PEDIDO y no
del mundo.

Un instrumento cuyo numero depende de cuanto le pedis no mide nada, y peor: da
la impresion de que algo mejoro o empeoro cuando lo unico que cambio fue el
argumento. Estos tests son la vara de la ventana que lo arregla. Corren
offline, sin credencial y sin tocar Firestore.

Cada test dice sobre cuantos casos corrio (regla 10.6 de CLAUDE.md).
"""
import banco_pruebas.produccion as PR

VENTANAS = [
    ("30m", 1800),
    ("18h", 64800),
    ("2d", 172800),
    ("45s", 45),
    ("  6H ", 21600),
    ("", 0),
    ("xx", 0),
    ("h", 0),
]


def test_la_ventana_se_lee_o_se_declara_invalida():
    """Cero significa SIN VENTANA, nunca "una ventana rara que interpreto".
    `main` corta con un mensaje antes de medir sobre un conjunto que no es el
    que se pidio."""
    for texto, esperado in VENTANAS:
        assert PR.ventana_a_segundos(texto) == esperado, texto


def test_cuantas_ventanas_se_probaron():
    assert len(VENTANAS) == 8, f"se probaron {len(VENTANAS)}, esperaba 8"


def test_el_reloj_de_firestore_se_lee_con_nanosegundos():
    """Firestore manda NANOsegundos y `fromisoformat` solo aguanta micro. Si
    esto devolviera cero, toda charla quedaria fuera de la ventana y la
    auditoria diria "no hay nada nuevo" para siempre, que es el peor de los
    fallos posibles: silencioso y con forma de buena noticia."""
    t = PR._cuando({"updateTime": "2026-09-03T03:16:53.747618234Z"})
    assert t > 1_700_000_000, t
    assert PR._cuando({}) == 0.0
    assert PR._cuando({"updateTime": "no es una fecha"}) == 0.0


def test_sin_ventana_el_informe_avisa_que_el_numero_no_se_compara():
    """La parte que evita que vuelva a pasar lo mismo por otro lado: si alguien
    corre sin `--desde`, el informe lo dice arriba de todo en vez de dejar un
    numero que parece comparable."""
    texto = PR.informe([("u1", ["hola"], [])], {})
    assert "SIN VENTANA" in texto, texto
    assert "NO se compara" in texto, texto


def test_con_ventana_el_informe_dice_cual_y_cuantas_entraron():
    """Un denominador sin su conjunto es media medicion."""
    texto = PR.informe([("u1", ["hola"], [])],
                       {"ventana_s": 64800, "vistas": 37, "usuario": ""})
    assert "ultimas 18 horas" in texto, texto
    assert "37 charlas" in texto, texto
    assert "entraron 1" in texto, texto
