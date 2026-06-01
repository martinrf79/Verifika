from google.cloud import firestore
db = firestore.Client(project="memory-engine-v1")

print("Documento tienda_principal:")
doc = db.collection("tiendas").document("tienda_principal").get()
print(" existe:", doc.exists)
if doc.exists:
    print(" datos:", doc.to_dict())

print("")
print("Productos en tienda_principal:")
prods = db.collection("tiendas").document("tienda_principal").collection("productos").limit(3).stream()
count = 0
for p in prods:
    count += 1
    print(" -", p.id)
    print("   datos:", p.to_dict())
print(" total mostrados:", count)
