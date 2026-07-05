# Mizaaj Backend

FastAPI service for Mizaaj, a private-first clothing fit memory product powered by Cognee.

## Local Setup

```bash
cd fitrecall
docker compose up -d postgres minio minio-bucket
```

```bash
cd fitrecall/backend
uv python install 3.12
uv sync --dev
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8080
```

For phone testing on the same Wi-Fi, bind the API to the LAN and make S3 URLs phone-reachable:

```powershell
$env:CORS_ORIGINS='["http://localhost:5173","http://127.0.0.1:5173","http://192.168.1.9:5173"]'
$env:S3_ENDPOINT_URL='http://192.168.1.9:9000'
$env:S3_PUBLIC_BASE_URL='http://192.168.1.9:9000/mizaaj-uploads'
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
```

The default runtime uses Postgres persistence, S3-compatible upload intents, OpenRouter extraction,
and local Cognee memory. Fill the missing keys in `.env` before running capture extraction or memory
flows that need those providers.

## Providers

- `STORE_PROVIDER=postgres`: persists profiles, captures, product snapshots, and purchases in Postgres.
- `MEMORY_PROVIDER=cognee_local`: calls `cognee.remember` and `cognee.recall` against local Cognee.
- `MEMORY_PROVIDER=cognee_cloud`: routes memory calls through Cognee Cloud.
- `ATLAS_PROVIDER=seed`: recalls curated public Atlas records from `backend/data` for local demos.
- `ATLAS_PROVIDER=cognee_cloud`: recalls the public Atlas dataset from Cognee Cloud.
- `UPLOAD_PROVIDER=s3`: returns presigned PUT URLs for AWS S3, MinIO, R2, or compatible storage.
- `EXTRACTION_PROVIDER=openrouter`: extracts reviewable product drafts with OpenRouter.

Local Cognee memory uses `OPENROUTER_API_KEY` for Cognee's LLM path unless `COGNEE_LLM_API_KEY`
is set. It uses `fastembed` by default for local embeddings so memory writes do not require a
second paid embedding provider during development.

For OpenRouter extraction, fill `OPENROUTER_API_KEY` and keep separate text and vision models:

- `OPENROUTER_TEXT_MODEL=deepseek/deepseek-v4-flash` for cheap text-only product pages,
  copied descriptions, and order text.
- `OPENROUTER_VISION_MODEL=qwen/qwen3.7-plus` for screenshots, clothing tags, and size charts.

The extractor only writes reviewable drafts. Confirmed memories are still created later in the
capture confirmation flow.

## Core Routes

- `POST /api/v1/captures`: create an extracted product draft from text/assets.
- `POST /api/v1/captures/{id}/confirm`: confirm claims into a product snapshot and private memory.
- `POST /api/v1/ask`: ask Mizaaj against profile, product evidence, saved outcomes, and Cognee recall.
- `POST /api/v1/ask/remember`: save approved conversation facts as private memory.
- `DELETE /api/v1/ask/memories/{id}`: delete one saved conversation memory.
- `DELETE /api/v1/memory/users/{user_id}/app-data`: delete all app rows and private Cognee memory.

## API

OpenAPI docs are available at `http://localhost:8080/docs`.

## Verification

Use the Windows runner to avoid inline environment-variable quoting issues:

```powershell
cd D:\Development\Projects\cognee-hackathon\fitrecall\backend
.\scripts\test-backend.ps1
```

For a fast backend loop:

```powershell
.\scripts\test-backend.ps1 -SkipLint
```

For the explicit live provider smoke, first run the dry config check:

```powershell
.\scripts\live-smoke.ps1
```

Then run the text-only OpenRouter plus local Cognee path when you intentionally want to spend a
small amount of provider credits:

```powershell
.\scripts\live-smoke.ps1 -SpendTokens
```

To spend one vision request against a public image URL:

```powershell
.\scripts\live-smoke.ps1 -SpendTokens -ImageUrl "https://example.com/clothing-tag.jpg"
```
