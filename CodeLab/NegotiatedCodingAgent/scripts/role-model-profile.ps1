$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
& $Python -m negotiated_agent.role_profile_cli --project-root $ProjectRoot --config (Join-Path $ProjectRoot "agent.config.json") --out (Join-Path $ProjectRoot "coordination\role_model_profile.sop")
