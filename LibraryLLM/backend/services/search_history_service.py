from datetime import datetime, timezone

from backend.database.mongodb import db


search_history_collection = db["search_history"]
counters_collection = db["counters"]


def initialize_search_id_counter():
    """
    Initialize the search_history counter based on existing maximum search_id.
    Safe to run multiple times (upsert ensures idempotency).
    
    This function should be run once during deployment to initialize the counter
    from the existing maximum search_id value, preventing ID collision with
    existing records.
    """
    last_search = search_history_collection.find_one(
        {},
        sort=[("search_id", -1)]
    )
    
    current_max = last_search["search_id"] if last_search else 0
    
    # Use $setOnInsert to only set the value if the document doesn't exist
    # This makes the function idempotent - safe to run multiple times
    result = counters_collection.update_one(
        {"_id": "search_history"},
        {"$setOnInsert": {"seq": current_max}},
        upsert=True
    )
    
    if result.upserted_id:
        print(f"[INIT] Search ID counter initialized to {current_max}")
    else:
        # Counter already exists, get current value
        counter = counters_collection.find_one({"_id": "search_history"})
        print(f"[INIT] Search ID counter already exists with value {counter['seq']}")


def get_next_search_id():
    """
    Atomically generates the next search_id using MongoDB's findOneAndUpdate with $inc.
    This eliminates race conditions by ensuring the read-increment-write happens atomically.
    
    Uses a dedicated counters collection with a document:
    { "_id": "search_history", "seq": <current_value> }
    
    The atomic $inc operation ensures that concurrent calls each receive a unique,
    sequential ID without any race conditions.
    """
    result = counters_collection.find_one_and_update(
        {"_id": "search_history"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True  # Return the document AFTER update
    )
    
    return result["seq"]


def create_search_history(
    user_id,
    query,
    top_k,
    results
):

    result_work_ids = [
        result["work_id"]
        for result in results
        if result.get("work_id")
    ]

    search_record = {
        "search_id": get_next_search_id(),
        "user_id": user_id,
        "query": query,
        "top_k": top_k,
        "result_work_ids": result_work_ids,
        "result_count": len(results),
        "created_at": datetime.now(timezone.utc)
    }

    try:
        search_history_collection.insert_one(
            search_record
        )

        search_record.pop("_id", None)

        return search_record
    
    except Exception as e:
        # Log the error but don't propagate - history persistence is not critical path
        # Search results should still be returned to the user even if history save fails
        print(f"[WARN] Failed to persist search history: {e}")
        return None  # Indicate failure without raising


def get_user_search_history(
    user_id,
    limit=50
):

    history = list(
        search_history_collection.find(
            {
                "user_id": user_id
            },
            {
                "_id": 0
            }
        )
        .sort(
            "created_at",
            -1
        )
        .limit(limit)
    )

    return history