# Mizaaj

![Backend](https://img.shields.io/badge/FastAPI-0f172a?logo=fastapi)
![Frontend](https://img.shields.io/badge/React%20%2B%20Vite-111827?logo=react)
![Memory](https://img.shields.io/badge/Memory-Cognee-38bdf8)
![License](https://img.shields.io/badge/License-MIT-f8fafc)

Mizaaj is a private AI fit-memory assistant for online clothing decisions.

It turns clothing tags, product screenshots, size charts, order notes, and try-on feedback into a
personal memory of what actually fits you. Instead of guessing from generic reviews, you can ask
Mizaaj whether a new item matches your own history, silhouette preferences, fabric sensitivities,
and confirmed outcomes.

<img width="1440" height="782" alt="Screenshot 2026-07-06 at 2 48 41 PM" src="https://github.com/user-attachments/assets/fee25932-2d7f-4368-ad44-07cfb3d84ae1" />

## Why It Exists

Online size charts forget the most important context: your body, your taste, and your past mistakes.
Mizaaj keeps that context private and recallable.

Cognee is the durable memory layer. Mizaaj uses it to remember confirmed profile facts, approved
product evidence, saved conversation insights, and real purchase outcomes, then recall them during
future fit questions.

## What Works

- Ask-first chat flow grounded in private Cognee recall.
- Mobile-friendly capture with camera/gallery uploads.
- OpenRouter text and vision extraction into reviewable product drafts.
- Confirmed product snapshots with image evidence.
- Conversation-to-memory approval with product linking.
- Purchase outcome tracking for kept, returned, exchanged, and altered items.
- Saved memory, product, capture, profile, and privacy CRUD APIs.
- Local Cognee mode plus Cognee Cloud provider support.
- Mizaaj Atlas: Cognee Cloud public fit intelligence seeded from source-labeled product pages and
  size guides, with a local seed fallback.
- Optional Clerk authentication shell for account-based user isolation.

## Architecture

```text
frontend/    React, Vite, TypeScript, shadcn-style UI
backend/     FastAPI domain services and API routes
docs/        Architecture, model choice, and Atlas identity notes
```

The backend keeps the important memory boundaries separate:

```text
raw evidence -> extracted drafts -> confirmed product snapshots
             -> saved chat memories -> purchase outcomes -> Cognee recall
```

Provider boundaries are intentionally explicit:

- `MemoryGateway`: Cognee local or Cognee Cloud.
- `AtlasGateway`: local seed fallback or Cognee Cloud public Atlas recall.
- `ExtractionGateway`: OpenRouter structured text/vision extraction.
- `UploadGateway`: S3-compatible storage such as MinIO, S3, or R2.
- `MizaajStore`: Postgres persistence with an in-memory test adapter.

## Quick Start

Requirements:

- Python 3.12
- `uv`
- Node.js 20+
- Docker

Start local infrastructure:

```powershell
docker compose up -d postgres minio minio-bucket
```

Start the API:

```powershell
cd backend
uv sync --dev
Copy-Item .env.example .env
uv run uvicorn app.main:app --reload --port 8080
```

Start the app:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`.

## Environment

Backend values live in `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://mizaaj:mizaaj@localhost:5432/mizaaj
UPLOAD_PROVIDER=s3
S3_ENDPOINT_URL=http://localhost:9000
S3_PUBLIC_BASE_URL=http://localhost:9000/mizaaj-uploads
OPENROUTER_API_KEY=
MEMORY_PROVIDER=cognee_cloud
ATLAS_PROVIDER=cognee_cloud
ATLAS_DATASET_NAME=mizaaj_atlas_seed_v2
COGNEE_DATASET_PREFIX=mizaaj_user
COGNEE_CLOUD_BASE_URL=
COGNEE_CLOUD_API_KEY=
```

Frontend values live in `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_CLERK_PUBLISHABLE_KEY=
VITE_USER_ID=00000000-0000-4000-8000-000000000001
```

For phone testing, expose both the API and object-storage URLs through your LAN IP:

```powershell
$env:CORS_ORIGINS='["http://localhost:5173","http://127.0.0.1:5173","http://YOUR_LAN_IP:5173"]'
$env:S3_ENDPOINT_URL='http://YOUR_LAN_IP:9000'
$env:S3_PUBLIC_BASE_URL='http://YOUR_LAN_IP:9000/mizaaj-uploads'
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
```

## Verification

Backend:

```powershell
cd backend
.\scripts\test-backend.ps1
```

Frontend:

```powershell
cd frontend
npm run test
npm run build
```

Live provider smoke tests are available in `backend/scripts/live-smoke.ps1`. Use `-SpendTokens`
only when you intentionally want to call configured LLM and memory providers.

Atlas can be dry-run or indexed from the backend:

```powershell
cd backend
uv run python scripts/seed_atlas.py
uv run python scripts/seed_atlas.py --spend-credits --forget-first
```
