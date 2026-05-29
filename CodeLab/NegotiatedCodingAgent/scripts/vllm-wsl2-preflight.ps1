param(
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

if ($Out -eq "") {
  $Out = Join-Path $ProjectRoot "coordination\vllm_wsl2_preflight.sop"
}

& $Python -m negotiated_agent.vllm_preflight_cli --out $Out
exit $LASTEXITCODE
