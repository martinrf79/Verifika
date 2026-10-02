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

- **ABIERTO** · 2-oct, PRIMER PASO DE LA SESION SIGUIENTE, antes de las 8 de `grab_1`: la atadura en el codigo, para cualquier modelo. Un validador revisa cada pieza del interprete contra el vocabulario de la tienda —tipo, rubro, campo, operador, tema—; lo que no existe se lleva al valor mas cercano o se descarta, y si queda algo roto se le devuelve una vez al modelo con el error. Hoy la lista cerrada la garantiza el esquema estricto de Gemini; DeepSeek directo solo da JSON a secas. Se prueba sin modelo contra `grab_1`. Despues, una grabacion de la vara compleja con DeepSeek, unos 10 centavos dentro del tope del libro, y comparar con `grab_1` charla por charla para elegir modelo. Alternativas con esquema estricto: DeepSeek por su modo de herramientas estrictas en beta, o por OpenRouter o DeepInfra.
- **ABIERTO** · 2-oct, LA SIGUIENTE SESION: las 8 de `grab_1`, verificadas contra la reproduccion `rep_1`, sin modelo. Cuatro clases, un arreglo por clase: 1) redaccion, C14 K06 K08, el codigo tiene el dato y la respuesta lo pierde: control despues del redactor, lo que el cliente nombro y los hechos traen va en la respuesta, si falta vuelve una vez; 2) memoria como texto, K17 K18: la busqueda vigente como estructura, el codigo hereda las condiciones; uno de cada uno sale de lo respondido en turnos anteriores, por id; 3) referencias que resuelve el codigo, M06 la segunda contando sobre lo mostrado, K19 el catalogo con los rubros de la tienda; 4) K12 algo parecido, tabla de rubros afines en `data/clientes/`: pide permiso a Martin. Orden: 3, 2, 1, 4; todo con la gratis y `--pausa 20`.
- **ABIERTO** · 1-oct: el pedido como estado, `app/core/pedido.py`. Si lo repartido no cierra, el bot confirma antes de calcular y con el si corre lo guardado. Probado sin modelo; SIN MEDIR EN VIVO, la gratis llego a su tope diario. Medir K20 y `--vara compleja` contra tabL con la gratis antes de deployar.
- **ESPERA A MARTIN** · 1-oct, 23 hs: la clave paga devuelve 402, creditos prepagos agotados. Produccion usa esa clave: hasta recargar en AI Studio el bot contesta el aviso de demanda. La prueba del interprete con `gemini-3.8-flash`, tabX, quedo sin medir por eso: 31 de 42 charlas sin modelo.
- **ABIERTO** · La compra por `reservar` entra al cierre; falta verla cerrar un pedido real con nombre y link.
- **ABIERTO** · `motor.esquema` ya no lo usa el turno: lo usan tests y banco. Se borra con sus tests en su propio commit; su campo `orden` ya no lo lee nadie.
- **ABIERTO** · El cache da cero: el prompt fijo no llega al mínimo del proveedor. Medir el umbral.
- **ABIERTO** · 27-sep, FICHA 63: C46 contesta "de los que te mencioné" sin buscar el resto; el 70/30 a veces sale como total. Desde el 28-sep el reparto se anticipa en la primera vuelta. Toda mejora pasa por `banco_pruebas/puerta.py`.
- **ABIERTO** · El modelo sigue diciendo "todo es chino" aunque las memorias son Taiwan o China; a veces pregunta en vez de armar el 70/30.
- **ABIERTO** · 1-oct: el tablero conserva los articulos, da total general con el reparto sobre el, y la memoria guarda lo que busco el cliente y los presupuestos por destino. `vara compleja` tabL: 31 de 42 en las tres, contra 29 o 30 de tabH. Falta probarlo por WhatsApp despues del deploy y leer `produccion.py`.
- **ABIERTO** · Complejas que siguen mal: K17, "y teclados?" pierde la exclusion de marcas aunque la memoria la trae; K18, "sumame uno de cada uno" mete notebooks vistas de mas; K12, "y algo parecido?" no va a tablet; K13 reserva en vez de contestar por mayorista; K10 y K11, el pedido anotado se pierde a los varios turnos; K08, rubros sin buscar; K19, el catalogo.
- **ESPERA A MARTIN** · K20 conserva los seis articulos y da total general y 70/30, pero su casilla pide el envio de 6.500 a Concordia y cuando ese bloque pasa los 250 mil el envio sale gratis, que es correcto. Cambiar la casilla es cambiar la vara: lo decide Martin.
- **ABIERTO** · `agente.turno`, `agente.sistema` y `agente.esquema` ya no los usa el turno: se borran con sus tests en su propio commit, como `motor.esquema`.
- **ESPERA A MARTIN** · El catalogo dice que los auriculares bluetooth son con cable: `specs_por_modelo.csv` no trae bluetooth y cae el valor del rubro. Es `data/clientes/`: pide su permiso.
- **ABIERTO** · El arranque de sesión muestra la interpretación "sin medir": su piso se archivó. Arreglar la línea toca `scripts/`, que deploya.
- **ESPERA A MARTIN** · Ante un tema `ambiguous` el código sirve todos los candidatos. Si Martín quiere la repregunta, es una línea.
- **ESPERA A MARTIN** · Alerta de presupuesto y tope de cuota para la clave paga, en la consola de Google Cloud: el banco gastó unos diez dólares en un día el 28 y 29-sep.
- **ESPERA A MARTIN** · Retención de charlas: cuánto tiempo y con qué criterio se borran.
- **ESPERA A MARTIN** · Restricción de origen: el campo del catálogo es prosa; hace falta un campo normalizado, no un arreglo de código.
