# Book Intelligence Platform

AI-powered Document Intelligence platform for books, built as a production-style full-stack system with scraping automation, structured metadata APIs, vector search, and grounded RAG Q&A.

---

## Why This Project Stands Out

- End-to-end architecture: ingestion -> enrichment -> indexing -> retrieval -> answer generation
- Practical AI pipeline: local embeddings + persistent vector storage + citation-friendly responses
- Real product UX: dashboard, book detail workflows, and conversational Q&A with history
- Deployment-aware design: local LLM option for offline development and hosted fallback for online environments

---

## Core Capabilities

- Multi-page automated book scraping with duplicate URL caching and resilient error handling
- AI insight generation per book:
1. 3-sentence summary
2. genre classification
3. sentiment + numeric score
- RAG pipeline with semantic chunk retrieval and source-aware responses
- Recommendation endpoint powered by vector similarity + deterministic fallback logic
- Chat history persistence and management APIs

---

## Tech Stack

### Backend
- Python 3.11+
- Django 4.2 + Django REST Framework
- SQLite (metadata)
- ChromaDB (vector store)
- sentence-transformers (`all-MiniLM-L6-v2`)
- BeautifulSoup4 + requests

### Frontend
- Next.js 14 (App Router)
- TypeScript (strict mode)
- Tailwind CSS
- React Query (TanStack Query)
- axios

### LLM Strategy (Important)
- **Primary (offline/local): LM Studio** via OpenAI-compatible endpoint
- **Fallback (online/deployed): Grok API** for hosted inference

This gives cost control + local privacy during development, with a cloud-ready path for production-style deployment.

---

## Project Structure

```text
book-intelligence/
  backend/
    config/
    books/
    manage.py
    requirements.txt
    db.sqlite3
  frontend/
    app/
    components/
    lib/
```

---

## Quick Start

### Backend

```powershell
cd D:\PROJECTS\ERGOSPHERE\book-intelligence\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

### Frontend

```powershell
cd D:\PROJECTS\ERGOSPHERE\book-intelligence\frontend
npm install
Copy-Item .env.example .env.local
npm run dev
```

- Frontend: `http://localhost:3000`
- Backend: `http://127.0.0.1:8000`

---

## Environment Variables

### Backend (`backend/.env`)
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `LLM_PROVIDER` (`lmstudio` or `grok`)
- `LM_STUDIO_BASE_URL`
- `LM_STUDIO_MODEL`
- `LM_STUDIO_API_KEY`
- `LM_STUDIO_TIMEOUT_SECONDS`
- `GROK_BASE_URL`
- `GROK_MODEL`
- `GROK_API_KEY`
- `ANTHROPIC_API_KEY` (optional env slot)

### Frontend (`frontend/.env.local`)
- `NEXT_PUBLIC_API_BASE_URL`
- Optional timeout tuning:
- `NEXT_PUBLIC_API_TIMEOUT_MS`
- `NEXT_PUBLIC_API_LONG_TIMEOUT_MS`

---

## One-Command Seed Pipeline

```powershell
cd D:\PROJECTS\ERGOSPHERE\book-intelligence\backend
python manage.py seed --pages 5
```

Pipeline stages:
1. Scrape books from `books.toscrape.com`
2. Generate AI insights
3. Index content into ChromaDB for RAG

Optional:

```powershell
python manage.py seed --pages 8 --force-insights
```

---

## API Documentation

### Response Envelope

```json
{ "success": true, "data": {}, "error": null }
```

### Book APIs

1. `GET /api/books/`  
Paginated books (20/page) with nested AI insight.

2. `GET /api/books/{id}/`  
Detailed book metadata + `chunks_count`.

3. `GET /api/books/{id}/recommendations/`  
Top related books from vector similarity.

4. `POST /api/books/scrape/`  
Trigger scraping.

Request:

```json
{ "pages": 5 }
```

5. `POST /api/books/{id}/generate-insights/`  
Generate or refresh AI insights.

Request:

```json
{ "force": false }
```

6. `POST /api/books/generate-all-insights/`  
Bulk insight generation.

7. `POST /api/books/{id}/index/`  
Index single book into vector store.

8. `POST /api/books/index-all/`  
Index all books.

### Q&A APIs

1. `POST /api/qa/ask/`

Request:

```json
{ "question": "Recommend uplifting books with strong reviews." }
```

Response example:

```json
{
  "success": true,
  "data": {
    "answer": "...",
    "sources": ["Book A", "Book B"],
    "chunk_references": [
      {
        "book_id": 12,
        "title": "Book A",
        "chunk_index": 0,
        "chroma_id": "book-12-chunk-0",
        "score": 0.87
      }
    ],
    "chat_id": 9
  },
  "error": null
}
```

2. `GET /api/qa/history/`  
Fetch recent Q&A history.

3. `DELETE /api/qa/history/`  
Clear chat history.

---

## Sample Questions

1. "Show books with optimistic tone and strong ratings."
2. "Find memoir-style books about resilience."
3. "Recommend books similar to mystery-driven narratives."

---

## UI Screenshots

Use these placeholders now, then replace with actual captured images before final submission.

- Dashboard UI: `https://your-cdn-or-github-user-images/dashboard.png`
- Book Detail UI: `https://your-cdn-or-github-user-images/book-detail.png`
- Q&A Chat UI: `https://your-cdn-or-github-user-images/qa-chat.png`
- Recommendations + Insights UI: `https://your-cdn-or-github-user-images/recommendations-insights.png`

---

## Deployment Notes

- **Local/offline mode:** run with `LLM_PROVIDER=lmstudio`
- **Hosted/online mode:** set `LLM_PROVIDER=grok` and configure Grok env keys
- Chroma vectors persist under `backend/chroma_db`
- Timestamps are UTC (`USE_TZ=True`, `TIME_ZONE=UTC`)

---

## Submission Checklist

- Source code pushed to GitHub repo
- README includes setup + API docs + screenshots
- `.env.example` files included for backend and frontend
- `requirements.txt` included

