[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'run', 'infra', 'status', 'stop', 'play-restart', 'help')]
    [string] $Command = 'start'
)

$ErrorActionPreference = 'Stop'

# start/run: ensure Survival + adapter, then open idle PLAY + OPTIMIZE Prime TUIs.
# If server+adapter are already up, start/run only launches the two harnesses
# (does not stop the bot, server, or existing Prime windows).

$projectRoot = 'D:\Codex\2026-08-26\plea'
$primeRoot = 'D:\Codex\2026-08-26\prime-agent'
$serverRoot = Join-Path $projectRoot 'work\wood-gate-server-26.1.2'
$serverScript = Join-Path $projectRoot 'tools\start-wood-gate-server.ps1'
$adapterScript = Join-Path $projectRoot 'work\delegated\B-mineflayer-adapter\mineflayer_adapter.py'
$adapterRoot = Join-Path $projectRoot 'work\delegated\B-mineflayer-adapter'
$nodeModules = Join-Path $projectRoot 'work\mindcraft-ce\node_modules'
$primeLauncher = Join-Path $projectRoot 'tools\prime-agent-on-d.ps1'
$optimizeScript = Join-Path $projectRoot 'tools\plea-optimize.ps1'
$evidenceRoot = Join-Path $projectRoot 'work\evidence\primecraft-live'
$serverLog = Join-Path $serverRoot 'logs\latest.log'
$idleJoinScript = Join-Path $projectRoot 'tools\ensure_primebot_presence.py'
$idleJoinStatus = Join-Path $evidenceRoot 'primebot-idle-join.json'
$pythonPath = 'C:\Python314\python.exe'
$nodePath = 'C:\Program Files\nodejs\node.exe'
$serverPort = 25566
$adapterPort = 18765
$adapterUrl = "http://127.0.0.1:$adapterPort"

New-Item -ItemType Directory -Force -Path @($evidenceRoot, $primeRoot) | Out-Null

function Get-ListeningProcessId {
    param([int] $Port)
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -eq $connection) { return $null }
    return [int]$connection.OwningProcess
}

function Wait-Listening {
    param([int] $Port, [int] $TimeoutSeconds = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $listenerPid = Get-ListeningProcessId -Port $Port
        if ($null -ne $listenerPid) { return $listenerPid }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    throw "listener_timeout:$Port"
}

function Get-AdapterHealth {
    try {
        return Invoke-RestMethod -Method Get -Uri "$adapterUrl/healthz" -TimeoutSec 3
    } catch {
        return $null
    }
}

function Format-ProcessArgument {
    param([Parameter(Mandatory = $true)][string] $Value)
    if ($Value -match '[\s"]') {
        return '"' + ($Value.Replace('"', '\"')) + '"'
    }
    return $Value
}

function Stop-AdapterEpisode {
    param([string] $EpisodeId, [string] $Reason)
    $body = @{
        episode_id = $(if ([string]::IsNullOrWhiteSpace($EpisodeId)) { 'primecraft-clear' } else { $EpisodeId })
        reason = $Reason
    } | ConvertTo-Json -Compress
    return Invoke-RestMethod -Method Post -Uri "$adapterUrl/v1/stop" -Body $body -ContentType 'application/json' -TimeoutSec 15
}

function Start-MineflayerAdapter {
    param([Parameter(Mandatory = $true)][string] $EvidenceDir)
    Write-Host "Starting Mineflayer adapter on 127.0.0.1:$adapterPort ..."
    $adapterArgLine = @(
        (Format-ProcessArgument $adapterScript),
        '--control-port', $adapterPort,
        '--mc-host', '127.0.0.1',
        '--mc-port', $serverPort,
        '--mc-version', '26.1.2',
        '--auth', 'offline',
        '--username', 'PrimeBot',
        '--allowed-target', "127.0.0.1:$serverPort",
        '--evidence-dir', (Format-ProcessArgument $EvidenceDir),
        '--node-exe', (Format-ProcessArgument $nodePath),
        '--client-script', (Format-ProcessArgument (Join-Path $adapterRoot 'mineflayer_client.cjs')),
        '--node-modules-dir', (Format-ProcessArgument $nodeModules),
        '--action-timeout-s', '30',
        '--lease-ttl-s', '60',
        '--enable-actions'
    ) -join ' '
    Start-Process -FilePath $pythonPath -WorkingDirectory $adapterRoot -WindowStyle Hidden -ArgumentList $adapterArgLine -RedirectStandardOutput (Join-Path $EvidenceDir 'adapter.stdout.log') -RedirectStandardError (Join-Path $EvidenceDir 'adapter.stderr.log') | Out-Null
}

function Test-AdapterUsable {
    param($Health)
    return (
        $null -ne $Health -and
        $Health.allow_actions -eq $true -and
        $Health.state -in @('ready', 'attached')
    )
}

function Wait-AdapterUsable {
    param(
        [int] $TimeoutSeconds = 45,
        [string] $EvidenceDir
    )
    # Accept ready or attached. Never stop a live episode here — that is `primecraft stop` only.
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $restarted = $false
    do {
        $health = Get-AdapterHealth
        if (Test-AdapterUsable $health) {
            return $health
        }
        if ($null -ne $health -and $health.state -in @('stopped', 'failed') -and -not $restarted) {
            try {
                $null = Stop-AdapterEpisode -EpisodeId ([string]$health.episode_id) -Reason 'primecraft-reopen-ready'
            } catch {
                Write-Warning "adapter_reopen_failed: $($_.Exception.Message)"
            }
            Start-Sleep -Milliseconds 500
            $health = Get-AdapterHealth
            if (Test-AdapterUsable $health) {
                return $health
            }
            $listenerPid = Get-ListeningProcessId -Port $adapterPort
            if ($null -ne $listenerPid) {
                Write-Host "Adapter state=$($health.state); restarting PID $listenerPid ..."
                Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 1
            }
            if ([string]::IsNullOrWhiteSpace($EvidenceDir)) {
                throw 'adapter_restart_needs_evidence_dir'
            }
            Start-MineflayerAdapter -EvidenceDir $EvidenceDir
            $restarted = $true
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    $final = Get-AdapterHealth
    $state = if ($null -eq $final) { 'unreachable' } else { [string]$final.state }
    throw "adapter_ready_timeout:state=$state"
}

function Get-Status {
    $serverPid = Get-ListeningProcessId -Port $serverPort
    $adapterPid = Get-ListeningProcessId -Port $adapterPort
    $health = Get-AdapterHealth
    [pscustomobject]@{
        server = if ($null -ne $serverPid) { "listening:$serverPid" } else { 'stopped' }
        adapter = if ($null -ne $adapterPid) { "listening:$adapterPid" } else { 'stopped' }
        adapter_health = $health
        project = $projectRoot
        evidence = $evidenceRoot
    } | ConvertTo-Json -Depth 8
}

function Stop-PrimeBotIdleJoin {
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and ($_.CommandLine -match 'ensure_primebot_presence\.py') } |
        ForEach-Object {
            Write-Host ("Stopping PrimeBot idle-join PID {0}" -f $_.ProcessId)
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Start-PrimeBotIdleJoin {
    if (-not (Test-Path -LiteralPath $idleJoinScript)) {
        throw "required_path_missing:$idleJoinScript"
    }
    Stop-PrimeBotIdleJoin
    Write-Host "Starting PrimeBot idle join (no goal). Chat: primebot join | primebot leave"
    $idleArgs = @(
        (Format-ProcessArgument $idleJoinScript),
        '--adapter-url', $adapterUrl,
        '--mc-host', '127.0.0.1',
        '--mc-port', $serverPort,
        '--mc-version', '26.1.2',
        '--username', 'PrimeBot',
        '--status-file', (Format-ProcessArgument $idleJoinStatus),
        '--server-log', (Format-ProcessArgument $serverLog),
        '--initial-desire', 'joined'
    )
    try {
        $idleArgs += @('--prime-agent-cmd', (Format-ProcessArgument (Get-PrimeAgentCmdPath)))
    } catch {
        Write-Warning "prime_agent_cmd_missing; in-game chat will not forward to PLAY"
    }
    $argLine = $idleArgs -join ' '
    Start-Process -FilePath $pythonPath -WorkingDirectory (Join-Path $projectRoot 'tools') -WindowStyle Minimized -ArgumentList $argLine -RedirectStandardOutput (Join-Path $evidenceRoot 'primebot-idle-join.stdout.log') -RedirectStandardError (Join-Path $evidenceRoot 'primebot-idle-join.stderr.log') | Out-Null
    Write-Host "Idle-join status: $idleJoinStatus"
}

function Start-PrimeHarnesses {
    param([string] $EvidenceDir)

    $env:PRIME_MINECRAFT_ADAPTER_URL = $adapterUrl
    $env:PRIME_MINECRAFT_TARGET_PORT = [string]$serverPort
    $playRoot = Join-Path $primeRoot 'play'
    New-Item -ItemType Directory -Force -Path @(
        $playRoot,
        (Join-Path $playRoot 'temp'),
        (Join-Path $playRoot 'sessions'),
        (Join-Path $primeRoot 'optimize\sessions')
    ) | Out-Null

    if (-not [string]::IsNullOrWhiteSpace($EvidenceDir)) {
        $statusOut = Join-Path $EvidenceDir 'agent-status'
        New-Item -ItemType Directory -Force -Path $statusOut | Out-Null
        $statusScript = Join-Path $projectRoot 'tools\capture-agent-status.py'
        Write-Host "Starting agent-status capture (play sessions) -> $statusOut"
        Start-Process -FilePath $pythonPath -WorkingDirectory $projectRoot -WindowStyle Minimized -ArgumentList @(
            $statusScript,
            '--session-dir', (Join-Path $playRoot 'sessions'),
            '--out-dir', $statusOut,
            '--poll-s', '0.5'
        ) -RedirectStandardOutput (Join-Path $statusOut 'capture.stdout.log') -RedirectStandardError (Join-Path $statusOut 'capture.stderr.log') | Out-Null
        Write-Host "Status capture: $(Join-Path $statusOut 'latest-status.txt')"
    }

    Write-Host "Opening OPTIMIZE TUI (xai/grok-4.6) ..."
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $projectRoot -WindowStyle Normal -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-NoExit',
        '-File', $optimizeScript,
        'start'
    ) | Out-Null

    Start-PlayHarness
    Write-Host "Both Prime harnesses launched (independent of this console / server log window)."
}

function Start-PlayHarness {
    $env:PRIME_MINECRAFT_ADAPTER_URL = $adapterUrl
    $env:PRIME_MINECRAFT_TARGET_PORT = [string]$serverPort
    $playRoot = Join-Path $primeRoot 'play'
    New-Item -ItemType Directory -Force -Path @(
        $playRoot,
        (Join-Path $playRoot 'temp'),
        (Join-Path $playRoot 'sessions'),
        (Join-Path $playRoot 'skills')
    ) | Out-Null
    $playHarness = Join-Path $projectRoot 'tools\play_harness.py'
    $launchFlags = ((& $pythonPath $playHarness '--launch-flags' '--play-root' $playRoot) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($launchFlags)) {
        throw "play_launch_flags_failed:$launchFlags"
    }
    Write-Host "Opening PLAY TUI (google/gemini-3.7-flash, play-only) ..."
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $playRoot -WindowStyle Normal -ArgumentList @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-NoExit',
        '-Command',
        ("`$Host.UI.RawUI.WindowTitle = 'prime-PLAY - plea'; & '{0}' -AgentProfile play --provider google --model gemini-3.7-flash --thinking high {1}" -f $primeLauncher, $launchFlags)
    ) | Out-Null
}

function Close-PlayWindows {
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -and ($_.MainWindowTitle -match 'prime-PLAY - plea') } |
        ForEach-Object {
            Write-Host ("Closing PLAY window PID {0}" -f $_.Id)
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
}

function Restart-PlayHarness {
    $primeCmd = Get-PrimeAgentCmdPath
    $playHarness = Join-Path $projectRoot 'tools\play_harness.py'
    Write-Host "Stopping current PLAY session(s) (OPTIMIZE and Minecraft stay up) ..."
    $receiptJson = & $pythonPath $playHarness '--stop' '--prime-agent-cmd' $primeCmd
    if ($LASTEXITCODE -ne 0) {
        throw "play_restart_stop_failed:$receiptJson"
    }
    Write-Host $receiptJson
    Close-PlayWindows
    Start-Sleep -Seconds 2
    Start-PlayHarness
    Write-Host "PLAY restarted. Bot stays in-world; tell it to start_presence() or chat in-game."
}

function Get-PrimeAgentCmdPath {
    $cmd = Get-Command 'prime-agent.cmd' -ErrorAction SilentlyContinue
    if ($null -ne $cmd) { return $cmd.Source }
    $fallback = Join-Path $env:USERPROFILE '.local\bin\prime-agent.cmd'
    if (Test-Path -LiteralPath $fallback) { return $fallback }
    throw 'prime_agent_cmd_missing'
}

function Test-PrimecraftHarnessSession {
    param($Session)
    if ($null -eq $Session) { return $false }
    $cwd = [string]$Session.cwd
    $file = [string]$Session.sessionFile
    $msg = [string]$Session.firstMessage
    if ($file -match '(?i)[\\/]prime-agent[\\/](play|optimize)([\\/]|$)') { return $true }
    if ($cwd -match '(?i)D:\\Codex\\2026-08-26\\plea$') { return $true }
    if ($msg -match '(?i)start_presence|Primecraft|Optimize the plea|PLAY ONLY|skill:primecraft|PLAY instance|PROJECT OPTIMIZER') {
        return $true
    }
    return $false
}

function Get-PrimecraftHarnessRole {
    param($Session)
    $file = [string]$Session.sessionFile
    $msg = [string]$Session.firstMessage
    $provider = [string]($Session.model.provider)
    if ($file -match '(?i)[\\/]play[\\/]') { return 'play' }
    if ($file -match '(?i)[\\/]optimize[\\/]') { return 'optimize' }
    if ($msg -match '(?i)start_presence|PLAY ONLY|Primecraft|PLAY instance') { return 'play' }
    if ($msg -match '(?i)Optimize the plea|PROJECT OPTIMIZER') { return 'optimize' }
    if ($provider -eq 'google') { return 'play' }
    if ($provider -eq 'xai') { return 'optimize' }
    return 'unknown'
}

function Stop-PrimecraftStack {
    $stopId = Get-Date -Format 'yyyyMMdd-HHmmss'
    $stopEvidence = Join-Path $evidenceRoot ("stop-" + $stopId)
    New-Item -ItemType Directory -Force -Path $stopEvidence | Out-Null
    $receipt = [ordered]@{
        schema = 'primecraft/full-stop'
        stopped_at = (Get-Date).ToUniversalTime().ToString('o')
        evidence = $stopEvidence
        harnesses = @()
        adapter = $null
        server = $null
        windows_closed = @()
        warnings = @()
    }

    $primeCmd = $null
    try {
        $primeCmd = Get-PrimeAgentCmdPath
    } catch {
        $receipt.warnings += $_.Exception.Message
        Write-Warning $_.Exception.Message
    }

    # 1) Ask live harnesses to record lessons, then stop them.
    $targets = @()
    if ($null -ne $primeCmd) {
        try {
            $listJson = & $primeCmd list --json 2>$null | Out-String
            $listed = $listJson | ConvertFrom-Json
            $targets = @(
                @($listed.sessions) |
                    Where-Object { $_.lifecycle -in @('live', 'draft') -and (Test-PrimecraftHarnessSession $_) }
            )
        } catch {
            $receipt.warnings += "list_failed:$($_.Exception.Message)"
            Write-Warning "prime-agent list failed: $($_.Exception.Message)"
        }
    }

    $lessonsPrompt = @'
SESSION ENDING (primecraft stop). Before you halt: append a short Lessons / Checkpoint to your session pad covering (1) what worked, (2) what failed, (3) the next smallest fix. Keep it evidence-backed and under ~15 lines. Do not start_presence, do not touch the adapter lease, and do not keep acting in Minecraft. Idle when the note is written.
'@

    foreach ($session in $targets) {
        $role = Get-PrimecraftHarnessRole $session
        $entry = [ordered]@{
            id = [string]$session.id
            role = $role
            lifecycle = [string]$session.lifecycle
            sessionFile = [string]$session.sessionFile
            lessons_requested = $false
            stopped = $false
            error = $null
        }
        Write-Host ("Harness {0} ({1}, {2})" -f $session.id, $role, $session.lifecycle)
        if ($session.lifecycle -eq 'live' -and $null -ne $primeCmd) {
            try {
                & $primeCmd send --steer --from primecraft-stop $session.id $lessonsPrompt 2>&1 | Out-Null
                $entry.lessons_requested = $true
                Write-Host "  requested lessons pad write"
            } catch {
                $entry.error = "send_failed:$($_.Exception.Message)"
                Write-Warning "  lessons send failed: $($_.Exception.Message)"
            }
        }
        $receipt.harnesses += $entry
    }

    if (@($receipt.harnesses | Where-Object { $_.lessons_requested }).Count -gt 0) {
        Write-Host 'Waiting 25s for harnesses to record lessons...'
        Start-Sleep -Seconds 25
    }

    foreach ($entry in $receipt.harnesses) {
        if ($null -eq $primeCmd) { continue }
        try {
            & $primeCmd stop $entry.id 2>&1 | Out-Null
            $entry.stopped = $true
            Write-Host ("  stopped {0}" -f $entry.id)
        } catch {
            $entry.error = "stop_failed:$($_.Exception.Message)"
            $receipt.warnings += $entry.error
            Write-Warning ("  stop failed for {0}: {1}" -f $entry.id, $_.Exception.Message)
        }
    }

    # Snapshot latest play/optimize pads into the stop evidence folder.
    foreach ($profile in @('play', 'optimize')) {
        $padRoot = Join-Path $primeRoot "$profile\pads"
        if (-not (Test-Path -LiteralPath $padRoot)) { continue }
        $latestPad = Get-ChildItem -LiteralPath $padRoot -Directory -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($null -eq $latestPad) { continue }
        $padFile = Join-Path $latestPad.FullName 'pad.md'
        if (Test-Path -LiteralPath $padFile) {
            Copy-Item -LiteralPath $padFile -Destination (Join-Path $stopEvidence ("lessons-{0}-pad.md" -f $profile)) -Force
        }
    }

    # 2) Stop idle-join helper, disconnect PrimeBot, then kill adapter listener.
    Stop-PrimeBotIdleJoin
    $health = Get-AdapterHealth
    if ($null -ne $health) {
        try {
            Write-Host 'Disconnecting PrimeBot (adapter /v1/stop)...'
            $stopBody = Stop-AdapterEpisode -EpisodeId ([string]$health.episode_id) -Reason 'primecraft-full-stop'
            $receipt.adapter = @{
                action = 'v1_stop'
                before = $health
                response = $stopBody
            }
        } catch {
            $receipt.warnings += "adapter_stop:$($_.Exception.Message)"
            Write-Warning "adapter_stop_not_confirmed: $($_.Exception.Message)"
        }
    } else {
        Write-Host 'Adapter not listening.'
        $receipt.adapter = @{ action = 'absent' }
    }

    $adapterPid = Get-ListeningProcessId -Port $adapterPort
    if ($null -ne $adapterPid) {
        Write-Host "Stopping adapter process PID $adapterPid ..."
        Stop-Process -Id $adapterPid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        $receipt.adapter = @{
            action = 'stopped_process'
            pid = $adapterPid
            still_listening = ($null -ne (Get-ListeningProcessId -Port $adapterPort))
        }
    }

    # 3) Stop Minecraft server on :25566.
    $serverPid = Get-ListeningProcessId -Port $serverPort
    if ($null -ne $serverPid) {
        Write-Host "Stopping Minecraft server PID $serverPid ..."
        Stop-Process -Id $serverPid -Force -ErrorAction SilentlyContinue
        # Also stop the PowerShell parent that launched java --nogui when still around.
        try {
            $javaProc = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid" -ErrorAction SilentlyContinue
            if ($null -ne $javaProc -and $javaProc.ParentProcessId -gt 0) {
                $parent = Get-Process -Id $javaProc.ParentProcessId -ErrorAction SilentlyContinue
                if ($null -ne $parent -and $parent.ProcessName -match 'powershell|pwsh|cmd') {
                    Stop-Process -Id $parent.Id -Force -ErrorAction SilentlyContinue
                }
            }
        } catch {}
        Start-Sleep -Milliseconds 800
        $receipt.server = @{
            action = 'stopped_process'
            pid = $serverPid
            still_listening = ($null -ne (Get-ListeningProcessId -Port $serverPort))
        }
    } else {
        Write-Host 'Minecraft server not listening.'
        $receipt.server = @{ action = 'absent' }
    }

    # 4) Close Primecraft harness console windows and status capture helpers.
    $titlePattern = 'prime-PLAY - plea|prime-OPTIMIZE - plea|plea-optimize|primecraft'
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle -and ($_.MainWindowTitle -match $titlePattern) } |
        ForEach-Object {
            Write-Host ("Closing window PID {0}: {1}" -f $_.Id, $_.MainWindowTitle)
            $receipt.windows_closed += @{ pid = $_.Id; title = $_.MainWindowTitle }
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }

    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and ($_.CommandLine -match 'capture-agent-status\.py') -and ($_.CommandLine -match 'prime-agent\\play|primecraft-live') } |
        ForEach-Object {
            Write-Host ("Stopping status capture PID {0}" -f $_.ProcessId)
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            $receipt.windows_closed += @{ pid = $_.ProcessId; title = 'capture-agent-status.py' }
        }

    $receiptPath = Join-Path $stopEvidence 'full-stop-receipt.json'
    ($receipt | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    Write-Host "Full stop receipt: $receiptPath"
    Get-Status
}

if ($Command -eq 'help') {
    @'
primecraft start   If server+adapter are already up: open PLAY + OPTIMIZE TUIs only.
                   Otherwise start missing infra, then open the two idle TUIs.
                   Starts PrimeBot idle join (no goal). In-game chat:
                   "primebot join" / "primebot leave".
primecraft run     Alias for start.
primecraft infra   Start or adopt server + adapter + idle PrimeBot join (no Prime-Agent).
primecraft status  Show server/adapter health.
primecraft play-restart
                   Stop the current PLAY Prime-Agent session and open a fresh PLAY TUI.
                   Does not stop OPTIMIZE, PrimeBot, the adapter, or the Minecraft server.
                   Same as: prime-agent play restart
primecraft stop    Full teardown from any cwd (C: or D:): ask PLAY/OPTIMIZE harnesses
                   to record lessons, stop those Prime-Agent sessions, disconnect
                   PrimeBot, stop the adapter, stop the Minecraft server, and close
                   Primecraft console windows. Writes a receipt under
                   work\evidence\primecraft-live\stop-*.
primecraft help    Show this help.

Works from any directory via %USERPROFILE%\.local\bin\primecraft.cmd
Join the world from Lunar Client at 127.0.0.1:25566 (Minecraft 26.1.2).
'@ | Write-Host
    exit 0
}

if ($Command -eq 'status') {
    Get-Status
    exit 0
}

if ($Command -eq 'stop') {
    Stop-PrimecraftStack
    exit 0
}

if ($Command -eq 'play-restart') {
    Restart-PlayHarness
    exit 0
}

foreach ($requiredPath in @($serverScript, $adapterScript, $primeLauncher, $optimizeScript, $pythonPath, $nodePath, $nodeModules)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "required_path_missing:$requiredPath"
    }
}

$serverPid = Get-ListeningProcessId -Port $serverPort
$adapterPid = Get-ListeningProcessId -Port $adapterPort
$infraAlreadyUp = ($null -ne $serverPid) -and ($null -ne $adapterPid)

if ($Command -in @('start', 'run') -and $infraAlreadyUp) {
    Write-Host "Server PID $serverPid and adapter PID $adapterPid already up; launching Prime harnesses only."
    $runEvidence = Join-Path $evidenceRoot ("harness-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force -Path $runEvidence | Out-Null
    Start-PrimeBotIdleJoin
    Start-PrimeHarnesses -EvidenceDir $runEvidence
    Get-Status
    exit 0
}

$runId = Get-Date -Format 'yyyyMMdd-HHmmss'
$runEvidence = Join-Path $evidenceRoot $runId
New-Item -ItemType Directory -Force -Path $runEvidence | Out-Null

if ($null -eq $serverPid) {
    Write-Host "Starting local Survival server on 127.0.0.1:$serverPort ..."
    # Detached window: closing this primecraft console must not kill the server.
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $serverRoot -WindowStyle Normal -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $serverScript
    ) | Out-Null
    $serverPid = Wait-Listening -Port $serverPort
} else {
    Write-Host "Adopting existing Minecraft server PID $serverPid."
}

if ($null -eq $adapterPid) {
    Start-MineflayerAdapter -EvidenceDir $runEvidence
} else {
    Write-Host "Adopting existing adapter PID $adapterPid."
}
$health = Wait-AdapterUsable -EvidenceDir $runEvidence
$health | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $runEvidence 'adapter-ready.json') -Encoding UTF8
Start-PrimeBotIdleJoin

if ($Command -eq 'infra') {
    Write-Host "Primecraft infrastructure is ready. Existing Prime-Agent sessions were not replaced."
    Get-Status
    exit 0
}

Start-PrimeHarnesses -EvidenceDir $runEvidence
Get-Status
exit 0
