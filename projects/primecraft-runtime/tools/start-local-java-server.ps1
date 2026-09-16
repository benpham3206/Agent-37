Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$serverRoot = 'D:\Codex\2026-08-26\plea\work\local-java-server-26.1.2'
$javaPath = 'C:\Users\hotdo\.lunarclient\jre\515e47c1d532181677af445d76add9cabc2317de\zulu25.30.17-ca-jre25.0.1-win_x64\bin\java.exe'
$jarPath = Join-Path $serverRoot 'server.jar'
$eulaPath = Join-Path $serverRoot 'eula.txt'

if (-not (Test-Path -LiteralPath $jarPath -PathType Leaf)) {
    throw "server_jar_missing"
}
if (-not (Test-Path -LiteralPath $javaPath -PathType Leaf)) {
    throw "java_runtime_missing"
}
if (-not (Test-Path -LiteralPath $eulaPath -PathType Leaf)) {
    throw "eula_file_missing"
}

$eulaLine = Get-Content -LiteralPath $eulaPath | Where-Object { $_ -match '^eula=(true|false)$' } | Select-Object -Last 1
if ($eulaLine -ne 'eula=true') {
    Write-Error "EULA_REQUIRED: review $eulaPath and set eula=true only if you accept the Minecraft EULA."
    exit 2
}

Set-Location -LiteralPath $serverRoot
& $javaPath '--enable-native-access=ALL-UNNAMED' '-Xms1G' '-Xmx2G' '-jar' $jarPath '--nogui'
exit $LASTEXITCODE
