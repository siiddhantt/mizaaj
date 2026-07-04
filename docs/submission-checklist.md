# Mizaaj Submission Checklist

This is the working truth for hackathon readiness. An item is only done when it is implemented, covered by useful tests, and manually smoke-tested through the API or UI when relevant.

## Product Scope

Mizaaj is a private AI fit-memory assistant. Users attach clothing evidence, ask fit questions, approve what should become memory, and later get advice grounded in their own saved outcomes and Cognee recall.

Out of scope before submission unless all core items are done:

- Public/shared brand memory.
- Browser extension capture.
- Affiliate or monetization flows.
- Large recommendation marketplace features.

## Coding Standard

- Keep code concise, typed, modular, and self-explanatory.
- Prefer small domain services over frontend-driven business logic.
- Preserve clear provider boundaries: `MemoryGateway`, `ExtractionGateway`, `UploadGateway`, and `MizaajStore`.
- Store raw evidence, extracted drafts, confirmed snapshots, purchases, and saved memories as separate concepts.
- Add error handling where users or API clients can recover.
- Mark checklist items done only after tests and a real smoke path pass.

## Current Done

- [x] React/Vite frontend renamed visually to Mizaaj.
- [x] FastAPI backend with provider abstractions.
- [x] Postgres app persistence.
- [x] S3-compatible upload intents and MinIO local setup.
- [x] OpenRouter structured extraction with fallback parsing.
- [x] Regional size-label normalization, including `UK L` and `EUR L`.
- [x] Non-image upload evidence uses text extraction instead of vision.
- [x] Ask-first flow with private memory recall.
- [x] Conversation-to-memory draft approval.
- [x] Saved chat memory listing.
- [x] Saved chat memory delete-one and clear-all, with Cognee rebuild.
- [x] Purchase outcome create/list/get/update/delete, with Cognee rebuild.
- [x] Capture list/get/delete.
- [x] Confirmed capture deletion removes product memory when no outcomes depend on it.
- [x] Confirmed capture deletion is blocked when saved outcomes depend on it.
- [x] Product snapshot delete.
- [x] Product snapshot deletion is blocked when saved outcomes depend on it.
- [x] Product deletion demotes the source capture back to an unconfirmed draft.
- [x] Profile updates rebuild private Cognee memory instead of leaving stale profile facts.
- [x] Delete all app data for current user through API, including Cognee memory.
- [x] README says Mizaaj and has current setup notes.
- [x] Optional Clerk auth shell and backend JWT verification.
- [x] Cognee local provider path.
- [x] Cognee Cloud provider path with request-shape tests.
- [x] Windows backend verification runner for lint, format, and tests.
- [x] Full fake-provider API workflow simulation.
- [x] Live text-only provider smoke against Postgres, OpenRouter, and local Cognee.
- [x] Live upload-backed provider smoke against Postgres, MinIO, OpenRouter, and local Cognee.
- [x] Live CRUD smoke for saved memory deletion and purchase outcome update/delete.
- [x] API failure-contract tests for validation, missing resources, and idempotent deletion.
- [x] API degraded-recall contract when the memory provider is slow or unavailable.
- [x] Frontend memory delete controls.
- [x] Backend tests pass.
- [x] Frontend tests and production build pass.

## Must Finish Before Submission

- [x] Capture API CRUD.
  - [x] List captures for current user.
  - [x] Get capture by id with ownership check.
  - [x] Delete unconfirmed capture.
  - [x] Decide and implement confirmed capture deletion semantics.
  - [x] Tests cover deletion behavior.

- [x] Product snapshot CRUD boundaries.
  - [x] Decide whether confirmed products can be edited directly or only through recapture.
  - [x] Delete product snapshot safely when there are no purchases.
  - [x] Block deletion or cascade intentionally when purchases exist.
  - [x] Tests cover product dependency behavior.

- [x] Profile memory consistency.
  - [x] Updating profile should rebuild private Cognee memory.
  - [ ] Profile UI should feel like onboarding, not a raw form.
  - [x] Tests cover profile update and recall.

- [ ] App-wide privacy controls.
  - [x] Clear saved chat memories through API and Memory UI.
  - [x] Clear all private Cognee memory through API.
  - [x] Delete all app data for current user through API.
  - [ ] Explain destructive actions in UI.
  - [x] Tests cover DB state and Cognee state after deletion.

- [ ] Cloud smoke test.
  - [ ] Switch `.env` to `MEMORY_PROVIDER=cognee_cloud`.
  - [ ] Run remember/recall/delete against Cognee Cloud credits.
  - [ ] Confirm dataset naming and auth work.
  - [ ] Decide final demo default: local fallback plus cloud mode, or cloud primary.

- [ ] Full API manual flow.
  - [x] Add fake-provider workflow test for the full private fit-memory path.
  - [x] Clean local app rows and local Cognee memory at live-smoke start.
  - [x] Create profile through live API path.
  - [x] Upload real clothing image or screenshot.
  - [x] Extract text-only draft through OpenRouter.
  - [x] Ask with the extracted capture.
  - [x] Save memory cards.
  - [x] Recall saved memory.
  - [x] Confirm capture into product memory.
  - [x] Log try-on outcome.
  - [x] Update and delete outcome.
  - [x] Delete saved memory.
  - [x] Verify deleted facts no longer recall when they should not.

- [ ] Full mobile UI manual flow.
  - [ ] Phone camera upload with multiple photos.
  - [ ] Ask screen does not clip on mobile or desktop.
  - [ ] Capture screen does not clip on mobile or desktop.
  - [ ] Memory delete and clear controls work.
  - [ ] Loading states are visible for extraction, Cognee indexing, and deletes.
  - [ ] Empty states are clean and not generic.

- [ ] Submission polish.
  - [x] README says Mizaaj and has current setup notes.
  - [ ] Docs explain why Cognee is necessary.
  - [ ] Demo script matches the implemented product.
  - [ ] Screenshots/video show a real clothing example.
  - [ ] Track choice is explicit: Cognee Cloud primary, OSS fallback.

## Nice If Core Is Done

- [ ] Shared brand-memory design document only, no rushed implementation.
- [ ] One anonymized public-memory prototype behind a disabled feature flag.
- [ ] Better extraction editing UI for title, brand, material, sizes, and claims.
- [ ] Export user memory as JSON.
- [ ] Browser-extension design stub, no extension implementation.

## Test Commands

Backend:

```powershell
cd D:\Development\Projects\cognee-hackathon\mizaaj\backend
.\scripts\test-backend.ps1
```

Fast backend loop without lint:

```powershell
cd D:\Development\Projects\cognee-hackathon\mizaaj\backend
.\scripts\test-backend.ps1 -SkipLint
```

Verbose workflow simulation:

```powershell
cd D:\Development\Projects\cognee-hackathon\mizaaj\backend
.\scripts\test-backend.ps1 -SkipLint -VerboseWorkflow
```

Live provider smoke:

```powershell
cd D:\Development\Projects\cognee-hackathon\mizaaj\backend
.\scripts\live-smoke.ps1
.\scripts\live-smoke.ps1 -SpendTokens
.\scripts\live-smoke.ps1 -SpendTokens -ImageUrl "https://example.com/clothing-tag.jpg"
```

Frontend:

```powershell
cd D:\Development\Projects\cognee-hackathon\mizaaj\frontend
npm run test
npm run build
```

Local services:

```powershell
cd D:\Development\Projects\cognee-hackathon\mizaaj
docker compose up -d
```
