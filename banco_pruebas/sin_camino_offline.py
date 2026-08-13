"""
LAS QUE NO PUEDEN CORRER OFFLINE — declaradas una por una, con su motivo.

POR QUE EXISTE (Martin, 13-ago-2026): *"el problema que hay es las cosas a
medias o las cosas sueltas... entiendo que no se puede hacer barrido a
funciones del LLM, del modelo. Pero para lo demas, tendria que haber una forma
de organizar para que quede todo ordenado"*.

QUE RESUELVE. La zona ciega del mapa mezclaba dos cosas muy distintas bajo un
mismo numero: codigo al que le falta la prueba, y codigo al que la prueba no se
le puede escribir. Las dos daban "ciega", asi que el numero no se podia bajar ni
leyendolo bien: 27 de 44 no iban a moverse nunca. Un numero que no puede bajar
deja de ser una señal, y peor, tapa al que si importa.

Aca se declara la segunda clase, una por una y con el motivo escrito. Lo que
queda en la zona ciega pasa a ser SOLO trabajo pendiente de verdad.

EL ANTI-TRUCO, y es lo que hace que esto no sea maquillaje.
`tests/test_mapa.py::test_la_lista_de_sin_camino_offline_no_es_un_atajo` mira
las tres formas de hacer trampa con una lista asi:

  1. Una clave que ya NO existe en `app/` queda podrida y nadie se entera: rojo.
  2. Una funcion declarada que en realidad SI la toca una prueba: rojo, y hay
     que sacarla de aca. Que este probada es la buena noticia; esconderla en la
     lista de excusas seria la mala.
  3. Un motivo vacio o de menos de veinte caracteres: rojo. "no se puede" no es
     un motivo, es una excusa.

Y la lista NO baja el piso sola: `mapa_piso.json` sigue guardando la zona ciega
entera. Estas 27 se restan al INFORMAR, no al medir, asi que si mañana alguien
suma una funcion a un conector, el piso la ve igual.

LAS TRES FAMILIAS, y son las tres el mismo caso: la unica forma de ejercitarlas
seria con una credencial y una llamada de verdad, que es justo lo que la
bateria offline no hace ni va a hacer.
"""

# {clave del mapa: motivo}. El motivo se lee, no se saltea: es lo que va a
# mirar la sesion que dentro de tres meses quiera saber por que esto esta aca.
SIN_CAMINO_OFFLINE = {
    # ── EL MODELO. La bateria lo reemplaza por su casete a proposito: si estas
    # corrieran de verdad, el CI saldria a la red, gastaria y seria no
    # determinista. `tests/test_casete_candado.py` ya vigila que la puerta este
    # tapada; que ademas figuren sin ejercitar es la consecuencia buscada.
    "app/verifika/llm_adapter.py:llm_complete":
        "la puerta al modelo; el casete la parchea para que el CI no salga a la red",
    "app/verifika/llm_adapter.py:_get_client":
        "arma el cliente HTTP del proveedor; sin credencial no hay nada que armar",
    "app/verifika/llm_adapter.py:_call_openai_compatible":
        "llamada HTTP real al proveedor compatible con OpenAI",
    "app/verifika/llm_adapter.py:_call_anthropic":
        "llamada HTTP real a Anthropic",
    "app/verifika/llm_adapter.py:_deepseek_thinking_off":
        "apaga el modo pensante de DeepSeek en el cuerpo de la llamada real",
    "app/verifika/llm_adapter.py:_gemini_thinking_off":
        "apaga el modo pensante de Gemini en el cuerpo de la llamada real",
    "app/verifika/llm_adapter.py:_nvidia_thinking_off":
        "apaga el modo pensante de NVIDIA en el cuerpo de la llamada real",
    "app/verifika/llm_adapter.py:_openrouter_reasoning_off":
        "apaga el razonamiento de OpenRouter en el cuerpo de la llamada real",
    "app/core/hub_venta.py:_cliente":
        "la puerta del redactor al modelo; el casete la parchea, ver casete._parchar",
    "app/core/hub_venta.py:_cliente_decisor":
        "la puerta del decisor al modelo; el casete la parchea, ver casete._parchar",

    # ── FIRESTORE. El doble `banco_pruebas/sim_firestore` las reemplaza con el
    # catalogo y la FAQ REALES del repo. Correr las de verdad pediria una base
    # en la nube y credenciales. Lo que si se puede vigilar, y se vigila en
    # `test_el_doble_de_firestore_no_se_despega_del_real`, es que el doble
    # acepte todo lo que acepta el real: si se despegan, los 875 tests estarian
    # midiendo una ficcion.
    "app/storage/firestore_client.py:get_all_faq":
        "lee la FAQ de Firestore; el doble la sirve desde el repo",
    "app/storage/firestore_client.py:get_categories":
        "lee las categorias de Firestore; el doble las deriva del catalogo real",
    "app/storage/firestore_client.py:get_conversation":
        "lee la conversacion de Firestore; el doble la guarda en memoria",
    "app/storage/firestore_client.py:save_conversation":
        "escribe la conversacion en Firestore; el doble valida los mismos tipos",
    "app/storage/firestore_client.py:reset_conversation":
        "borra la conversacion en Firestore; el doble la saca del dict",
    "app/storage/firestore_client.py:already_processed":
        "idempotencia por message_id contra Firestore; el doble la simula igual",
    "app/storage/firestore_client.py:get_tienda_by_phone_id":
        "resuelve la tienda por telefono contra Firestore; sin base no hay tienda",

    # ── EL ALMACENAMIENTO DEL LEAD. Misma clase que las de arriba y se
    # descubrio midiendo, el 13-ago: el mapa las daba por "trabajo pendiente" y
    # resulta que el doble tambien las reemplaza, con leads en RAM. El camino
    # REAL del cierre -`procesar_mensaje_para_lead`, `_finalizar_cierre`, los
    # gatillos y la pregunta suave- corre TAL CUAL y esta probado en
    # `tests/test_cierre_y_cobro.py`; lo que no corre es la coleccion Firestore.
    "app/core/leads.py:crear_lead":
        "escribe el lead en la coleccion Firestore; el doble lo guarda en RAM",
    "app/core/leads.py:actualizar_lead":
        "actualiza el lead en Firestore; el doble lo pisa en el dict de RAM",
    "app/core/leads.py:get_lead_activo":
        "consulta Firestore por el lead vigente; el doble filtra el dict de RAM",
    "app/core/leads.py:descartar_leads_activos":
        "marca descartados en Firestore; el doble los marca en el dict de RAM",
    "app/core/notificador.py:notificar_lead":
        "aviso HTTP saliente al dueño de la tienda; el doble lo anota y no sale",

    # ── LOS CONECTORES. Mandan y reciben HTTP de Meta y de Telegram. Probarlas
    # de verdad pide un token y un telefono; el turno completo ya se prueba por
    # dentro con los casetes, que entran por la funcion del webhook.
    "app/connectors/base.py:send_message":
        "interfaz del conector: manda el mensaje al canal por HTTP",
    "app/connectors/base.py:parse_incoming":
        "interfaz del conector: lee el payload que manda el canal",
    "app/connectors/whatsapp.py:send_message":
        "POST real a la Cloud API de Meta con el token de la tienda",
    "app/connectors/whatsapp.py:download_media":
        "baja el audio o la imagen desde los servidores de Meta",
    "app/connectors/whatsapp.py:get_whatsapp_connector_for_tienda":
        "arma el conector con el token de la tienda, que vive en Secret Manager",
    "app/connectors/telegram.py:send_message":
        "POST real a la API de Telegram con el token del bot",
    "app/connectors/telegram.py:parse_incoming":
        "lee el update que manda Telegram al webhook",
    "app/connectors/telegram.py:download_file":
        "baja el archivo desde los servidores de Telegram",
    "app/connectors/telegram.py:get_telegram_connector":
        "arma el conector con el token del bot, que vive en Secret Manager",
}
