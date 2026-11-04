# test_app.py
import pytest
from app import app, load_resources

@pytest.fixture
def client():
    load_resources()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_search_endpoint_success(client):
    """Verify that a valid query returns HTTP 200 and formatted search results."""
    response = client.post('/search', json={"q": "when is recycling collected?"})
    assert response.status_code == 200
    
    data = response.get_json()
    assert "query" in data
    assert data["query"] == "when is recycling collected?"
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0

    # Verify structured output of top result
    first_result = data["results"][0]
    assert "text" in first_result
    assert "source" in first_result
    assert "score" in first_result
    assert isinstance(first_result["score"], float)

def test_search_endpoint_empty_query(client):
    """Verify that an empty query returns HTTP 400 error response."""
    response = client.post('/search', json={"q": ""})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data