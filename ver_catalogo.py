from google.cloud import firestore
db = firestore.Client(project="memory-engine-v1")
docs = db.collection("tiendas").document("tienda_principal").collection("catalogo").limit(3).stream()
for doc in docs:
    print("ID:", doc.id)
    print("Datos:", doc.to_dict())
    print("---")
