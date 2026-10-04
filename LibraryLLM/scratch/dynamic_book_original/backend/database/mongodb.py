import os

from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

MONGO_DB_NAME = os.getenv(
    "MONGO_DB_NAME",
    "luminar_library"
)

client = MongoClient(MONGO_URI)

db = client[MONGO_DB_NAME]


# =========================
# Collections
# =========================

users_collection = db["users"]

email_verifications_collection = db["email_verifications"]

books_collection = db["books"]

issues_collection = db["issues"]

reservations_collection = db["reservations"]

fines_collection = db["fines"]

activity_collection = db["activity"]

recommendation_feedbacks_collection = db[
    "recommendation_feedbacks"
]

library_inventory_collection = db[
    "library_inventory"
]

inventory_preview_collection = db[
    "inventory_previews"
]

# Cached/precomputed book categories
book_categories_collection = db[
    "book_categories"
]

reading_list_collection = db[
    "reading_list"
]

reading_list_collection.create_index(
    [("user_id", 1), ("work_id", 1)],
    unique=True
)