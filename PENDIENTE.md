# PENDIENTE — lo que quedó abierto

Corto a propósito: el hook lo imprime entero. Lo hecho lo cuenta `git log`.
La historia hasta el 27-sep está en `archivo/documentacion/PENDIENTE_hasta_27sep.md`.

Estados: **ABIERTO** · **ESPERA A MARTIN**.

## Dónde está el proyecto

```
python3 -m pytest -q          la batería offline
```

Camino vivo: `orchestrator` → `respuesta.procesar_turno` → `tablero.turno` sobre
`motor.buscar`. Unidad de trabajo: `arquitectura/FICHA_65_el_tablero_y_la_biblioteca.md`.
Dónde está cada cosa: `MAPA.md`.

---

## Abierto

- **ABIERTO** · 8-oct, EL PEDIDO LO PONE EL CODIGO: K21 en la vara; el nombre y el si cierran con link, el reparto del mensaje lo lee el codigo y "armalo con esos" usa lo mostrado. K21 en vivo: 6 casillas mal contra 12. DECIDIDO por Martin el 8-oct: "dos auriculares" a dos destinos sigue dando dos modelos distintos; las casillas de 237000 de K21 fallan a sabiendas hasta que se vuelva al tema. Sigue el paso C.
- **ESPERA A MARTIN** · 8-oct, JEV como elector de candidatos con probabilidad: hace falta la clave, de `console.typesafe.ai` o por OpenRouter, cargada como secreto, y habilitar el dominio en la red del entorno. Con eso se mide en la vara.
- **ESPERA A MARTIN** · 9-oct, DOS LECTURAS DESCARTADAS, desmenuzado `dosl_1`: Gemini 41, DeepSeek 44 de 54; discrepan en 28, y en 20 las dos estaban bien; tomar la otra al discrepar da 43. Lo que fallan los dos es editar un pedido existente: propuesto que esas operaciones las aplique el codigo sobre el pedido guardado.
- **ABIERTO** · 4-oct, LA SESION SIGUIENTE: los NEXOS, `banco_pruebas/nexos/`. El modelo pide en lineas con un indice fijo, frases genericas y la memoria como estado del codigo; el codigo resuelve, suma y reparte. Sobre las charlas reales de WhatsApp, `reales_vara.py`, con DeepSeek: 24 y 22 de 28 turnos bien en dos repeticiones y 0 datos falsos en las dos, contra 21 y 2 del bot de hoy y 18 y 9 de lo que salio en WhatsApp. Falta, en orden: la guarda de montos del redactor, DeepSeek escribe montos sin origen en 12 de 481 turnos y Gemini en 2 de 374; la misma vara con Gemini; mas charlas reales; recien ahi pasarlo a `app/`. Elegir modelo es decision de Martin. Incluye la FICHA 66.
- **ABIERTO** · 2-oct: `grab_1` reproducida sin modelo da 40 de 41, `rep_lo_grabado_1`: el id que resuelve el interprete es la identidad en `producto` y `buscar`; la exclusion sigue valiendo en otro rubro y no se pierde en la revision; saber general y lo que no se vende llevan lo que vende la tienda; la memoria marca lo que respondio cada pedido por criterio y la cuenta suma eso. La que queda, K12 "dice no vendemos", es casilla de redaccion: el hecho ya dice que no se vende. Falta verlo en vivo con la gratis y `--pausa 20`.
- **ABIERTO** · 2-oct, LOS GUIONES: `--vara guiones`, diez guiones de memoria con casillas del catalogo real, grabados con DeepSeek, `grab_ds_g1`, 18 centavos. Reproducidos sin modelo: de 3 a 5 de 10 charlas, de 79 a 87 de 95 casillas, `rep_g_5`. Lo que queda es del interprete: G01 olvida el SSD del carrito, G04 pone tres unidades por destino, G06 lista alternativas como pedido; y del codigo, G05 sin color en un item no muestra los demas del bloque, y G07 ante "me habias dicho otro precio" no vuelve a dar el presupuesto.
- **ABIERTO** · 1-oct: el pedido como estado, `app/core/pedido.py`. Si lo repartido no cierra, el bot confirma antes de calcular y con el si corre lo guardado. Probado sin modelo; SIN MEDIR EN VIVO, la gratis llego a su tope diario. Medir K20 y `--vara compleja` contra tabL con la gratis antes de deployar.
- **ESPERA A MARTIN** · 1-oct, 23 hs: la clave paga devuelve 402, creditos prepagos agotados. Produccion usa esa clave: hasta recargar en AI Studio el bot contesta el aviso de demanda. La prueba del interprete con `gemini-3.8-flash`, tabX, quedo sin medir por eso: 31 de 42 charlas sin modelo.
- **ABIERTO** · La compra por `reservar` entra al cierre; falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · `motor.esquema` ya no lo usa el turno: lo usan tests y banco. Se borra con sus tests en su propio commit; su campo `orden` ya no lo lee nadie.
- **ABIERTO** · El cache da cero: el prompt fijo no llega al mínimo del proveedor. Medir el umbral.
- **ABIERTO** · 27-sep, FICHA 63: C46 contesta "de los que te mencioné" sin buscar el resto; el 70/30 a veces sale como total. Desde el 28-sep el reparto se anticipa en la primera vuelta. Toda mejora pasa por `banco_pruebas/puerta.py`.
- **ABIERTO** · El modelo sigue diciendo "todo es chino" aunque las memorias son Taiwan o China; a veces pregunta en vez de armar el 70/30.
- **ABIERTO** · 1-oct: el tablero conserva los articulos, da total general con el reparto sobre el, y la memoria guarda lo que busco el cliente y los presupuestos por destino. `vara compleja` tabL: 31 de 42 en las tres, contra 29 o 30 de tabH. Falta probarlo por WhatsApp despues del deploy y leer `produccion.py`.
- **ABIERTO** · Complejas que siguen mal en vivo, a medir de nuevo: K13 reserva en vez de contestar por mayorista; K10 y K11, el pedido anotado se pierde a los varios turnos; K08, rubros sin buscar.
- **ESPERA A MARTIN** · K20 conserva los seis articulos y da total general y 70/30, pero su casilla pide el envio de 6.500 a Concordia y cuando ese bloque pasa los 250 mil el envio sale gratis, que es correcto. Cambiar la casilla es cambiar la vara: lo decide Martin.
- **ABIERTO** · `agente.turno`, `agente.sistema` y `agente.esquema` ya no los usa el turno: se borran con sus tests en su propio commit, como `motor.esquema`.
- **ESPERA A MARTIN** · El catalogo dice que los auriculares bluetooth son con cable: `specs_por_modelo.csv` no trae bluetooth y cae el valor del rubro. Es `data/clientes/`: pide su permiso.
- **ABIERTO** · El arranque de sesión muestra la interpretación "sin medir": su piso se archivó. Arreglar la línea toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Ante un tema `ambiguous` el código sirve todos los candidatos. Si Martín quiere la repregunta, es una línea.
- **ESPERA A MARTIN** · Alerta de presupuesto y tope de cuota para la clave paga, en la consola de Google Cloud: el banco gastó unos diez dólares en un día el 28 y 29-sep.
- **ESPERA A MARTIN** · Retención de charlas: cuánto tiempo y con qué criterio se borran.
- **ESPERA A MARTIN** · Restricción de origen: el campo del catálogo es prosa; hace falta un campo normalizado, no un arreglo de código.
