param(
  [Parameter(Mandatory = $true)]
  [string]$Worker,
  [Parameter(Mandatory = $true)]
  [string]$Mailbox,
  [int]$MaxClaims = 1,
  [int]$LeaseMinutes = 30,
  [switch]$ClaimRecord,
  [switch]$RecordCycle,
  [switch]$RecordGateCycle,
  [switch]$WriteProofHandoff,
  [switch]$ConsumeProofHandoff,
  [string]$ExecutionGateRef = "",
  [string]$HandoffRef = "",
  [string]$ReadyCycleRef = "",
  [string]$HandoffId = "",
  [string]$ProofCommand = "",
  [string]$ProofRoute = "",
  [string]$CurrentFrontier = "",
  [string]$ExpiresAt = "",
  [string]$CycleId = "",
  [string]$CycleStatus = "completed",
  [string[]]$ClaimRef = @(),
  [string]$SliceRef = "none",
  [string[]]$ProofRef = @(),
  [string[]]$ChangedFile = @(),
  [string]$ManagerFrontierRequest = "none",
  [string]$ShaliachFindingRef = "none",
  [string]$CommitRef = "none",
  [string]$FailureRef = "none",
  [string]$RunProofCommand = "",
  [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @(
  "-m", "negotiated_agent.worker_runner_cli",
  "--project-root", $ProjectRoot,
  "--worker", $Worker,
  "--mailbox", $Mailbox,
  "--max-claims", $MaxClaims,
  "--lease-minutes", $LeaseMinutes
)
if ($ClaimRecord) {
  $argsList += "--claim-record"
}
if ($RecordCycle) {
  $argsList += "--record-cycle"
  if ($CycleId -ne "") {
    $argsList += @("--cycle-id", $CycleId)
  }
  $argsList += @("--cycle-status", $CycleStatus, "--slice-ref", $SliceRef)
  foreach ($Ref in $ClaimRef) {
    $argsList += @("--claim-ref", $Ref)
  }
  foreach ($Ref in $ProofRef) {
    $argsList += @("--proof-ref", $Ref)
  }
  foreach ($File in $ChangedFile) {
    $argsList += @("--changed-file", $File)
  }
  $argsList += @(
    "--manager-frontier-request", $ManagerFrontierRequest,
    "--shaliach-finding-ref", $ShaliachFindingRef,
    "--commit-ref", $CommitRef,
    "--failure-ref", $FailureRef
  )
}
if ($RecordGateCycle) {
  $argsList += "--record-gate-cycle"
  if ($ExecutionGateRef -ne "") {
    $argsList += @("--execution-gate-ref", $ExecutionGateRef)
  }
  if ($CycleId -ne "") {
    $argsList += @("--cycle-id", $CycleId)
  }
  foreach ($Ref in $ClaimRef) {
    $argsList += @("--claim-ref", $Ref)
  }
  if ($SliceRef -ne "none") {
    $argsList += @("--slice-ref", $SliceRef)
  }
  $argsList += @("--failure-ref", $FailureRef)
}
if ($WriteProofHandoff) {
  $argsList += "--write-proof-handoff"
  if ($ExecutionGateRef -ne "") {
    $argsList += @("--execution-gate-ref", $ExecutionGateRef)
  }
  if ($ReadyCycleRef -ne "") {
    $argsList += @("--ready-cycle-ref", $ReadyCycleRef)
  }
  if ($HandoffId -ne "") {
    $argsList += @("--handoff-id", $HandoffId)
  }
  if ($ProofCommand -ne "") {
    $argsList += @("--proof-command", $ProofCommand)
  }
  if ($ProofRoute -ne "") {
    $argsList += @("--proof-route", $ProofRoute)
  }
  if ($CurrentFrontier -ne "") {
    $argsList += @("--current-frontier", $CurrentFrontier)
  }
  if ($ExpiresAt -ne "") {
    $argsList += @("--expires-at", $ExpiresAt)
  }
}
if ($ConsumeProofHandoff) {
  $argsList += "--consume-proof-handoff"
  if ($HandoffRef -ne "") {
    $argsList += @("--handoff-ref", $HandoffRef)
  }
  if ($CurrentFrontier -ne "") {
    $argsList += @("--current-frontier", $CurrentFrontier)
  }
  if ($CycleId -ne "") {
    $argsList += @("--cycle-id", $CycleId)
  }
}
if ($RunProofCommand -ne "") {
  $argsList += @("--run-proof-command", $RunProofCommand, "--timeout-seconds", $TimeoutSeconds)
}

& $Python @argsList
exit $LASTEXITCODE
