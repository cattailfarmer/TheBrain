param(
  [string]$UpdateRecordRef = "coordination/narrative_coverage_update_record.sop",
  [string]$ManagerApprovalRef = "coordination/manager_narrative_append_approval.sop",
  [string]$ShaliachClearanceRef = "coordination/shaliach_narrative_append_clearance.sop",
  [string]$NarrativeSurfaceRef = "coordination/project_narrative_surface.sop",
  [string]$ResultId = "narrative-append-result-1",
  [string]$ExpectedSurfaceGuard,
  [switch]$GuardDiscovery,
  [switch]$ManagerApproval,
  [switch]$ShaliachClearance,
  [switch]$SynthesizeReviewDrafts,
  [string]$ApprovalId = "manager-narrative-append-approval-1",
  [string]$ApprovalStatus = "approved_for_narrative_append",
  [int]$ApprovedUpdateCount = 1,
  [string]$FrontierAtApproval = "",
  [string[]]$ResidualRisk = @(),
  [string]$ClearanceId = "shaliach-narrative-append-clearance-1",
  [string]$ClearanceStatus = "clear_for_narrative_append",
  [string[]]$CheckedProtocol = @("SOP"),
  [string[]]$Finding = @(),
  [string[]]$RequiredRework = @(),
  [string]$ManagerOut = "coordination/manager_narrative_append_approval.sop",
  [string]$ShaliachOut = "coordination/shaliach_narrative_append_clearance.sop",
  [switch]$Apply,
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
if (-not $GuardDiscovery -and -not $ManagerApproval -and -not $ShaliachClearance -and -not $SynthesizeReviewDrafts -and [string]::IsNullOrWhiteSpace($ExpectedSurfaceGuard)) {
  throw "ExpectedSurfaceGuard is required for plan mode"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
if ($Out -eq "") { $Out = Join-Path $ProjectRoot "coordination\narrative_append_result.sop" }
if ($ManagerApproval -and $Out -eq (Join-Path $ProjectRoot "coordination\narrative_append_result.sop")) {
  $Out = Join-Path $ProjectRoot "coordination\manager_narrative_append_approval.sop"
}
if ($ShaliachClearance -and $Out -eq (Join-Path $ProjectRoot "coordination\narrative_append_result.sop")) {
  $Out = Join-Path $ProjectRoot "coordination\shaliach_narrative_append_clearance.sop"
}
$argsList = @(
  "-m", "negotiated_agent.narrative_append_cli",
  "--project-root", $ProjectRoot,
  "--update-record-ref", $UpdateRecordRef,
  "--manager-approval-ref", $ManagerApprovalRef,
  "--shaliach-clearance-ref", $ShaliachClearanceRef,
  "--narrative-surface-ref", $NarrativeSurfaceRef,
  "--result-id", $ResultId,
  "--out", $Out
)
if ($GuardDiscovery) {
  $argsList += @("--guard-discovery")
} elseif ($ManagerApproval) {
  $argsList += @(
    "--manager-approval",
    "--approval-id", $ApprovalId,
    "--approval-status", $ApprovalStatus,
    "--approved-update-count", "$ApprovedUpdateCount",
    "--frontier-at-approval", $FrontierAtApproval
  )
  foreach ($risk in $ResidualRisk) {
    $argsList += @("--residual-risk", $risk)
  }
} elseif ($ShaliachClearance) {
  $argsList += @(
    "--shaliach-clearance",
    "--clearance-id", $ClearanceId,
    "--clearance-status", $ClearanceStatus
  )
  foreach ($protocol in $CheckedProtocol) {
    $argsList += @("--checked-protocol", $protocol)
  }
  foreach ($item in $Finding) {
    $argsList += @("--finding", $item)
  }
  foreach ($item in $RequiredRework) {
    $argsList += @("--required-rework", $item)
  }
} elseif ($SynthesizeReviewDrafts) {
  $argsList += @(
    "--synthesize-review-drafts",
    "--approval-id", $ApprovalId,
    "--clearance-id", $ClearanceId,
    "--frontier-at-approval", $FrontierAtApproval,
    "--manager-out", $ManagerOut,
    "--shaliach-out", $ShaliachOut
  )
  foreach ($risk in $ResidualRisk) {
    $argsList += @("--residual-risk", $risk)
  }
  foreach ($protocol in $CheckedProtocol) {
    $argsList += @("--checked-protocol", $protocol)
  }
  foreach ($item in $Finding) {
    $argsList += @("--finding", $item)
  }
} else {
  $argsList += @("--expected-surface-guard", $ExpectedSurfaceGuard)
}
if ($Apply) {
  $argsList += @("--apply")
}
& $Python @argsList
exit $LASTEXITCODE
