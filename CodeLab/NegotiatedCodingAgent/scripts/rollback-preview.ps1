param(
  [Parameter(Mandatory=$true)]
  [string]$RunRoot,
  [string]$Out = "rollback_preview.sop"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
& $Python -m negotiated_agent.rollback_cli --run-root $RunRoot --out $Out
exit $LASTEXITCODE
