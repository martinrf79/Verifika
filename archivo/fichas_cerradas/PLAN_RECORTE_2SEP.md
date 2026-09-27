# PLAN DE RECORTE — 2-sep-2026 — instrucciones ejecutables

Escrito para que lo ejecute Claude Code, Grok o cualquier IA, paso por paso.
Cada paso cierra con la bateria en verde, un commit y el numero que lo mide.
La red es git: cada paso es un commit propio y se revierte entero.

Objetivos que mandan, en este orden:
  1.  Demo Verifika: vende, no alucina, repregunta ante la duda.
  1b. Motor multitienda: una tienda nueva es una carpeta en data/clientes/
      con catalogo, FAQ, tarifas y voz, cero lineas de Python.

Regla del recorte: no se borra nada. Lo apagado va a archivo/, lo que se
puede reenchufar va a reserva/. Los dos tienen candado en tests/.

---

## LO MEDIDO ANTES DE EMPEZAR (2-sep-2026, commit 4effb96)

    app/          23.020 lineas en 49 archivos
                  11.686 de codigo, 11.334 de comentarios y docstrings (49%)
                  573 funciones, 540 corren en el turno vivo, 33 no (~200 lineas)
    tests/        105 archivos, 1,0 MB, 1209 pasan + 14 xfail en 2m50s
    banco_pruebas 54 archivos, 1,0 MB
    data/         3,3 MB, de los cuales 29 archivos sin ninguna referencia
    docs .md      270 KB en la raiz

Conclusion medida: en app/ NO hay codigo muerto que mover. El 94% de las
funciones corren en cada turno. Lo que hace grande e ilegible al repo es
(a) la prosa dentro de app/, (b) los instrumentos y documentos alrededor,
y (c) el diseño del turno con muchas piezas, que es el recorte de fondo.

---

## PASO 1 — HECHO Y EN MAIN. No se repite.

Se ejecuto el 2-sep en un clon de Cowork y el push no fue posible desde esa
sesion, asi que quedo aca como paso a repetir. **Ya se repitio con `git mv` y
esta en main**: que se movio y a donde lo dice `archivo/README.md`, que es el
unico lugar donde eso vive. La bateria dio igual antes y despues. Sin tocar
`app/`.
  - 5 instrumentos de banco_pruebas  -> archivo/instrumentos/
    (banco_atado_charlas, charla_sim, duelo_interprete, fiscalizador, peso_reposicion)
  - 3 scripts a mano                 -> archivo/scripts_viejos/
    (planilla_specs, planilla_compatibilidad, generar_embeddings)
  - 29 archivos de data/             -> archivo/datos_viejos/
    (todo lo que no es data/clientes/ ni data/geo/)
  - 3 apuntes .md                    -> archivo/documentacion/
    (APUNTE_ANTES_FICHA17, APUNTE_DESPUES_FICHA17, SONDA_OFERTA_APUNTE_25ago2026)
  - 4 presets config/*.env           -> archivo/config_viejo/
Efecto colateral bueno: la imagen de Docker deja de llevar 250 KB de bancos
viejos, porque el Dockerfile copia data/ entera.

---

## PASO 2 — HECHO Y EN MAIN. Una sola puerta al modelo.

Se ejecuto el 2-sep. `cierre.extraer_datos_cliente` usa `hub_venta._cliente`.
`llm_adapter.py` y el zoologico de providers de `config.py` quedaron en
`archivo/`. El casete intercepta esa unica puerta. Toca `app/`: el push
deploya.

---

## PASO 3 — LA PROSA A UNA LINEA. Zero comportamiento

Que hay hoy: 11.334 lineas de comentarios y docstrings en app/. Son la
historia de cada arreglo, contada en tres parrafos. CLAUDE.md ya hizo este
mismo recorte consigo mismo: "la regla esta entera; lo que se comprimio es el
cuento. Si algo hace falta, git log lo tiene."

Regla del corte, archivo por archivo, empezando por los cinco mas pesados
(herramientas 991, indice_turno 954, salida 854, mensaje 690, resolver 598):
  - Un docstring queda con su PRIMER parrafo: que hace y que garantiza.
  - Un bloque de comentario de mas de 4 lineas queda en 1 o 2: la regla,
    sin la fecha ni la charla que la origino. Si nombra un test, se deja
    el nombre del test.
  - No se toca ninguna linea de codigo. `git diff --stat` tiene que mostrar
    solo borrados en lineas que empiezan con `#` o estan dentro de """ """.
  - Candado: antes y despues, `python3 -c "import ast,sys;..."` que compare
    el AST de cada archivo sin docstrings tiene que dar identico. Escribirlo
    como `tests/test_prosa_no_cambia_codigo.py` con el hash del AST.
  - Bateria en verde despues de cada archivo. Un commit por archivo.

Numero que lo mide: app/ de 23.000 a unas 14.000 lineas. Una sesion nueva lee
el motor entero por la mitad de tokens.
Riesgo: nulo para el bot; el riesgo es perder un motivo. Por eso primer
parrafo y no borrado total, y por eso git lo conserva.

ESTE PASO NO SE HACE SIN QUE MARTIN LO DIGA: es borrar texto, aunque git lo
guarde.

---

## PASO 4 — EL MOTOR: de siete etapas a cinco. Necesita la clave paga

Es el recorte de fondo, el de PLAN_RECORTE.md y DECISIONES.md, y NO se puede
validar offline: la bateria replica casetes grabados, y un cambio en el
prompt o en las puertas cambia lo que el modelo escribe. Se mide con
`banco_pruebas/objetivo.py --vivo` (peor caso sobre seis redacciones) y con
las 15 charlas grabadas regrabadas.

El turno hoy (hub_venta.procesar_venta):
  1 decisor (llamada uno, registrar_pedido)
  2 resolver (derivar busquedas, cuenta, contrato)
  3 redactor (llamada dos)
  4 salida: procedencia, plata
  5 cierre y cobro (leads)
  6 salida: obligacion
  7 salida: higiene
  + memoria y el indice final

Lo que sobra por diseño, en orden de riesgo creciente:
  4a. Las cuatro puertas de salida (salida.py, 1650 lineas) se quedan en DOS:
      PLATA (todo peso viene de la calculadora, el bloque se pega entero) y
      PROCEDENCIA (atadura_prosa: cada dato con su id, lo que no cierra se
      poda). OBLIGACION queda solo con las dos obligaciones legales -aviso de
      bot y saludo- y el camino al cobro; HIGIENE queda con las dos reglas que
      se disparan de verdad (renglon repetido, bloque repetido del turno
      anterior). Lo demas -> archivo/salida_20260902.py.
      Vara: peor caso de objetivo.py no baja de 75; largo maximo no sube.
  4b. El grafo (app/verifika/grafo.py, 810 lineas) deja de envolver cada
      pieza y queda como UNA linea de log por etapa con su veredicto. Las
      funciones censo/barribles se van con los barridos que las leen a
      archivo/. Vara: hub_venta_ok sigue logueando etapas_ms y veredicto.
  4c. indice_turno (1738 lineas) se queda con los diez tipos de punto y los
      cuatro estados terminales; sale todo lo que reescribe o repone texto.
      La cobertura corre UNA vez antes de redactar y UNA vez sobre el texto
      final solo como log. Vara: `puerta_cobertura` no empeora en las 15
      charlas.
  4d. Recien con 4a-4c en verde: la repregunta obligatoria ante AMBIGUO y
      CONFLICTO como texto sellado del codigo (ya empezada en la FICHA 45),
      y el aviso de lead fuerte disparado por la pregunta de confirmacion,
      que es lo que Martin pidio.

Cada sub-paso: un commit, deploy, una tanda de objetivo.py --vivo con la
clave paga (Martin la exporta en su Cloud Shell, nunca se pega en el chat),
y revert entero si el peor caso baja.

NOTA (2-sep, tarde): este paso 4 queda SUPERADO por `BRIEF_MOTOR_V2.md`, que
en vez de recortar pieza por pieza escribe el turno nuevo en un archivo y mide
por capa con casos de oro. Se deja como referencia de que sobra y por que.

---

## PASO 5 — MULTITIENDA: el semaforo primero

Antes de portar nada: una segunda tienda de OTRO rubro adentro del repo,
`data/clientes/ferreteria_demo/` con 20 productos y 10 temas de FAQ, y dos
tests que HOY van a fallar y dicen la lista real de fugas:
  - `app/` no menciona `verifika_prod` ni ninguna categoria de electronica.
  - la tienda cero contesta 5 charlas grabadas sin tocar una linea de Python.
Lo que rompa es la lista de trabajo, medida y no supuesta. Las fugas ya
conocidas: `_INSTRUCCION_UNO/_DOS` en hub_venta, `geo_cp` clavado a
Argentina, y la politica de negocio (descuentos, umbrales, reparto de pago)
en calculadora.py y pago.py, que tiene que salir a `base_conocimiento.json`.

---

## COMO SE VUELVE ATRAS

    git log --oneline -8          # cada paso es un commit "Recorte N"
    git revert <hash>             # deshace ese paso solo, sin tocar los otros
