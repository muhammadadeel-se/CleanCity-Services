## Caching & Rate-Limiting Strategy

### 1. In-Memory TTL Cache
* **Storage:** In-memory dictionary with thread locking (`threading.Lock`).
* **TTL Duration:** 10 Minutes (600 Seconds).
* **Eviction Policy:** LRU eviction when size exceeds 500 keys.
* **Normalization:** Input queries are lowercased, stripped of punctuation, and collapsed for whitespace before cache checks (e.g., `"Recycling?"` and `"recycling"` share the same cache entry).
* **Logging:** Emits `CACHE HIT` and `CACHE MISS` logging entries on every request.

### 2. IP Rate-Limiting
* **Strategy:** Sliding-window timestamp counter per IP address (`request.remote_addr`).
* **Threshold:** Maximum **30 queries per hour** (3600s sliding window).
* **Rejection:** Returns `HTTP 429 Too Many Requests` status code with JSON error message when exceeded.
* **Logging:** Logs blocked IP address and request count warnings.