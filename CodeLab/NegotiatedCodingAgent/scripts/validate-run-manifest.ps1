param(
  [Parameter(Mandatory = $true)]
  [string]$Manifest,
  [string]$Out = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"

$argsList = @("-m", "negotiated_agent.run_manifest_cli", $Manifest)
if ($Out -ne "") {
  $argsList += @("--out", $Out)
}

& $Python @argsList
exit $LASTEXITCODE
