"""
LOCK DE LA CHARLA REAL DEL 24-jul 16:42 (leida de los logs y de Firestore).

    Cliente: Decime precio de tablet samsung
    Bot:     ... no trabajamos Samsung -> Tablet Lenovo Tab M10 - $223.000
    Cliente: Cuanta memoria ram y espacio de disco tiene
    Bot:     "Si querés, pasame el modelo exacto de tu notebook o PC y te
              confirmo cuál de estas opciones te sirve..."

La repregunta era sobre la TABLET que el bot acababa de ofrecer y el bot
contesto sobre MODULOS DE MEMORIA RAM. El interprete habia resuelto bien
(producto_resuelto = Tablet Lenovo Tab M10); se rompio despues, en tres
costuras del generador:

1. El UNIVERSO se armaba tambien por palabra suelta del mensaje: "memoria ram"
   es una categoria del catalogo, asi que los modulos de RAM entraban al enum.
2. El PROMPT del solver no llevaba ni el resumen de la charla, ni los productos
   ya mostrados, ni el FOCO que el interprete ya habia resuelto: la repregunta
   le llegaba huerfana.
3. La PODA de prosa descartaba el fragmento entero por tener un digito, asi que
   la respuesta de spec ("128GB") se perdia en silencio y quedaba solo el cierre.

Estos tests son la red para que no vuelva.
"""
import pytest

from app.core.generador_v2 import (_campo_ficha, _poda_prosa, _prompt,
                                   _specs_faltantes, universo_productos)

# El interprete de ese turno, tal cual quedo en el log (evento interpretador_ok)
INTERP_REPREGUNTA = {
    "intencion": "pregunta_especifica",
    "producto_resuelto": "Tablet Lenovo Tab M10 Plata",
    "productos_consultados": [{"producto": "Tablet Lenovo Tab M10 Plata",
                               "consulta": "ficha"}],
    "pedido": [],
    "solicitud_nueva": [],
    "categorias": ["tablet"],
}
MSG = "Cuanta memoria ram y espacio de disco tiene"


# ── 1. UNIVERSO: el contexto manda sobre las palabras del mensaje ────────────

def test_repregunta_de_spec_no_mete_la_categoria_que_nombra(firestore_doble):
    estado = {"productos_vistos": [{"id": "TAB0020",
                                    "nombre": "Tablet Lenovo Tab M10 Plata",
                                    "precio": 223000}]}
    u = universo_productos(MSG, estado, "verifika_prod", INTERP_REPREGUNTA)
    cats = {str(p.get("categoria", "")).lower() for p in u}
    assert "memoria ram" not in cats, (
        "la repregunta por la tablet metio modulos de RAM al enum")
    assert any(p["id"] == "TAB0020" for p in u), "se perdio la tablet en foco"


def test_si_pide_categoria_nueva_el_universo_igual_la_trae(firestore_doble):
    # disparo mutuamente excluyente: con solicitud_nueva SI se abre el universo.
    interp = {**INTERP_REPREGUNTA,
              "solicitud_nueva": [{"categoria": "memoria ram", "cantidad": 1,
                                   "criterio": None}]}
    u = universo_productos("y aparte mostrame memorias ram", {},
                           "verifika_prod", interp)
    assert any("memoria ram" in str(p.get("categoria", "")).lower() for p in u)


def test_sin_producto_en_foco_sigue_valiendo_la_palabra_del_mensaje(firestore_doble):
    u = universo_productos("tenes memoria ram?", {}, "verifika_prod", {})
    assert any("memoria ram" in str(p.get("categoria", "")).lower() for p in u)


# ── 2. PROMPT: la charla entera llega al solver ──────────────────────────────

def test_el_prompt_lleva_foco_mostrados_y_resumen(firestore_doble):
    estado = {"productos_vistos": [{"id": "TAB0020",
                                    "nombre": "Tablet Lenovo Tab M10 Plata"}],
              "resumen_charla": "El cliente pregunto por una tablet Samsung."}
    p = _prompt(MSG, [{"role": "user", "content": "Decime precio de tablet samsung"}],
                [{"id": "TAB0020", "nombre": "Tablet Lenovo Tab M10 Plata",
                  "precio_ars": 223000, "stock": 18}],
                ["costo_envio"], estado, interp=INTERP_REPREGUNTA)
    assert "FOCO DEL MENSAJE" in p
    assert "Tablet Lenovo Tab M10 Plata" in p
    assert "YA le mostraste" in p
    assert "pregunto por una tablet Samsung" in p


def test_el_prompt_sin_interprete_no_rompe(firestore_doble):
    p = _prompt("hola", [], [], ["costo_envio"], {})
    assert "FOCO DEL MENSAJE" not in p and "Mensaje del cliente" in p


# ── 3. PODA: la spec sobrevive, la plata no ─────────────────────────────────

@pytest.mark.parametrize("texto", [
    "Tiene 128GB de almacenamiento y la garantia es de 12 meses.",
    "Te llevas 2 unidades y entran en la misma caja.",
])
def test_la_prosa_con_numero_chico_sobrevive(texto):
    assert _poda_prosa(texto) == texto


@pytest.mark.parametrize("texto", [
    "Sale $223.000 con envio incluido.",
    "Te queda en 223000 pesos.",
    "Con transferencia tenes 10% de descuento.",
    "Son como 220 mil en total.",
])
def test_la_prosa_con_plata_se_poda(texto):
    assert _poda_prosa(texto) == ""


# ── 4. FICHA: puede contestar una spec desde la fuente ──────────────────────

def test_la_ficha_contesta_almacenamiento_y_medidas():
    prod = {"caracteristicas_extra": "128GB, 128GB", "peso_gramos": "344",
            "dimensiones": "17.0x16.2x0.7 cm",
            "contenido_caja": "Tablet, cargador, cable",
            "uso_recomendado": "Multimedia y estudio"}
    assert _campo_ficha(prod, "caracteristicas") == "Características: 128GB"
    assert "344" in _campo_ficha(prod, "medidas")
    assert "cargador" in _campo_ficha(prod, "contenido_caja")
    assert "Multimedia" in _campo_ficha(prod, "uso")


# ── 5. HONESTIDAD: la RAM no figura, el disco si ────────────────────────────

def test_ram_ausente_de_la_ficha_sale_honesta_y_el_disco_no():
    prod = {"nombre": "Tablet Lenovo Tab M10 Plata",
            "descripcion": ("Tablet Lenovo Tab M10, color Plata. 128GB. "
                            "peso 344g. Garantia oficial 12 meses."),
            "caracteristicas_extra": "128GB"}
    etiquetas = [e for e, _rx in _specs_faltantes(MSG, prod)]
    assert "la memoria RAM" in etiquetas, "la RAM no figura y hay que decirlo"
    assert "el almacenamiento" not in etiquetas, (
        "el 128GB SI esta en la ficha: no se puede decir que no lo especifica")
