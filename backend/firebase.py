import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("firebase_config.json")  # this is the service account file
firebase_admin.initialize_app(cred)

db = firestore.client()
doc = db.collection("users").document("test").get()
data = doc.to_dict()
print(data)
