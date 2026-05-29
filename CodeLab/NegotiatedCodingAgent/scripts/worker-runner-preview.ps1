param(
  [Parameter(Mandatory = $true)]
  [string]$Worker,
  [Parameter(Mandatory = $true)]
  [string]$Mailbox,
  [int]$MaxClaims = 1,
  [int]$LeaseMinutes = 30,
  [switch]$ClaimRecord,
  [switch]$RecordCycle,
  [string]$CycleId = "",
  [string]$CycleStatus = "completed",
  [string[]]$ClaimRef = @(),
  [string]$SliceRef = "none",
  [string[]]$ProofRef = @(),
  [string[]]$ChangedFile = @(),
  [string]$ManagerFrontierRequest = "none",
  [string]$ShaliachFindingRef = "none",
  [string]$CommitRef = "none",
  [string]$FailureRef = "none"
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

& $Python @argsList
exit $LASTEXITCODE
