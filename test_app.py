import pytest
import time
from app import app, query_cache, request_history, norm_query, RATE_LIMIT

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Clear in-memory state before each test
    query_cache.clear()
    request_history.clear()
    with app.test_client() as client:
        yield client

def test_norm_query_helper():
    """Verify query normalization behavior."""
    assert norm_query("  When is RECYCLING collected???  ") == "when is recycling collected"
    assert norm_query("???") == ""

def test_cache_hit_and_miss(client):
    """Verify cache miss on first query and cache hit on repeated identical query within TTL."""
    payload = {"q": "when is recycling collected?"}
    
    # 1st request -> Cache Miss
    res1 = client.post('/search', json=payload)
    assert res1.status_code == 200
    
    # 2nd request -> Cache Hit (Instant response from memory)
    res2 = client.post('/search', json=payload)
    assert res2.status_code == 200
    assert res1.get_json() == res2.get_json()

def test_rate_limiting_429(client):
    """Verify that requests exceeding 30 reqs/hr trigger HTTP 429."""
    payload = {"q": "waste collection"}
    
    # Send up to allowed limit (30 requests)
    for _ in range(RATE_LIMIT):
        res = client.post('/search', json=payload)
        assert res.status_code == 200

    # 31st request -> Blocked with 429
    res_blocked = client.post('/search', json=payload)
    assert res_blocked.status_code == 429
    assert res_blocked.get_json()["error"] == "Too Many Requests"

def test_empty_query_validation(client):
    """Verify empty/punctuation-only queries return HTTP 400."""
    res = client.post('/search', json={"q": "!!!"})
    assert res.status_code == 400