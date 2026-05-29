param(
  [Parameter(Mandatory = $true)]
  [string]$RunLocalRoot,
  [switch]$ManagerReview,
  [switch]$ShaliachReview,
  [switch]$Eligibility,
  [string]$ReviewId = "review-1",
  [string]$ReviewStatus = "",
  [string]$PlanRef = "",
  [string]$ResultRef = "",
  [string[]]$GeneratedFile = @(),
  [string]$FrontierAtReview = "unknown",
  [string]$RiskSummary = "none",
  [string[]]$CheckedProtocol = @(),
  [string]$FindingSummary = "none",
  [string]$RequiredResponse = "proceed_to_merge_review",
  [string]$ManagerReviewRef = "",
  [string]$ShaliachReviewRef = "",
  [string]$EligibilityId = "eligibility-1"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @("-m", "negotiated_agent.run_local_review_cli", "--project-root", $ProjectRoot, "--run-local-root", $RunLocalRoot)
if ($ManagerReview) { $argsList += "--manager-review" }
if ($ShaliachReview) { $argsList += "--shaliach-review" }
if ($Eligibility) { $argsList += "--eligibility" }
if ($ReviewId -ne "") { $argsList += @("--review-id", $ReviewId) }
if ($ReviewStatus -ne "") { $argsList += @("--review-status", $ReviewStatus) }
if ($PlanRef -ne "") { $argsList += @("--plan-ref", $PlanRef) }
if ($ResultRef -ne "") { $argsList += @("--result-ref", $ResultRef) }
foreach ($File in $GeneratedFile) { $argsList += @("--generated-file", $File) }
$argsList += @("--frontier-at-review", $FrontierAtReview, "--risk-summary", $RiskSummary)
foreach ($Protocol in $CheckedProtocol) { $argsList += @("--checked-protocol", $Protocol) }
$argsList += @("--finding-summary", $FindingSummary, "--required-response", $RequiredResponse)
if ($ManagerReviewRef -ne "") { $argsList += @("--manager-review-ref", $ManagerReviewRef) }
if ($ShaliachReviewRef -ne "") { $argsList += @("--shaliach-review-ref", $ShaliachReviewRef) }
if ($EligibilityId -ne "") { $argsList += @("--eligibility-id", $EligibilityId) }

& $Python @argsList
exit $LASTEXITCODE
