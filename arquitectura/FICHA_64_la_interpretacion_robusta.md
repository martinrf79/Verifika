# FICHA 64 — La interpretación robusta

28-sep-2026. Sigue a la 63, que sigue siendo el método: toda mejora entra
por la puerta. Esta ficha es el estado del problema de la interpretación y el
plan. Se lee entera antes de tocar el agente.

## El objetivo, dicho por Martín

Que el modelo traduzca bien el mensaje del cliente a lo que le pide al
código. No se busca 100 de 100: se busca que el cinco por ciento que no
traduce bien termine en una repregunta o en "ese dato no lo tengo", nunca en
un error dicho con seguridad.

## El único banco

`banco_pruebas/README.md`, sección "La interpretación y la respuesta". Las
68 charlas de la vara de las 58 por el clon, dos notas por charla —respuesta
e interpretación— y la puerta contra tres corridas de base. No se arma otro
banco: si falta un caso, se suma a la vara y a `desmenuzar.CASOS`.

## Dónde estamos, medido

Base `v58_p_`, tres corridas por el clon con la paga, código de `main` del
28-sep:

| | corrida 1 | corrida 2 | corrida 3 |
|---|---|---|---|
| respuesta bien | 62 | 61 | 63 |
| interpretación bien | 62 | 61 | 62 |

Nueve corridas guardadas de tres commits seguidos dan la respuesta entre 60
y 63: esa es la variación propia del modelo al redactar. Una baja a 56 o 57
no es ruido.

## Las seis charlas que fallan la interpretación, siempre

| charla | mensaje | qué pasa | causa |
|---|---|---|---|
| C27 | "de esos, cuál es el más barato" | no busca, elige entre lo mostrado | **la vara contradice al diseño**: la memoria de `respuesta._memoria_texto` le dice "de esos se elige entre estos, no en el catálogo". La respuesta sale bien |
| C37 | "tengo una notebook, qué memoria le sirve" | pregunta el modelo de notebook, no busca | **decisión de Martín**: si la vara acepta la pregunta o exige mostrar memorias de notebook |
| C45 | "y en blanco?" | contesta de memoria | memoria: un atributo nuevo tendría que ser una búsqueda nueva |
| C46 | "y alguno mecánico?" tras "que no sea Redragon" | contesta de memoria, o busca y pierde la exclusión | memoria, igual que C45 |
| C56 | "tienen 50 off, no?" | el código elige el tema `cambios` | `agente.temas_de` elige el tema por palabras en común: el código razonando |
| J01 | "dada la crisis dame uno acorde" | busca teclados sin orden por precio | el criterio implícito no llega a `orden`; ofrece uno de 55 mil habiendo uno de 14.500 |

## Lo que se probó y no entró

**Rubros y temas en lista cerrada**, corridas `v58_lp_`. `buscar.rubro` y
`politica.temas` como enum, la adivinanza de temas fuera de `app/`, y la
lista de rubros fuera del prompt. Arregló C56, C46 y J01; rompió ocho. La
respuesta bajó a 56-57. Se revirtió. Tres lecciones:

1. **La FAQ no tiene error.** Tiene temas generales —compatibilidad,
   especificaciones, stock— que nombran lo mismo que una herramienta. Con la
   lista a la vista el modelo mandó "¿es compatible con mi PC?" a `politica`,
   C38. Martín: el motor tiene que manejar cualquier FAQ; la data no se
   adapta al motor.
2. **Se cambiaron dos cosas a la vez**, las listas y el prompt. C01, C15 y
   J04 fallaron en la redacción y no se puede saber cuál las movió.
3. **C30 perdió la dependencia**: tras "no es compatible" no buscó la DDR5.

Solo el rubro en lista no se intenta: ninguna de las seis fallas es de rubro.

## El plan, en orden de probabilidad

1. **La vara donde contradice al diseño.** C27, y C37 según decida Martín.
   Commit propio, se recalifica la base, no llama al modelo. Casi seguro:
   62 → 64.
2. **Temas cerrados sin tocar la FAQ.** El motor tiene que separar "pregunta
   general de la casa" de "pregunta sobre un producto" sin depender de cómo
   se llamen los temas de cada tienda. Falta el diseño; la idea a medir es
   que `politica` no reciba preguntas que nombran un producto concreto, y que
   la segunda llave —el índice— compare con lo que eligió el modelo y, si no
   coinciden, traiga los dos o pregunte.
3. **Memoria en dos clases.** "De esos" elige entre lo mostrado; "y en
   blanco", "y alguno mecánico" es una búsqueda nueva con las condiciones de
   antes más la nueva. El código guarda la última búsqueda y se la pasa al
   modelo en la memoria. Probabilidad media. Ya se revirtió una vez obligarlo
   a buscar: esto no obliga, le da el dato.
4. **El orden implícito**, J01. Una sola charla.

Un cambio por vez, test offline primero, tres corridas y la puerta. Si no
pasa, se revierte.

## Ideas del diseño general, para cuando la interpretación esté firme

- Lo chico y fijo de la tienda —rubros, temas, campos— el modelo lo elige de
  una lista; lo grande —productos, modelos, colores— lo escribe con las
  palabras del cliente y el código lo certifica.
- Medir constancia: una charla vale si sale bien en las tres corridas.
- Variantes de las 58 dichas de otra forma, y cada falla real de producción,
  entran como casos. Después de consolidar lo que hay, no antes.
