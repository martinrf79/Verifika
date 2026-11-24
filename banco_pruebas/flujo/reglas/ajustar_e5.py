"""AJUSTA multilingual-e5-small CON LOS PARES DE datos_e5.py (24-nov-2026). Corre en el entorno aparte.

    E5=<carpeta del modelo base> venv/bin/python ajustar_e5.py      # ajusta y guarda en SALIDA
Mide antes y despues, sobre los alias apartados: si el documento correcto es el mas cercano entre todos.
"""
import json, os, random, sys, time
import numpy as np, torch
from sentence_transformers import InputExample, SentenceTransformer, losses, models
from torch.utils.data import DataLoader

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ["E5"]
SALIDA = os.environ.get("SALIDA", os.path.join(AQUI, "e5_ajustado"))
torch.set_num_threads(4)
D = json.load(open(os.path.join(AQUI, "pares_e5.json")))
q = lambda t: "query: " + t


def cargar(ruta):
    if os.path.exists(os.path.join(ruta, "modules.json")):
        return SentenceTransformer(ruta, device="cpu")
    tr = models.Transformer(ruta, max_seq_length=64)
    return SentenceTransformer(modules=[tr, models.Pooling(tr.get_word_embedding_dimension(), "mean"), models.Normalize()], device="cpu")


def medir(m, nombre):
    docs = D["docs"]
    dv = m.encode([q(x) for x in docs], normalize_embeddings=True, batch_size=64)
    av = m.encode([q(a) for a, _ in D["holdout"]], normalize_embeddings=True, batch_size=64)
    ok = sum(docs[int(i)] == d for i, (_, d) in zip((av @ dv.T).argmax(1), D["holdout"]))
    print(f"{nombre}: alias apartados con su documento primero {ok} de {len(D['holdout'])}", flush=True)


m = cargar(BASE)
medir(m, "sin ajustar")
ej = [InputExample(texts=[q(a), q(d)]) for a, d in D["train"]]
random.Random(2411).shuffle(ej)
dl = DataLoader(ej, shuffle=True, batch_size=32)
t = time.time()
m.fit(train_objectives=[(dl, losses.MultipleNegativesRankingLoss(m))], epochs=4, warmup_steps=20, show_progress_bar=False)
print(f"ajuste en {time.time() - t:.0f} s")
medir(m, "ajustado")
m.save(SALIDA)
