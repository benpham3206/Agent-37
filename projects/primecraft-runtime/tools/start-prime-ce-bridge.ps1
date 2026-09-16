[CmdletBinding()]
param(
    [string]$CeRoot = 'D:\Codex\2026-08-26\plea\work\mindcraft-ce',
    [int]$MindServerPort = 8080,
    [int]$ControlPort = 18766,
    [string]$AgentName = 'PrimeBot'
)
$ErrorActionPreference = 'Stop'
$node = 'C:\Program Files\nodejs\node.exe'
$bridge = Join-Path $CeRoot 'tools\prime-ce-bridge.mjs'
$main = Join-Path $CeRoot 'main.js'
if (-not (Test-Path -LiteralPath $node)) { throw "node_missing:$node" }
if (-not (Test-Path -LiteralPath $bridge)) { throw "bridge_missing:$bridge" }
if (-not (Test-Path -LiteralPath $main)) { throw "mindcraft_missing:$main" }
if ([string]::IsNullOrWhiteSpace($env:PRIME_CE_BRIDGE_TOKEN)) { throw 'PRIME_CE_BRIDGE_TOKEN is required' }
if ($MindServerPort -lt 1 -or $MindServerPort -gt 65535) { throw 'invalid_mindserver_port' }
if ($ControlPort -lt 1 -or $ControlPort -gt 65535) { throw 'invalid_control_port' }
if ($AgentName -notmatch '^[A-Za-z0-9_]{3,16}$') { throw 'invalid_agent_name' }

$ceArgs = @('main.js')
$ce = Start-Process -FilePath $node -WorkingDirectory $CeRoot -ArgumentList $ceArgs -PassThru
$bridgeArgs = @($bridge, '--mindserver-port', $MindServerPort, '--control-port', $ControlPort, '--agent', $AgentName)
$relay = Start-Process -FilePath $node -WorkingDirectory $CeRoot -ArgumentList $bridgeArgs -PassThru
[pscustomobject]@{
    mindcraft_pid = $ce.Id
    prime_bridge_pid = $relay.Id
    mindserver_port = $MindServerPort
    control_port = $ControlPort
    agent = $AgentName
    bind = '127.0.0.1'
} | ConvertTo-Json
