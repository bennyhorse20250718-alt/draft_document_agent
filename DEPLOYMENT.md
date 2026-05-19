# Deployment Guide — Draft Document AI Agent

This guide covers two deployment paths. Choose based on your needs:

| | Option A — VPS + Docker | Option B — Vercel + Render |
|---|---|---|
| **Effort** | Medium (server admin) | Low (managed platforms) |
| **Cost** | ~$6–20/month (VPS) | Free tier available |
| **Data control** | Full | Render persistent disk |
| **Custom domain** | Yes | Yes |
| **Best for** | Full control, intranet, large doc sets | Quick public launch |

---

## Architecture Overview

**Option A — VPS**
```
Internet → Nginx (SSL) → Frontend :3000
                       → Backend  :8000 → OpenRouter API
                                        → ChromaDB (local disk)
                                        → Embedding model (local)
```

**Option B — Vercel + Render**
```
Internet → Vercel (Frontend)  →  browser fetch  →  Render (Backend :8000)
                                                         → OpenRouter API
                                                         → ChromaDB (persistent disk)
                                                         → Embedding model (local)
```

> **Why can't the backend run on Vercel?**  
> The FastAPI backend uses ChromaDB (file-based vector DB) and sentence-transformers (a local ML model). Both require a persistent filesystem and significant memory — incompatible with Vercel's serverless runtime. The frontend is a perfect fit for Vercel; the backend needs a container-capable host.

---

## Common Prerequisites

| Requirement | Notes |
|---|---|
| OpenRouter API key | Sign up at https://openrouter.ai |
| Domain name | Optional but recommended |
| Git + GitHub repo | Required for Vercel/Render (Option B) |
| Docker + Docker Compose | Required for Option A only |

---

## Knowledge Base Storage Options

The app uses **ChromaDB** as its vector database. Choose where the data lives:

| Mode | `CHROMA_MODE` | Where data lives | Best for |
|---|---|---|---|
| **Local** (default) | `local` | Disk on the same server | VPS / development |
| **Chroma Cloud** | `cloud` | Managed cloud | Vercel+Render, multi-region |
| **Self-hosted HTTP** | `http` | Separate ChromaDB container/VM | Private cloud, on-prem |

### Why move to Chroma Cloud for public deployment?

- **Render free tier**: no persistent disk needed → saves ~$7/month  
- **Shared state**: re-deploy without losing your indexed documents  
- **Vercel preview deploys**: all preview environments share the same KB  
- **Free tier**: 1 million embeddings / 1 GB storage at no cost  

### Setting up Chroma Cloud

1. Sign up at https://cloud.trychroma.com  
2. Create a **Cluster** — note the **Tenant ID** from the dashboard  
3. Create an **API Key** under Settings → API Keys  
4. Set in `backend/.env`:

```dotenv
CHROMA_MODE=cloud
CHROMA_CLOUD_API_KEY=chr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHROMA_CLOUD_TENANT=your-tenant-id       # from the Chroma Cloud dashboard
CHROMA_CLOUD_DATABASE=default_database   # or create a custom database name
```

5. Run ingestion once to populate the cloud database:

```bash
# Option A (VPS)
docker compose exec backend python ingest_documents.py

# Option B (Render) — use Render's Shell tab or a one-off job
python ingest_documents.py
```

After ingestion, the ChromaDB data lives in Chroma Cloud and survives any container restart or redeploy.

### Migrating an existing local KB to Chroma Cloud

If you already have a populated local ChromaDB and want to move it to Chroma Cloud **without re-ingesting from scratch**, use the migration script. It copies vectors, documents and metadata directly — no re-embedding required.

**Step 1 — Keep `CHROMA_MODE=local` and add cloud credentials to `backend/.env`:**

```dotenv
# Keep local as source
CHROMA_MODE=local
CHROMA_DB_PATH=./data/chroma_db

# Add cloud destination credentials
CHROMA_CLOUD_API_KEY=chr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
CHROMA_CLOUD_TENANT=your-tenant-id
CHROMA_CLOUD_DATABASE=default_database
```

**Step 2 — Run the migration script:**

```bash
# Local (from backend/ directory, with venv activated)
cd backend
python migrate_to_chroma_cloud.py
```

```bash
# On VPS (Docker)
docker compose exec backend python migrate_to_chroma_cloud.py
```

The script prints progress and is **idempotent** — safe to re-run if interrupted.

```
[INFO] Local collection has 4,820 chunks.
[INFO] Connecting to Chroma Cloud (tenant=abc123, database=default_database) ...
[INFO] Cloud collection currently has 0 chunks.
[INFO] Starting migration in batches of 200 ...
  [ 20.7%]  1000/4820  — migrated 1000, skipped 0
  [ 41.5%]  2000/4820  — migrated 2000, skipped 0
  ...
[DONE] Migration complete.
       Local chunks  : 4,820
       Cloud chunks  : 4,820
       ✓ All chunks are present in Chroma Cloud.
```

**Step 3 — Switch the app to use Chroma Cloud:**

```dotenv
CHROMA_MODE=cloud
```

Then restart the backend (`docker compose restart backend`).

---

## Option A — VPS + Docker Compose

### A1 — Provision a Server

- OS: Ubuntu 22.04 LTS
- Min specs: 2 vCPU / 4 GB RAM / 20 GB SSD
- Open ports: 22 (SSH), 80 (HTTP), 443 (HTTPS)
- Recommended providers: Hetzner (~€4/mo), DigitalOcean ($6/mo), AWS EC2 t3.small

### A2 — Install Docker

```bash
ssh root@YOUR_VPS_IP
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
sudo apt install -y docker-compose-plugin
```

### A3 — Copy Project Files

```bash
# From your local machine
scp -r ./public_version user@your-server-ip:/opt/draft-agent

# Or clone from your private repo
git clone https://github.com/your-org/draft-agent.git /opt/draft-agent
```

### A4 — Configure Environment Variables

```bash
cd /opt/draft-agent
cp backend/.env.example backend/.env
nano backend/.env
```

```dotenv
# LLM (OpenRouter)
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=openai/gpt-4o-mini
OPENROUTER_SITE_URL=https://yourdomain.com
OPENROUTER_SITE_NAME=Draft Document AI Agent

# Storage
CHROMA_DB_PATH=./data/chroma_db
DOCUMENTS_PATH=./data/documents
EXPORT_PATH=./data/exports

# Server
HOST=0.0.0.0
PORT=8000
ALLOWED_ORIGINS=https://yourdomain.com
```

Create a root `.env` for Docker Compose variable substitution:

```bash
cat > /opt/draft-agent/.env << 'EOF'
ALLOWED_ORIGINS=https://yourdomain.com
NEXT_PUBLIC_API_URL=https://yourdomain.com/api
EOF
```

### A5 — Update Frontend API URL

The Next.js app bakes `NEXT_PUBLIC_API_URL` at build time. Edit `frontend/Dockerfile`:

```dockerfile
# Replace the existing ENV line
ENV NEXT_PUBLIC_API_URL=https://yourdomain.com/api
```

### A6 — Add Documents and Build

```bash
# Place .txt documents in Document/txt/<year-folder>/
# Then build and start
cd /opt/draft-agent
docker compose up --build -d
docker compose ps        # verify both containers are Up

# Ingest documents into ChromaDB (run once)
docker compose exec backend python ingest_documents.py
```

### A7 — Configure Nginx + HTTPS

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/draft-agent`:

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Frontend
    location / {
        proxy_pass         http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        rewrite            ^/api/(.*)$ /$1 break;
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/draft-agent /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d yourdomain.com
```

### A8 — Verify

| Check | URL |
|---|---|
| Frontend | `https://yourdomain.com` |
| Backend health | `https://yourdomain.com/api/health` → `{"status":"ok"}` |
| API docs | `https://yourdomain.com/api/docs` |

---

## Option B — Vercel (Frontend) + Render (Backend)

### Why This Combination

- **Vercel** is purpose-built for Next.js: instant deploys from GitHub, global CDN, free HTTPS.
- **Render** supports Docker containers with persistent disks — exactly what ChromaDB and the embedding model need.

### B1 — Push Code to GitHub

```bash
cd path/to/public_version

git init
git add .
# Make sure backend/.env is in .gitignore BEFORE this commit
git commit -m "initial commit"

# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/draft-agent.git
git push -u origin main
```

> **Important:** Add `backend/.env` to `.gitignore` before the first push. It contains your API key.

```bash
# Add to .gitignore if not already present
echo "backend/.env" >> .gitignore
```

### B2 — Deploy Backend on Render

1. Go to [render.com](https://render.com) → **New → Web Service**
2. Connect your GitHub repo
3. Configure the service:

   | Setting | Value |
   |---|---|
   | **Root Directory** | `backend` |
   | **Runtime** | `Docker` |
   | **Instance Type** | Starter ($7/mo) or higher |

4. **Persistent Disk** — only required if using `CHROMA_MODE=local`:
   - Mount path: `/app/data`
   - Size: **2 GB** minimum
   - ✅ **Skip this step if using Chroma Cloud** (`CHROMA_MODE=cloud`) — no persistent disk needed

5. Set environment variables in Render's dashboard:

   ```
   LLM_BASE_URL          = https://openrouter.ai/api/v1
   LLM_API_KEY           = sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxx
   LLM_MODEL             = openai/gpt-4o-mini
   OPENROUTER_SITE_URL   = https://your-app.vercel.app
   OPENROUTER_SITE_NAME  = Draft Document AI Agent
   EMBEDDING_MODEL       = all-MiniLM-L6-v2
   # --- Knowledge base: choose ONE mode ---
   # Option 1: Chroma Cloud (recommended — no persistent disk needed)
   CHROMA_MODE           = cloud
   CHROMA_CLOUD_API_KEY  = chr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   CHROMA_CLOUD_TENANT   = your-tenant-id
   CHROMA_CLOUD_DATABASE = default_database
   # Option 2: Local disk (requires persistent disk mounted at /app/data)
   # CHROMA_MODE         = local
   # CHROMA_DB_PATH      = ./data/chroma_db
   # ---
   DOCUMENTS_PATH        = ./data/documents
   EXPORT_PATH           = ./data/exports
   HOST                  = 0.0.0.0
   PORT                  = 8000
   ALLOWED_ORIGINS       = https://your-app.vercel.app
   ```

   > Replace `your-app.vercel.app` with your actual Vercel URL (set it after Step B3, then update here).

6. Click **Deploy**. Wait for build to finish.  
   Note your backend URL: `https://draft-agent-xxxx.onrender.com`

7. **Ingest documents** — use Render's Shell tab (or the API):

   ```bash
   python ingest_documents.py
   ```

   > Since `Document/` is part of your repo (read-only mount via the Docker volume in docker-compose), on Render you'll need to either include the txt files in the repo or upload them separately. See the note below.

   **Note on documents with Render:** The `Document/` folder is mounted as a read-only volume in `docker-compose.yml`, but Render doesn't use docker-compose directly — it builds from `backend/Dockerfile`. You have two options:
   - **Include documents in repo** (small sets): Copy `Document/txt/` into `backend/data/documents_source/` and adjust the ingestion path.
   - **Upload via the API**: Use the `/documents/upload` endpoint after deployment to upload documents through the UI.

### B3 — Deploy Frontend on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repo
3. Set **Root Directory** to `frontend`
4. Add environment variable:

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://draft-agent-xxxx.onrender.com` |

   > This tells the frontend where to reach the backend. Use the URL from Step B2.

5. Click **Deploy**. Your app is live at `https://your-app.vercel.app`.

6. Go back to **Render** and update `ALLOWED_ORIGINS` to match your Vercel URL exactly.

### B4 — Custom Domain (Optional)

**Vercel:** Settings → Domains → Add your domain. Vercel provides instructions for DNS setup.

**No custom domain needed for the backend** — only the frontend domain matters for end users.

### B5 — Verify

| Check | URL |
|---|---|
| Frontend | `https://your-app.vercel.app` |
| Backend health | `https://draft-agent-xxxx.onrender.com/health` |
| CORS working | Open browser DevTools → Network tab, no CORS errors |

---

## Choosing an OpenRouter Model

Visit https://openrouter.ai/models to browse. Recommended options:

| Use case | Model slug | Notes |
|---|---|---|
| Cost-efficient | `openai/gpt-4o-mini` | Fast, cheap, good quality |
| Higher quality | `openai/gpt-4o` | Best for complex drafts |
| Free tier | `google/gemini-flash-1.5` | Free with rate limits |
| Long context | `anthropic/claude-3.5-sonnet` | 200k context window |

---

## Data Persistence

| Option | Where ChromaDB lives | Notes |
|---|---|---|
| Option A (VPS) | `./backend/data/` on host via Docker volume | Survives container restarts |
| Option B (Render) | Persistent disk at `/app/data` | Survives deploys; backed up by Render |

**Backup (Option A):**
```bash
tar -czf backup-$(date +%Y%m%d).tar.gz backend/data/
```

---

## Updating the Application

**Option A:**
```bash
cd /opt/draft-agent
git pull
docker compose up --build -d
```

**Option B:**
Push to `main` on GitHub — Vercel and Render auto-deploy on every push.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Backend returns 401 | Wrong `LLM_API_KEY` | Check env vars |
| Backend returns 404 on model | Wrong `LLM_MODEL` slug | Check https://openrouter.ai/models |
| CORS error in browser | `ALLOWED_ORIGINS` mismatch | Match the frontend URL exactly (no trailing slash) |
| Streaming draft hangs (Option A) | Nginx `proxy_read_timeout` too low | Increase to 120s |
| ChromaDB empty | Ingestion not run | Run `ingest_documents.py` |
| Render: container exits on start | Embedding model OOM | Upgrade to a larger instance (1 GB+ RAM) |
| Vercel: blank page | Wrong `NEXT_PUBLIC_API_URL` | Check Vercel environment variables, redeploy |
| Chroma Cloud: 401 Unauthorized | Wrong `CHROMA_CLOUD_API_KEY` | Regenerate key in Chroma Cloud dashboard |
| Chroma Cloud: empty results | Ingestion not run against cloud | Run `ingest_documents.py` with `CHROMA_MODE=cloud` set |


| Requirement | Notes |
|---|---|
| Linux server | Ubuntu 22.04+ recommended, min 2 vCPU / 4 GB RAM |
| Domain name | DNS A-record pointing to your server IP |
| Docker + Docker Compose | Install instructions below |
| OpenRouter API key | Sign up at https://openrouter.ai |
| Outbound HTTPS | Server must reach `openrouter.ai` on port 443 |

---

## Step 1 — Prepare the Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose plugin
sudo apt install -y docker-compose-plugin

# Verify
docker compose version
```

---

## Step 2 — Copy Project Files to Server

```bash
# From your local machine (replace user/host)
scp -r ./public_version user@your-server-ip:/opt/draft-agent

# Or clone from your private repo
ssh user@your-server-ip
git clone https://github.com/your-org/draft-agent.git /opt/draft-agent
```

---

## Step 3 — Configure Environment Variables

### Backend `.env`

```bash
cd /opt/draft-agent
cp backend/.env.example backend/.env
nano backend/.env
```

Set these values:

```dotenv
# ── LLM (OpenRouter) ──────────────────────────────────────────────
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx   # your OpenRouter key
LLM_MODEL=openai/gpt-4o-mini                            # or any model slug from openrouter.ai/models

# Optional: helps OpenRouter identify your app (recommended)
OPENROUTER_SITE_URL=https://yourdomain.com
OPENROUTER_SITE_NAME=Draft Document AI Agent

# ── Embedding ─────────────────────────────────────────────────────
EMBEDDING_MODEL=all-MiniLM-L6-v2

# ── Storage ───────────────────────────────────────────────────────
CHROMA_DB_PATH=./data/chroma_db
DOCUMENTS_PATH=./data/documents
EXPORT_PATH=./data/exports

# ── Server ────────────────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000
ALLOWED_ORIGINS=https://yourdomain.com      # your actual frontend URL
```

> **Security:** Never commit `backend/.env` to source control. It contains your API key.

### Root `.env` (Docker Compose overrides)

Create a `.env` file in the project root for Docker Compose variable substitution:

```bash
cat > /opt/draft-agent/.env << 'EOF'
ALLOWED_ORIGINS=https://yourdomain.com
NEXT_PUBLIC_API_URL=https://yourdomain.com/api
EOF
```

---

## Step 4 — Add Your Documents

Place the source documents in the `Document/` folder before building:

```bash
/opt/draft-agent/Document/
├── txt/
│   ├── hhb-e_2324/   ← your .txt files
│   ├── hhb-e_2425/
│   └── hhb-e_2526/
└── pdf/              ← original PDFs (optional, read-only mount)
```

---

## Step 5 — Update Frontend Dockerfile for Production API URL

The Next.js app bakes `NEXT_PUBLIC_API_URL` at **build time**. Update the frontend Dockerfile so it uses your public domain:

```dockerfile
# frontend/Dockerfile — replace the ENV line
ENV NEXT_PUBLIC_API_URL=https://yourdomain.com/api
```

Or pass it as a build arg — edit `docker-compose.yml`:

```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
    args:
      - NEXT_PUBLIC_API_URL=https://yourdomain.com/api
```

And in `frontend/Dockerfile`:

```dockerfile
ARG NEXT_PUBLIC_API_URL=https://yourdomain.com/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
```

---

## Step 6 — Build and Start Containers

```bash
cd /opt/draft-agent

# Build images and start in detached mode
docker compose up --build -d

# Verify containers are running
docker compose ps

# Tail logs
docker compose logs -f
```

Expected output:

```
NAME                STATUS          PORTS
draft-agent-backend-1   Up    0.0.0.0:8000->8000/tcp
draft-agent-frontend-1  Up    0.0.0.0:3000->3000/tcp
```

---

## Step 7 — Ingest Documents

Run the ingestion script inside the backend container to populate ChromaDB:

```bash
docker compose exec backend python ingest_documents.py
```

This only needs to run once (or whenever new documents are added).

---

## Step 8 — Install and Configure Nginx

```bash
sudo apt install -y nginx
```

Create a site config:

```bash
sudo nano /etc/nginx/sites-available/draft-agent
```

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # Frontend
    location / {
        proxy_pass         http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api/ {
        rewrite            ^/api/(.*)$ /$1 break;
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;   # allow time for LLM streaming
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/draft-agent /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## Step 9 — Enable HTTPS (Let's Encrypt)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
# Follow prompts; certbot auto-edits the nginx config
sudo systemctl reload nginx
```

Certbot auto-renews; confirm the timer is active:

```bash
sudo systemctl status certbot.timer
```

---

## Step 10 — Verify Deployment

| Check | URL |
|---|---|
| Frontend loads | `https://yourdomain.com` |
| Backend health | `https://yourdomain.com/api/health` → `{"status":"ok"}` |
| API docs | `https://yourdomain.com/api/docs` |

---

## Choosing an OpenRouter Model

Visit https://openrouter.ai/models to browse available models. Recommended options:

| Use case | Model slug | Notes |
|---|---|---|
| Cost-efficient | `openai/gpt-4o-mini` | Fast, cheap, good quality |
| Higher quality | `openai/gpt-4o` | Best for complex drafts |
| Free tier | `google/gemini-flash-1.5` | Free with rate limits |
| Long context | `anthropic/claude-3.5-sonnet` | 200k context window |

Set the chosen model in `backend/.env`:

```dotenv
LLM_MODEL=openai/gpt-4o-mini
```

Then restart the backend container:

```bash
docker compose restart backend
```

---

## Data Persistence

ChromaDB and exports are stored in `./backend/data/` on the host via the Docker volume mount. No data is lost when containers restart.

To back up:

```bash
tar -czf backup-$(date +%Y%m%d).tar.gz backend/data/
```

---

## Updating the Application

```bash
cd /opt/draft-agent

# Pull latest code
git pull

# Rebuild and restart
docker compose up --build -d
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Backend returns 401 | Wrong `LLM_API_KEY` | Check `backend/.env` |
| Backend returns 404 on model | Wrong `LLM_MODEL` slug | Check https://openrouter.ai/models |
| CORS error in browser | `ALLOWED_ORIGINS` mismatch | Match frontend URL exactly |
| Streaming draft hangs | `proxy_read_timeout` too low | Increase in Nginx config |
| ChromaDB empty | Ingestion not run | Run `docker compose exec backend python ingest_documents.py` |
| Container fails to start | Port already in use | `sudo lsof -i :8000` or `:3000` |
