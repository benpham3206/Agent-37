# Starts the wood-gate Minecraft 26.1.2 server (user's local world, port 25566)
# in a detached PowerShell window. Safe to re-run; it only writes the server's
# own world/logs.
Start-Process powershell -WorkingDirectory 'D:\Codex\2026-08-26\plea\work\wood-gate-server-26.1.2' `
  -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','D:\Codex\2026-08-26\plea\tools\start-wood-gate-server.ps1'
Write-Host 'waiting for 25566...'
for ($i = 0; $i -lt 60; $i++) {
  if (Get-NetTCPConnection -State Listen -LocalPort 25566 -ErrorAction SilentlyContinue) {
    Write-Host 'server listening on 127.0.0.1:25566'
    exit 0
  }
  Start-Sleep 2
}
Write-Host 'timed out waiting for 25566'
exit 1
