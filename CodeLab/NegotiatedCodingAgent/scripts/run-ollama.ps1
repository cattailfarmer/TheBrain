$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

& $Python -m negotiated_agent run `
  --project-root $ProjectRoot `
  --config (Join-Path $ProjectRoot "agent.config.json") `
  --objective-file (Join-Path $ProjectRoot "examples\hello_cli_objective.txt")
