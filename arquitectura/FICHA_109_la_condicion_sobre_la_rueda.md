# FICHA 109 — LA CONDICION SOBRE LA RUEDA (26-nov-2026, para la sesion que sigue)

Se lee entera antes de proponer. Viene de la FICHA 108, seccion 9: la rueda desde la fila de Luna quedo medida y robusta
en la traduccion. Esta sesion construye y mide la capa 3, condicion y orden, encima de la rueda, en el banco. La memoria
de la charla queda para despues, si sobra.

## 1. Donde estamos

**La rueda**, `banco_pruebas/flujo/primeros/cadena.py`, sin cambios en el prompt de Luna, el v14f1b de
`llamada0_modelos.PROMPTS`:
1. Luna separa y traduce, una fila por pedido: "{palabras del cliente}[nombre del vocabulario]", con la ficha f1 de
   `luna_ficha._f1()`: PRODUCTOS, CARACTERISTICAS y PREGUNTAS de `alias.json`.
2. `cadena.leer(fila)` da por pedido: `rubro`, del corchete de PRODUCTOS o de un codigo suelto del catalogo; `consulta`,
   la fila entera; `nombre`, lo marcado como rubro, marca o modelo; `nombra` e `identifica`.
3. `cadena.dato2(fila)` da `(dato 2, condiciones)`. **Las condiciones son la entrada de esta capa:** cada una es
   `(palabras, nombre de caracteristica)`, con valor y sin pregunta: `("inalambrico", "conexion")`, `("negro", "color")`,
   `("que no sea carisimo", "precio ars")`, `("1 TB", "almacenamiento")`.
4. Existe corre sobre `nombre`; los embeddings ordenan solo dentro del rubro; lo sin rubro no se ofrece.

**Lo medido de la rueda**, FICHA 108, seccion 9.5: todos los rubros en 157 de 161 dificiles; la condicion llega a la fila
de su pedido en 206 de 220 del examen y 47 de 51 de las reales nuevas; 10 llegan en otra fila, casi siempre "el mas
barato" suelto. **Lo que hoy falla por falta de esta capa:** en las 137 muestras con condicion, 105 de 122 ventas y 16
ofertas equivocadas en 135, casi todas por condicion sin filtrar: "que no sea Genius", "con cable", "hasta 50 mil", "el
mas liviano", "en rojo", "64 GB por menos de 200 mil".

**Respuesta a Martin, 26-nov:** si, la rueda se adapta a la condicion, y mejor que antes: la condicion ya llega separada
y marcada con el nombre de la caracteristica, y se resuelve por codigo sobre la fuente. Los embeddings no deciden la
condicion: solo ordenan dentro del rubro lo que la condicion deja pasar. Asi se evita lo que paso con los embeddings, que
traian al candidato correcto pero no lo elegian.

## 2. Lo que tiene que hacer la capa

Por pedido, con el rubro y las condiciones de la rueda:
1. **Atar cada condicion por codigo**, sin modelo:
   - el nombre de la caracteristica dice el campo; las palabras, el valor;
   - los valores con nombre van a un concepto de `conceptos/conceptos.json`: atributo, color, plataforma, origen;
   - los numeros, con `conceptos/numeros.leer`: precio tope, capacidad, ram, pulgadas, hz, potencia;
   - marca y modelo, contra el catalogo;
   - la negacion, "que no sea", "sin", saca en vez de exigir;
   - el orden, "el mas barato", "el mas caro", "el mas liviano", a un `orden:` de conceptos.json.
2. **Filtrar la vista de la fuente** con lo atado, igual que `examen.aceptables`: lo exigido filtra, lo negado saca, la
   preferencia y el orden no vacian.
3. **Si nada cumple**, no hay, con lo mas cercano dicho como alternativa: el teclado azul, la notebook de 64 GB por menos
   de 200 mil. Nunca ofrecer algo que no cumple como si cumpliera.
4. **El orden corre sobre lo que cumple**, todo el rubro, nunca sobre los candidatos de los embeddings: FICHA 108,
   seccion 8, el 68 de 78 inflado.
5. **Lo que no se ata** a un campo queda dicho: "no tengo ese dato", y no filtra. Ejemplos: "que no se caliente",
   "resistente", "comodo".
6. **La salida** son los productos que cumplen, ordenados, con el veredicto: ofrecer, no hay, repreguntar o sin dato. La
   redaccion, capa 7, recibe eso con los ids.

Y lo que la rueda deja para esta capa, porque es condicion:
- **La condicion en otra fila**, 10 de 220: una fila sin producto que solo trae condicion u orden se pega al pedido de
  la fila anterior, o a todos si es global.
- **Lo que se pide a toda la tienda**, "el producto mas caro que tienen", "los dos articulos mas baratos": sin rubro y con
  orden, el orden corre sobre todo el catalogo.
- **La correccion del cliente**, "Redragon... no, perdon, mejor Logitech": vale lo ultimo.

## 3. Las piezas que ya existen, y que hacer con cada una

| Pieza | Que hace | Que se hace |
| --- | --- | --- |
| `banco_pruebas/flujo/conceptos/conceptos.json` y `conceptos.py` | cada concepto con su condicion sobre la vista, y `cumple` | se usa tal cual para atar |
| `banco_pruebas/flujo/conceptos/numeros.py` | lee plata, capacidad, potencia, hz, pulgadas, cantidad, numeros en letras | se usa tal cual |
| `banco_pruebas/flujo/conceptos/compat.py` | compatibilidad por familias | para "anda con", si aparece |
| `banco_pruebas/flujo/conceptos/fuente.py` | la vista por modelo con los numeros ya leidos | la base del filtro |
| `banco_pruebas/flujo/examen/examen.py` | `aceptables`, `_orden_ok`, `corregir` | la vara, no se toca |
| `banco_pruebas/flujo/chico/reparto.py` | el techo con traduccion perfecta: 77 de 78 | comparar contra ese techo |
| `app/core/flujo/nuevo/condicion.py` | el nexo de condicion del bot: embeddings y Jev | se reemplaza al llevar la rueda al bot; no se usa de base |
| `alias.json`, seccion de campos | como nombra el cliente cada campo | para atar el nombre de caracteristica de Luna |

**Lo que no se repite**, FICHA 108, seccion 7: el modelo chico para decidir si una condicion se cumple, y Luna eligiendo
entre candidatos.

## 4. La vara, contra que se mide

Cuatro conjuntos ya etiquetados, todos con lo que Luna separo grabado, sin gasto para medir:

| Conjunto | Etiqueta | Lo que Luna separo |
| --- | --- | --- |
| 138 reales del examen fijo | `examen/examen.json`, 81 pedidos con condicion | `examen/luna_b.jsonl` |
| 52 reales nuevas del pozo | `primeros/reales.json` | `primeros/luna_reales.jsonl` |
| 137 muestras con condicion | `primeros/muestras.json`, aceptables de su regla en `_acept` | `primeros/luna_muestras.jsonl` |
| 300 sinteticas | `primeros/examen.json` | `primeros/luna_b.jsonl` |

**Como se mide**, en este orden:
1. **Con entrada perfecta:** las condiciones de la etiqueta, los `cas`, contra la capa. Es el techo.
2. **Con la entrada de la rueda:** las condiciones de `dato2()`. La distancia al techo es lo que se pierde al atar.
3. **De punta a punta:** `cadena.py` con la capa puesta, el primero sirve con el orden aplicado, `examen._orden_ok`.
4. Se cuenta aparte, con el criterio de Martin, mitad vender y mitad no alucinar: venta perdida, oferta equivocada, no
   hay dicho cuando nada cumple, y "no tengo ese dato".

**La linea de base de hoy, sin la capa**, `cadena.py` con "sin rubro no ofrece":
- sinteticas: el primero sirve en 255 de 269 sin orden, 41 de 42 con orden, 18 ofertas equivocadas en 326;
- examen: 116 de 126 sin orden, 35 de 43 con orden, 17 en 194;
- reales nuevas: 30 de 32 sin orden, 14 de 17 con orden, 7 en 56;
- muestras: 105 de 122 sin orden, 16 en 135.

"Con orden" hoy cuenta un aceptable primero sin mirar el orden: con la capa se mide con el orden aplicado y va a bajar
antes de subir.

## 5. Las reglas de esta sesion

- Plan escrito antes de correr, en `banco_pruebas/flujo/lab/plan.md`. Guion revisado con unos casos contra lo grabado
  antes de creer el numero; cada falla clasificada: capa, etiqueta o prueba.
- Las etiquetas no se cambian despues de ver un resultado.
- Arreglo de clase, no por caso. Si para que pase un caso hay que sumar una palabra a una lista o poner un umbral, se
  para y se consulta con Martin. **Pendiente de consulta:** la lista de palabras que preguntan, `INTERROGA` en
  `cadena.py`, que decide si una caracteristica es condicion o dato 2.
- El prompt de Luna no se toca en esta sesion.
- Todo en el banco. El bot sigue con la llamada 0 v7 y su nexo de condicion; Martin, 26-nov: falla mucho en produccion y
  se puede cambiar, pero se lleva la rueda entera cuando la condicion este medida.

## 6. Los comandos

    python3 banco_pruebas/flujo/primeros/cadena.py [--examen|--reales|--muestras] [--ver]   # dato 1
    python3 banco_pruebas/flujo/primeros/cadena.py --dato2 [--examen] [--ver]                # dato 2
    python3 banco_pruebas/flujo/primeros/condicion_llega.py [--ver]      # si la condicion llega a su pedido
    python3 banco_pruebas/flujo/primeros/dificiles.py [--ver]            # las 300 dificiles, rubros y no vendido
    python3 banco_pruebas/flujo/primeros/control.py [--reales]           # controla y congela una etiqueta
    python3 banco_pruebas/flujo/primeros/luna.py [--examen|--reales|--muestras]   # Luna sobre un conjunto, retoma lo grabado

Los embeddings de las consultas quedan en `banco_pruebas/flujo/lab/vectores.json.gz`, fuera de git: se vuelven a pedir
con la clave gratis, o con la paga y la marca de Martin si la gratis se agota.

## 7. Lo gastado el 25 y 26-nov en esta linea

Luna, unos 25 centavos entre todas las corridas; embeddings, menos de un centavo con la paga autorizada por Martin;
Sonnet, para escribir y etiquetar, cinco tandas de unos 100 mil tokens cada una, con lectura cerrada y sin informe.
