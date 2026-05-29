param(
  [Parameter(Mandatory=$true)]
  [string]$CombinedValidation,
  [string]$ObjectiveRef = "objective",
  [string]$CheckpointRef = "coordination/long_run_checkpoint.sop",
  [string]$ManagerPacketId = "manager-prelive-review",
  [string]$ShaliachPacketId = "shaliach-prelive-review",
  [string]$ManagerOut = "",
  [string]$ShaliachOut = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$argsList = @(
  "-m", "negotiated_agent.prelive_review_cli",
  "--combined-validation", $CombinedValidation,
  "--objective-ref", $ObjectiveRef,
  "--checkpoint-ref", $CheckpointRef,
  "--manager-packet-id", $ManagerPacketId,
  "--shaliach-packet-id", $ShaliachPacketId
)
if ($ManagerOut -ne "") {
  $argsList += @("--manager-out", $ManagerOut)
}
if ($ShaliachOut -ne "") {
  $argsList += @("--shaliach-out", $ShaliachOut)
}
& $Python @argsList
exit $LASTEXITCODE
