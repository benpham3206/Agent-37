[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_]{3,16}$')]
    [string]$AccountAlias = 'MindcraftAlt'
)

$ErrorActionPreference = 'Stop'
$projectRoot = 'D:\Codex\2026-08-26\plea'
$mindcraftRoot = Join-Path $projectRoot 'work\mindcraft-ce'
$authCache = 'D:\Codex\2026-08-26\prime-agent\auth\mindcraft-lunar'
$scriptPath = Join-Path $projectRoot 'tools\mindcraft-lunar-device-login.cjs'

New-Item -ItemType Directory -Force -Path $authCache | Out-Null
$env:NODE_PATH = Join-Path $mindcraftRoot 'node_modules'
$env:MINDCRAFT_AUTH_CACHE_DIR = $authCache
$env:MINDCRAFT_AUTH_ALIAS = $AccountAlias

& node $scriptPath
exit $LASTEXITCODE
