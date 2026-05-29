param(
  [Parameter(Mandatory=$true)]
  [string]$Baseline,
  [string]$BaselineRef = "",
  [string]$PacketOut = "",
  [string]$AttemptOut = "",
  [string]$Provider = "openai_compatible",
  [string]$ModelRef = "unavailable",
  [string]$LiveStatus = "unavailable",
  [string]$FailureReason = "endpoint unavailable",
  [string[]]$ProtocolRef = @(),
  [string[]]$ProofRef = @()
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$argsList = @(
  "-m", "negotiated_agent.live_shaliach_cli",
  "--baseline", $Baseline,
  "--provider", $Provider,
  "--model-ref", $ModelRef,
  "--live-status", $LiveStatus,
  "--failure-reason", $FailureReason
)
if ($BaselineRef -ne "") { $argsList += @("--baseline-ref", $BaselineRef) }
if ($PacketOut -ne "") { $argsList += @("--packet-out", $PacketOut) }
if ($AttemptOut -ne "") { $argsList += @("--attempt-out", $AttemptOut) }
foreach ($ref in $ProtocolRef) { $argsList += @("--protocol-ref", $ref) }
foreach ($ref in $ProofRef) { $argsList += @("--proof-ref", $ref) }
& $Python @argsList
exit $LASTEXITCODE
