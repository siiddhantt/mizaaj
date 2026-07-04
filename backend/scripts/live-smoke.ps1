param(
    [switch]$SpendTokens,
    [switch]$UploadIntent,
    [switch]$CleanupEnd,
    [string]$ImageUrl
)

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $PSScriptRoot
Set-Location $BackendRoot
$env:UV_CACHE_DIR = ".uv-cache"
$env:PYTHONPATH = $BackendRoot
if (-not $env:COGNEE_TIMEOUT_SECONDS) {
    $env:COGNEE_TIMEOUT_SECONDS = "180"
}

$ArgsList = @("scripts/live_api_smoke.py")
if ($SpendTokens) {
    $ArgsList += "--spend-tokens"
}
if ($UploadIntent) {
    $ArgsList += "--upload-intent"
}
if ($CleanupEnd) {
    $ArgsList += "--cleanup-end"
}
if ($ImageUrl) {
    $ArgsList += "--image-url"
    $ArgsList += $ImageUrl
}

uv run python @ArgsList
