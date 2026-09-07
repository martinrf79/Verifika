# FICHA 49 — La obligación muda, el universal sin herramienta, y la política que no era política

Esta es la orden de trabajo. Sale de leer las charlas REALES del 3 y 4 de
septiembre por el puente de producción, issue 31, no de leer código a ojo.
Los tres defectos se reprodujeron offline antes de escribirse. La vara ya
está puesta: `tests/test_plan_de_la_obligacion.py`, seis rojos y un verde
de contracara.

**Los números viven en `MAPA_CABLEADO.md`, sección 4: D13, D14 y D15.**
Acá va el relato y la orden; los nombres no se duplican.

Piso medido antes de tocar nada, 6-sep-2026:

```
python3 -m pytest -q
```

```
python3 banco_pruebas/oro.py
```

493 verdes y 1 xfail en la batería; 48 de 65 en el banco, con capa 2 en 33
de 40, capa 4 en 0 de 10 y capa 5 en 15 de 15. Con esta ficha la batería
pasa a 494 verdes y 7 xfail, y los dos números de arriba no se mueven.

---

## Por qué estas tres y no las del orden que ya estaba escrito

`FORMULARIO_V2.md` sección 6 manda el orden de la arquitectura: primero D2,
la vara de la capa 4; después el hueco 4; después el hueco 1. **Ese orden
sigue en pie y esta ficha no lo cambia.**

Lo que pasa es que las tres de acá no son arquitectura: son tres cosas que
el cliente ya está leyendo mal en el teléfono, hoy, y las tres se arreglan
sin decidir nada grande. D13 es una línea. D14 es una guarda que ya existía
y se apagó sin reemplazo. D15 es un molde de texto.

La prioridad uno del repo dice que el bot vende y no alucina, y que si no
sabe lo dice o repregunta. Las tres de acá rompen esa frase por los tres
lados a la vez: una obligación que no sale, una afirmación sin evidencia, y
un "no sé" mal escrito.

---

## D13 · La línea obligatoria de que es un bot no sale nunca

**Estación T9.1 y T9.2, `turno._obligaciones`.**

`turno.py:984` llama `gs.con_saludo_inicial(texto, negocio, tienda_id)`, con
tres argumentos. `guardas_salida.py:136` la define
`con_saludo_inicial(respuesta, business_name)`, con dos. En el primer turno
de cada charla eso levanta `TypeError`, el `except` de abajo lo convierte en
un `warning` y el turno sigue como si nada.

Lo que se pierde es la obligación entera: el cliente nunca lee
`¡Hola! Soy el asistente automático de Verifika Tech.` Lo que lee es el
saludo que escribió el modelo por su cuenta.

Medido en producción el 3-sep a las 17:37:17 UTC, turno `tg_524215785`:

```
turno_guarda_error  error=TypeError: con_saludo_inicial() takes 2 positional arguments but 3 were given
```

Y en la charla del puente, ese mismo turno empieza con
`Hola, te comento como trabajamos en Verifika Tech.` Sin el aviso.

**Lo amargo es que este defecto ya se arregló una vez.** El comentario que
está justo arriba de la línea cuenta el arreglo del 3-sep, cuando la que
fallaba era `asegurar_honestidad_bot`. Se corrigió esa y se rompió la de al
lado, en el mismo bloque y el mismo día, porque **nada mide ese bloque**. Un
solo `try` alrededor de tres obligaciones significa que la primera que se
cae apaga a las que vienen abajo, y afuera no se nota.

Por eso la vara son dos tests y no uno: el primero exige la línea, el
segundo exige que llamar a las obligaciones no levante `TypeError`. El
segundo es el que evita la tercera vuelta de lo mismo.

Es una línea de código, y el bloque merece un `try` por obligación.

## D14 · Un universal sobre el catálogo sale sin que ninguna herramienta lo mire

**Estación T8.2, la poda de `tabla._limpiar`.**

Medido el 3-sep a las 17:38:51 UTC, turno `tg_524215788`. El cliente
preguntó `que producto tienen en mas de 5 tipos`. El log dice
`busquedas_derivadas` con `hechas=[]`: ninguna herramienta miró el catálogo.
El cliente leyó:

```
Actualmente, no contamos con ningun producto que disponga de mas de 5
variantes o tipos diferentes en nuestro catalogo.
```

Es una afirmación categórica sobre los 880 productos, escrita por el modelo,
sobre una fila `sin_material`. Y dos renglones más abajo, en el mismo
mensaje, el bot dice que no tiene el dato. **Afirma y se desdice en el mismo
mensaje.** Para un producto que se vende como anti-alucinación, éste es el
peor renglón posible.

La guarda que cazaba exactamente esto —`hub_venta_afirmo_sobre_el_catalogo`,
hoy en `archivo/plomeria_apagada/salida.py:844`— se apagó con el hub el
3-sep. **No la reemplazó nadie**, y la poda de hoy corta plata sin respaldo,
id interno, JSON filtrado y cifra en fila sin material: ninguna de las
cuatro ve un universal en prosa.

La regla que se pide es la misma que ya rige para la plata, y por eso no
inventa doctrina nueva: **una casilla sin material no afirma, dice que no
sabe.** El texto que hoy sale entero se poda, y la pregunta del punto queda,
que es lo único honesto que había en ese mensaje.

Lo que NO se hace: perseguir prosa con una lista de frases. Eso ya fracasó y
está contado en `archivo/README.md` —fueron 4 nodos, después 18, después 46—.
La condición es de ESTADO, no de vocabulario: la fila no tiene material y la
llamada no se hizo. La frase se mira sólo para saber si es una afirmación
sobre el conjunto, no para adivinar el tema.

## D15 · La pregunta que escribe el código llama política a una pregunta del cliente

**Estación T8.3, `tabla._pregunta_del_codigo`.**

Mismo turno. Cuando el punto quedó abierto, la compuerta escribió:

```
Sobre la politica de que producto tienen en mas de 5 tipos no tengo el
dato confirmado. Me lo precisas un poco?
```

La fila `temas` trae su `pregunto` armado como `la politica de ` más la frase
cruda del cliente. Cuando el modelo declaró como tema algo que no es una
política de la casa sino una pregunta sobre el catálogo, el molde genérico
pega la frase entera y sale eso.

El archivo lo dice él mismo, dos moldes más arriba: pegar el renglón crudo
`es exactamente el riesgo de que el codigo arme prosa`. Ya se corrigió para
`restricciones`, para `stock`, para `pide_precio` y para `reparto_pago`. El
molde genérico quedó sin corregir y es al que caen los `temas`.

**La contracara está escrita y nace verde**: cuando el punto SÍ es una
política de la casa —`la politica de garantia`— decir su nombre es lo
correcto y no se toca. El arreglo no puede volver mudo el caso legítimo.

---

## Cómo se verifica

1. `python3 -m pytest -q` verde. Las marcas `xfail` de lo que la sesión
   cierra se sacan en el mismo commit: `strict=True` obliga.
2. `python3 banco_pruebas/oro.py` no baja de 48 de 65.
3. El piso de las 15 charlas no baja.
4. `app/` no importa `archivo/`.
5. Después del deploy, una charla real por WhatsApp que arranque de cero:
   el primer mensaje tiene que traer la línea del asistente automático, y en
   los logs no puede aparecer `turno_guarda_error`.

## Qué NO se hace en esta ficha

No se toca `certificar_temas` ni el ruteo a FAQ: eso es D7 y tiene su propia
decisión. No se toca la fuente. No se reescribe ningún caso de oro. No se
sube un umbral para que un test pase. No se cambia el orden de
`FORMULARIO_V2.md`: D2, hueco 4 y hueco 1 siguen siendo la ficha grande y
ésta no se mete ahí.

Y una que importa: **arreglar D14 no es meterle una lista de frases
prohibidas al mensaje.** Si el arreglo empieza a crecer en vocabulario, está
mal y hay que volver a la condición de estado.

---

## Bloque para pegar al abrir la sesión que implementa

```
Repo: github.com/martinrf79/Verifika, rama main.
git fetch origin main && git checkout main && git status.
Si HEAD no es origin/main: arbol limpio y fast-forward posible ->
git pull --ff-only origin main y segui. Si el arbol esta sucio, hay
commits locales que no estan en origin, o no hay fast-forward: PARA y avisa.
Lee SOLO: CLAUDE.md bloque 0, arquitectura/FICHA_49_la_obligacion_muda.md,
arquitectura/MAPA_CABLEADO.md seccion 4.
Corre pytest -q y banco_pruebas/oro.py y anota los dos numeros.
Prioridad uno: el bot vende y no alucina. Si no sabe, lo dice o repregunta.
ESTA SESION ES LA FICHA 49: D13, D14 y D15. Nada mas.
La vara es tests/test_plan_de_la_obligacion.py y NO se afloja.
No se deposita grasa. No se toca certificar_temas. No se toca data/clientes.
Si el piso de las 15 charlas baja, revert.
PUSHEA a main. Toca app/: pedi el OK del push una vez, al final.
Nada de ramas.
```
