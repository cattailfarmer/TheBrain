param(
  [Parameter(Mandatory = $true)]
  [string]$Worker,
  [string]$ExecutionGateRef,
  [string]$ReadyCycleRef,
  [string]$RunId,
  [string]$CycleId,
  [string]$PlanId = "",
  [switch]$ExecutePlan,
  [string]$PlanRef = "",
  [string]$ResultId = "",
  [string]$GeneratedText = "Generated run-local implementation evidence.`n",
  [string]$WorkerCycleRef = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @(
  "-m", "negotiated_agent.run_local_execution_cli",
  "--project-root", $ProjectRoot,
  "--worker", $Worker
)
if ($ExecutionGateRef -ne "") {
  $argsList += @("--execution-gate-ref", $ExecutionGateRef)
}
if ($ReadyCycleRef -ne "") {
  $argsList += @("--ready-cycle-ref", $ReadyCycleRef)
}
if ($RunId -ne "") {
  $argsList += @("--run-id", $RunId)
}
if ($CycleId -ne "") {
  $argsList += @("--cycle-id", $CycleId)
}
if ($PlanId -ne "") {
  $argsList += @("--plan-id", $PlanId)
}
if ($ExecutePlan) {
  $argsList += "--execute-plan"
  if ($PlanRef -ne "") {
    $argsList += @("--plan-ref", $PlanRef)
  }
  if ($ResultId -ne "") {
    $argsList += @("--result-id", $ResultId)
  }
  if ($GeneratedText -ne "") {
    $argsList += @("--generated-text", $GeneratedText)
  }
  if ($WorkerCycleRef -ne "") {
    $argsList += @("--worker-cycle-ref", $WorkerCycleRef)
  }
}

& $Python @argsList
exit $LASTEXITCODE
