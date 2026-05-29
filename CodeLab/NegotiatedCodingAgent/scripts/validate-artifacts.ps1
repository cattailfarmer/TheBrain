param(
  [Parameter(Mandatory=$true)]
  [string]$Manifest,
  [string]$Checkpoint = "",
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$argsList = @(
  "-m", "negotiated_agent.artifact_validation_cli",
  "--manifest", $Manifest
)
if ($Checkpoint -ne "") {
  $argsList += @("--checkpoint", $Checkpoint)
}
if ($Out -ne "") {
  $argsList += @("--out", $Out)
}
& $Python @argsList
exit $LASTEXITCODE
