Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$serverRoot = 'D:\Codex\2026-08-26\plea\work\wood-gate-server-26.1.2'
$javaPath = 'C:\Users\hotdo\.lunarclient\jre\515e47c1d532181677af445d76add9cabc2317de\zulu25.30.17-ca-jre25.0.1-win_x64\bin\java.exe'
$jarPath = Join-Path $serverRoot 'server.jar'
$eulaPath = Join-Path $serverRoot 'eula.txt'
$serverPort = 25566

$listener = Get-NetTCPConnection -State Listen -LocalPort $serverPort -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    Write-Host "Minecraft server is already listening on 127.0.0.1:$serverPort (PID $($listener.OwningProcess))."
    exit 0
}

if (-not (Test-Path -LiteralPath $jarPath -PathType Leaf)) {
    throw 'server_jar_missing'
}
if (-not (Test-Path -LiteralPath $javaPath -PathType Leaf)) {
    throw 'java_runtime_missing'
}
if (-not (Test-Path -LiteralPath $eulaPath -PathType Leaf)) {
    throw 'eula_file_missing'
}

$eulaLine = Get-Content -LiteralPath $eulaPath |
    Where-Object { $_ -match '^eula=(true|false)$' } |
    Select-Object -Last 1
if ($eulaLine -ne 'eula=true') {
    throw 'eula_not_accepted'
}

# fast-brain bridge: detached watchdog waits for port 25566 (<=90 s), then starts
# the bridge on :8876 (skips if already listening). Survives this script blocking on java.
Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', 'C:\Users\hotdo\Documents\Codex\2026-09-11\crea\outputs\fast-brain\start-bridge.ps1'

Write-Host "Starting the disposable offline Survival server on 127.0.0.1:$serverPort."
Set-Location -LiteralPath $serverRoot
& $javaPath '--enable-native-access=ALL-UNNAMED' '-Xms1G' '-Xmx2G' '-jar' $jarPath '--nogui'
exit $LASTEXITCODE
