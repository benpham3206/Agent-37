[CmdletBinding()]
param(
    [ValidateSet('default', 'play', 'optimize')]
    [string] $AgentProfile = 'default',

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $PrimeArguments
)

$ErrorActionPreference = 'Stop'

$projectRoot = 'D:\Codex\2026-08-26\plea'
$primeRoot = 'D:\Codex\2026-08-26\prime-agent'

# Isolated roots so play and optimize never share session transcripts or pads.
switch ($AgentProfile) {
    'play' {
        $profileRoot = Join-Path $primeRoot 'play'
        # session_pad actors are a fixed enum; isolate play via pad/session roots.
        $actor = 'prime'
        $windowTitle = 'prime-PLAY - plea'
    }
    'optimize' {
        $profileRoot = Join-Path $primeRoot 'optimize'
        $actor = 'prime'
        $windowTitle = 'prime-OPTIMIZE - plea'
    }
    default {
        $profileRoot = $primeRoot
        $actor = 'prime'
        $windowTitle = 'prime-agent - plea'
    }
}

$sessionRoot = Join-Path $profileRoot 'sessions'
$tempRoot = Join-Path $profileRoot 'temp'
$padRoot = Join-Path $profileRoot 'pads'
$padTool = Join-Path $projectRoot 'tools\session_pad.py'

$conflictingArguments = @($PrimeArguments | Where-Object {
    $_ -match '^--(cwd|session-dir)(=|$)'
})
if ($conflictingArguments.Count -gt 0) {
    throw 'Do not override --cwd or --session-dir when using this wrapper; it keeps project state on D:.'
}

New-Item -ItemType Directory -Force -Path @($projectRoot, $sessionRoot, $tempRoot, $padRoot) | Out-Null

try {
    $Host.UI.RawUI.WindowTitle = $windowTitle
} catch {
    # Non-interactive hosts may not expose a title bar.
}

# Informational invocations must not create a durable session pad.
$isInformational = @($PrimeArguments) -contains '--help' -or @($PrimeArguments) -contains '-h' -or @($PrimeArguments) -contains '--version' -or @($PrimeArguments) -contains '-v'
if ($isInformational) {
    & prime-agent @($PrimeArguments) '--cwd' $projectRoot '--session-dir' $sessionRoot
    exit $LASTEXITCODE
}

$projectPad = $null
$projectPadArgument = $null
$forwardedArguments = New-Object System.Collections.Generic.List[string]
for ($index = 0; $index -lt $PrimeArguments.Count; $index++) {
    $argument = $PrimeArguments[$index]
    if ($argument -eq '--project-pad') {
        if ($index + 1 -ge $PrimeArguments.Count) {
            throw '--project-pad requires a pad.md path.'
        }
        $projectPadArgument = $PrimeArguments[++$index]
        continue
    }
    [void]$forwardedArguments.Add($argument)
}

function Invoke-PadTool {
    param([string[]] $Arguments)
    $output = & python $padTool @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw (($output | Out-String).Trim())
    }
    return ($output | Out-String)
}

if ($projectPadArgument) {
    $projectPad = (Resolve-Path -LiteralPath $projectPadArgument -ErrorAction Stop).Path
    $null = Invoke-PadTool @('validate', '--root', $padRoot, '--path', $projectPad)
    $padMetadata = Get-Content -Raw -LiteralPath (Join-Path (Split-Path -Parent $projectPad) 'metadata.json') | ConvertFrom-Json
} else {
    $isContinue = @($forwardedArguments) -contains '--continue' -or @($forwardedArguments) -contains '-c'
    if ($isContinue) {
        try {
            $latest = Invoke-PadTool @('latest', '--root', $padRoot, '--actor', $actor, '--json') | ConvertFrom-Json
            $projectPad = $latest.pad_path
            $padMetadata = $latest
        } catch {
            $newPad = Invoke-PadTool @('new', '--root', $padRoot, '--actor', $actor, '--label', 'continued-session-recovery', '--profile', $AgentProfile) | ConvertFrom-Json
            $projectPad = $newPad.pad_path
            $padMetadata = $newPad
        }
    } else {
        $newPad = Invoke-PadTool @('new', '--root', $padRoot, '--actor', $actor, '--label', "new-$AgentProfile-session", '--profile', $AgentProfile) | ConvertFrom-Json
        $projectPad = $newPad.pad_path
        $padMetadata = $newPad
    }
}

$env:PRIME_PROJECT_PAD = $projectPad
$env:PRIME_PROJECT_PAD_ROOT = $padRoot
$env:PRIME_PROJECT_PAD_OWNER = $padMetadata.owner
$env:PRIME_PROJECT_PAD_ID = $padMetadata.session_id
$env:PRIME_D_PROFILE = $AgentProfile
$env:TEMP = $tempRoot
$env:TMP = $tempRoot

$agentCwd = $projectRoot
if ($AgentProfile -eq 'play') {
    $agentCwd = $profileRoot
    $env:IPYTHONDIR = Join-Path $profileRoot 'ipython'
    $env:PRIMEBOT_BRIDGE_PATH = Join-Path $projectRoot '.prime\agent\skills\minecraft-control\src\minecraft_control\__init__.py'
}

$forwardedArguments = @($forwardedArguments) + @(
    '--cwd', $agentCwd,
    '--session-dir', $sessionRoot
)

Write-Host "Prime profile=$AgentProfile actor=$actor session-dir=$sessionRoot pad=$projectPad"
& prime-agent @forwardedArguments
exit $LASTEXITCODE
