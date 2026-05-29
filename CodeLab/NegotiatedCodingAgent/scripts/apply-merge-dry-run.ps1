param(
  [Parameter(Mandatory=$true)]
  [string]$RunRoot,

  [Parameter(Mandatory=$true)]
  [string]$TargetWorkspaceRoot,

  [string]$VerificationCommand
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

$ArgsList = @(
  "-m", "negotiated_agent.apply_cli",
  "--run-root", $RunRoot,
  "--target-workspace-root", $TargetWorkspaceRoot
)

if ($VerificationCommand) {
  $ArgsList += @("--verification-command", $VerificationCommand)
}

& $Python @ArgsList
