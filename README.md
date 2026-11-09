# CleanCity Services Hybrid Search API

Hybrid keyword and vector search microservice built with Flask, SQLite, FAISS (`sentence-transformers/all-MiniLM-L6-v2`), `OrderedDict` LRU caching, and sliding-window rate limiting.

---

## 1. Live Deployment & Reachability Evidence

* **Live Base URL:** https://noble-charisma-production-1dad.up.railway.app
* **Live Search Endpoint (POST):** https://noble-charisma-production-1dad.up.railway.app/search

### Direct Terminal Verification (PowerShell)
```powershell
Invoke-RestMethod -Uri "https://noble-charisma-production-1dad.up.railway.app/search" -Method Post -ContentType "application/json" -Body '{"q":"when is recycling collected?"}'