# DECISIONES

Una decision por linea, con su motivo en una frase. **La discusion no se guarda,
solo lo decidido.** Si una decision cambia, se tacha con su fecha y se escribe la
nueva abajo: no se borra, para que se pueda leer por que se cambio de idea.

Este archivo es corto a proposito. Si crece mas de dos pantallas, algo se esta
escribiendo aca que deberia ser un test.

---

## 19-ago-2026 — La arquitectura del turno

Todas salen de lo medido en `PASO0_CENSO.md`. Ninguna es una preferencia.

1. **La llamada UNO solo DECLARA; el codigo deriva las busquedas.** El modelo
   deja de elegir herramientas. Motivo: en el 57% de los turnos lo declarado y lo
   buscado no coinciden, y toda la etapa de reposicion existe para parchear esa
   diferencia. Sin dos versiones de la intencion, no hay nada que reconciliar.
2. **El esquema que ve el modelo baja de 25.230 a ~3.046 bytes**, efecto directo
   de la 1. Se cancela el prefiltro de temas por turno: el ahorro ya no hace
   falta y el prefiltro era superficie nueva que podia comerse un tema.
3. **El turno tiene un CONTRATO: los puntos, cada uno con un estado terminal.**
   RESUELTO, AMBIGUO (repregunta), NO SE SABE, CONFLICTO. El turno no sale si un
   punto quedo sin estado. `indice_turno` ya lo calcula y hoy se tira en un log.
4. **Los tipos de punto pasan de 6 a 10.** Faltan ATRIBUTO, STOCK,
   COMPATIBILIDAD y POLITICA: hoy una pregunta informativa no abre ningun punto,
   asi que la cobertura es ciega justo donde mas se alucina.
5. **Un solo escritor del texto.** Un invariante violado no se parchea: se
   rechaza y se vuelve a redactar UNA vez con la violacion como aviso; si falla
   de nuevo, sale un texto determinista. Motivo: 13 mutadores encadenados que no
   se conocen produjeron los dos bugs registrados.
6. **La verificacion es bidireccional y se mide sobre el texto que ve el
   cliente.** COBERTURA (todo punto tiene renglon) mata la omision; PROCEDENCIA
   (todo dato viene de un punto resuelto) mata la invencion. Las dos reemplazan a
   los 13 candados.
7. **Una sola puerta de busqueda.** `buscar_productos`, `consultar_catalogo`,
   `ficha_producto` y `ver_compatibilidad` leen el mismo catalogo cambiando la
   proyeccion. El motor de busqueda ya esta escrito en `filtros_catalogo`.
8. **La cuenta sube a la etapa de resolucion.** `_cuenta_con_lo_declarado`
   interviene en el 44% de los turnos: no es un parche de salida, es la
   resolucion del punto `precio` puesta en el lugar equivocado.
9. **`registrar()` en las seis etapas, no solo en salida.** Sin esto el censo hay
   que rehacerlo a mano cada vez.

## 19-ago-2026 — La prosa de venta

10. **Se cierra lo PROHIBIDO, no lo permitido.** Enumerar lo que el bot puede
    decir es infinito; enumerar lo que no puede decir nunca es finito y chico.
    Arrays cerrados de prosa serian el solver de fragmentos que se borro el
    2-ago.
11. **Cuatro niveles de atadura:** enum (que puede nombrar) · bloque sellado (lo
    que afirma plata o politica vuelve YA ESCRITO del codigo y se pega) · ancla
    por afirmacion (toda oracion que afirma algo apunta a un punto resuelto; los
    conectores y las preguntas son libres) · lista de lo prohibido.
12. **Si una regla tiene test, SALE del prompt.** Una regla en dos lados diverge.
    El prompt del redactor queda para lo unico que el modelo aporta: quien sos,
    como hablas, como vendes.
13. **El prompt se parte en dos:** nucleo del motor (invariable, en codigo) y
    persona de la tienda (en la fuente, editable por cliente).

## 19-ago-2026 — Que el bot venda

14. **Un punto sin resolver bloquea su renglon, NUNCA el turno.**
15. **Maximo UNA repregunta por turno**, y solo sobre lo que bloquea el cobro:
    identidad, cantidad, destino. Lo demas se dice y se sigue.
16. **Un punto en NO SE SABE jamas frena el cierre.** Y "no se sabe" nunca se
    dice como "no".
17. **Una falla nunca genera una explicacion.** El bot no dice por que no pudo.
    Nace del 429 que hizo que le echara la culpa al catalogo.
18. **El traspaso a humano es un estado terminal, no un fracaso, y se lleva el
    contrato con el.** El humano entra sabiendo; el cliente no repite nada.
19. **FALTA UN NUMERO DE VENTA.** Todo lo que se mide hoy es defensivo: no cae,
    no inventa, no omite. No hay tasa de cierre. Se instrumenta en el diseno.

## 19-ago-2026 — Datos, memoria y modalidades

20. **El bot pide el NOMBRE y nada mas.** Ni DNI, ni CUIT, ni tarjeta, ni el CBU
    del cliente: eso es de la pasarela. Lo que no se pide no viaja al proveedor
    del modelo, asi que el problema desaparece por diseno y no por politica.
21. **La memoria crece por el lado DURO, nunca por el blando.** Mas turnos vivos
    cuesta lineal en todos los turnos y rinde poco; el carrito y los vistos
    cuestan nada. "Memoria mas larga" se vende como CONTRATOS GUARDADOS, no como
    mas texto en el prompt.
22. **Tres modalidades, un solo motor.** LEAD, VENTA y POSVENTA no cambian el
    turno: cambian que familias de punto se habilitan y cual es el cierre.
23. **El cobro es un ADAPTADOR, nunca una rama.** Un solo lugar devuelve los
    datos de pago; hoy demo, manana un link real.
24. **Imagenes: entra la DESCRIPCION, no la imagen** (mismo patron que
    `transcriber.py` con el audio). Y **de una imagen sale una CONSULTA, nunca
    una AFIRMACION**: el reconocimiento produce un termino de busqueda y el
    codigo certifica.

## 19-ago-2026 — El motor multi-tienda

25. **El motor no puede contener ni un dato ni una politica de ninguna tienda.**
26. **Los prompts salen del codigo a la fuente.** Estaba como decision pendiente
    de Martin; deja de ser opcional, porque un prompt en el codigo es una tienda
    adentro del motor.
27. **Una tienda declara SEIS cosas:** catalogo, politica, dinero, logistica,
    persona y modalidad. Las tres primeras ya existen; las otras tres estan
    repartidas entre configuracion y codigo.
28. **El importador devuelve un INFORME DE HUECOS**, y eso es el producto: que
    campos faltan, que temas se pisan, que productos no se distinguen. Es lo que
    convierte semanas en horas: el trabajo no desaparece, se deja de descubrir
    por accidente.
29. **LA TIENDA CERO es el semaforo.** Una segunda tienda de otro rubro, 20
    productos, adentro del repo, y dos tests: que `app/` no mencione
    `verifika_prod`, y que conteste sus charlas sin tocar una linea de Python.
30. **Se vende "cualquier ecommerce con catalogo", NO "cualquier nicho".** Un
    seguro o un credito no traen un candidato: arman un calculo. Es otro producto.

## 19-ago-2026 — Como se trabaja

31. **El plan se entrega como TESTS ROJOS, no como prosa.** Un paso escrito en
    prosa es un pedido; un paso escrito como test rojo es un mecanismo.
32. **El test lo escribe OTRO, y el que implementa no lo puede modificar para que
    pase.** Mata el punto ciego compartido, que este repo ya documento.
33. **Todo test entra en ROJO y hay que verlo rojo.** Un test que nace verde es
    sospechoso: o no prueba nada, o la cosa ya estaba hecha.
34. **El test afirma sobre CUANTOS casos paso, no solo que paso.** El CI llamaba
    a los casetes con `|| true` y estuvo en verde cinco dias sin correr nada.
35. **El test se escribe sobre lo que ve el CLIENTE**, no sobre el mecanismo.
36. **La mitad de los tests son sobre lo que NO puede pasar.** Un banco donde el
    cliente siempre se porta bien mide amabilidad, no robustez.
37. **Ni la cantidad de tests ni la de casos pueden bajar**, y un test no se
    borra ni se saltea sin dejar el motivo escrito.
38. **El corte se hace JUNTO, no de a una pieza.** Estan acopladas: cortarlas de
    a una hace que cada corte perturbe a las otras, y ya paso dos veces.
39. **Regla del 10%:** son 23 nodos entre salida y reposicion. Si al cortarlos
    hay que reponer dos o tres, se corto bien. Si no hay que reponer nada, se
    corto poco.
40. **`banco_pruebas/` y `reserva/` NO deployan.** Estan en `.gcloudignore`, no
    entran a la imagen y no pueden afectar produccion.
