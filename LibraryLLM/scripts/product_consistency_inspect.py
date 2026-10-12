"""Read-only development state audit; never print hashes or credentials."""
from dotenv import load_dotenv
import os
import json
from pymongo import MongoClient
load_dotenv()
d = MongoClient(os.getenv('MONGO_URI'))['luminar_library']
print(json.dumps({'users': list(d.users.find({'is_email_verified': True, 'is_active': {'$ne': False}},
    {'_id': 0, 'user_id': 1, 'name': 1, 'email': 1, 'role': 1})),
    'sample': list(d.books.find({'work_id': {'$regex': '^OL[0-9]+W$'}, 'subjects': {'$exists': True}},
    {'_id': 0, 'book_id': 1, 'work_id': 1, 'title': 1, 'subjects': 1, 'authors': 1}).sort('book_id', 1).limit(5)),
    'books_indexes': list(d.books.list_indexes()),
    'categories': list(d.book_categories.find({}, {'_id':0}).limit(3))}, default=str, indent=2))
