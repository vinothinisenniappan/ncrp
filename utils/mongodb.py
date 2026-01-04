"""
MongoDB utility functions for NCRP Complaint Automation Tool
Handles all database operations
"""

import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from dotenv import load_dotenv

# Explicitly load .env from project root (Windows-safe)
_env_file = Path(__file__).resolve().parent.parent / ".env"
_env_loaded = load_dotenv(dotenv_path=_env_file)

# Debug: Print .env loading status
print(f"[DEBUG] .env file path: {_env_file}")
print(f"[DEBUG] .env file exists: {_env_file.exists()}")
print(f"[DEBUG] load_dotenv() result: {_env_loaded}")

# MongoDB configuration - Defaults to MongoDB Atlas format
# For MongoDB Atlas: mongodb+srv://username:password@cluster.mongodb.net/
# For local MongoDB: mongodb://localhost:27017/
MONGO_URI = os.environ.get("MONGODB_URI", os.environ.get("MONGO_URI", ""))

# Debug: Print what was loaded (masked for security)
_mongo_uri_debug = repr(MONGO_URI)
if MONGO_URI:
    # Mask password in debug output
    if "@" in MONGO_URI:
        parts = MONGO_URI.split("@")
        if len(parts) == 2:
            user_pass = parts[0].split("//")[-1] if "//" in parts[0] else parts[0]
            if ":" in user_pass:
                user, _ = user_pass.split(":", 1)
                _mongo_uri_debug = f"mongodb+srv://{user}:***@{parts[1]}"
print(f"[DEBUG] MONGODB_URI value: {_mongo_uri_debug}")
print(f"[DEBUG] MONGODB_URI length: {len(MONGO_URI) if MONGO_URI else 0}")

DB_NAME = os.environ.get("DB_NAME", "ncrp_database")
COLLECTION_NAME = "complaints"

# Validate that MongoDB URI is provided and not a placeholder
# Only check for actual placeholder strings, not valid Atlas URLs
_is_placeholder = (
    not MONGO_URI or 
    "username:password" in MONGO_URI.lower() or
    MONGO_URI == "mongodb+srv://username:password@cluster.mongodb.net/" or
    "YOUR_USERNAME" in MONGO_URI.upper() or
    "YOUR_PASSWORD" in MONGO_URI.upper() or
    "YOUR_CLUSTER" in MONGO_URI.upper()
)

if _is_placeholder:
    print("WARNING: MONGODB_URI contains placeholder values!")
    print("Please update your .env file with your actual MongoDB Atlas connection string")
    print("Get your connection string from: https://cloud.mongodb.com/")
    print("Format: mongodb+srv://YOUR_USERNAME:YOUR_PASSWORD@YOUR_CLUSTER.mongodb.net/")
    MONGO_URI = ""  # Set to empty so connection will fail gracefully

_client = None
_db = None
_collection = None


def get_mongodb_client():
    """Get MongoDB client (singleton) - Supports both MongoDB Atlas and local MongoDB"""
    global _client
    if _client is None:
        if not MONGO_URI:
            print("ERROR: MONGODB_URI not configured. Please set it in your .env file")
            return None
        
        try:
            # MongoDB Atlas uses mongodb+srv:// which requires TLS
            # Local MongoDB uses mongodb://
            # pymongo handles both automatically
            _client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=10000,  # 10 seconds for Atlas
                connectTimeoutMS=10000,
                retryWrites=True  # Enable retry writes for Atlas
            )
            # Test connection
            _client.admin.command('ping')
            print(f"✓ Successfully connected to MongoDB")
        except Exception as e:
            print(f"✗ MongoDB connection error: {e}")
            print(f"  Connection string format: {'mongodb+srv://' if 'mongodb+srv' in MONGO_URI else 'mongodb://'}")
            print(f"  Please check your MONGODB_URI in .env file")
            _client = None
    return _client


def get_mongodb_db():
    """Get MongoDB database"""
    global _db
    if _db is None:
        client = get_mongodb_client()
        if client:
            _db = client[DB_NAME]
    return _db


def get_complaints_collection():
    """Get complaints collection with unique index"""
    global _collection
    if _collection is None:
        db = get_mongodb_db()
        if db:
            _collection = db[COLLECTION_NAME]
            # Create unique index on Complaint_ID
            try:
                _collection.create_index("Complaint_ID", unique=True)
            except Exception:
                pass  # Index might already exist
    return _collection


def check_duplicate(complaint_id: str) -> bool:
    """Check if Complaint_ID already exists in MongoDB"""
    try:
        collection = get_complaints_collection()
        if not collection:
            return False
        result = collection.find_one({"Complaint_ID": complaint_id})
        return result is not None
    except Exception:
        return False


def save_to_mongodb(complaints: List[Dict]) -> Dict:
    """
    Save complaints to MongoDB
    Returns: {'new_count': int, 'duplicate_count': int, 'errors': list}
    """
    collection = get_complaints_collection()
    if not collection:
        return {'new_count': 0, 'duplicate_count': 0, 'errors': ['MongoDB connection failed']}
    
    new_count = 0
    duplicate_count = 0
    errors = []
    
    for complaint in complaints:
        complaint_id = str(complaint.get('Complaint_ID', '')).strip()
        
        if not complaint_id or complaint_id == "Not Available":
            errors.append(f"Skipping complaint without valid ID: {complaint}")
            continue
        
        # Check for duplicate
        if check_duplicate(complaint_id):
            duplicate_count += 1
            continue
        
        # Prepare document
        doc = complaint.copy()
        doc['created_at'] = datetime.utcnow()
        doc['updated_at'] = datetime.utcnow()
        
        try:
            collection.insert_one(doc)
            new_count += 1
        except DuplicateKeyError:
            duplicate_count += 1
        except Exception as e:
            errors.append(f"Error saving {complaint_id}: {str(e)}")
    
    return {
        'new_count': new_count,
        'duplicate_count': duplicate_count,
        'errors': errors
    }


def get_all_complaints() -> List[Dict]:
    """Get all complaints from MongoDB"""
    try:
        collection = get_complaints_collection()
        if not collection:
            return []
        
        complaints = list(collection.find({}).sort("created_at", -1))
        # Convert ObjectId to string for JSON serialization
        for complaint in complaints:
            if '_id' in complaint:
                complaint['_id'] = str(complaint['_id'])
        return complaints
    except Exception as e:
        print(f"Error fetching complaints: {e}")
        return []


def sync_mongodb_to_excel(excel_path: str) -> bool:
    """
    Sync all MongoDB data to Excel file
    Returns True if successful
    """
    try:
        import pandas as pd
        
        complaints = get_all_complaints()
        if not complaints:
            return False
        
        # Convert to DataFrame
        df = pd.DataFrame(complaints)
        
        # Remove MongoDB internal fields
        if '_id' in df.columns:
            df = df.drop('_id', axis=1)
        if 'created_at' in df.columns:
            df = df.drop('created_at', axis=1)
        if 'updated_at' in df.columns:
            df = df.drop('updated_at', axis=1)
        
        # Ensure Complaint_ID is string
        if 'Complaint_ID' in df.columns:
            df['Complaint_ID'] = df['Complaint_ID'].astype(str)
        
        # Save to Excel
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        df.to_excel(excel_path, index=False, engine='openpyxl')
        
        return True
    except Exception as e:
        print(f"Error syncing MongoDB to Excel: {e}")
        return False


def import_excel_to_mongodb(excel_path: str) -> int:
    """
    Import Excel file data to MongoDB
    Returns number of complaints imported
    """
    try:
        import pandas as pd
        
        if not os.path.exists(excel_path):
            return 0
        
        df = pd.read_excel(excel_path, dtype={'Complaint_ID': str})
        
        if df.empty:
            return 0
        
        complaints = df.to_dict('records')
        
        # Save to MongoDB (will skip duplicates automatically)
        result = save_to_mongodb(complaints)
        
        return result['new_count']
    except Exception as e:
        print(f"Error importing Excel to MongoDB: {e}")
        return 0


def test_connection() -> bool:
    """Test MongoDB connection"""
    try:
        client = get_mongodb_client()
        if client:
            client.admin.command('ping')
            return True
    except Exception:
        pass
    return False

