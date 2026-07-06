# PLAN COMERCIAL — Sparring, el gimnasio de ventas

Escrito el 6-jul-2026. Reemplaza al plan anterior de este archivo: Martín pidió
un producto digital NUEVO, diferenciador, de ticket medio, que se venda solo
con una demo. El producto ya está construido y probado en `sparring/`.

---

## 1. Qué es

Un simulador donde los vendedores entrenan por chat contra clientes difíciles
actuados por IA. Cada cliente tiene una condición oculta de compra: solo
compra si el vendedor hace lo correcto. Al terminar, un juez entrega un
veredicto con puntaje y evidencia: cada dimensión citada con la frase textual
del vendedor que la justifica, el turno exacto donde se cayó la venta con lo
que pensó el cliente en ese momento, la condición oculta revelada y un único
consejo accionable. El puntaje lo arma el código con fórmula fija más señales
duras deterministas; el LLM opina, el código decide y explica.

Estado real al 6-jul: motor, juez, API y UI completos y probados VIVOS con
DeepSeek. Un vendedor malo guionado sacó 0/100 y perdió a Marta; uno bueno
sacó 95 y 100, cerrando a Jorge. El juego discrimina.

## 2. Quién paga y cuánto

Comprador: dueños y jefes de venta de pymes LatAm cuyos vendedores venden por
WhatsApp: concesionarias de autos, inmobiliarias, corredores de seguros,
retail de ticket alto. El dolor: la venta se pierde en el chat y nadie
entrena eso; el roleplay con IA ya es categoría probada en inglés y cara,
en español rioplatense a precio pyme no existe.

- **Diagnóstico del equipo, por única vez: 150 a 250 dólares.** Todo el
  equipo juega las tres personas, el dueño recibe el ranking con los
  veredictos y los momentos donde cada vendedor pierde clientes. Es el
  producto de entrada y la caja rápida.
- **Abono gimnasio: 80 a 150 dólares por mes por equipo.** Personas nuevas
  por rubro, torneos internos, seguimiento de progreso.
- Costo marginal por partida con DeepSeek: centavos. Margen bruto arriba
  del 90%.

## 3. Cómo se vende solo

- **Demo pública jugable**: cualquiera entra, elige a Marta, Jorge o Caro y
  trata de venderles. El resultado es compartible en un toque: "Mi sparring
  contra Jorge: 100/100. ¿Le vendés vos?". El desafío se difunde en grupos
  de vendedores, de concesionarias y de e-commerce; el puntaje compartido
  trae al siguiente jugador. Nadie vende: el juego recluta.
- **Capacitadores de ventas como canal**: los consultores que hoy dan cursos
  usan Sparring en marca blanca como práctica para sus alumnos y como
  diagnóstico para sus clientes, con 30% recurrente. Ellos tratan con las
  personas.
- **El gancho del dueño**: "hacé pasar a tus vendedores de incógnito y mirá
  cuántos clientes pierden por mes". El reporte del equipo es el vendedor
  del abono.

## 4. Objetivos con umbral de corte

1. **Semana 1**: deploy público en Cloud Run con dominio propio, separado de
   agente-bot, y página con el desafío. Meta: 100 partidas de desconocidos.
   Se mide con los puntajes compartidos y las partidas por día.
2. **Semanas 2 a 4**: el modo equipo mínimo: código de invitación + reporte
   del dueño. Meta: **5 diagnósticos de equipo cobrados, 750 a 1.250
   dólares**. Umbral: si tras 200 partidas públicas y 30 charlas con dueños
   hay menos de 2 ventas, se ajusta precio, gancho o rubro, uno solo por vez.
3. **Semanas 5 a 8**: convertir diagnósticos a abono mensual con personas
   del rubro de cada cliente. Meta: **8 equipos en abono, 800 a 1.200
   dólares recurrentes**.
4. **Meses 2 a 4**: 2 o 3 capacitadores en marca blanca y torneos entre
   equipos. Meta: 25 equipos activos, 2.500 dólares mensuales.

## 5. Pendiente técnico, en orden

1. Mover `sparring/` a su propio repo con su propio servicio de Cloud Run.
   NO se mezcla con agente-bot ni con el camino vivo de Verifika.
2. Persistencia de partidas en Firestore (hoy las sesiones viven en memoria).
3. Modo equipo: invitaciones, ranking, reporte del dueño.
4. Checkout de Mercado Pago para el diagnóstico.
5. Generador de personas por rubro a partir de plantilla.

## 6. Riesgo, dicho derecho

Nadie garantiza ingresos al cien por ciento. Este plan acota el riesgo así:
el producto ya existe y costó cero pesos; los objetivos 2 y 3 SON plata
cobrada, no métricas; y cada etapa tiene umbral de corte para ajustar antes
de gastar. Lo que se paga por descubrir si funciona son semanas y charlas,
no inversión.
