# embed.py
import json
import sqlite3
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

JSON_FILE = "data.json"
DB_FILE = "cleancity.db"
INDEX_FILE = "faiss_index.bin"
MODEL_NAME = "all-MiniLM-L6-v2"


def prepare_documents():
    """Load data.json and construct formatted text strings and metadata mappings."""
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = []
    metadata = []

    # 1. Process FAQs
    for faq in data.get("faqs", []):
        text = f"Category: {faq['category']} | Question: {faq['question']} | Answer: {faq['answer']}"
        documents.append(text)
        metadata.append(("faq", faq["id"], faq["question"]))

    # 2. Process Schedules
    for sch in data.get("schedules", []):
        text = f"Zone: {sch['zone']} | Waste Type: {sch['waste_type']} | Collection Day: {sch['collection_day']} | Frequency: {sch['frequency']} | Notes: {sch['notes']}"
        documents.append(text)
        metadata.append((
            "schedule",
            sch["id"],
            f"{sch['zone']} - {sch['waste_type']}",
        ))

    # 3. Process Requests
    for req in data.get("requests", []):
        text = f"Request Type: {req['request_type']} | Description: {req['description']} | Required Info: {req['required_info']} | Fee: {req['fee']}"
        documents.append(text)
        metadata.append(("request", req["id"], req["request_type"]))

    return documents, metadata


def update_sqlite_meta(metadata):
    """Store FAISS index offset to SQLite table mapping in cleancity.db."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS faiss_meta")
    cursor.execute("""
    CREATE TABLE faiss_meta (
        idx INTEGER PRIMARY KEY,
        table_name TEXT NOT NULL,
        pk INTEGER NOT NULL,
        title TEXT NOT NULL
    )""")

    records = [
        (idx, table, pk, title) for idx, (table, pk, title) in enumerate(metadata)
    ]
    cursor.executemany(
        "INSERT INTO faiss_meta (idx, table_name, pk, title) VALUES (?, ?,"
        " ?, ?)",
        records,
    )

    conn.commit()
    conn.close()


def build_index():
    """Generate dense embeddings, construct FAISS IndexFlatL2, and persist to disk."""
    print(f"[INFO] Reading records from '{JSON_FILE}'...")
    documents, metadata = prepare_documents()
    print(f"[INFO] Prepared {len(documents)} document strings for embedding.")

    print(f"[INFO] Loading Sentence Transformer model '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)

    print("[INFO] Generating dense embeddings...")
    embeddings = model.encode(documents, show_progress_bar=True)
    embeddings = np.array(embeddings, dtype="float32")

    # Build IndexFlatL2 index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    print(f"[INFO] Persisting FAISS index to '{INDEX_FILE}'...")
    faiss.write_index(index, INDEX_FILE)

    print(f"[INFO] Updating SQLite 'faiss_meta' lookup table in '{DB_FILE}'...")
    update_sqlite_meta(metadata)

    print(
        "[SUCCESS] FAISS vector index successfully generated and saved to"
        f" '{INDEX_FILE}'."
    )


def load_and_test_query(query_text, k=3):
    """Reload persisted FAISS index and retrieve nearest neighbors for a sample query."""
    print(f"\n--- Testing Query: '{query_text}' ---")

    # Reload Index from disk
    index = faiss.read_index(INDEX_FILE)
    model = SentenceTransformer(MODEL_NAME)

    # Encode query string
    query_vector = model.encode([query_text]).astype("float32")

    # Perform nearest neighbor search
    distances, indices = index.search(query_vector, k)

    # Fetch mapping metadata from SQLite
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print(f"Top {k} Nearest Neighbors (L2 Distance):")
    for rank, (dist, idx) in enumerate(zip(distances[0], indices[0]), start=1):
        cursor.execute(
            "SELECT table_name, pk, title FROM faiss_meta WHERE idx = ?",
            (int(idx),),
        )
        row = cursor.fetchone()
        if row:
            table_name, pk, title = row
            print(
                f"  {rank}. [L2 Dist: {dist:.4f}] Table: {table_name} (ID:"
                f" {pk}) -> {title}"
            )

    conn.close()


if __name__ == "__main__":
    build_index()

    # Run verification tests
    load_and_test_query("What items are accepted in the blue recycling bin?")
    load_and_test_query("When is general waste collected in Downtown North?")
    load_and_test_query("How do I request removal of an old mattress?")