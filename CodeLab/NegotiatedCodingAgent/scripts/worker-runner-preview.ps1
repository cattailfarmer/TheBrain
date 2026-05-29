param(
  [Parameter(Mandatory = $true)]
  [string]$Worker,
  [Parameter(Mandatory = $true)]
  [string]$Mailbox,
  [int]$MaxClaims = 1,
  [int]$LeaseMinutes = 30
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

& $Python -m negotiated_agent.worker_runner_cli `
  --project-root $ProjectRoot `
  --worker $Worker `
  --mailbox $Mailbox `
  --max-claims $MaxClaims `
  --lease-minutes $LeaseMinutes
exit $LASTEXITCODE
