from google.cloud import firestore
db = firestore.Client(project="memory-engine-v1")
print("Colecciones raiz:")
for col in db.collections():
    print(" -", col.id)
