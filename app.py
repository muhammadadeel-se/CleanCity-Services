import os
import json
import time
import logging
from collections import OrderedDict
from threading import Lock
import numpy as np
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CleanCity-Services")

# --- CONFIGURATION ---
CACHE_TTL = 600           # 10 minutes (seconds)
CACHE_MAX_SIZE = 500     # Max cache size
RATE_LIMIT = 30           # Max requests per hour
WINDOW_SIZE = 3600        # 1 hour window (seconds)

HF_API_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

# In-Memory LRU Cache & Rate Limits
query_cache = OrderedDict()
cache_lock = Lock()
request_history = {}

# Global Data Store
documents = []
embeddings = None

def load_resources():
    global documents, embeddings
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            raw = json.load(f)
            documents = raw if isinstance(raw, list) else list(raw.values())
    if os.path.exists("embeddings.npy"):
        embeddings = np.load("embeddings.npy")
    logger.info("Loaded %d documents and embeddings shape %s", len(documents), str(embeddings.shape if embeddings is not None else None))

load_resources()

def get_query_vector(text):
    """Fetch query embedding from Hugging Face Free Inference API (0 MB RAM overhead)."""
    try:
        res = requests.post(
            HF_API_URL,
            json={"inputs": text, "options": {"wait_for_model": True}},
            timeout=8
        )
        if res.status_code == 200:
            vec = np.array(res.json(), dtype=np.float32)
            if vec.ndim > 1:
                vec = vec[0]
            return vec
    except Exception as e:
        logger.warning("HF API call failed: %s. Falling back to keyword match.", str(e))
    return None

def normalize_query(q):
    return " ".join(q.lower().strip().split())

def is_rate_limited(client_ip):
    now = time.time()
    cutoff = now - WINDOW_SIZE
    timestamps = [t for t in request_history.get(client_ip, []) if t > cutoff]
    if len(timestamps) >= RATE_LIMIT:
        request_history[client_ip] = timestamps
        return True
    timestamps.append(now)
    request_history[client_ip] = timestamps
    return False

@app.route("/search", methods=["POST"])
def search():
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if is_rate_limited(client_ip):
        logger.warning("Rate limit exceeded for IP: %s", client_ip)
        return jsonify({"error": "Rate limit exceeded"}), 429

    data = request.get_json() or {}
    raw_query = data.get("q", "")
    if not raw_query or not raw_query.strip():
        return jsonify({"error": "Query cannot be empty"}), 400

    norm_q = normalize_query(raw_query)

    # Check Cache
    with cache_lock:
        if norm_q in query_cache:
            cached_time, cached_val = query_cache[norm_q]
            if time.time() - cached_time < CACHE_TTL:
                query_cache.move_to_end(norm_q)
                logger.info("CACHE HIT: %s", norm_q)
                return jsonify(cached_val), 200
            else:
                del query_cache[norm_q]

    # Perform Search
    logger.info("CACHE MISS: %s", norm_q)
    results = []
    query_vec = get_query_vector(raw_query)

    if query_vec is not None and embeddings is not None and len(embeddings) > 0:
        # Cosine similarity using NumPy
        norm_q_vec = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        norm_embeds = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)
        scores = np.dot(norm_embeds, norm_q_vec)
        
        top_idx = np.argsort(scores)[::-1][:3]
        for idx in top_idx:
            doc = documents[idx] if isinstance(documents[idx], dict) else {"text": str(documents[idx]), "source": "N/A"}
            results.append({
                "score": float(round(scores[idx], 4)),
                "source": doc.get("source", "https://www.cleancityservices.gov/info"),
                "text": doc.get("text", str(doc))
            })
    else:
        # Fallback exact/keyword matching
        for doc in documents:
            text = doc.get("text", str(doc)) if isinstance(doc, dict) else str(doc)
            if any(word in text.lower() for word in norm_q.split()):
                results.append({
                    "score": 0.75,
                    "source": doc.get("source", "https://www.cleancityservices.gov/info") if isinstance(doc, dict) else "https://www.cleancityservices.gov/info",
                    "text": text
                })
        results = results[:3]

    response_payload = {
        "query": raw_query,
        "results": results
    }

    # Store in Cache
    with cache_lock:
        if len(query_cache) >= CACHE_MAX_SIZE:
            query_cache.popitem(last=False)
        query_cache[norm_q] = (time.time(), response_payload)

    return jsonify(response_payload), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)