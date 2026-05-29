param(
  [Parameter(Mandatory = $true)]
  [string]$ManagerAuthorizationRef,
  [Parameter(Mandatory = $true)]
  [string]$ShaliachClearanceRef,
  [Parameter(Mandatory = $true)]
  [string]$LeaseRef,
  [string]$CurrentFrontier = "",
  [string]$GateId = "",
  [switch]$Write,
  [string]$OutputDir = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @(
  "-m", "negotiated_agent.execution_gate_cli",
  "--project-root", $ProjectRoot,
  "--manager-authorization-ref", $ManagerAuthorizationRef,
  "--shaliach-clearance-ref", $ShaliachClearanceRef,
  "--lease-ref", $LeaseRef
)
if ($CurrentFrontier -ne "") {
  $argsList += @("--current-frontier", $CurrentFrontier)
}
if ($GateId -ne "") {
  $argsList += @("--gate-id", $GateId)
}
if ($Write) {
  $argsList += @("--write")
}
if ($OutputDir -ne "") {
  $argsList += @("--output-dir", $OutputDir)
}

& $Python @argsList
exit $LASTEXITCODE
