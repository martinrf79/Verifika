"""Condiciones vagas del cliente -> el campo de la fuente que las responde. Lo correcto se escribio ANTES de correr."""
import json, os, sys
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from fuente import FUENTE, llamar, REPO
SPECS = json.load(open(os.path.join(REPO, "data/clientes/verifika_prod/specs_preguntables.json")))["specs"]
CAMPOS = {s["id"]: s["etiqueta"] for s in SPECS}
CAMPOS.update({"origen": "el pais de fabricacion u origen", "marca": "la marca", "precio": "el precio",
               "color": "el color", "material": "el material", "peso": "el peso", "contenido_caja": "lo que trae la caja",
               "uso_recomendado": "para que uso se recomienda: oficina, gamer, estudio", "dimensiones": "el tamano o las medidas"})
VAGAS = [
    ("teclado con luces psicodelicas", "retroiluminacion"), ("que brille de colores", "retroiluminacion"),
    ("que tenga lucecitas", "retroiluminacion"), ("lo menos de partes chinas posible", "origen"),
    ("que sea yanqui", "origen"), ("nada hecho en china", "origen"), ("que no tenga cable", "conexion"),
    ("sin cablerio", "conexion"), ("que se conecte al celu", "bluetooth"), ("que aguante la lluvia", "resistencia_agua"),
    ("que dure todo el dia sin enchufar", "bateria"), ("que no se descargue rapido", "bateria"),
    ("para la oficina", "uso_recomendado"), ("para jugar al fortnite", "uso_recomendado"), ("para mi hijo que estudia", "uso_recomendado"),
    ("liviano para llevar", "peso"), ("que no pese nada", "peso"), ("chiquito que entre en la mochila", "dimensiones"),
    ("de las teclas que hacen clic", "switch_teclado"), ("teclas mecanicas rojas", "switch_teclado"),
    ("pantalla que vaya fluida para jugar", "hz"), ("que se vea nitido, bien definido", "resolucion"),
    ("que pueda tocar la pantalla", "tactil"), ("que se desbloquee con el dedo", "lector_huella"),
    ("para hacer zoom con la cara", "camara"), ("que le pueda meter mas memoria despues", "ram_ampliable"),
    ("que tenga lugar para muchas fotos", "almacenamiento"), ("que no se rompa al toque, que tenga respaldo", "garantia"),
    ("que suene fuerte", "potencia"), ("que traiga el cable y todo", "contenido_caja"), ("barato pero que no sea trucho", "precio"),
    ("de aluminio, no de plastico", "material"), ("que agarre bien el wifi del 5g", "wifi"), ("que mueva juegos pesados", "memoria_video"),
]
if __name__ == "__main__":
    res = []
    for rep in range(3):
        q = {f"v{i}": {"type": "choice", "criteria": CAMPOS, "instructions": f"El cliente pide: «{v}». Que dato del catalogo responde esa condicion?"} for i, (v, _) in enumerate(VAGAS)}
        a = llamar({"state": FUENTE, "model": "jev-latest", "questions": q})["answers"]
        res.append(a)
    for i, (v, g) in enumerate(VAGAS):
        cs = [(r[f"v{i}"]["choice"], r[f"v{i}"]["confidence"]) for r in res]
        top3 = [k for k, _ in sorted(res[0][f"v{i}"]["probabilities"].items(), key=lambda kv: -kv[1])][:3]
        print(f"{'OK ' if cs[0][0]==g else ('t3 ' if g in top3 else 'MAL')} «{v}» oro {g} | Jev {[c for c,_ in cs]} conf {[round(x,2) for _,x in cs]} top3 {top3}")
    print("top1", sum(res[0][f"v{i}"]["choice"] == g for i, (_, g) in enumerate(VAGAS)), "de", len(VAGAS),
          "| top3", sum(g in [k for k, _ in sorted(res[0][f"v{i}"]["probabilities"].items(), key=lambda kv: -kv[1])][:3] for i, (_, g) in enumerate(VAGAS)),
          "| iguales en 3 reps", sum(len({r[f"v{i}"]["choice"] for r in res}) == 1 for i in range(len(VAGAS))))
