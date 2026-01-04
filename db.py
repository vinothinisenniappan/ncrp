import os
from pymongo import MongoClient

MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("DB_NAME", "ncrp_database")

def get_db():
    if not MONGODB_URI:
        raise RuntimeError("MONGODB_URI not configured")

    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=5000
    )
    client.admin.command("ping")  # force connect
    return client[DB_NAME]
