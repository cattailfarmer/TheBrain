param(
  [Parameter(Mandatory=$true)]
  [string]$Artifact
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
& $Python -m negotiated_agent.shaliach_self_negotiation_cli $Artifact
exit $LASTEXITCODE
