$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\enjer\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

& $Python -m compileall (Join-Path $ProjectRoot "src")
& $Python -m unittest discover -s (Join-Path $ProjectRoot "tests")

