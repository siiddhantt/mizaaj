# Model Decision

Mizaaj uses extraction models only to create reviewable drafts. The user must still confirm facts
before they become private fit memory.

## Default OpenRouter Setup

- `OPENROUTER_TEXT_MODEL=deepseek/deepseek-v4-flash`
- `OPENROUTER_VISION_MODEL=qwen/qwen3.7-plus`

DeepSeek V4 Flash is the cost-first default for copied product descriptions, order text, manual
notes, and page metadata. It supports structured JSON output, but it is text-only, so it should not
be used for screenshots, clothing tags, or size-chart photos.

Qwen3.7 Plus is the current vision default because it supports text and image input with structured
outputs. It should be used when the capture includes public image URLs from object-storage uploads.

## Why Two Models

Most captures should not pay image-model prices. A user can paste or clip product text, and the text
model can produce the same `ProductDraft` shape at lower cost. When evidence includes a phone photo,
tag image, page screenshot, or size chart, the extraction gateway automatically switches to the
vision model.

## Failure Boundaries

- Missing model evidence becomes `null` or an empty array.
- The model does not infer whether the item fit well.
- The model does not create trusted memories directly.
- Bad provider responses return a provider error instead of partial memory writes.

## Swap Strategy

Model names are environment variables. If cost, latency, or quality changes, update the model in
`.env` without changing application code.
