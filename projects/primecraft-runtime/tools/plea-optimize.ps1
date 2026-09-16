[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'help')]
    [string] $Command = 'start'
)

$ErrorActionPreference = 'Stop'

$projectRoot = 'D:\Codex\2026-08-26\plea'
$primeLauncher = Join-Path $projectRoot 'tools\prime-agent-on-d.ps1'
$skillPath = Join-Path $projectRoot '.prime\agent\skills\plea-optimize'

if ($Command -eq 'help') {
    @'
plea-optimize start   Open an idle OPTIMIZE Prime TUI (xai/grok-4.6). No kickoff.
plea-optimize help    Show this help.

Usual path (play + optimize TUIs together):
  tools\primecraft.ps1 start
'@ | Write-Host
    exit 0
}

$provider = 'xai'
$model = 'grok-4.6'
$thinking = 'high'
try { $Host.UI.RawUI.WindowTitle = 'prime-OPTIMIZE - plea' } catch {}
Write-Host "Opening OPTIMIZE Prime TUI with $provider / $model / $thinking (prime-agent\optimize). No kickoff; instruct it yourself."
& $primeLauncher -AgentProfile optimize '--provider' $provider '--model' $model '--thinking' $thinking '--skill' $skillPath
exit $LASTEXITCODE
