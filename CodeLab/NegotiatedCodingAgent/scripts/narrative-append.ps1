param(
  [string]$UpdateRecordRef = "coordination/narrative_coverage_update_record.sop",
  [string]$ManagerApprovalRef = "coordination/manager_narrative_append_approval.sop",
  [string]$ShaliachClearanceRef = "coordination/shaliach_narrative_append_clearance.sop",
  [string]$ResultId = "narrative-append-result-1",
  [string]$ExpectedSurfaceGuard,
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
if ([string]::IsNullOrWhiteSpace($ExpectedSurfaceGuard)) {
  throw "ExpectedSurfaceGuard is required for plan mode"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
if ($Out -eq "") { $Out = Join-Path $ProjectRoot "coordination\narrative_append_result.sop" }
$argsList = @(
  "-m", "negotiated_agent.narrative_append_cli",
  "--project-root", $ProjectRoot,
  "--update-record-ref", $UpdateRecordRef,
  "--manager-approval-ref", $ManagerApprovalRef,
  "--shaliach-clearance-ref", $ShaliachClearanceRef,
  "--result-id", $ResultId,
  "--expected-surface-guard", $ExpectedSurfaceGuard,
  "--out", $Out
)
& $Python @argsList
exit $LASTEXITCODE
