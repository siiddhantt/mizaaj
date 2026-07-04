param(
    [switch]$SkipLint,
    [switch]$VerboseWorkflow
)

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $BackendRoot
$env:UV_CACHE_DIR = ".uv-cache"

if (-not $SkipLint) {
    uv run ruff check app tests scripts
    uv run ruff format --check app tests scripts
}

if ($VerboseWorkflow) {
    uv run pytest tests/test_full_api_workflow.py -q -s
}

uv run pytest
