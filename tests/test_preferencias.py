"""
Preferencia del cliente que persiste como decision — arreglos B y C.

El cliente dice "lo mas barato" una vez y el bot tiene que tratarlo como una
DECISION vigente: no repreguntar modelo ni color, elegir el mas barato con stock
solo. En la charla real de WhatsApp lo dijo tres veces y el bot seguia
preguntando; eso lo hizo renegar.

El dato tiene que VIAJAR por el flujo determinista: se detecta con codigo, se
persiste en el estado y se inyecta al solver, igual que los productos vistos o el
envio. Estos tests fijan ese contrato sobre las funciones puras del estado.

Estan escritos para el comportamiento CORRECTO, asi que HOY fallan (rojo). Cada
uno se apaga cuando se cablea su parte.
"""
from app.core import estado_venta


# ── B: el criterio se DETECTA determinista, sin depender del LLM ──────────────

def test_b_detecta_mas_barato():
    """'Los mas baratos si son buenos' lleva un criterio claro: el mas barato.
    Se detecta con codigo, no con el modelo, asi el dato es determinista."""
    assert estado_venta.detectar_criterio(
        "Los mas baratos si son buenos pasame precio") == "más barato"


def test_b_detecta_variantes_de_barato():
    """Distintas formas de pedir lo mas barato caen todas en el mismo criterio."""
    for msg in ("dame lo mas economico", "el teclado mas barato",
                "algo baratito", "la notebook mas barata"):
        assert estado_venta.detectar_criterio(msg) == "más barato", msg


def test_b_sin_criterio_devuelve_vacio():
    """Un mensaje sin criterio de precio no inventa uno."""
    assert estado_venta.detectar_criterio("dame el teclado gamer rojo") == ""


# ── B: el criterio PERSISTE en el estado y VIAJA al solver ────────────────────

def test_b_estado_persiste_criterio():
    """construir_estado levanta el criterio guardado en la conversacion, asi
    sobrevive entre turnos aunque el cliente no lo repita."""
    estado = estado_venta.construir_estado({"criterio_cliente": "más barato"}, None)
    assert estado.get("criterio") == "más barato"


def test_b_bloque_inyecta_criterio_y_prohibe_repreguntar():
    """El bloque del solver tiene que llevar el criterio Y la orden de no volver a
    preguntarlo: es lo que evita que repregunte modelo y color."""
    bloque = estado_venta.bloque_para_solver({"criterio": "más barato"})
    assert "más barato" in bloque
    assert "NO" in bloque  # instruccion explicita de no repreguntar
