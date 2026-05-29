$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
& $Python -m negotiated_agent.narrative_coverage_cli --project-root $ProjectRoot --out (Join-Path $ProjectRoot "coordination\narrative_coverage_report.sop")
