"""
Regresion del verificador determinista, la linea cero anti-alucinacion de plata.

Cubre tres errores confirmados. Estos tests estan escritos para el comportamiento
CORRECTO, asi que HOY fallan (rojo). Cada uno se apaga cuando se arregla su error.

  E1  El total de un pedido con varios envios distintos no se deriva como suma:
      _totales_derivables trata los envios como alternativas, nunca los suma. Un
      total que se come un envio no se distingue de uno valido.
  E2  Un numero de plata sin formato (sin puntos, sin signo, sin 'pesos') esquiva
      el verificador entero: no se cuenta como monto y pasa sin control.
  E7  Cualquier numero suelto en la prosa de una FAQ entra al pool de verdad y
      blanquea cualquier precio alucinado que coincida con el.
"""
from app.core import verificador


def test_e1_total_multienvio_se_deriva_como_suma():
    """E1: con dos envios distintos, el gran total que suma AMBOS tiene que ser
    derivable del PROOF. Hoy no lo es (solo deriva subtotal + cada envio suelto)."""
    proof = {
        "tipo": "calculo_total_fijo",
        "subtotal_productos": 100000,
        "operandos_productos": [{"id": "A", "monto": 100000}],
        "operandos_extras": [
            {"faq_tema": "costo_envio", "concepto": "env_cordoba",
             "modalidad": "fijo", "monto": 8000},
            {"faq_tema": "costo_envio", "concepto": "env_caba",
             "modalidad": "fijo", "monto": 5000},
        ],
        "resultado": 113000,
    }
    derivables = verificador._totales_derivables(proof)
    assert 113000 in derivables, (
        "El total con los dos envios (100000+8000+5000) debe ser derivable; "
        "hoy los envios se tratan como alternativas y no se suman.")


def test_e1_total_que_come_un_envio_se_bloquea():
    """E1: un total al que le falta un envio no debe validar como correcto."""
    proof = {
        "tipo": "calculo_total_fijo",
        "subtotal_productos": 100000,
        "operandos_productos": [{"id": "A", "monto": 100000}],
        "operandos_extras": [
            {"faq_tema": "costo_envio", "concepto": "env_cordoba",
             "modalidad": "fijo", "monto": 8000},
            {"faq_tema": "costo_envio", "concepto": "env_caba",
             "modalidad": "fijo", "monto": 5000},
        ],
        "resultado": 113000,
    }
    ev = [{"tipo": "proof", "proof": proof}]
    # 108000 = subtotal + solo el envio de cordoba, se olvida el de CABA.
    r = verificador.verificar_respuesta("El total final es $108.000", ev)
    assert not r["ok"], (
        "Un total que se come un envio no debe pasar como valido.")


def test_e2_monto_sin_formato_se_verifica():
    """E2: un precio alucinado escrito sin puntos ni signo igual tiene que
    verificarse y bloquearse, no esquivar el control."""
    ev = [{"tipo": "producto", "nombre": "Mouse Gamer", "precio_ars": 45000}]
    r = verificador.verificar_respuesta("El combo te sale 999999 en total", ev)
    assert not r["ok"], (
        "999999 es un precio sin respaldo; sin formato hoy se cuela sin control.")


def test_e7_numero_de_prosa_faq_no_respalda_precio():
    """E7: un numero que solo aparece en el texto libre de una FAQ no debe servir
    para blanquear un precio de producto alucinado."""
    ev = [{"tipo": "faq",
           "respuesta": "Compras mayores a 150000 tienen envio gratis."}]
    r = verificador.verificar_respuesta("Ese monitor sale $150.000", ev)
    assert not r["ok"], (
        "150000 viene de la prosa de la FAQ, no es un precio de catalogo; "
        "no debe respaldar un precio de producto.")
