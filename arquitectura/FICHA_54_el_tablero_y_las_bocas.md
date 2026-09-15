# FICHA 54 — EL TABLERO Y LAS BOCAS TIENEN QUE DECIR LO MISMO

**Decision de Martin, 15-sep-2026.** La unidad de trabajo abierta es esta.
Las anteriores quedan cerradas: los cinco ramales estan enchufados, la cuenta
del retorno tambien.

Los nombres —bocas, ramales, retorno, tablero— se definen en la FICHA 52 y en
`MAPA_CABLEADO.md`. Aca no se vuelven a describir.

---

## 1. LA CONSIGNA, EN UNA LINEA

**Lo que el modelo VE en el tablero tiene que ser exactamente lo que las bocas
PUEDEN contestar.** Ni un campo de mas, ni una forma de nombrar las cosas que
la fuente no use, ni dos caminos para la misma pregunta.

Si el tablero y las bocas no dicen lo mismo, el modelo elige mal y el defecto
sale por el otro lado, en la respuesta, donde ya no se ve de donde vino.

**LO QUE NO SE HACE:** mas bancos de prueba nuevos. Ya se ramifico por ahi
tres veces y se termino en un lugar desconocido. El banco que hay
—`tanda_tablero.py`— se corre antes y despues de cada cambio, y nada mas.

---

## 2. EL NUMERO DE HOY, para poder comparar

Medido el 15-sep con `python3 banco_pruebas/tanda_tablero.py`, clave gratis,
17 mensajes, cero turnos caidos:

    PIDIO LO QUE HACIA FALTA    13 de 16   (81%)
    VUELTAS POR TURNO           2.65
    BUSCARON                    17 de 17

    campo            la vara pedia   declarado
    consultas                9               9
    temas                    2               2
    envios                   2               2
    cuenta                   2               1
    compatibilidad           1               0
    criterio                 1               0

**Esos tres ceros y ese uno son el trabajo.** El banco los nombra uno por uno
al final de la corrida.

---

## 3. LAS TRES FALLAS NO SON LA MISMA COSA, y ahi esta el trabajo real

### 3.1 `criterio` — ES desalineacion de tablero. Se arregla aca.

"Me sirve para diseño grafico" fue a filtrar el catalogo por el campo
`uso_recomendado` en vez de preguntarle a la casa. El hueco de valor lo dejo
escrito: *la fuente no escribe 'diseño grafico' en uso_recomendado*.

**LA CAUSA:** hay DOS caminos para "para que sirve". Un campo del catalogo que
se llama `uso_recomendado` y vive en el enum, y una boca de la casa que se
llama `criterio`. El modelo eligio el que estaba en el enum.

Es exactamente la consigna del punto 1, rota.

### 3.2 `compatibilidad` y `cuenta` — NO son desalineacion. Son DOS PASOS.

Las dos consumen un id CERTIFICADO, que es la regla 10.0 y no se toca. El
modelo no tiene ese id en la primera vuelta: tiene que buscar, recibir el id, y
recien ahi pedir la boca.

Medido: "el teclado K380 anda con mi PS5" hizo el paso uno bien —busco el
K380— y volvio `ambiguo`. Ahi se quedo, que ante un ambiguo es lo correcto.

**Ordenar el tablero NO arregla esto.** Lo que hay que decidir es otra cosa:
como se pide una boca que necesita un id que todavia no existe.

**DECIDIDO EL 15-sep, Y YA CORRE EN LAS DOS BOCAS: certifica el codigo,
adentro.** El modelo escribe el nombre que uso el cliente y la boca lo resuelve
con el mismo certificador de identidad. La regla 10.0 no se toca: lo que cambia
es QUIEN certifica, no si se certifica. La vara no es la misma en las dos, y la
diferencia es la plata: la compatibilidad puede contestar sin elegir cuando los
candidatos dan el mismo veredicto, la cuenta no puede, porque cada candidato
tiene su precio. Ahi un nombre que pega con mas de uno vuelve `sin_total` con
la repregunta.

---

## 4. LO QUE YA SE DECIDIO Y NO SE VUELVE A DISCUTIR

**LOS VEINTE MOLDES SALEN DE LAS VUELTAS DE BUSQUEDA.** Decision de Martin,
15-sep. Pesan 1.036 tokens y viajan en las tres vueltas; en la vuelta de buscar
no se decide como suena la respuesta, asi que ahi no pertenecen.

Y no es solo costo: INDUCEN. Las tres fallas del punto 3 tienen la misma forma
—el modelo elige un tipo y despues declara los campos que ese tipo sugiere—, y
al pedido con reparto 70/30 le puso `identidad_ambigua`.

La simetria ya existe del otro lado: el tablero desaparece en la vuelta de
contestar. Los moldes tienen que desaparecer en las de buscar.

**EL ESQUEMA DE RESPUESTA SE QUEDA EN LAS TRES.** Es otra cosa que los moldes:
el esquema OBLIGA el formato, los moldes enseñan la prosa. Medido el 12-sep:
sin esquema el modelo contestaba en markdown y el tipo salia vacio en tres de
cada cuatro turnos.

---

## 5. EL OTRO DEFECTO ABIERTO, que no es del tablero

**EL PROMPT SE CONTRADICE SOBRE LA PLATA.** `respuesta._REGLAS` dice "el precio
es el UNICO numero de plata que podes escribir" y seis renglones despues dice
que el total de la cuenta "lo copias igual que un precio". Y despues amenaza:
"cualquier cifra que no salga de una ficha o de esos dos huecos tira la
respuesta entera abajo".

El total de la cuenta no es una ficha ni un hueco. **El prompt le dice al
modelo que si escribe el total, mata la respuesta.**

Lo escribio esta sesion, el 14-sep, al enchufar la cuenta. Es la enumeracion de
casos lo que se desincroniza: tiene que ser UNA frase —todo numero sale del
retorno o de una ficha, lo demas no sale— y no una lista.

---

## 6. EL ORDEN, y la razon del orden

Un cambio, una corrida del banco. Si se mueven juntos no se sabe cual sirvio.

1. **Sacar los moldes de las vueltas de busqueda.** Es el punto 4, ya decidido.
   Contesta si el 81% se mueve y si las 2,65 vueltas bajan.
2. **Cerrar el doble camino de `criterio`.** Es el punto 3.1.
3. **Sacar la contradiccion de la plata.** Es el punto 5.
4. **Decidir el dos pasos.** Es el punto 3.2. Decidido y hecho el 15-sep en
   las dos bocas: compatibilidad y cuenta certifican adentro.
5. **Que el tablero hable el idioma de la fuente campo por campo.** Es el punto
   1 aplicado a la leyenda: los ocho campos de si o no dejaron de enumerar su
   prosa —19 formas de decir que algo tiene bluetooth— y dicen las dos palabras
   que el motor compara. La lista de lo que falta mirar de este paso no es
   otra: es la misma corrida del banco.
