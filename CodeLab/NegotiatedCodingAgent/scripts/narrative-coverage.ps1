param(
  [switch]$StaleCheck,
  [switch]$UpdateRecord,
  [string]$CheckId = "narrative-stale-check-1",
  [string]$UpdateId = "narrative-coverage-update-1",
  [string]$StaleCheckRef = "coordination/narrative_stale_check.sop",
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$argsList = @("-m", "negotiated_agent.narrative_coverage_cli", "--project-root", $ProjectRoot)
if ($UpdateRecord) {
  $defaultOut = Join-Path $ProjectRoot "coordination\narrative_coverage_update_record.sop"
  $argsList += @("--update-record", "--update-id", $UpdateId, "--stale-check-ref", $StaleCheckRef)
} elseif ($StaleCheck) {
  $defaultOut = Join-Path $ProjectRoot "coordination\narrative_stale_check.sop"
  $argsList += @("--stale-check", "--check-id", $CheckId)
} else {
  $defaultOut = Join-Path $ProjectRoot "coordination\narrative_coverage_report.sop"
}
if ($Out -eq "") { $Out = $defaultOut }
$argsList += @("--out", $Out)
& $Python @argsList
exit $LASTEXITCODE
