[CmdletBinding()]
param(
    [string]$EpisodeId = 'live-local-20260827-014120',
    [string]$EvidenceDir = 'D:\Codex\2026-08-26\plea\work\evidence\live-local-20260827-014120',
    [string]$ServerLog = 'D:\Codex\2026-08-26\plea\work\local-java-server-26.1.2\logs\latest.log'
)

$ErrorActionPreference = 'Stop'

function Require-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required evidence file is missing: $Path"
    }
}

Require-File (Join-Path $EvidenceDir 'adapter-events.jsonl')
Require-File (Join-Path $EvidenceDir 'v1-attach.json')
Require-File (Join-Path $EvidenceDir 'v1-observation-initial.json')
Require-File (Join-Path $EvidenceDir 'v1-observation-after.json')
Require-File (Join-Path $EvidenceDir 'v1-instruction.json')
Require-File (Join-Path $EvidenceDir 'v1-stop.json')
Require-File $ServerLog

$events = @(Get-Content -LiteralPath (Join-Path $EvidenceDir 'adapter-events.jsonl') | ForEach-Object { $_ | ConvertFrom-Json })
$episodeEvents = @($events | Where-Object { $_.episode_id -eq $EpisodeId })
$eventTypes = @($episodeEvents | ForEach-Object { $_.event_type } | Sort-Object -Unique)
$requiredEventTypes = @(
    'attached',
    'observation',
    'controller_claimed',
    'instruction_received',
    'action_completed',
    'stopped'
)
$missingEventTypes = @($requiredEventTypes | Where-Object { $_ -notin $eventTypes })
if ($missingEventTypes.Count -gt 0) {
    throw "Required adapter event types are missing: $($missingEventTypes -join ', ')"
}

$completedActions = @($episodeEvents | Where-Object { $_.event_type -eq 'action_completed' } | ForEach-Object { $_.action_kind } | Sort-Object -Unique)
$requiredActions = @('chat', 'move', 'stop')
$missingActions = @($requiredActions | Where-Object { $_ -notin $completedActions })
if ($missingActions.Count -gt 0) {
    throw "Required completed actions are missing: $($missingActions -join ', ')"
}

$attach = Get-Content -Raw -LiteralPath (Join-Path $EvidenceDir 'v1-attach.json') | ConvertFrom-Json
$initialObservation = Get-Content -Raw -LiteralPath (Join-Path $EvidenceDir 'v1-observation-initial.json') | ConvertFrom-Json
$afterObservation = Get-Content -Raw -LiteralPath (Join-Path $EvidenceDir 'v1-observation-after.json') | ConvertFrom-Json
$instruction = Get-Content -Raw -LiteralPath (Join-Path $EvidenceDir 'v1-instruction.json') | ConvertFrom-Json
$stop = Get-Content -Raw -LiteralPath (Join-Path $EvidenceDir 'v1-stop.json') | ConvertFrom-Json
$serverLogText = Get-Content -Raw -LiteralPath $ServerLog

$checks = [ordered]@{
    server_startup = ($serverLogText -match 'Starting minecraft server version 26\.1\.2' -and $serverLogText -match 'Starting Minecraft server on 127\.0\.0\.1:25565' -and $serverLogText -match 'Done \(')
    server_survival = ($serverLogText -match 'Default game type: SURVIVAL')
    adapter_attached = ($attach.status -eq 'attached' -and $attach.spawned -eq $true -and $attach.logged_in -eq $true)
    initial_live_observation = ($initialObservation.observation.dimension -eq 'overworld' -and $initialObservation.observation.is_alive -eq $true -and $null -ne $initialObservation.observation.position)
    after_live_observation = ($afterObservation.observation.dimension -eq 'overworld' -and $afterObservation.observation.is_alive -eq $true -and $null -ne $afterObservation.observation.position)
    instruction_accepted = ($instruction.status -eq 'accepted')
    minecraft_chat = ($serverLogText -match '<PrimeBot> Prime checkpoint ready')
    minecraft_login = ($serverLogText -match 'PrimeBot joined the game')
    minecraft_leave = ($serverLogText -match 'PrimeBot left the game')
    adapter_stopped = ($stop.status -eq 'stopped' -and $stop.state -eq 'stopped')
    server_stopped = ($serverLogText -match 'Stopping the server' -and $serverLogText -match 'All dimensions are saved')
    no_checkpoint_listeners = (@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in 25565, 18765 }).Count -eq 0)
}

$failedChecks = @($checks.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })
if ($failedChecks.Count -gt 0) {
    throw "Live checkpoint verification failed: $($failedChecks -join ', ')"
}

$summary = [ordered]@{
    schema = 'minecraft-ce/live-checkpoint-receipt'
    schema_version = 1
    episode_id = $EpisodeId
    finalized_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    scope = 'bounded live bridge checkpoint'
    result = 'pass'
    server = [ordered]@{
        version = '26.1.2'
        mode = 'survival'
        host = '127.0.0.1'
        port = 25565
        log = $ServerLog
    }
    bot = [ordered]@{
        username = 'PrimeBot'
        auth = 'offline'
        dimension_initial = $initialObservation.observation.dimension
        initial_position = $initialObservation.observation.position
        after_position = $afterObservation.observation.position
        initial_health = $initialObservation.observation.health
        after_health = $afterObservation.observation.health
    }
    control = [ordered]@{
        controller_id = 'prime-coordinator'
        instruction_id = 'instruction-live-1'
        completed_actions = $completedActions
        action_path = @('chat', 'move(250ms forward)', 'stop-motion')
    }
    checks = $checks
    provenance = [ordered]@{
        primary_adapter_evidence = (Join-Path $EvidenceDir 'adapter-events.jsonl')
        primary_server_evidence = $ServerLog
        note = 'The controller identity is the reviewed coordinator control sequence; an actual Prime-Agent model turn issuing this instruction remains the next integration checkpoint.'
    }
}
$summaryPath = Join-Path $EvidenceDir 'live-checkpoint-summary.json'
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding utf8

$manifestPath = Join-Path $EvidenceDir 'SHA256SUMS.txt'
$hashLines = @(
    "# SHA-256 manifest for $EpisodeId"
    "# Generated by tools/finalize-live-evidence.ps1; manifest itself excluded."
)
Get-ChildItem -LiteralPath $EvidenceDir -File | Where-Object { $_.Name -ne 'SHA256SUMS.txt' } | Sort-Object Name | ForEach-Object {
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    $hashLines += "$hash  $($_.Name)"
}
$hashLines | Set-Content -LiteralPath $manifestPath -Encoding ascii

Write-Output "Verified live checkpoint: $EpisodeId"
Write-Output "Summary: $summaryPath"
Write-Output "Manifest: $manifestPath"
Write-Output "Checks passed: $($checks.Keys -join ', ')"
