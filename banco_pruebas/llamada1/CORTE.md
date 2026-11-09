# Corte de la llamada 1, intención de compra, escrito antes de medir, 9-nov
A: la consigna del intérprete del 21-oct, git 28d956c. B: la misma, con el párrafo de LA INTENCION DE COMPRA.
Datos: primer turno de las charlas cuya agenda a mano compra, más 6 de control de buscar y producto; cinco formas; una vez
cada una, clave gratis. Se califica con banco_pruebas/capa_buscar.py del repo, mismos productos que la agenda a mano.
B SIRVE si, en las mismas corridas, gana a A por 5 casos o más en comprar y no pierde más de 1 en buscar y producto.
Si no, el párrafo no entra y se busca otra causa.

## Resultado de B, 9-nov: no pasa
B gana 7, 6 de comprar, y pierde 2: C06 "quiero un mouse inalambrico" y C34 "cuanto sale mandar un g203" pasaron a compra.
## B2, mismo corte, escrito antes de correrla
B2 acota el parrafo: comprar es de un modelo concreto o de algo de la libreta; un rubro sin modelo es buscar aunque diga
"quiero"; preguntar cuanto sale algo, o mandarlo, es producto y envio. Pasa si gana a A por 5 o mas en comprar y no
pierde mas de 1 en buscar y producto.

## Resultado de B2, 9-nov: pasa
comprar A 79 de 90, B2 85; producto 15 y 15 de 20; buscar 47 y 50 de 50. Gana 7, pierde 0. Una corrida de cada una.

## Como se repite
`llamada1.py` corre dentro del arbol del 21-oct, el que grabo traduccion58: `git archive 28d956c app banco_pruebas | tar -x
-C <dir>`, un enlace `<dir>/data` al `data/` del repo, y se copia ahi `llamada1.py` y `textos.json`. Con la clave gratis.
`calificar.py B2` corre desde el repo y califica con `capa_buscar.py`.
