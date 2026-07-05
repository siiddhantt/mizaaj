# Mizaaj Submission Checklist

This is the working truth for hackathon readiness. An item is only done when it is implemented, covered by useful tests, and manually smoke-tested through the API or UI when relevant.

## Product Scope

Mizaaj is a private AI fit-memory assistant. Users attach clothing evidence, ask fit questions, approve what should become memory, and later get advice grounded in their own saved outcomes, curated public fit intelligence, and Cognee recall.

The submission scope now includes Mizaaj Atlas: a small, curated, seeded public knowledge layer for product and brand fit intelligence. Atlas is not a user-review marketplace. It exists to show how Mizaaj can help a first-time user before their private memory is rich, while still keeping private user memories separate.

Out of scope before submission unless all core items are done:

- Browser extension capture.
- Affiliate or monetization flows.
- Large recommendation marketplace features.
- Unmoderated public user-review ingestion.

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
- [x] Mizaaj Atlas v2 clean seed schema and Cognee Cloud ingestion script.
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
  - [x] Profile UI should feel like onboarding, not a raw form.
  - [x] Tests cover profile update and recall.

- [ ] App-wide privacy controls.
  - [x] Clear saved chat memories through API and Memory UI.
  - [x] Clear all private Cognee memory through API.
  - [x] Delete all app data for current user through API.
  - [ ] Explain destructive actions in UI.
  - [x] Tests cover DB state and Cognee state after deletion.

- [ ] Cloud smoke test.
  - [x] Switch `.env` to `MEMORY_PROVIDER=cognee_cloud`.
  - [x] Confirm Cognee Cloud API key auth and dataset naming work.
  - [x] Run private remember/rebuild against Cognee Cloud credits.
  - [x] Run recall against Cognee Cloud from the app flow.
  - [ ] Run memory clear/rebuild against Cognee Cloud from the app flow.
  - [x] Decide final demo default: Cognee Cloud primary, local/seed fallback.

- [ ] Mizaaj Atlas curated knowledge layer.
  - [x] Define Atlas dataset naming, e.g. `mizaaj_atlas_seed_v2`, separate from private user datasets.
  - [x] Create structured seed files for brands, products, size charts, fabric notes, and fit risks.
  - [x] Remove demo questions and user-taste assumptions from Atlas seed memory.
  - [x] Document product identity, matching, and ambiguity rules.
  - [x] Add a backend ingestion script that indexes Atlas seed files into Cognee Cloud.
  - [x] Re-index the cleaned Atlas v2 seed into Cognee Cloud.
  - [x] Directly smoke-test Atlas v2 recall against Cognee Cloud.
  - [x] Add a backend provider/service that recalls Atlas facts separately from private memories.
  - [x] Update Ask response shape to label `private_memory`, `current_item`, and `mizaaj_atlas` evidence.
  - [x] Add tests proving private and Atlas recall are separated and source-labeled.
  - [x] Add UI badges/sections for Atlas evidence without making answers cluttered.
  - [x] Manually smoke-test a new product where private memory is sparse but Atlas improves the answer.

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
  - [x] Ask screen does not clip on mobile or desktop.
  - [ ] Capture screen does not clip on mobile or desktop.
  - [ ] Memory delete and clear controls work.
  - [ ] Loading states are visible for extraction, Cognee indexing, and deletes.
  - [ ] Empty states are clean and not generic.

- [ ] Submission polish.
  - [x] README says Mizaaj and has current setup notes.
  - [x] Docs explain why Cognee is necessary.
  - [x] Demo script matches the implemented product.
  - [ ] Screenshots/video show a real clothing example.
  - [x] Track choice is explicit: Cognee Cloud primary, OSS fallback.
  - [ ] Cognee Cloud dashboard shows the private user brain and Atlas brain used in the demo.
  - [ ] Demo proves one returning-user flow and one first-time/new-product flow.

## Demo Seed Checklist

- [ ] Existing Bear House black tee becomes the private-memory anchor.
  - [ ] Product photos are visible in Memory.
  - [ ] Saved chat is linked to the product.
  - [ ] One try-on outcome explains why it worked.
- [ ] Puma or similar tee becomes the negative/fabric-risk memory.
  - [ ] Capture tag/product images.
  - [ ] Save an outcome about stretching, flimsy fabric, or poor drape.
  - [ ] Ask later about a similar item and verify Mizaaj warns from private memory.
- [x] Atlas has enough seeded public knowledge to help on day one.
  - [x] 13 records across H&M, SNITCH, PUMA, Levi's, and ZARA.
  - [x] Product-specific and brand/category size-guide records are separated.
  - [x] At least 1 source-backed non-personal derived rule per product: fit intent, fabric risk, size interpretation, or styling evidence.
  - [x] Category-level notes cover relaxed tees, shirts, and jeans for the demo.

## Nice If Core Is Done

- [ ] Shared brand-memory design document only, no rushed implementation.
- [ ] One anonymized public-memory prototype behind a disabled feature flag.
- [ ] Better extraction editing UI for title, brand, material, sizes, and claims.
- [ ] Export user memory as JSON.
- [ ] Browser-extension design stub, no extension implementation.

## Test Commands

Backend:

```powershell
cd D:\Development\Projects\cognee-hackathon\fitrecall\backend
.\scripts\test-backend.ps1
```

Fast backend loop without lint:

```powershell
cd D:\Development\Projects\cognee-hackathon\fitrecall\backend
.\scripts\test-backend.ps1 -SkipLint
```

Verbose workflow simulation:

```powershell
cd D:\Development\Projects\cognee-hackathon\fitrecall\backend
.\scripts\test-backend.ps1 -SkipLint -VerboseWorkflow
```

Live provider smoke:

```powershell
cd D:\Development\Projects\cognee-hackathon\fitrecall\backend
.\scripts\live-smoke.ps1
.\scripts\live-smoke.ps1 -SpendTokens
.\scripts\live-smoke.ps1 -SpendTokens -ImageUrl "https://example.com/clothing-tag.jpg"
```

Frontend:

```powershell
cd D:\Development\Projects\cognee-hackathon\fitrecall\frontend
npm run test
npm run build
```

Local services:

```powershell
cd D:\Development\Projects\cognee-hackathon\fitrecall
docker compose up -d
```
