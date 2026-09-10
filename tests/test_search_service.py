import pytest

from services.search.service import SearchService


def test_search_service_requires_initialization():
    service = SearchService()

    with pytest.raises(RuntimeError):
        service.search("python")