param(
  [string]$BaseUrl = "http://localhost:8000",
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @("-m", "negotiated_agent.openai_health_cli", "--base-url", $BaseUrl)
if ($Out -ne "") {
  $argsList += @("--out", $Out)
}

& $Python @argsList
exit $LASTEXITCODE
