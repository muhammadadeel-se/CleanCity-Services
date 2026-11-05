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
    """Verify that a valid query returns HTTP 200 and a topic-relevant result."""
    response = client.post('/search', json={"q": "when is recycling collected?"})
    assert response.status_code == 200
    
    data = response.get_json()
    assert "query" in data
    assert data["query"] == "when is recycling collected?"
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0

    # Verify structured output format
    first_result = data["results"][0]
    assert "text" in first_result
    assert "source" in first_result
    assert "score" in first_result
    assert isinstance(first_result["score"], float)
    assert first_result["score"] > 0.0

    # Criterion 4 Fix: Verify the top result is semantically relevant to the query topic
    top_text = first_result["text"].lower()
    relevant_terms = ["recycl", "collect", "schedule", "bin", "waste"]
    assert any(term in top_text for term in relevant_terms), (
        f"Top result text lacks query relevance: '{first_result['text']}'"
    )

def test_search_endpoint_relevance_hazardous_waste(client):
    """Verify hazardous waste query returns relevant FAQ or schedule metadata."""
    response = client.post('/search', json={"q": "hazardous waste disposal"})
    assert response.status_code == 200
    
    data = response.get_json()
    assert len(data["results"]) > 0
    
    top_text = data["results"][0]["text"].lower()
    relevant_terms = ["hazard", "waste", "dispos", "paint", "chemical", "faq", "request"]
    assert any(term in top_text for term in relevant_terms), (
        f"Top result text lacks query relevance: '{data['results'][0]['text']}'"
    )

def test_search_endpoint_empty_query(client):
    """Verify that an empty query returns HTTP 400 error response."""
    response = client.post('/search', json={"q": ""})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data