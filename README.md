# CleanCity Services Hybrid Search API

Hybrid keyword and vector search microservice built with Flask, SQLite, FAISS (`sentence-transformers/all-MiniLM-L6-v2`), LRU caching, and sliding-window rate limiting.

## Live Deployment
* **Live API Base URL:** `https://cleancity-search-production.up.railway.app`
* **Search Endpoint:** `POST https://cleancity-search-production.up.railway.app/search`

---

## API Contract

### Request Format
`POST /search`
```json
{
  "q": "When is recycling collected in Zone A?"
}