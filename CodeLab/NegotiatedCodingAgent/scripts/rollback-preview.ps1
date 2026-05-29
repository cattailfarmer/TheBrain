param(
  [Parameter(Mandatory=$true)]
  [string]$RunRoot,
  [string]$TargetWorkspaceRoot = "",
  [switch]$IUnderstandThisMutatesWorkspace,
  [string]$Out = "rollback_preview.sop"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$argsList = @("-m", "negotiated_agent.rollback_cli", "--run-root", $RunRoot, "--out", $Out)
if ($TargetWorkspaceRoot -ne "") {
  $argsList += @("--target-workspace-root", $TargetWorkspaceRoot)
}
if ($IUnderstandThisMutatesWorkspace) {
  $argsList += @("--i-understand-this-mutates-workspace")
}
& $Python @argsList
exit $LASTEXITCODE
