param(
  [string]$BaseUrl = "http://localhost:8000",
  [string[]]$Model = @(),
  [string]$Out = "coordination/live_route_config_draft.sop"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

$argsList = @(
  "-m",
  "negotiated_agent.route_draft_cli",
  "--project-root",
  $ProjectRoot,
  "--base-url",
  $BaseUrl,
  "--out",
  $Out
)
foreach ($item in $Model) {
  foreach ($modelName in ($item -split ",")) {
    $trimmed = $modelName.Trim()
    if ($trimmed -ne "") {
      $argsList += @("--model", $trimmed)
    }
  }
}

& $Python @argsList
exit $LASTEXITCODE
