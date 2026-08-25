# SONDA DEL 25-AGO — los defectos, con turno exacto

## LAS GRABACIONES ESTÁN ACÁ

**Corrección del 25-ago, tarde.** Una versión anterior de este archivo decía
que las grabaciones se habían perdido. No se perdieron: el contenedor de la
sesión de la sonda seguía vivo, se pusheó desde ahí, y los **15 casetes** están
en esta misma carpeta. Lo que sí se perdió y hubo que reconstruir fueron dos
commits del arreglo de compatibilidad, que ya están en `main` y además
aparecieron un segundo crasher en `reposicion.py` y el candado de grabación.

**Lección, y quedó como regla en `ARRANQUE.md`:** el contenedor se recicla y lo
que no está en `origin` no existe. Se pushea al cerrar la sesión, siempre.

**Esto NO es el corpus y no se fija como tal.** La batería lee
`banco_pruebas/casetes/*.json` y esta carpeta es hermana, así que no la toca y
nada se rompe. Son prosa **viva** del modelo: sirven para verificar los
arreglos de abajo **sin gastar un token de clave**. Cuando se regrabe, los
casetes nuevos van a `casetes/` por el camino de siempre.

## LOS DEFECTOS

### 1. EL CUARTO FRENO — la oferta pisa una pregunta propia sin contestar
Tres turnos ofrecen encima de una pregunta que el mismo bot acaba de hacer:
**76 t1, 80 t6, 80 t8**. Los tres frenos que existen hoy miran herramienta
ambigua; ninguno mira si el turno dejó una pregunta propia abierta.

### 2. EL DETECTOR DE OFERTA ES LAXO
Cuenta **16 OFRECIDO** y al menos cuatro no son ofertas:

- **71 t3** — cortesía de cierre genérica
- **73 t3** — mención de descuento
- **80 t8** — pedido de confirmación
- **76 t2** — no nombra ningún producto

Entran todos por el mismo agujero: `_RE_PRONOMBRE` en `indice_turno.py` deja
que un "lo" pelado haga de producto. Mientras el detector cuente esto, todo lo
que se mida sobre oferta está sucio.

### 3. UNIVERSAL SOBRE EL CATÁLOGO — alucinación
**46 t4** y **62 t2** afirman algo general del catálogo que no salió de ninguna
herramienta. Prioridad uno: es invención, no estilo.

### 4. NOTA INTERNA AL CLIENTE
**80 t6** le mandó al cliente el texto "el cliente pide". El nodo
`sin_narracion_interna` corre en todos los turnos y no lo vio: su vocabulario
cerrado nombra la máquina ("el sistema me", "la herramienta") y no cubre hablar
del cliente en tercera persona. No está muerto, está ciego.

### 5. PROMESA SIN DATO
**79 t1** promete un dato y no lo da. `camino_al_cobro` bajó de **9/15 a 7/15**.

## EL ORDEN

No se regraba todavía. Primero (1) y (2), que son los que ensucian la medición;
regrabar antes de arreglarlos es pagar la grabación dos veces. Y los dos se
pueden verificar **gratis** contra los 15 casetes de esta carpeta.
