param(
  [Parameter(Mandatory = $true)]
  [string]$Worker,
  [Parameter(Mandatory = $true)]
  [string]$ExecutionGateRef,
  [Parameter(Mandatory = $true)]
  [string]$ReadyCycleRef,
  [Parameter(Mandatory = $true)]
  [string]$RunId,
  [Parameter(Mandatory = $true)]
  [string]$CycleId,
  [string]$PlanId = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @(
  "-m", "negotiated_agent.run_local_execution_cli",
  "--project-root", $ProjectRoot,
  "--worker", $Worker,
  "--execution-gate-ref", $ExecutionGateRef,
  "--ready-cycle-ref", $ReadyCycleRef,
  "--run-id", $RunId,
  "--cycle-id", $CycleId
)
if ($PlanId -ne "") {
  $argsList += @("--plan-id", $PlanId)
}

& $Python @argsList
exit $LASTEXITCODE
