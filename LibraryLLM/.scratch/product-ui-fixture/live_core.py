import sys
sys.path.insert(0, 'D:\\SDC\\LibraryLLM')

from backend.main import app
from backend.services import book_service
from backend.database.mongodb import client
class ReadOnly:
    def __init__(self, collection): self.collection = collection
    def __getattr__(self, name):
        if name not in {'find', 'find_one', 'aggregate', 'estimated_document_count', 'count_documents'}:
            raise RuntimeError('Fixture prohibits global metadata writes')
        return getattr(self.collection, name)
book_service.books_collection = ReadOnly(client['luminar_library']['books'])
book_service.book_categories_collection = ReadOnly(client['luminar_library']['book_categories'])
