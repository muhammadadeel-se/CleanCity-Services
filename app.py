import os
import re
import string
import time
import logging
import sqlite3
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from threading import Lock
from flask import Flask, jsonify, request

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CleanCityAPI")

app = Flask(__name__)

# --- CONFIGURATION ---
CACHE_TTL = 600       # 10 minutes
CACHE_MAX_SIZE = 500  
RATE_LIMIT = 30       # 30 reqs/hr
WINDOW_SIZE = 3600    # 1 hour

query_cache = {}
cache_lock = Lock()
request_history = {}
rate_limit_lock = Lock()

# Global variables for models/indexes
embed_model = None
faiss_index = None

def get_db_connection():
    conn = sqlite3.connect("cleancity.db")
    conn.row_factory = sqlite3.Row
    return conn

def load_resources():
    global embed_model, faiss_index
    if embed_model is None:
        embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    if faiss_index is None:
        faiss_index = faiss.read_index("faiss_index.bin")

def norm_query(q: str) -> str:
    if not q:
        return ""
    q = q.lower().strip()
    q = q.translate(str.maketrans("", "", string.punctuation))
    q = re.sub(r"\s+", " ", q)
    return q

def get_cached_response(norm_q: str):
    now = time.time()
    with cache_lock:
        if norm_q in query_cache:
            data, timestamp = query_cache[norm_q]
            if now - timestamp < CACHE_TTL:
                logger.info(f"CACHE HIT: '{norm_q}'")
                return data
            else:
                del query_cache[norm_q]
        logger.info(f"CACHE MISS: '{norm_q}'")
        return None

def set_cached_response(norm_q: str, data: dict):
    now = time.time()
    with cache_lock:
        if len(query_cache) >= CACHE_MAX_SIZE:
            oldest_key = min(query_cache.keys(), key=lambda k: query_cache[k][1])
            del query_cache[oldest_key]
        query_cache[norm_q] = (data, now)

def is_rate_limited(client_ip: str) -> bool:
    now = time.time()
    with rate_limit_lock:
        if client_ip not in request_history:
            request_history[client_ip] = []
        request_history[client_ip] = [t for t in request_history[client_ip] if now - t < WINDOW_SIZE]
        if len(request_history[client_ip]) >= RATE_LIMIT:
            logger.warning(f"RATE LIMIT EXCEEDED: IP {client_ip} blocked.")
            return True
        request_history[client_ip].append(now)
        return False

def keyword_search(query_text, limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    tokens = query_text.lower().split()
    results = {}

    tables = [
        ("faq", ["question", "answer", "category"], "id", "source_url"),
        ("schedule", ["zone", "waste_type", "collection_day", "notes"], "id", None),
        ("request", ["request_type", "description"], "id", None)
    ]

    for table, fields, pk_col, src_col in tables:
        where_clauses = []
        params = []
        for t in tokens:
            clause = " OR ".join([f"{f} LIKE ?" for f in fields])
            where_clauses.append(f"({clause})")
            params.extend([f"%{t}%"] * len(fields))

        sql = f"SELECT * FROM {table}"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        for r in rows:
            pk = r[pk_col]
            key = (table, pk)
            if table == "faq":
                text = f"FAQ [{r['category']}]: {r['question']} - {r['answer']}"
                source = r[src_col]
            elif table == "schedule":
                text = f"Schedule [{r['zone']}]: {r['waste_type']} collected on {r['collection_day']}"
                source = "https://www.cleancityservices.gov/collection-schedules"
            elif table == "request":
                text = f"Request [{r['request_type']}]: {r['description']} | Fee: {r['fee']}"
                source = "https://www.cleancityservices.gov/special-requests"

            results[key] = {"text": text, "source": source, "kw_score": 1.0}

    conn.close()
    return results

def vector_search(query_text, k=10):
    load_resources()
    query_vec = embed_model.encode(query_text).astype("float32")
    distances, indices = faiss_index.search(np.array([query_vec]), k)

    conn = get_db_connection()
    cursor = conn.cursor()
    results = {}

    for idx in indices[0]:
        if idx == -1: continue
        cursor.execute("SELECT table_name, pk FROM faiss_meta WHERE idx = ?", (int(idx),))
        row = cursor.fetchone()
        if not row: continue

        table_name, pk = row["table_name"], row["pk"]
        key = (table_name, pk)

        doc_vec = faiss_index.reconstruct(int(idx))
        norm_q, norm_d = np.linalg.norm(query_vec), np.linalg.norm(doc_vec)
        cos_sim = float(np.dot(query_vec, doc_vec) / (norm_q * norm_d)) if norm_q > 0 and norm_d > 0 else 0.0
        vec_score = float((cos_sim + 1.0) / 2.0)

        if table_name == "faq":
            cursor.execute("SELECT question, answer, category, source_url FROM faq WHERE id = ?", (pk,))
            r = cursor.fetchone()
            text, source = f"FAQ [{r['category']}]: {r['question']} - {r['answer']}", r["source_url"]
        elif table_name == "schedule":
            cursor.execute("SELECT zone, waste_type, collection_day, frequency, notes FROM schedule WHERE id = ?", (pk,))
            r = cursor.fetchone()
            text, source = f"Schedule [{r['zone']}]: {r['waste_type']} collected on {r['collection_day']}", "https://www.cleancityservices.gov/collection-schedules"
        elif table_name == "request":
            cursor.execute("SELECT request_type, description, fee FROM request WHERE id = ?", (pk,))
            r = cursor.fetchone()
            text, source = f"Request [{r['request_type']}]: {r['description']} | Fee: {r['fee']}", "https://www.cleancityservices.gov/special-requests"
        else:
            continue

        results[key] = {"text": text, "source": source, "vector_score": vec_score}

    conn.close()
    return results

def hybrid_search(query_text, alpha=0.6, top_k=5):
    kw_results = keyword_search(query_text, limit=10)
    vec_results = vector_search(query_text, k=10)

    all_keys = set(kw_results.keys()).union(set(vec_results.keys()))
    combined = []

    for key in all_keys:
        kw_item = kw_results.get(key, {})
        vec_item = vec_results.get(key, {})

        text = vec_item.get("text") or kw_item.get("text")
        source = vec_item.get("source") or kw_item.get("source")
        kw_score = kw_item.get("kw_score", 0.0)
        vec_score = vec_item.get("vector_score", 0.0)

        hybrid_score = round(float((alpha * vec_score) + ((1.0 - alpha) * kw_score)), 4)

        combined.append({
            "text": text,
            "source": source,
            "score": hybrid_score,
            "vec_score": vec_score
        })

    combined.sort(key=lambda x: (x["score"], x["vec_score"]), reverse=True)

    return [
        {"text": r["text"], "source": r["source"], "score": float(r["score"])}
        for r in combined[:top_k]
    ]

@app.before_request
def enforce_rate_limit():
    if request.path == "/search":
        client_ip = request.remote_addr or "127.0.0.1"
        if is_rate_limited(client_ip):
            return jsonify({
                "error": "Too Many Requests",
                "message": f"Rate limit exceeded. Maximum {RATE_LIMIT} requests per hour allowed."
            }), 429

@app.route("/search", methods=["POST"])
def search_endpoint():
    data = request.get_json(silent=True) or {}
    raw_query = data.get("q", "")
    normalized_q = norm_query(raw_query)

    if not normalized_q:
        return jsonify({"error": "Invalid or empty query parameter 'q'."}), 400

    cached_data = get_cached_response(normalized_q)
    if cached_data is not None:
        return jsonify(cached_data), 200

    results = hybrid_search(raw_query, alpha=0.6, top_k=5)
    response_payload = {"query": raw_query, "results": results}

    set_cached_response(normalized_q, response_payload)

    return jsonify(response_payload), 200

if __name__ == "__main__":
    app.run(debug=True)