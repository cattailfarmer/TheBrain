param(
  [Parameter(Mandatory = $true)]
  [string]$RunLocalRoot,
  [switch]$ManagerAcceptance,
  [switch]$ShaliachReview,
  [switch]$PacketProposal,
  [string]$DraftInputRef = "run_local_merge_draft_input.sop",
  [string]$AcceptanceId = "manager-packet-acceptance-1",
  [string]$AcceptanceStatus = "needs_human_review",
  [int]$AcceptedEntryCount = 0,
  [string]$FrontierAtAcceptance = "unknown",
  [string]$RiskSummary = "none",
  [string]$ReviewId = "shaliach-packet-review-1",
  [string]$ReviewStatus = "needs_human_review",
  [string[]]$CheckedProtocol = @(),
  [string]$FindingSummary = "none",
  [string]$RequiredResponse = "proceed_to_packet_proposal",
  [string]$ManagerAcceptanceRef = "manager_packet_proposal_acceptance.sop",
  [string]$ShaliachReviewRef = "shaliach_packet_proposal_review.sop",
  [string]$PacketId = "manual-merge-packet-1",
  [string]$VerificationCommand = "powershell -ExecutionPolicy Bypass -File scripts/test.ps1"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @(
  "-m", "negotiated_agent.packet_proposal_cli",
  "--project-root", $ProjectRoot,
  "--run-local-root", $RunLocalRoot,
  "--draft-input-ref", $DraftInputRef
)
if ($ManagerAcceptance) { $argsList += "--manager-acceptance" }
if ($ShaliachReview) { $argsList += "--shaliach-review" }
if ($PacketProposal) { $argsList += "--packet-proposal" }
$argsList += @(
  "--acceptance-id", $AcceptanceId,
  "--acceptance-status", $AcceptanceStatus,
  "--accepted-entry-count", $AcceptedEntryCount,
  "--frontier-at-acceptance", $FrontierAtAcceptance,
  "--risk-summary", $RiskSummary,
  "--review-id", $ReviewId,
  "--review-status", $ReviewStatus
)
foreach ($Protocol in $CheckedProtocol) { $argsList += @("--checked-protocol", $Protocol) }
$argsList += @(
  "--finding-summary", $FindingSummary,
  "--required-response", $RequiredResponse,
  "--manager-acceptance-ref", $ManagerAcceptanceRef,
  "--shaliach-review-ref", $ShaliachReviewRef,
  "--packet-id", $PacketId,
  "--verification-command", $VerificationCommand
)

& $Python @argsList
exit $LASTEXITCODE
