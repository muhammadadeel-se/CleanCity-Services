# app.py
import re
import sqlite3
import numpy as np
import faiss
from flask import Flask, jsonify, request
from sentence_transformers import SentenceTransformer

app = Flask(__name__)

DB_FILE = "cleancity.db"
INDEX_FILE = "faiss_index.bin"
MODEL_NAME = "all-MiniLM-L6-v2"

embed_model = None
faiss_index = None


def load_resources():
    """Load Sentence Transformer model and FAISS index at startup."""
    global embed_model, faiss_index
    if embed_model is None:
        print(f"[INFO] Loading embedding model '{MODEL_NAME}'...")
        embed_model = SentenceTransformer(MODEL_NAME)
    if faiss_index is None:
        print(f"[INFO] Loading FAISS index from '{INDEX_FILE}'...")
        faiss_index = faiss.read_index(INDEX_FILE)


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def keyword_search(query_text, limit=10):
    """Perform SQLite LIKE keyword search across faqs, schedules, and requests."""
    conn = get_db_connection()
    cursor = conn.cursor()

    words = [
        re.sub(r"\W+", "", w).lower()
        for w in query_text.split()
        if len(w) > 2
    ]
    if not words:
        conn.close()
        return {}

    results = {}

    # 1. Search FAQ table
    for word in words:
        pattern = f"%{word}%"
        cursor.execute(
            """
            SELECT id, question, answer, category, source_url 
            FROM faq 
            WHERE question LIKE ? OR answer LIKE ? OR category LIKE ?
        """,
            (pattern, pattern, pattern),
        )
        for row in cursor.fetchall():
            key = ("faq", row["id"])
            if key not in results:
                results[key] = {
                    "table": "faq",
                    "pk": row["id"],
                    "text": (
                        f"FAQ [{row['category']}]: {row['question']} -"
                        f" {row['answer']}"
                    ),
                    "source": row["source_url"],
                    "kw_matches": 0,
                }
            results[key]["kw_matches"] += 1

    # 2. Search Schedule table
    for word in words:
        pattern = f"%{word}%"
        cursor.execute(
            """
            SELECT id, zone, waste_type, collection_day, frequency, notes 
            FROM schedule 
            WHERE zone LIKE ? OR waste_type LIKE ? OR notes LIKE ? OR collection_day LIKE ?
        """,
            (pattern, pattern, pattern, pattern),
        )
        for row in cursor.fetchall():
            key = ("schedule", row["id"])
            if key not in results:
                results[key] = {
                    "table": "schedule",
                    "pk": row["id"],
                    "text": (
                        f"Schedule [{row['zone']}]: {row['waste_type']}"
                        f" collected on {row['collection_day']}"
                        f" ({row['frequency']}). Notes: {row['notes']}"
                    ),
                    "source": (
                        "https://www.cleancityservices.gov/collection-schedules"
                    ),
                    "kw_matches": 0,
                }
            results[key]["kw_matches"] += 1

    # 3. Search Request table
    for word in words:
        pattern = f"%{word}%"
        cursor.execute(
            """
            SELECT id, request_type, description, required_info, fee 
            FROM request 
            WHERE request_type LIKE ? OR description LIKE ?
        """,
            (pattern, pattern),
        )
        for row in cursor.fetchall():
            key = ("request", row["id"])
            if key not in results:
                results[key] = {
                    "table": "request",
                    "pk": row["id"],
                    "text": (
                        f"Request [{row['request_type']}]: {row['description']}"
                        f" | Fee: {row['fee']}"
                    ),
                    "source": (
                        "https://www.cleancityservices.gov/special-requests"
                    ),
                    "kw_matches": 0,
                }
            results[key]["kw_matches"] += 1

    conn.close()

    total_words = len(words)
    for key, item in results.items():
        item["kw_score"] = min(1.0, item["kw_matches"] / total_words)

    return results


def vector_search(query_text, k=10):
    """Query FAISS index and compute cosine similarity vector scores."""
    load_resources()

    query_vec = embed_model.encode(query_text).astype("float32")
    distances, indices = faiss_index.search(np.array([query_vec]), k)

    conn = get_db_connection()
    cursor = conn.cursor()

    results = {}
    for idx in indices[0]:
        if idx == -1:
            continue

        cursor.execute(
            "SELECT table_name, pk FROM faiss_meta WHERE idx = ?", (int(idx),)
        )
        row = cursor.fetchone()
        if not row:
            continue

        table_name, pk = row["table_name"], row["pk"]
        key = (table_name, pk)

        # Retrieve indexed document vector & calculate Cosine Similarity
        doc_vec = faiss_index.reconstruct(int(idx))
        norm_q = np.linalg.norm(query_vec)
        norm_d = np.linalg.norm(doc_vec)

        if norm_q > 0 and norm_d > 0:
            cos_sim = np.dot(query_vec, doc_vec) / (norm_q * norm_d)
        else:
            cos_sim = 0.0

        # Scale cosine similarity from range [-1, 1] to [0, 1]
        vec_score = float((cos_sim + 1.0) / 2.0)

        # Hydrate record fields
        if table_name == "faq":
            cursor.execute(
                "SELECT question, answer, category, source_url FROM faq WHERE"
                " id = ?",
                (pk,),
            )
            r = cursor.fetchone()
            text = f"FAQ [{r['category']}]: {r['question']} - {r['answer']}"
            source = r["source_url"]
        elif table_name == "schedule":
            cursor.execute(
                "SELECT zone, waste_type, collection_day, frequency, notes"
                " FROM schedule WHERE id = ?",
                (pk,),
            )
            r = cursor.fetchone()
            text = (
                f"Schedule [{r['zone']}]: {r['waste_type']} collected on"
                f" {r['collection_day']} ({r['frequency']}). Notes:"
                f" {r['notes']}"
            )
            source = "https://www.cleancityservices.gov/collection-schedules"
        elif table_name == "request":
            cursor.execute(
                "SELECT request_type, description, fee FROM request WHERE id ="
                " ?",
                (pk,),
            )
            r = cursor.fetchone()
            text = (
                f"Request [{r['request_type']}]: {r['description']} | Fee:"
                f" {r['fee']}"
            )
            source = "https://www.cleancityservices.gov/special-requests"
        else:
            continue

        results[key] = {
            "table": table_name,
            "pk": pk,
            "text": text,
            "source": source,
            "vector_score": vec_score,
        }

    conn.close()
    return results


def hybrid_search(query_text, alpha=0.6, top_k=5):
    """Combine keyword & vector search results with cosine scoring and tie-breaking."""
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

        hybrid_score = round(
            (alpha * vec_score) + ((1.0 - alpha) * kw_score), 4
        )

        combined.append(
            {
                "text": text,
                "source": source,
                "score": hybrid_score,
                "vec_score": round(vec_score, 4),
            }
        )

    # Sort primarily by hybrid_score, secondarily by vec_score (tie-breaker)
    combined.sort(key=lambda x: (x["score"], x["vec_score"]), reverse=True)

    # Remove internal vec_score field before returning public results
    output_results = [
        {"text": r["text"], "source": r["source"], "score": r["score"]}
        for r in combined[:top_k]
    ]

    return output_results


@app.route("/search", methods=["POST"])
def search_endpoint():
    """POST /search API accepting JSON payload {'q': 'query_string'}."""
    data = request.get_json(silent=True) or {}
    query = data.get("q", "").strip()

    if not query:
        return jsonify({"error": "Missing or empty query parameter 'q'."}), 400

    results = hybrid_search(query, alpha=0.6, top_k=5)
    return jsonify({"query": query, "results": results}), 200


if __name__ == "__main__":
    load_resources()
    app.run(host="0.0.0.0", port=5000, debug=True)