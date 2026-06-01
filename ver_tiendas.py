from google.cloud import firestore
db = firestore.Client(project="memory-engine-v1")
print("Tiendas:")
for doc in db.collection("tiendas").stream():
    print(" -", doc.id)
    print("   datos:", doc.to_dict())
