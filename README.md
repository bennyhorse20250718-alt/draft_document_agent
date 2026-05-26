# Project Summary — Draft Document AI Agent

## Overview

A **RAG-powered official document drafting assistant** that uses a local vector knowledge base and an LLM to generate formal documents (government/corporate) based on reference materials. Users upload source documents, search the knowledge base, then generate, refine, and export drafts.

---

## Architecture

```
┌─────────────────────────┐      HTTP      ┌──────────────────────────┐
│  Frontend (Next.js 16)  │ ─────────────► │  Backend (FastAPI)       │
│  Tailwind CSS / TypeScript│              │  Python 3.x / Uvicorn    │
│  localhost:3000          │              │  localhost:8000           │
└─────────────────────────┘              └──────────┬───────────────┘
                                                      │
                               ┌──────────────────────┼──────────────────┐
                               ▼                      ▼                  ▼
                    ChromaDB (vector store)   OpenAI-compatible    sentence-transformers
                    local / cloud / http       LLM API              (embedding, local)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Backend | FastAPI, Uvicorn, Python |
| Embeddings | `fastembed` / `sentence-transformers` (`all-MiniLM-L6-v2` default) |
| Vector Store | ChromaDB (local SQLite, self-hosted HTTP, or Chroma Cloud) |
| LLM | Any OpenAI-compatible API (OpenRouter default; configurable) |
| Document Parsing | PyMuPDF, python-docx, pypdf |
| Export | `python-docx` → `.docx` download |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
public_version/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app entry point, CORS, lifespan
│   │   ├── config.py           # Pydantic settings (all env vars)
│   │   ├── schemas.py          # Request / response models
│   │   ├── chroma_client.py    # ChromaDB client factory (local/cloud/http)
│   │   ├── routes/
│   │   │   ├── documents.py    # Upload, list, delete documents
│   │   │   ├── search.py       # Semantic search, preview, PDF serving
│   │   │   ├── draft.py        # Generate, stream, refine drafts
│   │   │   └── export.py       # Export draft as DOCX
│   │   └── services/
│   │       ├── ingestion.py    # Parse + chunk + embed + store documents
│   │       ├── retrieval.py    # Semantic search wrapper
│   │       ├── generation.py   # LLM prompting + citation extraction
│   │       └── export_service.py # DOCX export
│   ├── ingest_documents.py     # CLI: bulk ingest from Document/txt/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/                # Next.js App Router pages
│   │   ├── components/         # Shared UI components
│   │   └── lib/api.ts          # Central API client (typed fetch wrappers)
│   ├── package.json
│   └── Dockerfile
├── Document/
│   ├── pdf/<year>/             # Source PDFs (read-only reference)
│   └── txt/<year>/             # Parsed plain-text versions used for ingestion
├── docker-compose.yml
├── start_backend.ps1
├── start_frontend.ps1
├── DEPLOYMENT.md               # Self-hosted VM deployment guide
└── DEPLOY_CLOUD.md             # Render + Vercel cloud deployment guide
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/documents/upload` | Upload & ingest a PDF/DOCX/TXT file |
| `GET` | `/documents` | List all ingested documents |
| `DELETE` | `/documents/{doc_id}` | Remove a document from the knowledge base |
| `POST` | `/search` | Semantic search with optional filters |
| `GET` | `/search/preview/{doc_id}` | Full text preview of a document |
| `GET` | `/search/pdf/{doc_id}` | Stream original PDF |
| `POST` | `/draft` | Generate full draft with citations |
| `POST` | `/draft/stream` | Stream draft tokens (SSE) |
| `POST` | `/draft/refine` | Refine the entire draft |
| `POST` | `/draft/refine-section` | Rewrite a specific section |
| `POST` | `/draft/regenerate-selection` | Regenerate a highlighted passage |
| `POST` | `/export/docx` | Export draft as DOCX |
| `GET` | `/export/download/{filename}` | Download exported file |

---

## Key Environment Variables (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `LLM_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible endpoint |
| `LLM_API_KEY` | _(required)_ | API key for the LLM provider |
| `LLM_MODEL` | `openai/gpt-4o-mini` | Model slug |
| `LLM_MAX_TOKENS` | `16384` | Max tokens per LLM response |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local sentence-transformers model |
| `CHROMA_MODE` | `local` | `local` \| `cloud` \| `http` |
| `CHROMA_DB_PATH` | `./data/chroma_db` | Path for local ChromaDB |
| `CHROMA_CLOUD_API_KEY` | _(cloud mode)_ | Chroma Cloud API key |
| `CHROMA_CLOUD_TENANT` | _(cloud mode)_ | Chroma Cloud tenant ID |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS allowed origins |

---

## How to Run

### Local (PowerShell)

```powershell
# Backend
.\start_backend.ps1

# Frontend (separate terminal)
$env:Path = "C:\nodejs;" + $env:Path
.\start_frontend.ps1
```

### Docker Compose

```bash
# Copy and fill in environment variables
cp backend/.env.example backend/.env

# Build and start both services
docker compose up --build
```

Frontend → http://localhost:3000  
Backend API → http://localhost:8000  
API Docs (Swagger) → http://localhost:8000/docs

### Ingest Documents (CLI)

```bash
cd backend
python ingest_documents.py
```

Place `.txt` source files under `Document/txt/<year-folder>/` before ingesting.

---

## Deployment Options

- **Self-hosted VM**: Docker Compose on any Linux server — see [DEPLOYMENT.md](DEPLOYMENT.md)
- **Cloud (Render + Vercel)**: Backend on Render (Docker), frontend on Vercel — see [DEPLOY_CLOUD.md](DEPLOY_CLOUD.md)

---

## Using a Custom LLM Provider (e.g. GLM / Zhipu AI)

Because the backend uses the standard OpenAI Python SDK pointed at a configurable `LLM_BASE_URL`, **any OpenAI-compatible API works**. See the section below for Zhipu AI GLM.
