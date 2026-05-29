param(
  [Parameter(Mandatory=$true)]
  [string]$SelfNegotiation,
  [Parameter(Mandatory=$true)]
  [string]$Finding,
  [string]$Response = "",
  [string]$InspectionId = "shaliach-cross-artifact-inspection-1",
  [string]$ExpectedSubjectRef = "",
  [string]$ExpectedSelfNegotiationRef = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$argsList = @(
  "-m", "negotiated_agent.shaliach_cross_artifact_cli",
  "--self-negotiation", $SelfNegotiation,
  "--finding", $Finding,
  "--inspection-id", $InspectionId
)
if ($Response -ne "") {
  $argsList += @("--response", $Response)
}
if ($ExpectedSubjectRef -ne "") {
  $argsList += @("--expected-subject-ref", $ExpectedSubjectRef)
}
if ($ExpectedSelfNegotiationRef -ne "") {
  $argsList += @("--expected-self-negotiation-ref", $ExpectedSelfNegotiationRef)
}
& $Python @argsList
exit $LASTEXITCODE
