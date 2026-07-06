# PLAN COMERCIAL — Verifika: el vendedor de WhatsApp que no inventa

Documento pedido por Martín el 6-jul-2026. Es el plan de comercialización del
producto. Las reglas del proyecto siguen en `CLAUDE.md` y el estado técnico en
`RESUMEN_PARA_NUEVO_CHAT.md`. Este archivo es el tercero: el plan de negocio.

---

## 1. El producto y por qué este

**Producto: Verifika, vendedor verificado por WhatsApp para tiendas online.**
No se construye un producto nuevo. El activo ya existe, está deployado en
`agente-bot`, tiene 229 tests offline y 8 vivos en verde, y hace algo que
ningún chatbot comercial del mercado puede garantizar: **nunca inventa un
precio, un stock ni una condición de venta**, porque el dato duro lo pone el
código, no el modelo.

La regla de este plan: flujo de caja rápido se logra vendiendo lo que ya
funciona, no construyendo otra cosa. Cada semana de desarrollo nuevo es una
semana sin ingresos.

## 2. El nicho elegido

**Tiendas argentinas de tecnología, informática y gaming que venden por
WhatsApp, empezando por las que usan Tiendanube.**

Por qué este nicho y no otro:

1. **La demo ya existe.** El catálogo vivo de 880 productos ES de tecnología.
   La demo pública se puede mostrar hoy, sin un día de trabajo extra.
2. **La inflación argentina hace letal la alucinación de precios.** En un
   rubro donde los precios se remarcan cada semana, un bot que inventa un
   precio viejo te obliga a vender a pérdida o a pelearte con el cliente.
   Los chatbots genéricos con IA alucinan precios; Verifika no puede, por
   arquitectura. En Argentina eso no es una feature, es LA feature.
3. **Las consultas del rubro son de compatibilidad.** "¿Este mouse anda con
   Mac?", "¿esta memoria entra en mi notebook?". Verifika ya separa identidad
   de compatibilidad por diseño. Los bots de plantilla no pueden responder
   esto; los de IA libre lo responden mal.
4. **El canal de expansión existe y es indirecto.** Tiendanube tiene más de
   cien mil tiendas en LatAm y una tienda de aplicaciones donde los
   comerciantes compran solos. Distribución sin tratar con personas.

## 3. El diferenciador: no se vende un bot, se vende una garantía

Todo el mundo vende "chatbot con IA para WhatsApp". Eso ya es un commodity y
compite por precio. Verifika vende otra cosa:

> **"Si el bot le inventa un precio o un stock a un cliente tuyo, ese mes no
> lo pagás."**

Ningún competidor puede copiar esa promesa sin reescribir su arquitectura,
porque sus bots son un LLM suelto con un prompt. Acá el verificador de plata,
el de stock y el de FAQ numérica son código determinista: la garantía se puede
firmar porque el sistema la hace cumplir. La garantía ES el producto.

## 4. La estrategia outside the box: el producto se vende solo

Pediste tratar con personas pero indirectamente. La estrategia tiene tres
motores, y en ninguno Martín sale a vender puerta a puerta:

**Motor 1 — El desafío público: "Hacelo inventar un precio".**
Se publica el número de WhatsApp de la tienda demo con un reto abierto en las
comunidades donde ya están los dueños de tiendas: grupos de Tiendanube, foros
y grupos de e-commerce argentino, comunidades de vendedores de tecnología.
El mensaje es uno solo: "Este vendedor atiende una tienda de 880 productos.
Intentá que te invente un precio, un stock o una cuota. Si lo lográs, te
muestro cómo. Si no lo lográs en diez minutos, imaginalo atendiendo tu tienda
a las 2 de la mañana." El que prueba la demo ya vio el producto funcionando;
no hace falta venderle nada. El bot es el vendedor del bot.

**Motor 2 — Agencias y Expertos Tiendanube como fuerza de venta.**
Tiendanube tiene un ecosistema de agencias que ya les cobran a las tiendas por
servicios. Se les ofrece a tres a cinco agencias: 30% recurrente de por vida
por cada cliente que traigan, y el pitch armado con la demo y la garantía.
Ellas tratan con las personas; nosotros mantenemos el motor. Una agencia con
cartera propia vale más que cien contactos fríos.

**Motor 3 — La tienda de aplicaciones de Tiendanube para escalar.**
Cuando haya clientes pagando y caso de estudio, se publica la app en el
marketplace de Tiendanube. Ahí el comerciante se instala solo, paga solo y el
canal trae demanda sin tocar a nadie. Es el motor de expansión, no el de
arranque: los marketplaces amplifican productos probados, no validan
productos nuevos.

## 5. Precios

- **Setup: 200 dólares** o equivalente en pesos, por única vez. Incluye carga
  del catálogo, conexión del número de WhatsApp y calibración de la FAQ. El
  setup es lo que genera caja inmediata.
- **Mensual: 70 dólares** o equivalente. Con DeepSeek el costo de LLM por
  tienda es de centavos: el margen bruto supera el 90%.
- **Garantía:** mes bonificado si el bot inventa un dato duro. Con los
  verificadores en verde, el riesgo real de pagar esa garantía es mínimo, y
  cada mes que no se paga es marketing gratis.
- **Agencias: 30% recurrente** sobre el mensual de los clientes que traen.

Diez clientes son 2.000 dólares de setups más 700 mensuales recurrentes.
Cincuenta clientes vía marketplace y agencias son 3.500 mensuales con costo
marginal casi nulo.

## 6. Los objetivos, en orden, con sus umbrales

Cada objetivo está diseñado para que cumplirlo sea sinónimo de cobrar o de
acercarse a cobrar, no una métrica de vanidad. Y cada uno tiene un umbral de
corte: si no se llega, se corrige el tiro antes de gastar más, no se insiste.

**Objetivo 1 — Semana 1: la demo pública y la oferta publicada.**
Tienda demo con el catálogo de 880 andando en un número público, una landing
de una página con el desafío, la garantía y el precio a la vista, y el flujo
de alta documentado. Meta medible: 50 conversaciones de desconocidos con la
demo. Costo: cero, es difusión en comunidades.

**Objetivo 2 — Semanas 2 a 4: los primeros cinco que pagan.**
Treinta conversaciones reales con dueños de tiendas de tecnología, salidas
del desafío y de las comunidades, más propuesta enviada a tres agencias.
Meta: **5 pilotos pagos con setup cobrado, primeros 1.000 dólares.**
Umbral de corte: si después de 30 conversaciones reales hay menos de 2
pilotos, el problema es el precio, el mensaje o el rubro; se ajusta uno solo
de esos tres y se repite. No se construye nada nuevo hasta pasar este punto.

**Objetivo 3 — Semanas 5 a 8: la prueba de que conviene quedarse.**
Los pilotos pasan a plan mensual. Se instrumenta el número que vende solo:
consultas atendidas fuera de horario, ventas cerradas por el bot, precios
que habría inventado un bot común y Verifika bloqueó. Con eso se arma UN caso
de estudio con números reales. Meta: **10 clientes pagando mensual, 700 a
1.000 dólares recurrentes.**

**Objetivo 4 — Meses 2 a 4: expansión sin tocar personas.**
App publicada en la tienda de aplicaciones de Tiendanube con onboarding
self-service, y 3 agencias activas revendiendo. Meta: **30 a 50 clientes,
2.000 a 3.500 dólares mensuales recurrentes**, con el crecimiento entrando
por canales que no dependen del tiempo de Martín.

## 7. Lo técnico mínimo que falta para cobrar

En orden, y nada más que esto. Todo lo demás es ruido hasta el Objetivo 2:

1. **La charla real de humo** que ya está pendiente en el RESUMEN: validar el
   camino vivo con conversaciones reales. Sin esto no se publica el desafío.
2. **Alta de tienda repetible:** que dar de alta un cliente nuevo con su CSV,
   su FAQ y su número sea una receta de horas, no un proyecto. Ya es
   multi-tenant; falta el procedimiento pulido de punta a punta.
3. **Cobro:** suscripciones por Mercado Pago para el mensual. El setup se
   cobra por transferencia al principio; no bloquear la venta por el billing.
4. Recién para el Objetivo 4: onboarding self-service y app de Tiendanube.

## 8. Sobre la promesa del cien por ciento

Nadie puede garantizar ingresos al cien por ciento, y cualquier plan que lo
prometa miente. Lo que este plan sí hace es dos cosas concretas. Primera: los
objetivos no son proxies, el Objetivo 2 ES plata cobrada, así que "cumplir
los objetivos" y "que aparezcan los ingresos" son la misma cosa por
construcción. Segunda: los umbrales de corte hacen que el escenario malo no
sea perder meses, sino descubrir en 30 conversaciones que hay que ajustar
precio, mensaje o rubro, con costo hundido cercano a cero. El riesgo no se
elimina; se paga en semanas y en conversaciones, no en plata ni en meses.

La estrategia queda además reutilizable para cualquier producto futuro:
demo pública que se demuestra sola, garantía que la competencia no puede
firmar, canales que tratan con las personas por vos, y objetivos que son
cobros con umbral de corte. Ese es el molde.
