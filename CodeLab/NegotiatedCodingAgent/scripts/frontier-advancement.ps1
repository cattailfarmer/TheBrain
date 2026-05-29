param(
  [string]$OutputDir = "",
  [string]$AdvancementId = "frontier-advancement-1",
  [Parameter(Mandatory = $true)]
  [string]$PreviousFrontier,
  [Parameter(Mandatory = $true)]
  [string]$NextFrontier,
  [string]$CurrentFrontier = "",
  [Parameter(Mandatory = $true)]
  [string]$ManagerDecisionRef,
  [Parameter(Mandatory = $true)]
  [string]$ManagerDecisionStatus,
  [Parameter(Mandatory = $true)]
  [string]$ShaliachReviewRef,
  [Parameter(Mandatory = $true)]
  [string]$ShaliachReviewStatus,
  [string[]]$ProofRef = @(),
  [string[]]$PacketRef = @(),
  [string]$ResidualRiskSummary = "none"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @(
  "-m", "negotiated_agent.frontier_advancement_cli",
  "--project-root", $ProjectRoot,
  "--advancement-id", $AdvancementId,
  "--previous-frontier", $PreviousFrontier,
  "--next-frontier", $NextFrontier,
  "--manager-decision-ref", $ManagerDecisionRef,
  "--manager-decision-status", $ManagerDecisionStatus,
  "--shaliach-review-ref", $ShaliachReviewRef,
  "--shaliach-review-status", $ShaliachReviewStatus,
  "--residual-risk-summary", $ResidualRiskSummary
)
if ($OutputDir -ne "") { $argsList += @("--output-dir", $OutputDir) }
if ($CurrentFrontier -ne "") { $argsList += @("--current-frontier", $CurrentFrontier) }
foreach ($Ref in $ProofRef) { $argsList += @("--proof-ref", $Ref) }
foreach ($Ref in $PacketRef) { $argsList += @("--packet-ref", $Ref) }

& $Python @argsList
exit $LASTEXITCODE
