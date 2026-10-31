"""Optional facet-provider compatibility; authorization failures remain visible."""
from types import SimpleNamespace
import pytest
from pymongo.errors import OperationFailure
from search.query_execution import global_facets


def test_find_only_catalogue_has_optional_empty_facets():
    result=global_facets(SimpleNamespace(books_collection=SimpleNamespace(find=lambda *a:[])))
    assert result['results']==[] and result['capabilities']['rating']


def test_mongo_facet_authorization_error_is_not_hidden():
    class Denied:
        def find(self,*args):raise OperationFailure('fixture denied',code=13)
    with pytest.raises(OperationFailure) as error:
        global_facets(SimpleNamespace(books_collection=SimpleNamespace(database=SimpleNamespace(book_categories=Denied()))))
    assert error.value.code==13
