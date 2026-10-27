from pymongo import MongoClient
from pymongo.errors import AutoReconnect
try:
    MongoClient('mongodb://127.0.0.1:27018').admin.command('shutdown')
except AutoReconnect:
    pass
