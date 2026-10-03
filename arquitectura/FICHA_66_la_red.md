# FICHA 66 — LA RED: cuando el modelo entiende mal, el código pregunta en vez de afirmar

Abierta el 2-oct-2026. Método de la FICHA 63: toda mejora se mide contra la base, charla a charla.

## El problema

El modelo traduce bien la mayoría de los mensajes, pero no todos. Cuando traduce mal, hoy el error
sale tal cual: un total sin el SSD del carrito, tres unidades por destino en vez de una, alternativas
sumadas como si fueran el pedido. Medido sobre `grab_ds_g1` con DeepSeek: G01, G04 y G06.

La meta no es que el modelo no se equivoque. Es que **su error nunca llegue al cliente como un hecho**:
o sale bien, o sale una pregunta.

## Lo que ya existe

`app/core/pedido.py` confirma antes de calcular, pero con una sola señal: lo repartido por destino no
cierra con lo pedido, K20. La red generaliza ese mecanismo; no lo duplica.

## Capa 1 — antes de calcular, el código se controla

Lo entendido contra lo que el código sabe por su cuenta. Si una señal salta, no se afirma: se dice lo
entendido y se pregunta, con `pedido.guardar`.

1. Un producto del carrito vigente falta en la cuenta y el mensaje no lo saca. G01.
2. Las unidades de la cuenta no coinciden con los números del mensaje. G04.
3. El intérprete marca `falta` en una cuenta: no se calcula con lo adivinado. G06.
4. Un ítem ambiguo: se muestra lo certificado y se pregunta solo por ese. G05.
5. El cliente discute un precio: se le repite el último presupuesto guardado. G07.

Caso real del 3-oct, ya arreglado en su causa: el aviso de artículos decía "el teclado no estaba entre
los artículos pedidos" y el redactor escribió "no figura en nuestro catálogo"; al turno siguiente, ante
"no tenés teclados", le dio la razón al cliente. Ahora el aviso dice que la tienda sí lo vende y una
verificación sin producto lleva lo que vende la tienda. La red tiene que cubrir la clase: un hecho del
catálogo nunca se niega sin una consulta al catálogo que lo respalde.

## Capa 2 — después de redactar, una salida sin modelo

Si la guarda de plata tira la respuesta, hoy sale `VERIFIKA_FALLBACK_MESSAGE`, "dejame consultar".
K15 y C31 con DeepSeek. En su lugar sale una respuesta armada por el código con los hechos ya
certificados: el detalle de la cuenta, el precio, la pregunta pendiente.

## Cómo se mide

Las tres grabaciones, sin modelo: `grab_1`, `grab_ds_1` y `grab_ds_g1`, con `--reproducir`. El banco
cuenta por turno tres cosas: bien, pregunta segura y error afirmado. La vara es el error afirmado, y
tiene que bajar a cero sin que baje el bien de `grab_1`, hoy 40 de 41.
