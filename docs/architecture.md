# Mizaaj Architecture

## Product Boundary

Mizaaj starts as a private memory product, not a global clothing database. The MVP is useful
when it only knows one user's fit history. Shared product intelligence can be added later through
new providers and scopes.

## Data Layers

1. Raw evidence
   - Uploaded images, page URLs, copied text, order notes, tag photos, and size chart screenshots.
   - Stored as capture assets and text blocks.

2. Extracted claims
   - Structured facts inferred from raw evidence.
   - Each claim has subject, predicate, value, source, confidence, and status.
   - Claims are drafts until the user confirms them.

3. Product snapshots
   - Best-effort item records created from confirmed capture data.
   - SKU and canonical URLs strengthen identity when available.
   - A capture keeps a stable provisional identity until it is confirmed or explicitly linked to
     an existing product. Saved conversations are rewritten to that canonical product identity.

4. Private fit memory
   - Confirmed profile facts, product evidence, purchases, returns, and fit outcomes.
   - Stored in Cognee per user dataset.

5. Mizaaj Atlas
   - Curated public product evidence, size guides, and category caveats.
   - Stored in a separate Cognee Cloud dataset.
   - Used only as source-labeled public evidence and never merged into private user memory.

6. Grounded answers
   - Private recall and Atlas recall run concurrently and return context rather than composing the
     final answer themselves.
   - A strict-schema reasoning gateway applies the evidence order: exact outcomes, comparable
     outcomes, current profile and private memory, current item facts, then Atlas.
   - Advice is never stored automatically. Memory cards and try-on outcomes require user approval.

## Backend Modules

- `api/`: FastAPI route modules.
- `core/`: settings, dependencies, and error mapping.
- `domain/captures`: evidence capture and confirmation workflow.
- `domain/extraction`: AI extraction gateway.
- `domain/memory`: Cognee local and Cognee Cloud memory gateway.
- `domain/atlas`: seed fallback and Cognee Cloud public Atlas gateway.
- `domain/reasoning`: grounded answer synthesis and structured memory/outcome proposals.
- `domain/products`: product snapshot model.
- `domain/profiles`: private fit profile.
- `domain/purchases`: purchase outcome and feedback.
- `domain/recommendations`: fit recommendation service.
- `domain/uploads`: S3-compatible upload gateway.
- `storage`: Postgres-backed persistence with a test-only in-memory adapter.

## Provider Strategy

Business services depend on protocols, not concrete providers:

- `MemoryGateway`: local Cognee and Cognee Cloud.
- `AtlasGateway`: local seed fallback and Cognee Cloud public Atlas recall.
- `ExtractionGateway`: OpenRouter text and vision extraction.
- `UploadGateway`: S3-compatible presigned uploads.

Tests use explicit provider overrides. Runtime configuration points at real infrastructure.

## Private Memory Scope

Every user's Cognee dataset is derived from a configurable prefix:

```text
mizaaj_private_<user_uuid_without_dashes>
```

Public product memory uses the separate Atlas dataset:

```text
mizaaj_atlas_seed_v2
```

Private memory wins over Atlas when they conflict. Atlas can help first-time decisions, but it must
stay source-labeled and non-personal.

Postgres remains the source of truth. Cognee is a derived, user-scoped semantic and graph index.
Destructive rebuilds delete each indexed item and use Cognee's unified per-item forget operation as
a Cloud compatibility fallback before writing canonical records again.

## Database Path

The current persistence layer uses Postgres tables with JSONB payloads:

- fit_profiles
- captures
- product_snapshots
- purchase_records
- saved_memory_records

This keeps raw evidence, extracted drafts, and product snapshots durable while the schema is still
evolving. Hot query paths can be normalized later without changing the route and service layers.
