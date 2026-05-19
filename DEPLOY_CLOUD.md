# Cloud Deployment Guide
## Stack: Chroma Cloud · Render (Backend) · Vercel (Frontend)

```
Users → Vercel (Next.js frontend)
              ↓ NEXT_PUBLIC_API_URL
        Render (FastAPI backend)
              ├── OpenRouter API       (LLM)
              ├── Chroma Cloud         (vector knowledge base)
              └── sentence-transformers (embedding, runs on Render)
```

---

## Accounts You Need

| Service | Purpose | Free tier |
|---|---|---|
| [github.com](https://github.com) | Host your code | Yes |
| [openrouter.ai](https://openrouter.ai) | LLM API calls | Pay-per-use |
| [cloud.trychroma.com](https://cloud.trychroma.com) | Vector database | 1M embeddings / 1 GB |
| [render.com](https://render.com) | Backend hosting (Docker) | Starter $7/mo (needed for always-on) |
| [vercel.com](https://vercel.com) | Frontend hosting (Next.js) | Yes |

---

## Before You Start — Checklist

- [ ] You have a Chroma Cloud account with a cluster created  
- [ ] You have your Chroma Cloud **API key**, **Tenant ID**, and **Database name** ready  
- [ ] Your local knowledge base is populated (`backend/data/chroma_db/` exists and has data)  
- [ ] You have an OpenRouter API key  
- [ ] Git is installed locally  

---

## Step 1 — Prepare the Repository

### 1.1 Protect your secrets

Make sure `backend/.env` is listed in `.gitignore` before your first commit:

```bash
# In project root
echo "backend/.env" >> .gitignore
echo "backend/data/" >> .gitignore
```

### 1.2 Push to GitHub

```bash
cd path/to/public_version

git init
git add .
git commit -m "initial: draft document AI agent"

# Create a new repo on github.com (do NOT initialise with README), then:
git remote add origin https://github.com/YOUR_USERNAME/draft-agent.git
git push -u origin main
```

---

## Step 2 — Migrate Local Knowledge Base to Chroma Cloud

You already have documents ingested locally. This step copies all vectors to Chroma Cloud **without re-embedding** (fast, typically < 2 minutes).

### 2.1 Update `backend/.env` with Chroma Cloud credentials

Add the following lines to your `backend/.env` (keep `CHROMA_MODE=local` for now — the script reads local as source):

```dotenv
# Keep as source during migration
CHROMA_MODE=local
CHROMA_DB_PATH=./data/chroma_db

# Destination: Chroma Cloud
CHROMA_CLOUD_API_KEY=ck-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHROMA_CLOUD_TENANT=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CHROMA_CLOUD_DATABASE=document
```

> Your credentials are already in `backend/.env`. Just confirm they are correct.

### 2.2 Run the migration script

```bash
# Activate your Python virtual environment first
cd backend
.\venv\Scripts\Activate.ps1          # Windows PowerShell
# source venv/bin/activate           # macOS / Linux

python migrate_to_chroma_cloud.py
```

Expected output:

```
[INFO] Local collection has X,XXX chunks.
[INFO] Connecting to Chroma Cloud (tenant=..., database=document) ...
[INFO] Cloud collection currently has 0 chunks.
[INFO] Starting migration in batches of 200 ...
  [ 20.7%]  200/XXX  — migrated 200, skipped 0
  ...
[DONE] Migration complete.
       ✓ All chunks are present in Chroma Cloud.
```

The script is idempotent — safe to re-run if interrupted.

---

## Step 3 — Deploy the Backend on Render

### 3.1 Create a new Web Service

1. Go to [render.com](https://render.com) → **New → Web Service**
2. Click **Connect a GitHub repository** and select your repo
3. Configure:

   | Setting | Value |
   |---|---|
   | **Name** | `draft-agent-backend` |
   | **Root Directory** | `backend` |
   | **Runtime** | `Docker` |
   | **Instance Type** | **Starter** ($7/mo) — free tier sleeps after 15 min inactivity |

   > **No persistent disk needed** — ChromaDB data lives in Chroma Cloud.

### 3.2 Set environment variables in Render

In the **Environment** tab, add these key-value pairs:

```
LLM_BASE_URL              https://openrouter.ai/api/v1
LLM_API_KEY               sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL                 openai/gpt-4o-mini
OPENROUTER_SITE_NAME      Draft Document AI Agent

EMBEDDING_MODEL           all-MiniLM-L6-v2

CHROMA_MODE               cloud
CHROMA_CLOUD_API_KEY      ck-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHROMA_CLOUD_TENANT       xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
CHROMA_CLOUD_DATABASE     document

DOCUMENTS_PATH            ./data/documents
EXPORT_PATH               ./data/exports
HOST                      0.0.0.0
PORT                      8000
ALLOWED_ORIGINS           https://your-app.vercel.app
```

> **`ALLOWED_ORIGINS`**: set this after Step 4 once you know your Vercel URL. Use the exact URL with no trailing slash.

### 3.3 Deploy

Click **Deploy Web Service**. The first build takes 3–5 minutes (Docker image + downloading sentence-transformers model).

Note your backend URL: `https://draft-agent-backend-xxxx.onrender.com`

### 3.4 Verify backend is alive

```
GET https://draft-agent-backend-xxxx.onrender.com/health
→ {"status": "ok"}
```

---

## Step 4 — Deploy the Frontend on Vercel

### 4.1 Create a new project

1. Go to [vercel.com](https://vercel.com) → **Add New → Project**
2. Import your GitHub repository
3. Configure:

   | Setting | Value |
   |---|---|
   | **Framework Preset** | Next.js (auto-detected) |
   | **Root Directory** | `frontend` |
   | **Build Command** | `npm run build` (default) |
   | **Output Directory** | `.next` (default) |

   > Vercel builds Next.js natively — **do not use the Dockerfile** for Vercel.

### 4.2 Set environment variables

In the **Environment Variables** section before deploying, add:

| Name | Value | Environments |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `https://draft-agent-backend-xxxx.onrender.com` | Production, Preview, Development |

> `NEXT_PUBLIC_*` variables are baked into the JavaScript bundle at **build time**. If you change this value later you must redeploy.

### 4.3 Deploy

Click **Deploy**. Build takes ~1–2 minutes.

Your app is live at: `https://your-app.vercel.app`

---

## Step 5 — Wire Up CORS

Go back to **Render → draft-agent-backend → Environment** and update:

```
ALLOWED_ORIGINS    https://your-app.vercel.app
```

Click **Save Changes** — Render auto-redeploys the backend.

If you add a custom domain to Vercel later, update this value again to match the custom domain.

---

## Step 6 — Add a Custom Domain (Optional)

### Vercel (frontend)
Settings → Domains → Add domain → follow the DNS instructions.

### Update backend CORS after custom domain
```
ALLOWED_ORIGINS    https://yourdomain.com
```

---

## Step 7 — Verify the Full Stack

| Check | Expected result |
|---|---|
| `https://your-app.vercel.app` | App loads, no white screen |
| `https://your-backend.onrender.com/health` | `{"status":"ok"}` |
| `https://your-backend.onrender.com/docs` | FastAPI Swagger UI |
| Open browser DevTools → Network tab, make a search | No CORS errors |
| Draft a document | Streams content, shows citations |

---

## Uploading New Documents After Deployment

You have two options to add new documents to the knowledge base:

### Option A — Upload via the UI
Use the **Documents** page in the app to upload PDF / DOCX / TXT files. They are ingested directly into Chroma Cloud.

### Option B — Bulk ingest on Render (Shell)
1. On Render, go to your web service → **Shell** tab
2. Copy your text files into the container's `data/documents_source/` folder (or adjust the path)
3. Run:
   ```bash
   python ingest_documents.py
   ```

---

## Updating the Application

Push changes to the `main` branch — both Render and Vercel auto-deploy on every push.

```bash
git add .
git commit -m "your change description"
git push origin main
```

- **Vercel**: frontend rebuilds in ~1 minute
- **Render**: backend rebuilds Docker image in ~3–5 minutes

---

## Cost Summary

| Service | Plan | Cost |
|---|---|---|
| Vercel | Hobby (free) | $0/mo |
| Render | Starter (always-on) | ~$7/mo |
| Chroma Cloud | Free tier | $0/mo (up to 1M embeddings) |
| OpenRouter | Pay per token | ~$0.15–$2 per 1M tokens depending on model |
| **Total** | | **~$7/mo + LLM usage** |

> Render's **free tier** sleeps after 15 minutes of inactivity and takes ~30 seconds to wake up on the next request. Upgrade to Starter to avoid cold starts for end users.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Render build fails | Wrong root directory | Set Root Directory to `backend` in Render settings |
| `{"detail":"Not Found"}` on all API routes | Backend started on wrong path | Check Render logs: `docker compose logs` |
| CORS error in browser | `ALLOWED_ORIGINS` mismatch | Must exactly match your Vercel URL, no trailing slash |
| Blank page on Vercel | Wrong `NEXT_PUBLIC_API_URL` | Update in Vercel → Settings → Environment Variables, then redeploy |
| `401 Unauthorized` from OpenRouter | Wrong `LLM_API_KEY` | Update in Render → Environment |
| Chroma Cloud `401` | Wrong `CHROMA_CLOUD_API_KEY` | Regenerate key at cloud.trychroma.com |
| Chroma Cloud returns empty results | KB not migrated | Re-run `python migrate_to_chroma_cloud.py` locally |
| Render cold start (~30s delay) | Free tier sleeping | Upgrade to Starter plan |
| sentence-transformers OOM | Instance too small | Upgrade Render to Standard (2 GB RAM) |
