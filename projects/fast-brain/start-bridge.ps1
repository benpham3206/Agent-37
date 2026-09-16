# Start the fast-brain bridge detached once the Minecraft server accepts connections.
# Safe to run standalone or from start-wood-gate-server.ps1; skips when 8876 is already listening.
$ErrorActionPreference = 'Stop'

$serverPort = 25566
$bridgePort = 8876
$nodePath = 'D:\Codex\2026-08-26\plea\work\node-v22.23.2-win-x64\node.exe'
$bridgeDir = 'C:\Users\hotdo\Documents\Codex\2026-09-11\crea\outputs\fast-brain'

# already running?
if (Get-NetTCPConnection -State Listen -LocalPort $bridgePort -ErrorAction SilentlyContinue) {
    Write-Host "fast-brain bridge already listening on 127.0.0.1:$bridgePort."
    exit 0
}

# wait for the Minecraft server (up to 90 s)
$deadline = (Get-Date).AddSeconds(90)
$up = $false
while ((Get-Date) -lt $deadline) {
    if (Get-NetTCPConnection -State Listen -LocalPort $serverPort -ErrorAction SilentlyContinue) { $up = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $up) { throw "server_port_timeout_$serverPort" }

# cmd wrapper so the child gets MC_PORT/MC_VERSION (Start-Process can't set env vars)
Start-Process -FilePath 'cmd.exe' `
    -WorkingDirectory $bridgeDir `
    -ArgumentList '/c', 'set MC_PORT=25566&& set MC_VERSION=26.1.2&& "D:\Codex\2026-08-26\plea\work\node-v22.23.2-win-x64\node.exe" bridge.mjs' `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $bridgeDir 'logs\bridge-live.log') `
    -RedirectStandardError (Join-Path $bridgeDir 'logs\bridge-live.err.log')
Write-Host 'fast-brain bridge launching (MC_PORT=25566 MC_VERSION=26.1.2).'
exit 0
