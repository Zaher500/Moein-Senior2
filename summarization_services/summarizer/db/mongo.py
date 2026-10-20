from pymongo import MongoClient
from datetime import datetime
import os


# =========================================================
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "summarization_service"
COLLECTION_NAME = "summaries"

#  client must be MongoClient
client = MongoClient(MONGO_URI)

# db must be a Database object, not string
db = client[DB_NAME]

#  this must be a Collection object
summaries_collection = db[COLLECTION_NAME]

def save_summary(lecture_id: str, summary_text: str):
    now = datetime.utcnow()

    summaries_collection.update_one(
        {"lecture_id": lecture_id},
        {
            "$set": {
                "summary_text": summary_text,
                "status": "READY",
                "updated_at": now
            },
            "$setOnInsert": {
                "created_at": now
            }
        },
        upsert=True
    )


def save_extracted_text(
    lecture_id: str,
    extracted_text: str,
    student_id: str
):
    now = datetime.utcnow()

    summaries_collection.update_one(
        {"lecture_id": str(lecture_id)},
        {
            "$set": {
                "extracted_text": extracted_text,
                "student_id": str(student_id),
                "updated_at": now
            },
            "$setOnInsert": {
                "created_at": now
            }
        },
        upsert=True
    )



def get_summary_by_lecture_id(lecture_id: str):
    return summaries_collection.find_one(
        {"lecture_id": lecture_id, "status": "READY"},
        {"_id": 0}  # hide Mongo internal id
    )


def is_summary_ready(lecture_id: str) -> bool:
    print("Checking summary readiness for lecture_id:", lecture_id)
    return summaries_collection.find_one(
        {"lecture_id": lecture_id, "status": "READY"}
    ) is not None