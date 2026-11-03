# CleanCity Services Semantic Search Engine

An intelligent search application for city-wide waste collection schedules, recycling rules, and special pickup requests.

## Data Schema & Sources (Task 1)

### Database Schema (`cleancity.db` & `data.json`)
- **`faq`** (15 entries): `id`, `question`, `answer`, `category`, `source_url`
- **`schedule`** (10 entries): `id`, `zone`, `waste_type`, `collection_day`, `frequency`, `notes`
- **`request`** (5 entries): `id`, `request_type`, `description`, `required_info`, `processing_days`, `fee`

---

## Vector Indexing & Embeddings (Task 2)

We use the `sentence-transformers/all-MiniLM-L6-v2` model to encode structured records into 384-dimensional dense vector space and index them with FAISS (`IndexFlatL2`).

### Index Pipeline Architecture
1. **Serialization:** Records from `data.json` are concatenated with domain tags (`Category`, `Zone`, `Request Type`) into string representations.
2. **Dense Vector Encoding:** Embeddings are generated using SentenceTransformers.
3. **FAISS Storage:** Dense vectors are written to `faiss_index.bin`.
4. **Metadata Mapping:** SQLite table `faiss_meta` correlates vector offsets (`0, 1, 2...`) with source table names and primary keys.

### How to Re-run Indexing
If database or `data.json` records change, regenerate the index and SQLite mapping by executing:

```bash
python embed.py