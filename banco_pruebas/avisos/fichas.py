"""PASO 2: LAS FICHAS — los nueve tipos de respuesta de un e-commerce, cada uno con sus casillas, de donde sale cada una, y
cuando va y cuando no frente al tipo con que se confunde. Salen de las casillas de la ficha 10 y de los comandos del
contrato 2, con lo que corrigieron en sus rondas. Reemplazan a LOS COMANDOS de la consigna de V3; el resto de V3 queda
igual: pistas, esquema, avisos y tercera vuelta.

  V4  las fichas nuestras.
  V5  las fichas reescritas por Gemini con sus palabras, `fichas_gemini.txt`.
"""
import os
import re

import comandos as Cm
import variante3 as V3

AQUI = os.path.dirname(os.path.abspath(__file__))

FICHAS = """LOS NUEVE TIPOS DE PEDIDO. Cada cosa que pide el cliente es de UN tipo, y cada tipo es un comando con sus casillas.
Las casillas se llenan con las palabras del cliente, o con un numero de la LIBRETA si senala algo de la charla.

1. PRODUCTO producto="" quiere_saber="" color="" afirma=""
   Un modelo concreto que el cliente nombra o senala. producto: lo que dijo, o "M-2"; si lo que senala puede ser varios
   y no dice cual, la lista "[M-1, M-2]" y el codigo pregunta. quiere_saber: precio si no dice otra cosa, stock, o el
   dato que pide —garantia, peso, conexion—. afirma: lo que da por cierto del producto.
   VA: "cuanto sale el K120", "y ese es inalambrico?", "el G305 tiene garantia?": la garantia de un producto es un dato
   suyo, no una regla de la tienda.
   NO VA: si pide un tipo de producto sin modelo, es BUSCAR.
   ELEGIR ENTRE DOS POR UN DATO, "dame el que sea inalambrico": un PRODUCTO por cada uno con ese dato, y un AGREGAR por
   cada uno con si="n:si" del suyo.

2. BUSCAR rubro="" cantidad="" orden="" condiciones="" entre_lo_mostrado="si"
   Productos sin modelo concreto, uno por rubro. rubro de la lista RUBROS. cantidad: cuantos articulos distintos.
   orden: "mas barato" —economico, barato, de acuerdo a la crisis—, "mas caro" —lo mejor—, "mas <dato>" —mas potente,
   mas liviano— o "nada". condiciones en palabras, separadas por ";": marca, color, un dato del rubro, precio por unidad,
   "que no sea X". Lo que exige un equipo suyo, "que aguante mi fuente de 550 W", es una condicion de la busqueda.
   Las EXCLUSIONES VIGENTES de la libreta van en cada busqueda nueva, y lo que el cliente suelta, "ya no importa la
   marca", se saca de las condiciones.
   entre_lo_mostrado: SOLO si elige dentro de lo ya mostrado, "de esos", "cual de todos". "Otras opciones", "alguno
   mas", "y alguno mecanico" piden ver mas: no es entre lo mostrado.
   NO VA: si nombra un modelo, es PRODUCTO.

3. ENVIO destino=""
   Cotizar el envio a UN lugar. destino: del mensaje, o la localidad del CLIENTE en la libreta si dice "a casa", "a mi
   ciudad" o "con envio" sin lugar. Dos lugares, dos ENVIO. Si corrige el lugar y no hay pedido, es un ENVIO al nuevo.
   NO VA: la regla general, "hacen envios a todo el pais?", "es gratis el envio?", es POLITICA.

4. CUENTA tope="" si_pasa="" reparto=""
   Sumar: "cuanto es", "cuanto sale todo", un presupuesto, "cuanto me sale con envio". tope: un monto del total.
   si_pasa: lo que saca si el total pasa el tope. reparto: "medio porcentaje; medio porcentaje", sin medio "sin decir".
   "El G203 con envio": PRODUCTO, ENVIO y CUENTA. Un "si" a "¿Lo dejo así?" que no cambia nada es CUENTA con
   responde="R-n": muestra el total.
   NO VA: el precio de un solo producto, sin envio ni suma, es PRODUCTO.

5. POLITICA tema="" afirma=""
   Una regla de la tienda que pregunta: factura, cuotas, medios de pago, devoluciones, promociones, horarios, envios en
   general. tema de la lista TEMAS. afirma: lo que da por cierto, "tienen 50 off".
   NO VA: un dato de un producto, el costo de un envio a un lugar, una cuenta.

6. COMPATIBILIDAD producto="" con="" falta_modelo="si"
   Si un producto concreto anda con algo. con: el equipo o producto. falta_modelo: si es un equipo suyo sin modelo, "mi
   notebook". "Si no le sirve, que otra hay": COMPATIBILIDAD y un BUSCAR con si="n:no".
   NO VA: buscar un producto que cumpla un requisito tecnico es BUSCAR con esa condicion.

7. COMPRA: AGREGAR producto="" cantidad="" color="" destino="" | SACAR renglon="L-1" | CAMBIAR renglon="L-1" y lo que
   cambia | CONFIRMAR renglon="L-2" | ACEPTAR renglon="L-2" | TOTAL cantidad="" | REEMPLAZAR
   AGREGAR: lo que decide llevar —lo compra, se lo lleva, "mandame", "anotame", "llevo dos"—: un modelo, un "M-2", un
   rubro o "los otros". Un renglon por producto y destino. Pedir ver, mostrar o el precio es consulta, no compra.
   SACAR, CAMBIAR, CONFIRMAR, ACEPTAR, TOTAL y REEMPLAZAR son cambios a un pedido que YA esta en la LIBRETA, BORRADOR:
   si no hay borrador, es otro tipo. CONFIRMAR si dice que si a lo que falta confirmar, ACEPTAR si acepta lo SUPUESTO,
   TOTAL si dice cuantos son, REEMPLAZAR si rehace el pedido entero y los AGREGAR son como queda.

8. EXPLICAR pregunta=""
   Saber general de tecnologia, no de la tienda: "que conviene, cable o inalambrico?".

9. OTRO que=""
   Lo que no pide nada al codigo: saludo, dato —lo que dice de si mismo, que va tambien en CLIENTE—, corrige —lo que
   retira en el mismo mensaje, "ah no"—, humano, fuera_de_tema, catalogo —que vende la tienda—.

CLIENTE es="" nombre="" localidad="" equipo=""
   Lo que dice de si mismo, sin numero de renglon.

PARA TODOS: lo que depende de otro renglon —"si no hay", "si anda", "si sale menos de"— lleva si="n:si" o si="n:no". Si
contesta lo que pregunto el vendedor, lleva responde="R-n"."""


_BASE = V3.consigna  # la de V3, tomada antes de reemplazarla


def _con_fichas(texto_fichas: str):
    def consigna(tienda_id: str) -> str:
        base = _BASE(tienda_id)
        a, b = base.index("LOS COMANDOS:"), base.index("LOS DATOS DE CADA RUBRO")
        return base[:a] + texto_fichas + "\n\n" + base[b:]
    return consigna


def instalar(variante: str):
    texto = FICHAS if variante in ("V4", "V6") else open(os.path.join(AQUI, "fichas_gemini.txt"), encoding="utf-8").read()
    V3.consigna = _con_fichas(texto)
    V3.instalar()
