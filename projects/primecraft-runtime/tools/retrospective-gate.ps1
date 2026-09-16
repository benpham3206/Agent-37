param(
    [Parameter(Mandatory = $true)]
    [string]$RecordPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    [Console]::Error.WriteLine("FAIL $Message")
    exit 1
}

function HasProperty($Object, [string]$Name) {
    return $null -ne $Object -and $Object.PSObject.Properties.Name -contains $Name
}

function IsBlank($Value) {
    return $null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)
}

try {
    $resolvedPath = (Resolve-Path -LiteralPath $RecordPath).Path
} catch {
    Fail "record_missing"
}

$recordRoot = [IO.Path]::GetFullPath('D:\Codex\2026-08-26\prime-agent\artifacts\retrospectives')
$recordPrefix = $recordRoot.TrimEnd('\') + '\'
if (-not $resolvedPath.StartsWith($recordPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    Fail "record_outside_prime_artifacts"
}
if ([IO.Path]::GetExtension($resolvedPath) -ne '.json') {
    Fail "record_must_be_json"
}

try {
    $record = Get-Content -Raw -LiteralPath $resolvedPath | ConvertFrom-Json
} catch {
    Fail "invalid_json"
}

if ($record.schema -ne 'prime-task-retrospective' -or $record.schema_version -ne 1) {
    Fail "unsupported_schema"
}
if ((@('in_progress', 'complete', 'blocked') -notcontains [string]$record.status)) {
    Fail "invalid_status"
}
if (IsBlank $record.task_id -or IsBlank $record.project_root) {
    Fail "missing_identity"
}
if (-not ([string]$record.project_root).StartsWith('D:\Codex\2026-08-26\plea', [StringComparison]::OrdinalIgnoreCase)) {
    Fail "project_root_not_on_D"
}

$definitionItems = @($record.definition_of_done)
$evidenceItems = @($record.evidence)
if ($definitionItems.Count -eq 0) {
    Fail "missing_definition_of_done"
}
if (-not (HasProperty $record 'metrics')) {
    Fail "missing_metrics"
}

$definitionIds = @{}
foreach ($item in $definitionItems) {
    if (IsBlank $item.id -or IsBlank $item.statement) {
        Fail "invalid_definition_item"
    }
    if ($definitionIds.ContainsKey([string]$item.id)) {
        Fail "duplicate_definition_id"
    }
    $definitionIds[[string]$item.id] = $true
}

$evidenceByCheck = @{}
foreach ($item in $evidenceItems) {
    if (IsBlank $item.check_id -or IsBlank $item.kind -or IsBlank $item.ref -or IsBlank $item.result) {
        Fail "invalid_evidence_item"
    }
    if (-not $definitionIds.ContainsKey([string]$item.check_id)) {
        Fail "evidence_without_definition"
    }
    if (@('pass', 'fail', 'unresolved') -notcontains [string]$item.result) {
        Fail "invalid_evidence_result"
    }
    if (-not $evidenceByCheck.ContainsKey([string]$item.check_id)) {
        $evidenceByCheck[[string]$item.check_id] = @()
    }
    $evidenceByCheck[[string]$item.check_id] += $item
}

foreach ($definitionId in $definitionIds.Keys) {
    if (-not $evidenceByCheck.ContainsKey($definitionId)) {
        Fail "definition_without_evidence_$definitionId"
    }
}

if ($record.status -eq 'complete') {
    foreach ($definitionId in $definitionIds.Keys) {
        if (@($evidenceByCheck[$definitionId] | Where-Object { $_.result -eq 'pass' }).Count -eq 0) {
            Fail "complete_without_passing_evidence_$definitionId"
        }
    }
}

$mismatchClass = if (HasProperty $record 'mismatch_class') { [string]$record.mismatch_class } else { 'none' }
if ($mismatchClass -ne 'none') {
    if (IsBlank $record.delta -or IsBlank $record.root_cause -or -not (HasProperty $record 'lesson') -or $record.lesson.kind -ne 'corrective' -or IsBlank $record.lesson.text) {
        Fail "mismatch_without_correction"
    }
}

if ($record.status -eq 'blocked') {
    if (IsBlank $record.root_cause -or @($evidenceItems | Where-Object { $_.result -in @('fail', 'unresolved') }).Count -eq 0) {
        Fail "blocked_without_external_evidence"
    }
}

if ((HasProperty $record 'promotion') -and $record.promotion.decision -eq 'applied') {
    if (IsBlank $record.change.ref -or $record.regression.result -ne 'pass' -or IsBlank $record.regression.ref) {
        Fail "applied_promotion_without_regression"
    }
}

[Console]::WriteLine("PASS $resolvedPath")
exit 0
